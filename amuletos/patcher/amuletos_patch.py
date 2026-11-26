#!/usr/bin/env python3
"""amuletOS patcher: turns the official Hidizs AP30 firmware (V1.7.8, HIFIYF18.IMG) into amuletOS.

  python amuletos_patch.py HIFIYF18.IMG [OUT.IMG]            install amuletOS
  python amuletos_patch.py --stock HIFIYF18.IMG [OUT.IMG]    go back: the official firmware, re-stamped newer

The AP30 only installs a file stamped newer than the firmware it runs, so the official file cannot be copied over
amuletOS as it is; --stock gives it a newer stamp (and the matching checksum) and changes nothing else. After that,
install a later amuletOS release (this one is older than the re-stamped file).

Download the official V1.7.8 firmware from the Hidizs download center, run this script on it, copy the result
(named HIFIYF18.IMG) to the AP30's internal storage and restart the player. Python 3.8+, no other packages.

The patch holds only amuletOS's own code, art and font. Everything that comes from Hidizs is taken from your own
copy of the official file: code moved inside the image is copied from it, and the restyled stock images are
recoloured from its pixels here. Nothing is written unless the input is exactly V1.7.8 and the output matches the
amuletOS build byte for byte (SHA-256 checks).

Patch format (zlib-compressed), little-endian:
  "AMUP" u32 version | 32 B SHA-256 of the input | 32 B SHA-256 of the output | u32 size (input = output)
  u32 image section offset (ROCK26IMAGERES) | 65536 x u16 recolour table (RGB565 in -> RGB565 out)
  u32 image ops, each: u16 image, u8 kind (1 recolour, 2 lighten), u8 0, then for lighten 6 B: glyph RGB, tile RGB
  u32 byte ops, each: u32 offset, u32 length, u8 kind (0 data: length bytes follow, 1 copy: u32 source offset)
Image ops run first, on the input; byte ops then overwrite. Copies read the original input.
"""
import hashlib, math, struct, sys, zlib

PATCH_B64 = None          # filled in by tools/make_patch.py
RESTORE_B64 = None        # the --stock patch (stamp + checksum only), filled in by tools/make_patch.py
VERSION = "0.3"


def _images(buf, sec):
    """(offset in file, width, height) of each image in the ROCK26IMAGERES section at sec"""
    n = struct.unpack_from("<I", buf, sec + 16)[0]
    out = []
    for i in range(n):
        w, h, _x, _y, size, off = struct.unpack_from("<4H2I", buf, sec + 32 + 16 * i)
        out.append((sec + off, w, h))
    return out


def _x8(v):
    """RGB565 (big-endian value) -> 8-bit RGB by bit replication, as the image export does"""
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def lighten(src, off, w, h, col, tile, out):
    """art/pocket.py lighten_icon: dark stock tile -> light tile; glyph strength = distance from the corner colour"""
    px = [_x8(src[off + 2 * i] << 8 | src[off + 2 * i + 1]) for i in range(w * h)]
    bg = px[0]
    d = [math.sqrt(((p[0] - bg[0]) ** 2 + (p[1] - bg[1]) ** 2) + (p[2] - bg[2]) ** 2) for p in px]
    m = max(max(d), 1)
    for i, di in enumerate(d):
        a = min(max(di / m, 0.0), 1.0)
        c = [min(max(tile[k] * (1 - a) + col[k] * a, 0.0), 255.0) for k in range(3)]
        r, g, b = int(c[0]), int(c[1]), int(c[2])
        v = (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)
        out[off + 2 * i] = v >> 8
        out[off + 2 * i + 1] = v & 0xFF


def apply(src, patch):
    """patch (decompressed) applied to src (bytes); returns the output bytes or raises ValueError"""
    if patch[:4] != b"AMUP":
        raise ValueError("not an amuletOS patch")
    p = 8
    sha_in, sha_out = patch[p:p + 32], patch[p + 32:p + 64]; p += 64
    size, sec = struct.unpack_from("<II", patch, p); p += 8
    if len(src) != size or hashlib.sha256(src).digest() != sha_in:
        raise ValueError("this is not the official Hidizs AP30 V1.7.8 HIFIYF18.IMG")
    lut = struct.unpack_from("<65536H", patch, p); p += 131072
    out = bytearray(src)
    imgs = _images(src, sec)
    n = struct.unpack_from("<I", patch, p)[0]; p += 4
    for _ in range(n):
        idx, kind = struct.unpack_from("<HB", patch, p); p += 4
        off, w, h = imgs[idx]
        if kind == 1:
            for i in range(off, off + 2 * w * h, 2):
                v = lut[src[i] << 8 | src[i + 1]]
                out[i] = v >> 8; out[i + 1] = v & 0xFF
        elif kind == 2:
            col, tile = patch[p:p + 3], patch[p + 3:p + 6]; p += 6
            lighten(src, off, w, h, col, tile, out)
        else:
            raise ValueError("unknown image op")
    n = struct.unpack_from("<I", patch, p)[0]; p += 4
    for _ in range(n):
        off, ln, kind = struct.unpack_from("<IIB", patch, p); p += 9
        if kind == 0:
            out[off:off + ln] = patch[p:p + ln]; p += ln
        else:
            s = struct.unpack_from("<I", patch, p)[0]; p += 4
            out[off:off + ln] = src[s:s + ln]
    if hashlib.sha256(out).digest() != sha_out:
        raise ValueError("the result does not match amuletOS " + VERSION + "; nothing was written")
    return bytes(out)


def main():
    import base64, os
    args = sys.argv[1:]
    stock = "--stock" in args
    args = [x for x in args if x != "--stock"]
    if not args or PATCH_B64 is None:
        sys.exit(__doc__)
    src = open(args[0], "rb").read()
    folder = "official-firmware" if stock else "amuletOS-" + VERSION
    dst = args[1] if len(args) > 1 else os.path.join(folder, "HIFIYF18.IMG")
    try:
        out = apply(src, zlib.decompress(base64.b64decode(RESTORE_B64 if stock else PATCH_B64)))
    except ValueError as e:
        sys.exit("Error: " + str(e))
    if os.path.dirname(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "wb").write(out)
    what = "The official firmware (re-stamped)" if stock else f"amuletOS {VERSION}"
    print(f"{what} written to {dst}. Copy it to the AP30's internal storage as HIFIYF18.IMG and restart.")


if __name__ == "__main__":
    main()
