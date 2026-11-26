#!/usr/bin/env python3
"""ROCK26IMAGERES tool (UI images section of the AP30 firmware).

  imgres.py list   IMAGES_BIN
  imgres.py export IMAGES_BIN OUTDIR        -> OUTDIR/NNN.png + index.json
  imgres.py pack   IMAGES_BIN PNGDIR OUT    -> new images.bin (sizes must match)

Format (V1.7.8):
  0x00  "ROCK26IMAGERES  " (16 bytes)
  0x10  u32 count (478), 12 bytes zero
  0x20  count x 16-byte entries: u16 w, u16 h, u16 x, u16 y, u32 size, u32 offset
  pixels: raw RGB565, BIG-endian, row-major, upright; size = w*h*2; stored back to
  back from 0x2200. Bytes after the last image are kept as they are.

Colour conversion is lossless both ways (5/6-bit values expand by bit replication,
and compress by truncation), so export + pack of unchanged PNGs is byte-identical.
"""
import json, os, struct, sys
import numpy as np
from PIL import Image

MAGIC = b"ROCK26IMAGERES  "

def entries(d):
    assert d[:16] == MAGIC, "not a ROCK26IMAGERES section"
    n = struct.unpack_from("<I", d, 16)[0]
    return [dict(zip("w h x y size off".split(), struct.unpack_from("<4H2I", d, 32 + 16 * i)))
            for i in range(n)]

def to_rgb(raw, w, h):
    v = np.frombuffer(raw, dtype=">u2").reshape(h, w).astype(np.uint16)
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return np.dstack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))).astype(np.uint8)

def to_565(rgb):
    a = rgb.astype(np.uint16)
    v = ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)
    return v.astype(">u2").tobytes()

def cmd_list(d):
    for i, e in enumerate(entries(d)):
        print(f"{i:3d} {e['w']:3d}x{e['h']:<3d} at ({e['x']:3d},{e['y']:3d})  off 0x{e['off']:07X}")

def cmd_export(d, out):
    os.makedirs(out, exist_ok=True)
    es = entries(d)
    for i, e in enumerate(es):
        Image.fromarray(to_rgb(d[e["off"]:e["off"] + e["size"]], e["w"], e["h"])).save(os.path.join(out, f"{i:03d}.png"))
    json.dump(es, open(os.path.join(out, "index.json"), "w"), indent=0)
    print(f"exported {len(es)} images to {out}")

def cmd_pack(d, pngdir, out):
    es = entries(d)
    b = bytearray(d)
    changed = 0
    for i, e in enumerate(es):
        im = Image.open(os.path.join(pngdir, f"{i:03d}.png")).convert("RGB")
        if im.size != (e["w"], e["h"]):
            sys.exit(f"{i:03d}.png is {im.size[0]}x{im.size[1]}, must be {e['w']}x{e['h']}")
        raw = to_565(np.asarray(im))
        if raw != d[e["off"]:e["off"] + e["size"]]:
            changed += 1
        b[e["off"]:e["off"] + e["size"]] = raw
    open(out, "wb").write(b)
    print(f"packed {out}: {changed} of {len(es)} images changed")

def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    d = open(a[1], "rb").read()
    if a[0] == "list": cmd_list(d)
    elif a[0] == "export": cmd_export(d, a[2])
    elif a[0] == "pack": cmd_pack(d, a[2], a[3])
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
