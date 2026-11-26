#!/usr/bin/env python3
"""Peak, the song pet (mock-ups v4): an original soft-serve creature for the custom AP30 firmware.

Look: stacked soft-serve tiers (a wide bottom scoop, two smaller swirls) ending in a peak that curls over like a
music note's flag. Stubby feet, big glossy eyes, rosy cheeks, banded cel shading lit from the top left, a shadow
line under every overhang, outlines in a deeper shade of the body colour. No arms, no floating head ornament.
Drawn procedurally at 40x40 so diet reshapes it, not just recolours it. Melting = sulking.
Dark diet: thick rounded locks spill from the peak like melting drips, arch over and hang down at staggered
lengths; eyebags and half-lidded eyes.

  python art/pet.py OUT.png      contact sheet of poses and diet forms (scaled 4x)
"""
import math, sys
from PIL import Image, ImageDraw

S = 40
EYE, EYE_LO, WHITE = (46, 48, 86), (110, 118, 190), (255, 255, 255)
BLUSH, MOUTH, TONGUE = (255, 150, 172), (128, 44, 66), (240, 120, 140)
NOTE, SPAT, TEXT = (115, 83, 224), (158, 162, 176), (35, 37, 46)

# fill, shade, deep, outline, light
PAL = {"mint":    ((150, 226, 206), (102, 192, 178), (70, 152, 150), (44, 100, 108), (222, 250, 242)),
       "spiky":   ((250, 146, 166), (224, 104, 132), (184, 72, 104), (124, 44, 74), (255, 218, 226)),
       "sleepy":  ((156, 190, 244), (116, 154, 218), (86, 118, 186), (58, 80, 138), (222, 236, 255)),
       "sparkly": ((255, 220, 112), (240, 186, 70), (208, 148, 44), (150, 100, 30), (255, 247, 200)),
       "goth":    ((146, 118, 184), (112, 88, 152), (84, 64, 120), (40, 28, 62), (200, 182, 226))}
LOCK = ((86, 64, 124), (60, 44, 92), (128, 104, 170))   # dark-diet locks: base, shadow side, lit side

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


def ellipse(cx, cy, rx, ry, flat=None):
    """pixels of an ellipse; flat cuts the bottom at cy + flat * ry (where it sits)"""
    out = set()
    for y in range(S):
        for x in range(S):
            dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
            if dx * dx + dy * dy <= 1 and (flat is None or dy <= flat):
                out.add((x, y))
    return out


def tube(points, r):
    """a soft round-ended tube of radius r along a polyline"""
    out = set()
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        n = max(1, int(math.hypot(bx - ax, by - ay) * 3))
        for k in range(n + 1):
            f = k / n
            out |= ellipse(ax + (bx - ax) * f, ay + (by - ay) * f, r, r)
    return out


def tiers(form, pose):
    """soft-serve tiers bottom to top as (cx, cy, rx, ry, flat)"""
    if pose == "sulk":                                   # melted: a wide puddle with a lump on top
        return [(20, 33.5, 17.5, 4.6, 0.8), (18.5, 29.5, 6.5, 2.8, None)]
    t = [(20, 27.5, 12.8, 8.6, 0.86), (21, 18.8, 8.8, 4.8, None), (19.6, 12.6, 5.6, 3.5, None), (20.4, 8.6, 2.8, 2.3, None)]
    if form == "sleepy":                                 # squatter and wider: settled
        t = [(cx, 35.5 - (35.5 - cy) * 0.86, rx * 1.1, ry * 0.92, f) for cx, cy, rx, ry, f in t]
    return t


def shade_tube(p, shape, outline, behind=None):
    """locks: lit on the left, shadowed on the right, outlined where they meet anything else"""
    for (x, y) in shape:
        if behind is not None and (x, y) in behind:
            continue
        left_open, right_open = (x - 1, y) not in shape, (x + 1, y) not in shape
        p.set(x, y, LOCK[2] if left_open else LOCK[1] if right_open else LOCK[0])
    for (x, y) in shape:
        if behind is not None and (x, y) in behind:
            continue
        if any((x + dx, y + dy) not in shape for dx, dy in ((0, 1), (-1, 0), (1, 0))) and (x, y + 1) not in shape:
            p.set(x, y, outline)                         # round tips
        elif any((x + dx, y + dy) not in shape and (behind is None or (x + dx, y + dy) not in behind)
                 for dx, dy in ((1, 0), (-1, 0))):
            p.set(x, y, outline)


def locks(tx, ty):
    """dark diet: thick locks spilling from the peak, arching over, hanging at staggered lengths.
    Returns (back, front): back locks sit behind the body, front locks fall over its sides."""
    spec = [(6.5, 31), (10.0, 36), (13.5, 26), (27.0, 26), (30.5, 37), (34.0, 30),      # behind
            (8.5, 33.5), (32.0, 34.5)]                                                    # in front
    shapes = []
    for xf, end in spec:
        side = -1 if xf < tx else 1
        rise = ty - 2 - (4 - abs(xf - tx) / 4)                                            # arch height
        pts = [(tx + 0.5 + side, ty + 1), (tx + 0.5 + (xf - tx) * 0.45, rise),
               (xf - side * 0.8, ty + 2.5), (xf, ty + 8), (xf, end)]
        shapes.append(tube(pts, 1.6))
    return shapes[:6], shapes[6:]


def creature(form="mint", pose="idle"):
    p = Pix()
    fill, shade, deep, outline, light = PAL[form]
    goth = form == "goth"
    T = tiers(form, pose)
    owner = {}                                            # pixel -> index of the tier in front (the higher one)
    for i, (cx, cy, rx, ry, flat) in enumerate(T):
        for px in ellipse(cx, cy, rx, ry, flat):
            owner[px] = i
    mask = set(owner)

    # the peak curls over like a note's flag, growing out of the top tier
    top_cx, top_cy, _, top_ry, _ = T[-1]
    tx, ty = int(top_cx), int(top_cy - top_ry)
    if pose == "sulk":
        curl = [(tx + 1, ty), (tx + 2, ty), (tx + 3, ty + 1), (tx + 4, ty + 1)]          # flopped over
    else:
        curl = [(tx, ty), (tx, ty - 1), (tx + 1, ty - 2), (tx + 2, ty - 2), (tx + 3, ty - 2),
                (tx + 4, ty - 1), (tx + 4, ty), (tx + 1, ty - 1), (tx + 1, ty)]
    for px in curl:
        mask.add(px); owner[px] = len(T) - 1

    if form == "spiky":                                   # soft bumps on the swirls' sides
        for i in (1, 2):
            cx, cy, rx, ry, _ = T[i]
            for side in (-1, 1):
                bx, by = int(cx + side * (rx + 0.5)) - (1 if side < 0 else 0), int(cy)
                for dx, dy in ((0, 0), (side, 0), (0, -1), (side, -1), (2 * side, -1), (0, 1)):
                    mask.add((bx + dx, by + dy)); owner[(bx + dx, by + dy)] = i

    feet = set()
    if pose != "sulk":
        cx, cy, rx, ry, flat = T[0]
        bottom = int(cy + ry * flat)
        for fx in (int(cx - rx * 0.42) - 2, int(cx + rx * 0.42) - 1):
            for dx in range(4):
                for dy in (0, 1):
                    if not (dy == 1 and dx in (0, 3)):
                        feet.add((fx + dx, bottom + dy)); owner[(fx + dx, bottom + dy)] = 0
        mask |= feet

    back, front = locks(tx, ty) if goth and pose != "sulk" else ([], [])
    for shape in back:                                    # behind the body: drawn first, body paints over
        shade_tube(p, shape, outline, behind=mask)

    # shading: each tier lit as its own soft sphere, light from the top left
    L = (-0.45, -0.6, 0.66)
    for (x, y) in mask:
        cx, cy, rx, ry, _ = T[owner[(x, y)]]
        nx, ny = (x + 0.5 - cx) / (rx * 1.15), (y + 0.5 - cy) / (ry * 1.3)
        nz = math.sqrt(max(0.0, 1 - nx * nx - ny * ny))
        i = nx * L[0] + ny * L[1] + nz * L[2]
        c = light if i > 0.86 else fill if i > 0.45 else shade if i > 0.12 else deep
        if (x, y) in feet:
            c = shade if x < 20 else deep
        p.set(x, y, c)
    for (x, y) in mask:
        here = owner[(x, y)]
        above = owner.get((x, y - 1))
        if any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            p.set(x, y, outline)                          # soft outline in the body's own deep tone
        elif above is not None and above > here:
            p.set(x, y, outline)                          # crisp line under each overhang...
            if (x, y + 1) in mask and owner[(x, y + 1)] == here:
                p.set(x, y + 1, deep)                     # ...and its shadow

    if pose == "sulk":                                    # melted face-down: no face, just "..."
        p.word("...", 16, 22, TEXT)
        return p

    # face on the bottom scoop
    cx, cy, rx, ry, _ = T[0]
    ey, my = int(cy - 3), int(cy + 3)
    eyes = (int(cx - 5), int(cx + 3))

    def open_eye(ex, star=False, lid=False):
        for dy in range(5):
            for dx in range(3):
                if dy in (0, 4) and dx != 1:
                    continue
                p.set(ex + dx, ey + dy, EYE)
        p.set(ex + 1, ey + 3, EYE_LO); p.set(ex + 2, ey + 3, EYE_LO)
        if star:
            p.set(ex + 1, ey + 1, WHITE)
            for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
                p.set(ex + dx, ey + dy, (255, 236, 150))
        else:
            p.set(ex, ey + 1, WHITE); p.set(ex, ey + 2, WHITE); p.set(ex + 2, ey + 3, WHITE)
        if lid:                                           # half-lidded, unimpressed
            for dx in range(-1, 4):
                p.set(ex + dx, ey, outline); p.set(ex + dx, ey + 1, outline)

    def eyebags(ex):
        for dx in range(-1, 4):
            p.set(ex + dx, ey + 5, deep)
        for dx in range(0, 3):
            p.set(ex + dx, ey + 6, deep)

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

    def smile():
        for (x, y) in ((18, my), (19, my + 1), (20, my + 1), (21, my)):
            p.set(x, y, MOUTH)

    if form == "sleepy":
        for ex in eyes:
            closed_eye(ex, False)
        blush()
        p.set(19, my + 1, MOUTH); p.set(20, my + 1, MOUTH)
        p.word("zZ", 29, 6, TEXT)
    elif pose == "feast":
        for ex in eyes:
            closed_eye(ex, True)
        blush()
        for dx in range(-2, 2):
            p.set(20 + dx, my, MOUTH)
        p.set(19, my + 1, TONGUE); p.set(20, my + 1, TONGUE)
        p.set(17, my - 1, MOUTH); p.set(22, my - 1, MOUTH)
    elif pose == "hiccup":
        p.set(eyes[0], ey + 1, EYE); p.set(eyes[0] + 1, ey + 2, EYE); p.set(eyes[0], ey + 3, EYE)        # >
        p.set(eyes[1] + 2, ey + 1, EYE); p.set(eyes[1] + 1, ey + 2, EYE); p.set(eyes[1] + 2, ey + 3, EYE)   # <
        blush()
        for (x, y) in ((19, my), (20, my), (19, my + 1), (20, my + 1)):
            p.set(x, y, MOUTH)
        p.word("hic!", 26, 2, TEXT)
        for (x, y) in ((29, 10), (30, 9), (30, 11), (31, 10)):
            p.set(x, y, (200, 230, 250))
    else:
        open_eye(eyes[0], star=form == "sparkly", lid=goth)
        open_eye(eyes[1], star=form == "sparkly", lid=goth)
        if goth:
            eyebags(eyes[0]); eyebags(eyes[1])
        else:
            blush(wide=pose == "spit")
        if pose == "eat":
            for (x, y) in ((19, my), (20, my), (18, my + 1), (21, my + 1), (19, my + 2), (20, my + 2)):
                p.set(x, y, MOUTH)
            p.set(19, my + 1, TONGUE); p.set(20, my + 1, MOUTH)
            for (x, y) in ((13, my + 1), (14, my + 1), (13, my + 2), (14, my + 2), (14, my), (14, my - 1), (15, my - 2)):
                p.set(x, y, NOTE)
            p.word("nom", 27, 2, TEXT)
        elif pose == "spit":
            p.set(22, my, MOUTH); p.set(23, my, MOUTH)
            for (x, y) in ((28, my - 1), (29, my - 1), (28, my), (29, my), (30, my), (31, my - 2), (32, my - 3)):
                p.set(x, y, SPAT)
            p.word("pt", 30, 3, TEXT)
        elif goth:
            p.set(18, my + 2, MOUTH); p.set(19, my + 2, MOUTH); p.set(20, my + 2, MOUTH)    # flat, unimpressed
        elif form == "spiky":
            p.set(eyes[0] - 1, ey - 2, EYE); p.set(eyes[0], ey - 1, EYE)                       # determined brows
            p.set(eyes[1] + 3, ey - 2, EYE); p.set(eyes[1] + 2, ey - 1, EYE)
            smile()
            p.set(21, my + 1, WHITE)                                                           # tiny fang
        else:
            smile()

    for shape in front:                                   # front locks fall over the body's sides
        shade_tube(p, shape, outline)

    if form == "sparkly":
        for (x, y) in ((5, 12), (34, 9), (5, 30), (34, 27)):
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                p.set(x + dx, y + dy, WHITE if (dx, dy) == (0, 0) else (255, 210, 70))
    return p


def sheet(path):
    cells = [("idle", "mint", "idle"), ("eating", "mint", "eat"), ("spits a skip", "mint", "spit"),
             ("MP3 hiccups", "mint", "hiccup"), ("hi-res feast", "mint", "feast"), ("sulking (melted)", "mint", "sulk"),
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
