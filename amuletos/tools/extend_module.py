#!/usr/bin/env python3
"""Give a stock screen module its own extra code: copy the module's code into donor file space and link our
extension right after it, at the module's own run addresses (build 37).

  extend_module.py SRC_DIR OUT_DIR --module 22 SOURCE.c|.S [...] [--json e22.json] [--donor 100] [--at OFF]

Slot 2 (the only resident RAM) is full; hooks that only run while one screen is up belong in that screen's module.
The module's code is copied to the donor span at the next free offset (OUT_DIR/donor.json "next"; --at overrides), the extension is
linked at run = module run end (4-aligned) and appended, and the module's table entry is pointed at the copy with
the larger code size. Data / ZI are untouched, and the extension may not have .data / .bss (stack only).

Donor: stock game module 100 (13 KB, task 33; unreachable since the Games tile opens Blockz). On first use its
span is zeroed and recorded in OUT_DIR/donor.json; tools/build_module.py then points the donor's table entry at the
module it installs (Playlists), so a launch would open that instead of garbage. Symbols go to OUT_DIR/<json> for
tools/patch_code.py.
"""
import argparse, json, os, shutil, struct, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x03050000
WINDOW_END = 0x0308BF84              # music engine (module 33) starts here

from toolchain import tool                # noqa: E402  (tools/toolchain.py: ARM_TOOLCHAIN_BIN or PATH)

def run(*a):
    r = subprocess.run([str(x) for x in a], capture_output=True, text=True)
    if r.returncode: sys.exit(f"{' '.join(map(str, a))}\n{r.stdout}{r.stderr}")
    return r.stdout

def entry(code, i): return list(struct.unpack_from("<8I", code, 8 + 32 * i))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("src"); p.add_argument("out"); p.add_argument("sources", nargs="+")
    p.add_argument("--module", type=int, required=True)
    p.add_argument("--at", type=lambda s: int(s, 0), default=None)
    p.add_argument("--donor", type=int, default=100)
    p.add_argument("--json", default=None)
    p.add_argument("-D", dest="defines", action="append", default=[], help="preprocessor define (e.g. AMU_TIMING=1)")
    a = p.parse_args()

    if os.path.abspath(a.src) != os.path.abspath(a.out):
        os.makedirs(a.out, exist_ok=True)
        for f in os.listdir(a.src):
            if os.path.isfile(os.path.join(a.src, f)) and f != "HIFIYF18.IMG":
                shutil.copy(os.path.join(a.src, f), a.out)
    cp = os.path.join(a.out, "code.bin")
    code = bytearray(open(cp, "rb").read())

    # donor span (stock layout: code then data, contiguous); remembered in donor.json once taken
    dj = os.path.join(a.out, "donor.json")
    if os.path.exists(dj):
        dinfo = json.load(open(dj))
        span0, span1 = dinfo["span"]
    else:
        d = entry(code, a.donor)
        span0, span1 = d[0] - BASE, d[3] - BASE + d[5]
        assert d[3] - BASE - (span0 + d[2]) < 4, "donor code and data not contiguous"
        code[span0:span1] = bytes(span1 - span0)
        dinfo = {"donor": a.donor, "span": [span0, span1], "next": 0}
        print(f"donor module {a.donor}: span {span0:#x}..{span1:#x} ({span1 - span0} B) zeroed")

    m = entry(code, a.module)
    cl, ce, cs = m[0], m[1], m[2]
    old = bytes(code[cl - BASE:cl - BASE + cs])
    ext_run = (ce + cs + 3) & ~3
    work = os.path.join(a.out, f"ext{a.module}_build"); os.makedirs(work, exist_ok=True)
    elf, binf = os.path.join(work, "ext.elf"), os.path.join(work, "ext.bin")
    # slot-2 helpers as absolute H_<name> symbols (build 57: the main menu installs the timing hooks); taken as data
    # addresses so the linker never treats them as ARM code
    hj = os.path.join(a.src, "helpers.json")
    defsyms = [f"-Wl,--defsym=H_{k}={v:#x}" for k, v in (json.load(open(hj)).items() if os.path.exists(hj) else ())
               if k[:1].isalpha() and k.replace("_", "").isalnum()]
    run(tool("gcc"), *["-D" + d for d in a.defines], "-mcpu=cortex-m3", "-mthumb", "-Os", "-ffreestanding", "-nostdlib", "-nostartfiles",
        "-fno-tree-loop-distribute-patterns", "-ffunction-sections", "-Wall", "-Wextra", "-Wno-unused-parameter",
        "-I", os.path.join(ROOT, "game"), f"-Wl,-Ttext={ext_run:#x}", "-Wl,--no-warn-rwx-segments", "-Wl,-e,0",
        "-Wl,-Map=" + os.path.join(work, "ext.map"), *defsyms, "-o", elf, *a.sources)
    sizes = {f[0]: int(f[1], 16) for f in (l.split() for l in run(tool("size"), "-A", "-x", elf).splitlines())
             if len(f) == 3 and f[0].startswith(".")}
    for s in (".data", ".bss", ".rodata"):
        assert not sizes.get(s), f"extension must not use {s} (tables go in .text)"
    run(tool("objcopy"), "-O", "binary", "-j", ".text", elf, binf)
    ext = open(binf, "rb").read()
    syms = {f[2]: int(f[0], 16) for f in (l.split() for l in run(tool("nm"), elf).splitlines())
            if len(f) == 3 and f[1] in "Tt" and not f[2].startswith("$")}

    blob = old + bytes(ext_run - (ce + cs)) + ext
    t_off = span0 + (a.at if a.at is not None else dinfo["next"])
    assert t_off + len(blob) <= span1, f"donor span full: needs {t_off + len(blob) - span0:#x} of {span1 - span0:#x}"
    assert not any(code[t_off:t_off + len(blob)]), "donor area at --at is not empty"
    assert ce + len(blob) <= WINDOW_END, "extension runs into the music engine"
    code[t_off:t_off + len(blob)] = blob
    struct.pack_into("<3I", code, 8 + 32 * a.module, BASE + t_off, ce, len(blob))
    open(cp, "wb").write(code)
    dinfo["next"] = (t_off + len(blob) - span0 + 3) & ~3
    json.dump(dinfo, open(dj, "w"))
    if a.json:
        json.dump(syms, open(os.path.join(a.out, a.json), "w"), indent=1)
    print(f"module {a.module}: code {cs:#x} -> {len(blob):#x} B (extension {len(ext)} B at run {ext_run:#x}), "
          f"code.bin {t_off:#x}; donor next {dinfo['next']:#x} of {span1 - span0:#x}")

if __name__ == "__main__":
    main()
