#!/usr/bin/env python3
"""Build a stock image with an injected hook.

  build_hook.py HOOK STAMP16 [--src build/stock] [--out build/<hook>]

The hook (hooks/*.S) is linked at its run address and its bytes are stored in
code.bin at GAP_FILE (16 KB of zeros between module 0's code and data sources).

Loading: the boot ROM / ModuleOverlay (0x030683DE) copy modules from FLASH by
module-table entry; the file gap itself is never loaded (H0/H0a proved this).
So a hook gets a module-table slot: stock already calls ModuleOverlay(2, 7) on
an empty slot 2 in ~21 places, including module 10's USB start right after
ModuleOverlay(12, 7). Slot 2 is pointed at the hook (source GAP_FILE, run
address HOOK_RUN), so stock itself copies the hook into free RAM above every
module (0x0309F7CC is the highest module end; 0x0309FFF0 holds reset magic).

Then the hooked BL is redirected to the hook's entry symbol, and the image is
packed and verified.
"""
import argparse, os, shutil, struct, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TC = r"C:\Users\Admin\tools\arm-gnu-toolchain\arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi\bin"
BASE = 0x03050000
GAP_FILE, GAP_SIZE = 0x57B8C, 0x4000
GAP_RUN = 0x030A7B8C                     # H0/H0a assumption: NOT loaded, past end of 640 KB RAM
HOOK_RUN, HOOK_MAX = 0x0309F800, 0x7F0   # free RAM 0x0309F800..0x0309FFF0
TABLE = 8                                # module table starts at code.bin 8, 32 bytes per entry

# name -> (source, entry symbol, run address, module slot or None, BL site run, BL site code.bin, original target)
HOOKS = {
    "h0":  ("h0_inquiry.S", "h0_send",  GAP_RUN,  None, 0x03083978, 0x81750, 0x03081AA4),  # failed on device
    "h0a": ("h0a_pass.S",   "h0a_send", GAP_RUN,  None, 0x03083978, 0x81750, 0x03081AA4),  # failed on device
    "h1":  ("h0_inquiry.S", "h0_send",  HOOK_RUN, 2,    0x03083978, 0x81750, 0x03081AA4),
    "h1a": ("h0a_pass.S",   "h0a_send", HOOK_RUN, 2,    0x03083978, 0x81750, 0x03081AA4),
    "d1":  ("d1_diag.S",    "d1_send",  HOOK_RUN, 2,    0x03083978, 0x81750, 0x03081AA4),
    "amu": ("amu_inq.S",    "amu_send", HOOK_RUN, 2,    0x03083978, 0x81750, 0x03081AA4),  # build 36: name only
}

def bl_decode(hw, pc):
    h, l = struct.unpack("<HH", hw)
    if (h & 0xF800) != 0xF000 or (l & 0xD000) != 0xD000:
        return None
    s = (h >> 10) & 1
    j1, j2 = (l >> 13) & 1, (l >> 11) & 1
    i1, i2 = 1 - (j1 ^ s), 1 - (j2 ^ s)
    off = (s << 24) | (i1 << 23) | (i2 << 22) | ((h & 0x3FF) << 12) | ((l & 0x7FF) << 1)
    if s: off -= 1 << 25
    return pc + 4 + off

def bl_encode(pc, target):
    off = target - (pc + 4)
    assert -(1 << 24) <= off < (1 << 24) and off % 2 == 0, "BL out of range"
    off &= (1 << 25) - 1
    s = (off >> 24) & 1
    i1, i2 = (off >> 23) & 1, (off >> 22) & 1
    j1, j2 = (1 - i1) ^ s, (1 - i2) ^ s
    h = 0xF000 | (s << 10) | ((off >> 12) & 0x3FF)
    l = 0xD000 | (j1 << 13) | (j2 << 11) | ((off >> 1) & 0x7FF)
    return struct.pack("<HH", h, l)

def tool(name, *args):
    subprocess.run([os.path.join(TC, f"arm-none-eabi-{name}.exe"), *args], check=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("hook"); p.add_argument("stamp")
    p.add_argument("--src", default=os.path.join(ROOT, "build", "stock"))
    p.add_argument("--out")
    a = p.parse_args()
    src, sym, run, slot, site_run, site_file, orig = HOOKS[a.hook]
    out = a.out or os.path.join(ROOT, "build", a.hook)
    obj = os.path.join(out, "obj"); os.makedirs(obj, exist_ok=True)

    # assemble + link at the run address
    o, elf, binf = (os.path.join(obj, a.hook + e) for e in (".o", ".elf", ".bin"))
    tool("as", "-mcpu=cortex-m3", "-mthumb", "-o", o, os.path.join(ROOT, "hooks", src))
    tool("ld", "-Ttext", hex(run), "-e", sym, "-o", elf, o)
    tool("objcopy", "-O", "binary", "-j", ".text*", elf, binf)
    blob = open(binf, "rb").read()
    blob += b"\0" * (-len(blob) % 4)
    syms = subprocess.run([os.path.join(TC, "arm-none-eabi-nm.exe"), elf], capture_output=True, text=True, check=True).stdout
    entry = next(int(l.split()[0], 16) for l in syms.splitlines() if l.split()[-1] == sym)
    assert len(blob) <= (HOOK_MAX if slot is not None else GAP_SIZE), f"hook is {len(blob)} bytes, too big"
    assert run <= entry & ~1 < run + len(blob), "entry symbol outside the hook blob"

    # copy stock sections, patch code.bin
    for f in os.listdir(a.src):
        if os.path.isfile(os.path.join(a.src, f)):
            shutil.copy(os.path.join(a.src, f), out)
    cp = os.path.join(out, "code.bin")
    code = bytearray(open(cp, "rb").read())
    assert not any(code[GAP_FILE:GAP_FILE + GAP_SIZE]), "gap is not empty in source code.bin"
    got = bl_decode(code[site_file:site_file + 4], site_run)
    assert got == orig, f"site holds BL to {got and hex(got)}, expected {orig:#x}"
    code[GAP_FILE:GAP_FILE + len(blob)] = blob

    if slot is not None:
        eo = TABLE + 32 * slot
        cl, ce, cs, dl, de, ds, ze, zs = struct.unpack_from("<8I", code, eo)
        assert cs == 0 and ds == 0 and zs == 0, f"slot {slot} is not empty"
        struct.pack_into("<3I", code, eo, BASE + GAP_FILE, run, len(blob))
        print(f"slot {slot}: code {BASE + GAP_FILE:#x} -> {run:#x}, {len(blob)} bytes (data/ZI stay empty)")

    target = entry & ~1
    code[site_file:site_file + 4] = bl_encode(site_run, target)
    assert bl_decode(code[site_file:site_file + 4], site_run) == target
    open(cp, "wb").write(code)
    print(f"{a.hook}: {len(blob)} bytes, file {GAP_FILE:#x}, run {run:#x}; "
          f"BL @{site_run:#x} -> {target:#x} (was {orig:#x})")

    img = os.path.join(out, "HIFIYF18.IMG")
    py = sys.executable
    subprocess.run([py, os.path.join(ROOT, "tools", "ap30fw.py"), "pack", out, img, "--stamp", a.stamp], check=True)
    subprocess.run([py, os.path.join(ROOT, "tools", "ap30fw.py"), "verify", img], check=True)

if __name__ == "__main__":
    main()
