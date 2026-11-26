#!/usr/bin/env python3
"""Make the amuletOS release patchers from the official firmware and an amuletOS build (v0.3 release).

  make_patch.py STOCK_IMG AMULETOS_IMG OUT_DIR [--version 0.3]

Writes OUT_DIR/amuletos_patch.py (command line) and OUT_DIR/amuletOS-<version>-patcher.html (browser), both with
the patch embedded, after checking that the patch turns STOCK_IMG into AMULETOS_IMG exactly.

The patch must not carry Hidizs's firmware (owner rule; docs/HANDOFF.md): only amuletOS's code, art and font go in
as data. Images recoloured by art/recolor.py (pocket palette, a per-pixel function) become a recolour op plus one
65536-entry table; the dark list icons lightened by art/pocket.py lighten_icon become a lighten op (glyph and tile
colours); stock code that a build copied elsewhere in the image (tools/extend_module.py) becomes a copy op that
reads the user's own file. The patch maker reports how many data bytes are left that also occur in stock code.
"""
import argparse, base64, hashlib, os, struct, sys, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "patcher"))
sys.path.insert(0, os.path.join(ROOT, "art"))
import amuletos_patch as AP                      # noqa: E402  (the applier; the same file ships to users)

MIN_COPY = 32                                    # shortest run sent as a copy from the stock file
KEY = 16


def recolor_lut():
    import numpy as np
    import recolor as R
    R.GREY, R.WARM = R.POCKET_GREY, R.POCKET_WARM
    v = np.arange(65536, dtype=np.uint32)
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    a = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), -1).astype(np.uint8)[None]
    o = R.recolor(a)[0].astype(np.uint32)
    return [int(x) for x in ((o[:, 0] >> 3) << 11) | ((o[:, 1] >> 2) << 5) | (o[:, 2] >> 3)]


def lighten_candidates():
    import pocket as P
    from zeal import rgb
    return [(rgb(P.GRAPE), rgb(P.TINT)), (rgb(P.SKY), rgb(P.WHITE)), (rgb(P.INK), rgb(P.WHITE))]


def code_span(img):
    """file span of the code section (0x200 up to the first font, docs: image layout); copy sources come from here"""
    return 0x200, 0x188914


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stock"); ap.add_argument("build"); ap.add_argument("out")
    ap.add_argument("--version", default="0.3")
    ap.add_argument("--restore-stamp", default="2620071161000000",
                    help="stamp for 'back to stock': newer than this amuletOS build (the AP30 installs newer stamps only)")
    a = ap.parse_args()
    src = open(a.stock, "rb").read()
    dst = open(a.build, "rb").read()
    assert len(src) == len(dst), "image sizes differ"
    sec = src.find(b"ROCK26IMAGERES")
    assert sec == dst.find(b"ROCK26IMAGERES") and src[sec:sec + 32 + 16 * 478] == dst[sec:sec + 32 + 16 * 478], \
        "image tables differ"
    lut = recolor_lut()
    cands = lighten_candidates()

    # ---- image ops ----
    pred = bytearray(src)
    img_ops = b""
    nimg = {"same": 0, "recolour": 0, "lighten": 0, "art": 0}
    for idx, (off, w, h) in enumerate(AP._images(src, sec)):
        n = 2 * w * h
        s, d = src[off:off + n], dst[off:off + n]
        if s == d:
            nimg["same"] += 1; continue
        rec = bytearray(n)
        for i in range(0, n, 2):
            v = lut[s[i] << 8 | s[i + 1]]; rec[i] = v >> 8; rec[i + 1] = v & 0xFF
        if rec == d:
            pred[off:off + n] = d; img_ops += struct.pack("<HBB", idx, 1, 0); nimg["recolour"] += 1; continue
        hit = False
        if w <= 40 and h <= 40:
            for col, tile in cands:
                tmp = bytearray(src)
                AP.lighten(src, off, w, h, col, tile, tmp)
                if tmp[off:off + n] == d:
                    pred[off:off + n] = d
                    img_ops += struct.pack("<HBB", idx, 2, 0) + bytes(col) + bytes(tile)
                    nimg["lighten"] += 1; hit = True; break
        if not hit:
            nimg["art"] += 1                     # amuletOS art: goes in as data below

    # ---- byte ops: what is still different, with copies from the stock code region ----
    c0, c1 = code_span(src)
    index = {}
    for i in range(c0, c1 - KEY, 2):
        index.setdefault(src[i:i + KEY], i)
    ops, data_bytes, copy_bytes = [], 0, 0
    n = len(dst)
    i = 0
    while i < n:
        if pred[i] == dst[i]:
            i += 1; continue
        j = i
        while j < n:                             # a run: differences with gaps shorter than 8 equal bytes
            if pred[j] != dst[j]:
                j += 1; continue
            k = j
            while k < n and k - j < 8 and pred[k] == dst[k]:
                k += 1
            if k - j >= 8 or k == n:
                break
            j = k
        run_end = j
        p = i
        lit = p
        while p < run_end:
            s = index.get(dst[p:p + KEY]) if run_end - p >= MIN_COPY else None
            if s is not None:
                L = 0
                while p + L < run_end and src[s + L] == dst[p + L]:
                    L += 1
                if L >= MIN_COPY:
                    if lit < p:
                        ops.append(struct.pack("<IIB", lit, p - lit, 0) + dst[lit:p]); data_bytes += p - lit
                    ops.append(struct.pack("<IIBI", p, L, 1, s)); copy_bytes += L
                    p += L; lit = p; continue
            p += 2 if p + 1 < run_end else 1
        if lit < run_end:
            ops.append(struct.pack("<IIB", lit, run_end - lit, 0) + dst[lit:run_end]); data_bytes += run_end - lit
        i = run_end

    count = nimg["recolour"] + nimg["lighten"]
    patch = (b"AMUP" + struct.pack("<I", 1) + hashlib.sha256(src).digest() + hashlib.sha256(dst).digest()
             + struct.pack("<II", len(src), sec) + struct.pack("<65536H", *lut)
             + struct.pack("<I", count) + img_ops + struct.pack("<I", len(ops)) + b"".join(ops))

    # ---- check: the shipped applier must rebuild the amuletOS image exactly ----
    out = AP.apply(src, patch)
    assert out == dst, "patch does not reproduce the build"

    # stock code that still travels as data (should be tiny: instruction-sized fragments)
    leak = 0
    for op in ops:
        off, ln, kind = struct.unpack_from("<IIB", op)
        if kind == 0 and ln >= KEY and off < c1:            # code region only; flat blocks (padding) don't count
            body = op[9:]
            for q in range(0, ln - KEY + 1, KEY):
                blk = body[q:q + KEY]
                if len(set(blk)) > 2 and blk in index: leak += KEY
    z = zlib.compress(patch, 9)
    b64 = base64.b64encode(z).decode()

    # ---- back to stock: the official file with a newer stamp (both headers) and the matching checksum ----
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import ap30fw
    st = bytes.fromhex(a.restore_stamp)
    assert st[4] > dst[4] and st[:4] == dst[:4], "restore stamp must be newer than the amuletOS build"
    rest = bytearray(src)
    bk = struct.unpack_from("<I", src, 0x1F4)[0]
    rest[0:8] = st; rest[bk:bk + 8] = st
    struct.pack_into("<I", rest, len(rest) - 4, ap30fw.rkcrc(rest[:len(rest) - 4]))
    rops = b"".join(struct.pack("<IIB", o, n_, 0) + bytes(rest[o:o + n_])
                    for o, n_ in ((0, 8), (bk, 8), (len(rest) - 4, 4)))
    assert sum(x != y for x, y in zip(src, rest)) <= 20
    rpatch = (b"AMUP" + struct.pack("<I", 1) + hashlib.sha256(src).digest() + hashlib.sha256(rest).digest()
              + struct.pack("<II", len(src), sec) + bytes(131072) + struct.pack("<I", 0) + struct.pack("<I", 3) + rops)
    assert AP.apply(src, rpatch) == bytes(rest)
    tmp = os.path.join(a.out, "restore_check.img")
    os.makedirs(a.out, exist_ok=True)
    open(tmp, "wb").write(rest)
    import subprocess
    v = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ap30fw.py"), "verify", tmp], capture_output=True, text=True)
    os.remove(tmp)
    assert v.returncode == 0 and "FAIL" not in v.stdout, v.stdout + v.stderr
    rb64 = base64.b64encode(zlib.compress(rpatch, 9)).decode()
    os.makedirs(a.out, exist_ok=True)
    py = open(os.path.join(ROOT, "patcher", "amuletos_patch.py"), encoding="utf-8").read()
    py = py.replace('PATCH_B64 = None          # filled in by tools/make_patch.py', 'PATCH_B64 = "' + b64 + '"')
    py = py.replace('RESTORE_B64 = None        # the --stock patch (stamp + checksum only), filled in by tools/make_patch.py',
                    'RESTORE_B64 = "' + rb64 + '"')
    py = py.replace('VERSION = "0.3"', f'VERSION = "{a.version}"')
    open(os.path.join(a.out, "amuletos_patch.py"), "w", encoding="utf-8", newline="\n").write(py)
    html = open(os.path.join(ROOT, "patcher", "patcher.html"), encoding="utf-8").read()
    html = html.replace("__PATCH_B64__", b64).replace("__RESTORE_B64__", rb64).replace("__VERSION__", a.version) \
               .replace("__SHA_IN__", hashlib.sha256(src).hexdigest()).replace("__SHA_OUT__", hashlib.sha256(dst).hexdigest())
    hp = os.path.join(a.out, f"amuletOS-{a.version}-patcher.html")
    open(hp, "w", encoding="utf-8", newline="\n").write(html)
    print(f"images: {nimg}")
    print(f"byte ops {len(ops)}: data {data_bytes} B, copies from stock {copy_bytes} B; data matching stock code "
          f"{leak} B; patch {len(patch)} B, compressed {len(z)} B")
    print("output sha256", hashlib.sha256(dst).hexdigest())
    print("wrote", os.path.join(a.out, "amuletos_patch.py"), "and", hp)


if __name__ == "__main__":
    main()
