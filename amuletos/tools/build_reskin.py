#!/usr/bin/env python3
"""Build a reskinned firmware image.

  build_reskin.py BASE_DIR ART_DIR STAMP16 [--out build/v01]

BASE_DIR  an unpacked image directory (e.g. build/d1 or build/stock): its sections
          are copied as they are, except images.bin.
ART_DIR   PNGs named NNN.png (stock image index); each replaces that image and must
          match its size. Every other image stays byte-identical to BASE_DIR's.

--font STYLE  also replace ASCII glyphs in font0/font1 with art/font.py STYLE (e.g. bold1x).

Packs OUT/HIFIYF18.IMG with the given stamp and verifies it.
"""
import argparse, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

def run(*a):
    subprocess.run([sys.executable, *a], check=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("base"); p.add_argument("art"); p.add_argument("stamp")
    p.add_argument("--out", default=os.path.join(ROOT, "build", "v01"))
    p.add_argument("--font", help="art/font.py style for stock's text fonts")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.base):
        if os.path.isfile(os.path.join(a.base, f)) and f != "HIFIYF18.IMG":
            shutil.copy(os.path.join(a.base, f), a.out)
    art = sorted(f for f in os.listdir(a.art) if len(f) == 7 and f.endswith(".png") and f[:3].isdigit())
    with tempfile.TemporaryDirectory() as tmp:
        run(os.path.join(TOOLS, "imgres.py"), "export", os.path.join(a.base, "images.bin"), tmp)
        for f in art:
            shutil.copy(os.path.join(a.art, f), os.path.join(tmp, f))
        run(os.path.join(TOOLS, "imgres.py"), "pack", os.path.join(a.base, "images.bin"), tmp,
            os.path.join(a.out, "images.bin"))
    print("replaced:", ", ".join(f[:3] for f in art))
    if a.font:
        sys.path.insert(0, os.path.join(ROOT, "art"))
        import font
        f0 = open(os.path.join(a.base, "font0.bin"), "rb").read()
        f1 = open(os.path.join(a.base, "font1.bin"), "rb").read()
        n0, n1 = font.patch_fonts(f0, f1, a.font)
        open(os.path.join(a.out, "font0.bin"), "wb").write(n0)
        open(os.path.join(a.out, "font1.bin"), "wb").write(n1)
        print("fonts:", a.font, "(ASCII glyphs replaced; sizes unchanged:", len(n0) == len(f0) and len(n1) == len(f1), ")")
    img = os.path.join(a.out, "HIFIYF18.IMG")
    run(os.path.join(TOOLS, "ap30fw.py"), "pack", a.out, img, "--stamp", a.stamp)
    run(os.path.join(TOOLS, "ap30fw.py"), "verify", img)

if __name__ == "__main__":
    main()
