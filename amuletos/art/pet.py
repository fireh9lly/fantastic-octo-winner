#!/usr/bin/env python3
"""Song pet mock-ups (v3): an original teardrop creature for the custom AP30 firmware.

Look: a soft teardrop whose tip curls into a little hook like a music note's flag (its signature), stubby feet, big
glossy eyes and rosy cheeks, banded cel shading lit from the top left, outlines in a deeper shade of the body colour.
No arms, no floating head ornament. Drawn procedurally at 40x40 so diet can reshape it, not just recolour it.

  python art/pet.py OUT.png      contact sheet of poses and diet forms (scaled 4x)
"""
import math, sys
from PIL import Image, ImageDraw

S = 40
EYE, EYE_LO, WHITE = (46, 48, 86), (110, 118, 190), (255, 255, 255)
BLUSH, MOUTH, TONGUE = (255, 150, 172), (128, 44, 66), (240, 120, 140)
NOTE, SPAT = (115, 83, 224), (158, 162, 176)
TEXT = (35, 37, 46)

# fill, shade, deep, outline, light
PAL = {"mint":    ((132, 220, 200), (92, 186, 174), (64, 148, 148), (44, 100, 108), (214, 248, 238)),
       "spiky":   ((250, 140, 160), (222, 100, 128), (182, 70, 102), (124, 44, 74), (255, 214, 222)),
       "sleepy":  ((150, 186, 242), (112, 150, 216), (84, 116, 184), (58, 80, 138), (220, 234, 255)),
       "sparkly": ((255, 218, 104), (238, 184, 64), (206, 146, 40), (150, 100, 30), (255, 246, 196)),
       "goth":    ((140, 112, 178), (108, 84, 148), (80, 60, 116), (50, 36, 76), (196, 178, 222))}
HAIR = ((54, 40, 80), (82, 64, 116))            # goth strands: dark, lit edge

GLYPH = {"h": ["1..", "1..", "111", "1.1", "1.1"], "i": ["1", ".", "1", "1", "1"], "c": ["...", "111", "1..", "1..", "111"],
         "!": ["1", "1", "1", ".", "1"], "z": ["111", "..1", ".1.", "1..", "111"], "Z": ["1111", "...1", "..1.", ".1..", "1111"],
         ".": [".", ".", ".", ".", "1"], "n": ["...", "11.", "1.1", "1.1", "1.1"], "o": ["...", ".1.", "1.1", "1.1", ".1."],
         "m": [".....", "11.1.", "1.1.1", "1.1.1", "1.1.1"], "p": ["...", "11.", "1.1", "11.", "1.."],
         "t": [".1.", "111", ".1.", ".1.", ".11"]}


class Pix:
    def __init__(self, w=S, h=S):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def get(self, x, y):
        return self.px[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def word(self, s, x, y, c):
        for ch in s:
            g = GLYPH[ch]
            for r, row in enumerate(g):
                for k, v in enumerate(row):
                    if v == "1":
                        self.set(x + k, y + r, c)
            x += len(g[0]) + 1

    def image(self, k, bg):
        im = Image.new("RGB", (self.w * k, self.h * k), bg)
        d = ImageDraw.Draw(im)
        for y in range(self.h):
            for x in range(self.w):
                c = self.px[y][x]
                if c:
                    d.rectangle([x * k, y * k, x * k + k - 1, y * k + k - 1], fill=c)
        return im


def teardrop(cx=20.0, cy=25.0, r=12.0, tip=8.0, squash=0.0):
    """round bottom (flattened where it sits) tapering with concave sides up to a tip; squash = rounder/squatter"""
    rx, ry = r * (1 + squash), r * (1 - squash * 0.45)
    tip_y = cy - ry - tip * (1 - squash)
    m = set()
    for y in range(S):
        yc = y + 0.5
        for x in range(S):
            xc = x + 0.5
            if yc >= cy:
                inside = ((xc - cx) / rx) ** 2 + ((yc - cy) / ry) ** 2 <= 1 and yc - cy <= ry * 0.84
            elif yc >= tip_y:
                t = (yc - tip_y) / (cy - tip_y)
                inside = abs(xc - cx) <= rx * t ** 1.35
            else:
                inside = False
            if inside:
                m.add((x, y))
    return m, int(tip_y), int(cy + ry * 0.84)


def creature(form="mint", pose="idle"):
    p = Pix()
    fill, shade, deep, outline, light = PAL[form]
    squash = {"sleepy": 0.22, "sparkly": 0.05}.get(form, 0.0)
    cx, cy, r = 20.0, 25.0, 12.0
    if pose == "sulk":
        squash, cy = 0.75, 31.0
    body, tip_y, bottom = teardrop(cx, cy, r, squash=squash)
    mask = set(body)

    # signature: the tip curls over into a hook (a note's flag)
    tipx = int(cx)
    curl = [(tipx, tip_y - 1), (tipx + 1, tip_y - 2), (tipx + 2, tip_y - 2), (tipx + 3, tip_y - 1), (tipx + 3, tip_y)]
    if pose == "sulk":
        curl = [(tipx + 1, tip_y), (tipx + 2, tip_y), (tipx + 3, tip_y + 1)]      # drooping
    mask |= set(curl)
    # intense diet: soft rounded bumps down the back of the head
    if form == "spiky":
        for by in (tip_y + 4, tip_y + 8, tip_y + 12):
            row = [x for (x, y) in body if y == by]
            for ex, out in ((min(row), -1), (max(row), 1)):
                for (dx, dy) in ((out, 0), (out, -1), (out, 1), (2 * out, -1), (2 * out, 0), (3 * out, -1)):
                    mask.add((ex + dx, by + dy))
    # feet: two stubby nubs
    feet = set()
    if pose != "sulk":
        for fx in (int(cx - r * 0.45) - 1, int(cx + r * 0.45) - 2):
            for dx in range(4):
                for dy in (0, 1):
                    if not (dy == 1 and dx in (0, 3)):
                        feet.add((fx + dx, bottom - 1 + dy))
    mask |= feet

    # banded cel shading from a sphere normal, light from the top left
    sx, sy, R = cx, cy - r * 0.25, r * 1.25
    L = (-0.45, -0.6, 0.66)
    for (x, y) in mask:
        nx, ny = (x + 0.5 - sx) / R, (y + 0.5 - sy) / R
        nz = math.sqrt(max(0.0, 1 - nx * nx - ny * ny))
        i = nx * L[0] + ny * L[1] + nz * L[2]
        c = fill if i > 0.5 else shade if i > 0.18 else deep
        if (x, y) in feet:
            c = shade if i > 0.3 else deep
        p.set(x, y, c)
    for (x, y) in mask:                                       # soft outline: deeper tone of the body colour
        if any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            p.set(x, y, outline)
    hx, hy = int(cx - r * 0.5), int(cy - r * 0.62) if pose != "sulk" else int(cy - 3)
    for (x, y) in ((hx, hy), (hx + 1, hy), (hx, hy + 1), (hx + 2, hy - 1 if pose != "sulk" else hy)):   # gloss
        if (x, y) in body:
            p.set(x, y, light)
    if pose != "sulk":
        p.set(hx + 1, hy + 1, light)

    if pose == "sulk":                                        # melted face-down: no face, just "..."
        p.word("...", 17, tip_y - 7, TEXT)
        return p

    # face
    ey, my = int(cy - 3), int(cy + 3)
    eyes = (int(cx - 5), int(cx + 3))

    def open_eye(ex, star=False, lid=False):
        for dy in range(5):
            for dx in range(3):
                if (dy in (0, 4)) and dx != 1:
                    continue
                p.set(ex + dx, ey + dy, EYE)
        p.set(ex + 1, ey + 3, EYE_LO); p.set(ex + 2, ey + 3, EYE_LO)
        if star:
            p.set(ex + 1, ey + 1, WHITE); p.set(ex, ey + 1, (255, 236, 150)); p.set(ex + 2, ey + 1, (255, 236, 150))
            p.set(ex + 1, ey, (255, 236, 150)); p.set(ex + 1, ey + 2, (255, 236, 150))
        else:
            p.set(ex, ey + 1, WHITE); p.set(ex, ey + 2, WHITE); p.set(ex + 2, ey + 3, WHITE)
        if lid:                                               # half-lidded, unimpressed
            for dx in range(-1, 4):
                p.set(ex + dx, ey, outline); p.set(ex + dx, ey + 1, outline)

    def closed_eye(ex, happy):
        if happy:   # ^
            p.set(ex, ey + 2, EYE); p.set(ex + 1, ey + 1, EYE); p.set(ex + 2, ey + 2, EYE)
        else:       # sleeping arc
            p.set(ex, ey + 2, EYE); p.set(ex + 1, ey + 3, EYE); p.set(ex + 2, ey + 2, EYE)

    def blush(wide=False):
        for ex, side in ((eyes[0], -1), (eyes[1], 1)):
            bx = ex - 1 if side < 0 else ex + 1
            for dx in range(4 if wide else 3):
                p.set(bx + dx - (1 if wide and side < 0 else 0), ey + 6, BLUSH)

    if form == "sleepy":
        for ex in eyes: closed_eye(ex, False)
        blush()
        p.set(19, my + 1, MOUTH); p.set(20, my + 1, MOUTH)
        p.word("zZ", 28, 4, TEXT)
        return p
    if pose == "feast":
        for ex in eyes: closed_eye(ex, True)
        blush()
        for dx in range(-2, 2):                               # big happy open mouth
            p.set(20 + dx, my, MOUTH)
        for dx in range(-1, 1):
            p.set(20 + dx, my + 1, TONGUE)
        p.set(17, my - 1, MOUTH); p.set(22, my - 1, MOUTH)
        return p
    if pose == "hiccup":
        p.set(eyes[0], ey + 1, EYE); p.set(eyes[0] + 1, ey + 2, EYE); p.set(eyes[0], ey + 3, EYE)       # >
        p.set(eyes[1] + 2, ey + 1, EYE); p.set(eyes[1] + 1, ey + 2, EYE); p.set(eyes[1] + 2, ey + 3, EYE)  # <
        blush()
        p.set(19, my, MOUTH); p.set(20, my, MOUTH); p.set(19, my + 1, MOUTH); p.set(20, my + 1, MOUTH)
        p.word("hic!", 26, 3, TEXT)
        for (x, y) in ((25, 12), (26, 11), (26, 13), (27, 12)):
            p.set(x, y, (200, 230, 250))
        return p

    goth = form == "goth"
    open_eye(eyes[0], star=form == "sparkly", lid=goth)
    open_eye(eyes[1], star=form == "sparkly", lid=goth)
    if not goth:
        blush(wide=pose == "spit")
    if pose == "eat":
        for (x, y) in ((19, my), (20, my), (18, my + 1), (21, my + 1), (19, my + 2), (20, my + 2)):
            p.set(x, y, MOUTH)
        p.set(19, my + 1, TONGUE); p.set(20, my + 1, MOUTH)
        for (x, y) in ((13, my + 1), (14, my + 1), (13, my + 2), (14, my + 2), (14, my), (14, my - 1), (15, my - 2)):
            p.set(x, y, NOTE)                                 # a little note going in
        p.word("nom", 26, 3, TEXT)
    elif pose == "spit":
        p.set(22, my, MOUTH); p.set(23, my, MOUTH)
        for (x, y) in ((28, my - 1), (29, my - 1), (28, my), (29, my), (30, my), (31, my - 2), (32, my - 3)):
            p.set(x, y, SPAT)
        p.word("pt", 29, 4, TEXT)
    elif goth:
        p.set(18, my + 1, MOUTH); p.set(19, my + 1, MOUTH); p.set(20, my + 1, MOUTH)   # flat, unimpressed
    elif form == "spiky":
        p.set(17, ey - 2, EYE); p.set(18, ey - 1, EYE)        # determined brows
        p.set(24, ey - 2, EYE); p.set(23, ey - 1, EYE)
        for (x, y) in ((18, my), (19, my + 1), (20, my + 1), (21, my)):
            p.set(x, y, MOUTH)
        p.set(21, my + 1, WHITE)                              # tiny fang
    else:
        for (x, y) in ((18, my), (19, my + 1), (20, my + 1), (21, my)):
            p.set(x, y, MOUTH)

    if form == "sparkly":
        for (x, y) in ((5, 12), (34, 9), (6, 30), (33, 27)):
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                p.set(x + dx, y + dy, WHITE if (dx, dy) == (0, 0) else (255, 210, 70))

    if goth:
        # one lank mass of hair: starts at the tip, drapes along the head's slope, covers the left eye and hangs
        # past the chin; lighter strands inside, ragged uneven ends, a little outward drift at the bottom
        xs = [x for (x, y) in body]
        left, right = min(xs) - 1, eyes[0] + 4
        for x in range(left, right + 1):
            ys = [y for (xx, y) in body if xx in (x, x + 1)]
            if not ys:
                continue
            y0 = min(ys)
            span = (right - x) / max(1, right - left)            # 1 at the outer edge, 0 at the parting
            y1 = int(my + 2 + span * 11) + (x * 5) % 3            # ragged ends
            for y in range(y0, y1):
                drift = 1 if (y > bottom - 3 and span > 0.6) else 0
                c = HAIR[1] if (x % 3 == 0 and y < y1 - 2) else HAIR[0]   # continuous lighter strands
                p.set(x - drift, y, c)
            p.set(x, y1, HAIR[0]) if x % 2 else None
        for y in range(tip_y, tip_y + 3):                         # parting at the tip
            for x in range(tipx - 1, tipx + 1):
                p.set(x, y, HAIR[0])
    return p


def sheet(path):
    cells = [("idle", "mint", "idle"), ("eating", "mint", "eat"), ("spits a skip", "mint", "spit"),
             ("MP3 hiccups", "mint", "hiccup"), ("hi-res feast", "mint", "feast"), ("sulking", "mint", "sulk"),
             ("intense diet", "spiky", "idle"), ("calm diet", "sleepy", "idle"), ("bright diet", "sparkly", "idle"),
             ("dark diet", "goth", "idle")]
    k, cols = 4, 5
    cw, ch = S * k + 24, S * k + 36
    bg = (251, 251, 248)
    im = Image.new("RGB", (cols * cw, ((len(cells) + cols - 1) // cols) * ch), bg)
    d = ImageDraw.Draw(im)
    for i, (label, form, pose) in enumerate(cells):
        x, y = (i % cols) * cw + 12, (i // cols) * ch + 6
        im.paste(creature(form, pose).image(k, bg), (x, y))
        d.text((x + 4, y + S * k + 4), label, fill=TEXT)
    im.save(path)


if __name__ == "__main__":
    sheet(sys.argv[1] if len(sys.argv) > 1 else "pet_sheet.png")
