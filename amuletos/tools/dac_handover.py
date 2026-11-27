#!/usr/bin/env python3
"""USB DAC hand-over fix for Hidizs V1.8.3 (stock or a theme made from it): phones can see the DAC.

  dac_handover.py IN.IMG OUT.IMG [--stamp HEX16]

The problem (traced 2026-11-27, third attempt)
  In USB DAC mode the host is not talking to the AP30's main chip (the RKNano) but to a separate Realtek USB audio
  chip (0bda:4a35 "Realtek AP30"); a USB switch (GPIO0 pin 14: 1 RKNano, set at boot; 0 Realtek) picks which one.
  At plug-in the RKNano's USB controller connects (module 10 calls UsbDevInit 0x03068D90 for every USB session), but
  while the File transfer / DAC question is on screen nothing answers the host. Choosing DAC then runs, at
  0x03084CD2..0x03084D84:
      1 audio power on (GPIO1 pin 4 = 1)       4 audio power on again
      2 USB lines -> Realtek (GPIO0 pin 14 = 0) 5 USB lines -> Realtek again
      3 headphone amp on (GPIO2 pin 1 = 0)     6 GPIO1 pin 0 = 0 (Realtek related; not its power: see below)
  The switch swaps one connected device for another with no gap, so the host sees no unplug: it only finds the
  Realtek if it happens to retry enumeration afterwards. A Linux laptop keeps retrying for about a minute, and the
  Realtek answers the first retry after the switch (laptop log, stock firmware, 12:52: two -71 errors, then the
  Realtek on the next attempt, no power cut). A phone that has given up on the unanswering RKNano never retries.

The fix (same module, same size, no other changes)
  block 2 (0x03084CEE, 30 B) becomes: RKNano USB soft-disconnect (DCTL 0x60080804 |= 2, SftDiscon, the same write as
           module 10's disconnect at 0x0308242E, used when a computer ejects the player), then DelayMs(200) + kick;
  block 4 (0x03084D2A, 30 B, a repeat of block 1) becomes 3 x (DelayMs(200); watchdog kick) = 600 ms;
  block 5 (stock) then switches the lines to the Realtek. The host sees the player unplugged for 0.8 s, then a new
  device: an ordinary DAC plug-in. The next plug-in reconnects the RKNano as usual (UsbDevInit clears SftDiscon).

  Replacement bytes, assembled with arm-none-eabi-as 13.3.1 (Thumb) and linked at their run addresses:
    b2 @ 0x3084CEE: movw r0,#0x800; movt r0,#0x6008; ldr r1,[r0,#4]; movs r2,#2; orrs r1,r2; str r1,[r0,#4];
                    movs r0,#200; bl DelayMs(0x03065E34); bl WatchdogKick(0x03062B34); nop; nop
    b4 @ 0x3084D2A: 3 x (movs r0,#200; bl DelayMs; bl WatchdogKick)

  Earlier attempts, both wrong, each built and tested on the laptop:
    1. block 2 = GPIO1 pin 0 = 0, block 4 = 600 ms, then the switch (theory: the Realtek boots too late);
    2. block 4 = GPIO1 pin 0 = 1, block 5 = 600 ms (theory: the Realtek needs a reset). The Realtek enumerated
       inside those 600 ms, so GPIO1 pin 0 = 1 does not switch it off.

The original bytes are checked first, so it refuses anything that isn't V1.8.3's module 9 (including an image that
has attempt 1 or 2). The image is patched in place (code bytes, stamp in both header copies, CRC; layout untouched).
The output gets the input's stamp with the build number + 1 (or --stamp), so the player installs it over the input.
Never share the image: it contains Hidizs firmware.
"""
import argparse, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 0x03050000
MODULE = 9
PATCHES = [  # (run address, original V1.8.3 bytes, replacement)
    (0x03084CEE, "00220e211046cdf782ff01220e210020d2f703f900220e211046d2f71bf9",
                 "40f60000c6f208004168022211434160c820e1f798f8ddf716ff00bf00bf"),
    (0x03084D2A, "002204210120cdf764ff012204211046d2f7e5f8012204211046d2f7fdf8",
                 "c820e1f782f8ddf700ffc820e1f77df8ddf7fbfec820e1f778f8ddf7f6fe"),
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
    print(f"wrote {a.out} (stamp {stamp}): main chip leaves USB, 0.8 s, then the lines go to the Realtek DAC")


if __name__ == "__main__":
    main()
