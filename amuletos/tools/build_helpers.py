#!/usr/bin/env python3
"""Append resident C helpers to module slot 2 (after the D1 hook).

  build_helpers.py SRC_DIR OUT_DIR SOURCE [SOURCE ...]

Slot 2 is loaded by stock at boot (module 1, config load) into free RAM at 0x0309F800 and that
RAM is never reused, so code placed there is available to patched stock modules at any time.
The helpers are linked right after slot 2's current code, written into code.bin after it, and
slot 2's code size is extended. Writes OUT_DIR/helpers.json with the symbol addresses.
No data or ZI is allowed (stack only).
"""
import json, os, shutil, struct, subprocess, sys

BASE, SLOT = 0x03050000, 2
RUN0, RUN_END = 0x0309F800, 0x0309FF28   # 0x0309FF28.. playlist table (pl_table.h), 0x0309FFC0.. libscan.c FP, 0x0309FFF0 stock magic
FILE_END = 0x58800               # keep clear of the Blockz module (build_module.py --at 0x58800)

from toolchain import tool                # noqa: E402  (tools/toolchain.py: ARM_TOOLCHAIN_BIN or PATH)

def run(*a):
    r = subprocess.run([str(x) for x in a], capture_output=True, text=True)
    if r.returncode: sys.exit(f"{' '.join(map(str, a))}\n{r.stdout}{r.stderr}")
    return r.stdout

def main():
    src, out, sources = sys.argv[1], sys.argv[2], sys.argv[3:]
    defines = [x for x in sources if x.startswith("-D")]    # e.g. -DAMU_TIMING=1 (dev builds: timing log)
    sources = [x for x in sources if not x.startswith("-D")]
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(src):
        if os.path.isfile(os.path.join(src, f)) and f != "HIFIYF18.IMG":
            shutil.copy(os.path.join(src, f), out)
    code = bytearray(open(os.path.join(out, "code.bin"), "rb").read())
    ent = 8 + 32 * SLOT
    cl, ce, cs = struct.unpack_from("<3I", code, ent)
    assert ce == RUN0, f"slot 2 runs at {ce:#x}"
    at_run = (ce + cs + 3) & ~3
    at_file = cl - BASE + (at_run - ce)

    work = os.path.join(out, "helpers_build"); os.makedirs(work, exist_ok=True)
    elf, bin_ = os.path.join(work, "helpers.elf"), os.path.join(work, "helpers.bin")
    run(tool("gcc"), *defines, "-mcpu=cortex-m3", "-mthumb", "-Os", "-ffreestanding", "-nostdlib", "-nostartfiles",
        "-fno-tree-loop-distribute-patterns", "-ffunction-sections", "-Wall", "-Wextra", "-Wno-unused-parameter",
        f"-Wl,-Ttext={at_run:#x}", "-Wl,-e,np_load", "-Wl,--no-warn-rwx-segments",
        "-Wl,-Map=" + os.path.join(work, "helpers.map"), "-o", elf, *sources)
    sizes = {f[0]: int(f[1], 16) for f in (l.split() for l in run(tool("size"), "-A", "-x", elf).splitlines())
             if len(f) == 3 and f[0].startswith(".")}
    for s in (".data", ".bss", ".rodata"):
        assert not sizes.get(s), f"helpers must not use {s}"
    run(tool("objcopy"), "-O", "binary", "-j", ".text", elf, bin_)
    blob = open(bin_, "rb").read()
    syms = {f[2]: int(f[0], 16) for f in (l.split() for l in run(tool("nm"), elf).splitlines())
            if len(f) == 3 and f[1] in "Tt"}
    assert at_run + len(blob) <= RUN_END, "slot 2 RAM overflow"
    assert at_file + len(blob) <= FILE_END, "helpers would overlap the Blockz module area"
    assert not any(code[at_file:at_file + len(blob)]), "file area after slot 2 not empty"
    code[at_file:at_file + len(blob)] = blob
    struct.pack_into("<I", code, ent + 8, (at_run - ce) + len(blob))
    open(os.path.join(out, "code.bin"), "wb").write(code)
    json.dump({k: v for k, v in syms.items() if not k.startswith("$")}, open(os.path.join(out, "helpers.json"), "w"), indent=1)
    print(f"slot 2: helpers {len(blob)} B at run {at_run:#x} (code.bin {at_file:#x}); slot size {cs:#x} -> {(at_run - ce) + len(blob):#x}")
    for k in ("np_artist", "np_title_width", "np_title_draw", "np_title_fill", "lib_gate", "cfg_write", "cfg_boot_write", "lib_force"):
        if k in syms: print(f"  {k} = {syms[k]:#x}")

if __name__ == "__main__":
    main()
