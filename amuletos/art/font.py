"""amuletOS UI font for stock's text renderer (font0 = 12 px, font1 = 16 px sections).

Original glyphs on a 5x8 art grid: capitals and digits from zeal.py (rows 0-6), lower case with
x-height 5 and a 1-row descender (row 7). Encodes them into stock's records (docs/HARDWARE.md, Fonts):
  font0: 32 B per code point, 12 rows x u16 BE (bit 15 = left), byte 24 = 0x80 | advance
  font1: 33 B per code point, 16 rows x u16 BE, byte 32 = 0x80 | advance
Only printable ASCII (U+0021..U+007E) is replaced; space and everything else stays stock.

  python art/font.py preview OUTDIR      render comparison sheets from build/stock fonts
"""
import sys
from pathlib import Path
from zeal import F as CAPS

LOWER = {
 "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####", "....."],
 "b": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "####.", "....."],
 "c": [".....", ".....", ".####", "#....", "#....", "#....", ".####", "....."],
 "d": ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####", "....."],
 "e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".####", "....."],
 "f": ["..##.", ".#...", "####.", ".#...", ".#...", ".#...", ".#...", "....."],
 "g": [".....", ".....", ".####", "#...#", "#...#", ".####", "....#", ".###."],
 "h": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#", "....."],
 "i": ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###.", "....."],
 "j": ["...#.", ".....", "..##.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
 "k": ["#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "....."],
 "l": [".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###.", "....."],
 "m": [".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#", "....."],
 "n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#", "....."],
 "o": [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###.", "....."],
 "p": [".....", ".....", "####.", "#...#", "#...#", "####.", "#....", "#...."],
 "q": [".....", ".....", ".####", "#...#", "#...#", ".####", "....#", "....#"],
 "r": [".....", ".....", "#.##.", "##..#", "#....", "#....", "#....", "....."],
 "s": [".....", ".....", ".####", "#....", ".###.", "....#", "####.", "....."],
 "t": [".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##.", "....."],
 "u": [".....", ".....", "#...#", "#...#", "#...#", "#..##", ".##.#", "....."],
 "v": [".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#..", "....."],
 "w": [".....", ".....", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#.", "....."],
 "x": [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "....."],
 "y": [".....", ".....", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
 "z": [".....", ".....", "#####", "...#.", "..#..", ".#...", "#####", "....."],
}
EXTRA = {   # punctuation not in zeal.py, same 5x7 style
 "\"": [10, 10, 0, 0, 0, 0, 0], "#": [10, 31, 10, 10, 31, 10, 0], "$": [4, 15, 20, 14, 5, 30, 4],
 "*": [0, 21, 14, 31, 14, 21, 0], ";": [0, 12, 12, 0, 12, 4, 8], "<": [2, 4, 8, 16, 8, 4, 2],
 "=": [0, 0, 31, 0, 31, 0, 0], ">": [8, 4, 2, 1, 2, 4, 8], "@": [14, 17, 23, 21, 23, 16, 14],
 "[": [14, 8, 8, 8, 8, 8, 14], "\\": [16, 16, 8, 4, 2, 1, 1], "]": [14, 2, 2, 2, 2, 2, 14],
 "^": [4, 10, 17, 0, 0, 0, 0], "_": [0, 0, 0, 0, 0, 0, 31], "`": [8, 4, 0, 0, 0, 0, 0],
 "{": [2, 4, 4, 8, 4, 4, 2], "|": [4, 4, 4, 4, 4, 4, 4], "}": [8, 4, 4, 2, 4, 4, 8], "~": [0, 0, 8, 21, 2, 0, 0],
 "&": [12, 18, 20, 8, 21, 18, 13], "(": [2, 4, 8, 8, 8, 4, 2], ")": [8, 4, 2, 2, 2, 4, 8],
}

def glyph_rows(ch, caps_only=False):
    """8 rows of 5-bit ints (bit 4 = left) for ch, or None if we don't draw it."""
    if caps_only and ch.isalpha():
        ch = ch.upper()
    if ch in LOWER:
        return [int(r.replace("#", "1").replace(".", "0"), 2) for r in LOWER[ch]]
    g = CAPS.get(ch) or EXTRA.get(ch)
    return list(g) + [0] if g else None

def trimmed(rows):
    """(rows shifted to start at column 0, used width in columns)."""
    used = 0
    for r in rows: used |= r
    if not used: return rows, 2
    left = max(c for c in range(5) if used & (1 << c))      # bit 4 = column 0
    right = min(c for c in range(5) if used & (1 << c))
    width = left - right + 1
    shift = 4 - left
    return [(r << shift) & 31 for r in rows], width

def encode(ch, rows_total, scale, top, caps_only=False, bold=False):
    """stock record bitmap rows (u16 list) and advance for ch."""
    g = glyph_rows(ch, caps_only)
    if g is None: return None
    g, w = trimmed(g)
    out = [0] * rows_total
    for r, bits in enumerate(g):
        for sy in range(scale):
            y = top + r * scale + sy
            if not 0 <= y < rows_total: continue
            v = 0
            for c in range(5):
                if bits & (16 >> c):
                    for sx in range(scale):
                        v |= 0x8000 >> (c * scale + sx)
            out[y] |= (v | ((v >> 1) & ~(v << 1) & 0xFFFF)) if bold else v   # bold: widen strokes, keep 1-px gaps open
    return out, (w + 1) * scale + (1 if bold else 0)

def encode_tall(ch, rows_total, top, bold=True):
    """stock record rows and advance from font_tall.TALL (12-row glyphs, up to 6 columns)."""
    from font_tall import TALL
    rows = TALL.get(ch)
    if rows is None: return None
    cols = [c for c in range(len(rows[0])) if any(r[c] == "#" for r in rows)]
    left, width = cols[0], cols[-1] - cols[0] + 1
    out = [0] * rows_total
    for r, line in enumerate(rows):
        y = top + r
        if not 0 <= y < rows_total: continue
        v = 0
        for c in range(left, len(line)):
            if line[c] == "#": v |= 0x8000 >> (c - left)
        out[y] = (v | ((v >> 1) & ~(v << 1) & 0xFFFF)) if bold else v
    return out, width + 1 + (1 if bold else 0)

# Styles: (name, font1 scale/top/caps, font0 scale/top/caps); "tall" uses font_tall in both
STYLES = {
    "caps2x":  dict(f1=(2, 0, True),  f0=(1, 2, True)),
    "mixed2x": dict(f1=(2, 0, False), f0=(1, 2, False)),
    "mixed1x": dict(f1=(1, 4, False), f0=(1, 2, False)),
    "bold1x":  dict(f1=(1, 4, False, True), f0=(1, 2, False)),
    "tall":    dict(tall=True, f1=3, f0=0),
}

def patch_fonts(font0: bytes, font1: bytes, style: str):
    st = STYLES[style]
    f0, f1 = bytearray(font0), bytearray(font1)
    for cp in range(0x21, 0x7F):
        ch = chr(cp)
        for buf, rec, rows, spec in ((f1, 33, 16, st["f1"]), (f0, 32, 12, st["f0"])):
            e = encode_tall(ch, rows, spec) if st.get("tall") else encode(ch, rows, *spec)
            if e is None: continue
            bm, adv = e
            o = cp * rec
            for r, v in enumerate(bm):
                buf[o + 2 * r] = v >> 8; buf[o + 2 * r + 1] = v & 0xFF
            buf[o + rows * 2] = 0x80 | adv
    return bytes(f0), bytes(f1)

# ---------- preview ----------
def draw_string(px, x, y, s, font, rec, rows, color, space):
    for ch in s:
        cp = ord(ch)
        if cp == 0x20:
            x += space; continue
        o = cp * rec
        for r in range(rows):
            v = font[o + 2 * r] << 8 | font[o + 2 * r + 1]
            for c in range(16):
                if v & (0x8000 >> c) and 0 <= x + c < px.shape[1] and 0 <= y + r < px.shape[0]:
                    px[y + r, x + c] = color
        x += font[o + rows * 2] & 0x7F
    return x

def preview(outdir):
    import numpy as np
    from PIL import Image, ImageDraw
    root = Path(__file__).resolve().parent.parent
    s0 = (root / "build/stock/font0.bin").read_bytes()
    s1 = (root / "build/stock/font1.bin").read_bytes()
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    lines16 = ["Artists", "Yasunori Mitsuda", "Scars of Time",
               "Radical Dreamers - Le Tresor Interdit", "03:12 / 04:05  FLAC 16/44"]
    lines12 = ["Battery 87%  Volume 42  EQ: Rock", "Updating library... 1203 files"]
    panel, ink, frame = (255, 253, 246), (18, 26, 64), (40, 60, 136)
    names = sys.argv[3].split(",") if len(sys.argv) > 3 else list(STYLES)
    sets = [("stock", s0, s1)] + [(n, *patch_fonts(s0, s1, n)) for n in names]
    titles = {"stock": "Stock (now)", "caps2x": "A  Capitals, 2x (mockup)",
              "mixed2x": "B  Upper + lower, 2x", "mixed1x": "C  Upper + lower, 1x (stock size)",
              "bold1x": "D  Upper + lower, 1x bold (build 17)",
              "tall": "E  Tall: fills stock's cell (proposed build 18)"}
    shots = []
    for name, f0, f1 in sets:
        px = np.zeros((240, 296, 3), np.uint8); px[:] = panel
        px[0:2, :] = frame; px[-2:, :] = frame; px[:, 0:2] = frame; px[:, -2:] = frame
        y = 12
        for s in lines16:
            end = draw_string(px, 10, y, s, f1, 33, 16, ink, 4)
            if end > 286: px[y:y + 16, 286:288] = (220, 60, 60)        # red tick = runs past the edge
            y += 26
        y += 6
        px[y - 6:y - 5, 10:286] = (200, 205, 220)
        for s in lines12:
            draw_string(px, 10, y, s, f0, 32, 12, ink, 4)
            y += 20
        shots.append((titles[name], Image.fromarray(px)))
    # sheet: 2x zoom, 2 columns
    cw, ch = 296 * 2 + 20, 240 * 2 + 44
    sheet = Image.new("RGB", (cw * 2, ch * ((len(shots) + 1) // 2)), (27, 33, 64))
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(shots):
        x, y = (i % 2) * cw + 10, (i // 2) * ch + 34
        sheet.paste(im.resize((592, 480), Image.NEAREST), (x, y))
        d.text((x, y - 24), t, fill=(232, 236, 248))
    sheet.save(out / "font_options.png")
    for t, im in shots:
        im.resize((592, 480), Image.NEAREST).save(out / f"font_{t.split()[0].lower()}.png")
    print("wrote", out / "font_options.png")

if __name__ == "__main__":
    if sys.argv[1:2] == ["preview"]:
        preview(sys.argv[2] if len(sys.argv) > 2 else "build/font_preview")
