#!/usr/bin/env python3
"""USB DAC hand-over fix for Hidizs V1.8.3 (stock or a theme made from it): phones can see the DAC.

  dac_handover.py IN.IMG OUT.IMG [--stamp HEX16]

The problem (traced 2026-11-27)
  In USB DAC mode the host is not talking to the AP30's main chip but to a separate Realtek USB audio chip (0bda:4a35
  "Realtek AP30"). GPIO1 pin 0 switches that chip off (1) and on (0) (inferred: DAC entry sets 0, DAC exit and the
  end of a file-transfer session set 1; the schematic isn't public). Leaving DAC mode only switches it off when the
  cable is still plugged in (module 9, 0x03084F32: "if DAC was on and the cable is present"), and module 0's
  end-of-USB-session code (0x03065F5C) skips it while DAC mode was on. So after a DAC session that ended with the cable
  being pulled, the Realtek chip stays on, and at the next plug-in it starts up while the USB lines are still wired to
  the main chip (GPIO0 pin 14 = 1 from boot until DAC is chosen).
  Choosing DAC then runs, at 0x03084CD2..0x03084D84:
      1 audio power on (GPIO1 pin 4 = 1)       4 audio power on again
      2 USB lines -> Realtek (GPIO0 pin 14 = 0) 5 USB lines -> Realtek again
      3 headphone amp on (GPIO2 pin 1 = 0)     6 Realtek chip on (GPIO1 pin 0 = 0)
  Step 6 changes nothing when the chip is already on, so the host never gets a clean start: a Linux laptop logs
  timeouts and protocol errors until it cuts and restores USB power, which resets the chip; a phone never does that,
  so the DAC never appears.

The fix (same module, same size, no other changes)
  block 4 (0x03084D2A, 30 B, a repeat of block 1) becomes "Realtek chip off" (GPIO1 pin 0 = 1, as the exit path does);
  block 5 (0x03084D48, 30 B, a repeat of block 2) becomes 3 x (DelayMs(200); watchdog kick) = 600 ms;
  block 6 then switches the chip on with the USB lines already connected to it: the host sees the device leave and
  arrive, as after a power cut (the laptop's cut lasted about 380 ms).

  Replacement bytes, assembled with arm-none-eabi-as 13.3.1 (Thumb) and linked at their run addresses:
    b4 @ 0x3084D2A: movs r2,#0; mov r1,r2; movs r0,#1; bl PinMux(0x03052BFC); movs r2,#1; movs r1,#0; mov r0,r2;
                    bl GpioDir(0x03056F08); movs r2,#1; movs r1,#0; mov r0,r2; bl GpioSet(0x03056F42)
    b5 @ 0x3084D48: 3 x (movs r0,#200; bl DelayMs(0x03065E34); bl WatchdogKick(0x03062B34))

  The first attempt (block 2 = Realtek on, block 4 = 600 ms wait, then the switch) started the chip before it was
  connected, the same fault, and was replaced by this one.

The original bytes are checked first, so it refuses anything that isn't V1.8.3's module 9 (including an image that
already has the first attempt). The image is patched in place (code bytes, stamp in both header copies, CRC; layout
untouched). The output gets the input's stamp with the build number + 1 (or --stamp), so the player installs it over
the input. Never share the image: it contains Hidizs firmware.
"""
import argparse, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 0x03050000
MODULE = 9
PATCHES = [  # (run address, original V1.8.3 bytes, replacement)
    (0x03084D2A, "002204210120cdf764ff012204211046d2f7e5f8012204211046d2f7fdf8",
                 "002211460120cdf764ff012200211046d2f7e5f8012200211046d2f7fdf8"),
    (0x03084D48, "00220e211046cdf755ff01220e210020d2f7d6f800220e211046d2f7eef8",
                 "c820e1f773f8ddf7f1fec820e1f76ef8ddf7ecfec820e1f769f8ddf7e7fe"),
]


def bump(stamp):
    """YY YY DD MM BB 00 00 00 (BCD): build + 1"""
    b = bytearray.fromhex(stamp)
    n = int(f"{b[4]:02x}") + 1
    assert n <= 99, "build number would pass 99: give --stamp"
    b[4] = int(str(n), 16)
    return b.hex()


def main():
    """patch the image in place: the code bytes, the stamp in both header copies and the CRC; nothing else moves
    (repacking would also move the backup header to a 64 KB boundary, where Hidizs uses 32 KB)"""
    sys.path.insert(0, HERE)
    import ap30fw as F
    p = argparse.ArgumentParser()
    p.add_argument("inp"); p.add_argument("out"); p.add_argument("--stamp")
    a = p.parse_args()
    img = bytearray(open(a.inp, "rb").read())
    bad = [n for n, ok in F.checks(img) if not ok]
    assert not bad, f"{a.inp} fails its integrity checks: {bad}"
    hdr = img[:F.HDR]
    code_off = next(s["offset"] for s in F.read_sections(hdr) if s["name"] == "code")
    cl, ce, cs = struct.unpack_from("<3I", img, code_off + 8 + 32 * MODULE)
    for addr, old, new in PATCHES:
        assert ce <= addr < ce + cs, f"{addr:#x} is outside module {MODULE}: not V1.8.3?"
        o = code_off + cl - BASE + (addr - ce)
        have = img[o:o + len(old) // 2].hex()
        if have == new:
            sys.exit(f"{a.inp}: already has the DAC hand-over fix")
        assert have == old, f"{addr:#x}: expected V1.8.3 bytes {old}, found {have}: refusing"
        img[o:o + len(new) // 2] = bytes.fromhex(new)
    stamp = a.stamp or bump(hdr[:8].hex())
    backup = F.u32(hdr, F.BACKUP_PTR)
    img[0:8] = bytes.fromhex(stamp)
    img[backup:backup + 8] = bytes.fromhex(stamp)
    struct.pack_into("<I", img, len(img) - 4, F.rkcrc(memoryview(img)[:len(img) - 4]))
    bad = [n for n, ok in F.checks(img) if not ok]
    assert not bad, f"result fails its integrity checks: {bad}"
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "wb").write(img)
    print(f"wrote {a.out} (stamp {stamp}): USB lines to the Realtek chip, chip off 600 ms, then on")


if __name__ == "__main__":
    main()
