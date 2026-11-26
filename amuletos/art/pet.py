#!/usr/bin/env python3
"""Song pet mock-ups: an original gumdrop creature with a speaker-grille mouth and music-note antennae.

Drawn procedurally at 32x32 so diet can reshape the body (spiky / round / sparkly / gothy), not just recolour it.

  python art/pet.py OUT.png      contact sheet of poses and diet forms (scaled 5x)
"""
import sys
from PIL import Image, ImageDraw

S = 32
INK, WHITE = (35, 37, 46), (255, 255, 255)
BODY = {"teal": ((31, 176, 166), (20, 128, 121), (160, 232, 226)),
        "sleepy": ((120, 168, 232), (84, 120, 184), (200, 222, 250)),
        "sparkly": ((244, 191, 42), (196, 140, 20), (255, 236, 160)),
        "goth": ((92, 60, 130), (58, 36, 86), (150, 120, 190)),
        "spiky": ((226, 69, 122), (165, 45, 90), (250, 170, 200))}
GRILLE = (60, 64, 78)

# 3x5 pixel glyphs for tiny in-sprite words
GLYPH = {"h": ["1.0", "1..", "111", "1.1", "1.1"], "i": ["1", ".", "1", "1", "1"], "c": ["...", "111", "1..", "1..", "111"],
         "!": ["1", "1", "1", ".", "1"], "z": ["111", "..1", ".1.", "1..", "111"], "Z": ["1111", "...1", "..1.", ".1..", "1111"],
         ".": [".", ".", ".", ".", "1"], "n": ["...", "11.", "1.1", "1.1", "1.1"], "o": ["...", ".1.", "1.1", "1.1", ".1."],
         "m": [".....", "11.1.", "1.1.1", "1.1.1", "1.1.1"], "f": [".11", "1..", "11.", "1..", "1.."], "e": ["...", "11.", "111", "1..", ".11"]}
GLYPH["h"] = ["1..", "1..", "111", "1.1", "1.1"]
GLYPH["p"] = ["...", "11.", "1.1", "11.", "1.."]
GLYPH["t"] = [".1.", "111", ".1.", ".1.", ".11"]


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


def body_mask(cx=16, cy=20, a=11.0, b=9.0, squash=0.0, spikes=False):
    """gumdrop: an ellipse that narrows towards the top; squash widens and flattens"""
    a, b = a * (1 + squash), b * (1 - squash * 0.6)
    m = set()
    for y in range(S):
        for x in range(S):
            dy = (y + 0.5 - cy) / b
            f = min(max((dy + 1) / 2, 0), 1)                 # 0 top .. 1 bottom
            ax = a * (0.72 + 0.28 * f ** 0.6)
            dx = (x + 0.5 - cx) / ax
            if dx * dx + dy * dy <= 1 and y < cy + b * 0.85:   # flat bottom
                m.add((x, y))
    if spikes:
        top = min(y for _, y in m)
        for sx in (9, 13, 17, 21):                            # spikes along the top and sides
            for k in range(4):
                for j in range(-(3 - k) // 2, (3 - k) // 2 + 1):
                    m.add((sx + j, top - k + 1))
        for side, sx in ((-1, cx - int(a * (1 + squash)) + 1), (1, cx + int(a * (1 + squash)) - 2)):
            for sy in (cy - 3, cy + 2):
                for k in range(3):
                    for j in range(-(2 - k) // 2, (2 - k) // 2 + 1):
                        m.add((sx + side * (k + 1), sy + j))
    return m


def creature(form="teal", pose="idle"):
    p = Pix()
    squash = {"sleepy": 0.25}.get(form, 0.0)
    if pose == "sulk":
        squash = 0.55
    cy = 21 if pose != "sulk" else 25
    m = body_mask(cy=cy, squash=squash, spikes=(form == "spiky"))
    fill, shade, light = BODY[form]
    top = min(y for _, y in m)
    for (x, y) in m:
        edge = any((x + dx, y + dy) not in m for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if edge:
            p.set(x, y, INK)
        elif (x + 1, y + 1) not in m or (x, y + 2) not in m:
            p.set(x, y, shade)
        else:
            p.set(x, y, fill)
    for (x, y) in ((11, top + 3), (12, top + 3), (11, top + 4)):   # shine
        if (x, y) in m and p.get(x, y) != INK:
            p.set(x, y, light)

    # antennae: eighth notes (stem + head + flag); droop when sulking or goth
    if pose != "sulk":
        droop = form == "goth"
        for sx, flip in ((12, -1), (20, 1)):
            lean = (lambda k: flip * (k // 2)) if droop else (lambda k: 0)
            for k in range(1, 5):                            # stem
                p.set(sx + lean(k), top - k, INK)
            hx, hy = sx + lean(5), top - 6                   # round note head (3x3 minus corners)
            for dx, dy in ((0, -1), (-1, 0), (0, 0), (1, 0), (0, 1), (-1, 1), (1, -1)):
                p.set(hx + dx - 1, hy + dy + 1, INK)
            p.set(sx + lean(4) + 1, top - 4, INK)            # flag
            p.set(sx + lean(3) + 2, top - 3, INK)

    ey = top + 6 if pose != "sulk" else cy - 1
    if pose == "sulk":                                       # face-down: no face, just a tiny "..."
        p.word("...", 14, cy - 12, INK)
        return p
    # eyes
    for ex in (12, 19):
        if form == "sleepy" or pose in ("feast",):
            for k in range(3):
                p.set(ex - 1 + k, ey + 1, INK)               # closed / blissful
            if pose == "feast":                            # blissful ^ ^
                p.set(ex - 1, ey + 1, None); p.set(ex + 1, ey + 1, None)
                p.set(ex - 1, ey + 1, INK); p.set(ex, ey, INK); p.set(ex + 1, ey + 1, INK)
                p.set(ex, ey + 1, p.get(ex - 2, ey + 1))
        elif pose == "hiccup":
            p.set(ex - 1, ey, INK); p.set(ex, ey + 1, INK); p.set(ex + 1, ey, INK)   # squeezed > <
        else:
            for dy in range(3):
                p.set(ex, ey + dy, INK); p.set(ex + 1, ey + dy, INK)
            p.set(ex + 1, ey, WHITE)
            if form == "goth":                               # heavy lids
                p.set(ex - 1, ey - 1, INK); p.set(ex, ey - 1, INK); p.set(ex + 1, ey - 1, INK); p.set(ex + 2, ey - 1, INK)
    # mouth: speaker grille; open wider when eating / spitting
    mh = {"eat": 4, "spit": 4, "feast": 2}.get(pose, 2)
    my = ey + 5
    for x in range(11, 22):
        for y in range(my, my + mh + 2):
            if x in (11, 21) or y in (my, my + mh + 1):
                p.set(x, y, INK)
            else:
                p.set(x, y, GRILLE if x % 2 else INK)
    if pose == "eat":                                        # a little note going in
        for (x, y) in ((6, my + 1), (7, my + 1), (6, my + 2), (7, my + 2), (7, my - 1), (7, my), (8, my - 2)):
            p.set(x, y, (115, 83, 224))
        p.word("nom", 18, 1, INK)
    if pose == "spit":                                       # a grey rejected-song blob flying out
        for (x, y) in ((25, my + 1), (26, my + 1), (27, my + 2), (26, my + 2), (25, my + 2), (28, my), (29, my - 1)):
            p.set(x, y, (150, 154, 166))
        p.word("pt", 23, 2, INK)
    if pose == "hiccup":
        p.word("hic!", 18, 1, INK)
    if form == "sleepy" and pose == "idle":
        p.word("zZ", 22, 3, INK)
    if form == "sparkly":
        for (x, y) in ((4, 9), (27, 12), (5, 24), (26, 27)):
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                p.set(x + dx, y + dy, (255, 214, 60) if (dx, dy) != (0, 0) else WHITE)
    if form == "goth":                                       # tiny bow
        for (x, y) in ((20, top + 1), (21, top + 2), (22, top + 1), (21, top + 1), (20, top + 2), (22, top + 2)):
            p.set(x, y, INK)
    return p


def sheet(path):
    cells = [("idle", "teal", "idle"), ("eating", "teal", "eat"), ("spits a skip", "teal", "spit"),
             ("MP3 hiccups", "teal", "hiccup"), ("hi-res feast", "teal", "feast"), ("sulking", "teal", "sulk"),
             ("intense diet", "spiky", "idle"), ("calm diet", "sleepy", "idle"), ("bright diet", "sparkly", "idle"),
             ("dark diet", "goth", "idle")]
    k, cw, ch, cols = 5, 32 * 5 + 24, 32 * 5 + 40, 5
    bg = (251, 251, 248)
    im = Image.new("RGB", (cols * cw, ((len(cells) + cols - 1) // cols) * ch), bg)
    d = ImageDraw.Draw(im)
    for i, (label, form, pose) in enumerate(cells):
        x, y = (i % cols) * cw + 12, (i // cols) * ch + 8
        im.paste(creature(form, pose).image(k, bg), (x, y))
        d.text((x + 4, y + 32 * k + 6), label, fill=INK)
    im.save(path)


if __name__ == "__main__":
    sheet(sys.argv[1] if len(sys.argv) > 1 else "pet_sheet.png")
