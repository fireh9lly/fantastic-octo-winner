#!/usr/bin/env python3
"""Install C code as a code-only overlay in an empty module slot.

  build_overlay.py SRC_DIR OUT_DIR SOURCE [SOURCE ...] --slot 28 --run 0x030843DC --max 0x684 --at 0x5B400 --json npui.json
  build_overlay.py ... --entry lib_entry     (callers jump to fixed offsets: check that symbol is at --run)

The sources are linked at --run (no data, ZI or rodata: stack only), written into code.bin's file gap
at --at, and slot N's table entry points at them (code only; data/ZI sizes 0). Stock loads it with
ModuleOverlay(N, 7) from wherever we call it (e.g. np_load in slot 2). Writes OUT_DIR/<json> with the
symbol addresses for tools/patch_code.py.
"""
import argparse, json, os, shutil, struct, subprocess, sys

BASE = 0x03050000
GAP = (0x5805C, 0x5C05C)

from toolchain import tool                # noqa: E402  (tools/toolchain.py: ARM_TOOLCHAIN_BIN or PATH)

def run(*a):
    r = subprocess.run([str(x) for x in a], capture_output=True, text=True)
    if r.returncode: sys.exit(f"{' '.join(map(str, a))}\n{r.stdout}{r.stderr}")
    return r.stdout

def main():
    p = argparse.ArgumentParser()
    p.add_argument("src"); p.add_argument("out"); p.add_argument("sources", nargs="+")
    p.add_argument("--slot", type=int, required=True)
    p.add_argument("--run", type=lambda s: int(s, 0), required=True)
    p.add_argument("--max", type=lambda s: int(s, 0), required=True)
    p.add_argument("--at", type=lambda s: int(s, 0), required=True)
    p.add_argument("--json", required=True)
    p.add_argument("--entry", default=None, help="symbol that must sit at --run (an entry table callers rely on)")
    a = p.parse_args()
    if os.path.abspath(a.src) != os.path.abspath(a.out):
        os.makedirs(a.out, exist_ok=True)
        for f in os.listdir(a.src):
            if os.path.isfile(os.path.join(a.src, f)) and f != "HIFIYF18.IMG":
                shutil.copy(os.path.join(a.src, f), a.out)
    code = bytearray(open(os.path.join(a.out, "code.bin"), "rb").read())
    ent = 8 + 32 * a.slot
    cl, ce, cs = struct.unpack_from("<3I", code, ent)
    assert cs == 0, f"slot {a.slot} is not empty (code size {cs:#x})"

    work = os.path.join(a.out, f"overlay{a.slot}_build"); os.makedirs(work, exist_ok=True)
    elf, bin_ = os.path.join(work, "o.elf"), os.path.join(work, "o.bin")
    run(tool("gcc"), "-mcpu=cortex-m3", "-mthumb", "-Os", "-ffreestanding", "-nostdlib", "-nostartfiles",
        "-fno-tree-loop-distribute-patterns", "-ffunction-sections", "-Wall", "-Wextra", "-Wno-unused-parameter",
        f"-Wl,-Ttext={a.run:#x}", "-Wl,-e,0", "-Wl,--no-warn-rwx-segments",
        "-Wl,-Map=" + os.path.join(work, "o.map"), "-o", elf, *a.sources)
    sizes = {f[0]: int(f[1], 16) for f in (l.split() for l in run(tool("size"), "-A", "-x", elf).splitlines())
             if len(f) == 3 and f[0].startswith(".")}
    for s in (".data", ".bss", ".rodata"):
        assert not sizes.get(s), f"overlay must not use {s} ({sizes.get(s):#x} B)"
    run(tool("objcopy"), "-O", "binary", "-j", ".text", elf, bin_)
    blob = open(bin_, "rb").read()
    assert len(blob) <= a.max, f"overlay is {len(blob)} B, room for {a.max}"
    assert GAP[0] <= a.at and a.at + len(blob) <= GAP[1], "outside the code.bin gap"
    assert not any(code[a.at:a.at + len(blob)]), "file area not empty"
    code[a.at:a.at + len(blob)] = blob
    # table entry: code load/exec/size, data load/exec/size, ZI exec/size
    _, _, _, dl, de, _, ze, _ = struct.unpack_from("<8I", code, ent)      # keep the empty slot's data/ZI words
    struct.pack_into("<8I", code, ent, BASE + a.at, a.run, len(blob), dl, de, 0, ze, 0)
    open(os.path.join(a.out, "code.bin"), "wb").write(code)
    syms = {f[2]: int(f[0], 16) for f in (l.split() for l in run(tool("nm"), elf).splitlines())
            if len(f) == 3 and f[1] in "Tt" and not f[2].startswith("$")}
    if a.entry:
        assert syms.get(a.entry) == a.run, f"{a.entry} is at {syms.get(a.entry, 0):#x}, not at the run address {a.run:#x}"
    json.dump(syms, open(os.path.join(a.out, a.json), "w"), indent=1)
    print(f"slot {a.slot}: {len(blob)} of {a.max} B at run {a.run:#x} (code.bin {a.at:#x})")

if __name__ == "__main__":
    main()
