"""Original 24x24 amuletOS menu icons, built from shapes with an automatic outline.

Two sets: "classic" (Game Boy Color style symbols) and "relic" (Zeal artefacts).
Each icon: a dict of named colour layers painted in order, then a 1 px outline.
"""
import math
import numpy as np
from zeal import rgb, mix

N = 24

class Sprite:
    def __init__(self):
        self.c = np.zeros((N, N, 3), np.uint8)
        self.m = np.zeros((N, N), bool)

    def put(self, x, y, col):
        if 0 <= x < N and 0 <= y < N:
            self.c[y, x] = rgb(col); self.m[y, x] = True

    def rect(self, x, y, w, h, col):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, col)

    def ellipse(self, cx, cy, rx, ry, col):
        for yy in range(N):
            for xx in range(N):
                if ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0:
                    self.put(xx, yy, col)

    def ring(self, cx, cy, r0, r1, col):
        for yy in range(N):
            for xx in range(N):
                d = math.hypot(xx - cx, yy - cy)
                if r0 <= d <= r1:
                    self.put(xx, yy, col)

    def line(self, x0, y0, x1, y1, col, w=1):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for k in range(n + 1):
            x = round(x0 + (x1 - x0) * k / n); y = round(y0 + (y1 - y0) * k / n)
            self.rect(x, y, w, w, col)

    def poly(self, pts, col):
        for yy in range(N):
            for xx in range(N):
                px, py = xx + 0.5, yy + 0.5
                inside = False
                for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
                    if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
                        inside = not inside
                if inside:
                    self.put(xx, yy, col)

    def clear(self, x, y, w=1, h=1):
        self.m[y:y + h, x:x + w] = False

    def outlined(self, ink):
        o = self.m.copy()
        grow = np.zeros_like(o)
        grow[1:, :] |= o[:-1, :]; grow[:-1, :] |= o[1:, :]; grow[:, 1:] |= o[:, :-1]; grow[:, :-1] |= o[:, 1:]
        edge = grow & ~o
        c = self.c.copy(); c[edge] = rgb(ink)
        return c, (o | edge)

# palette pieces shared by both sets
GOLD, GOLD_HI, GOLD_LO = "#e8b23a", "#fbe08a", "#a8701c"
LAV, LAV_HI, LAV_LO = "#b9a0f0", "#e6dcff", "#7d5bc9"
SKY, SKY_HI, SKY_LO = "#68a8ec", "#bfe0ff", "#3a68b8"
ROSE, ROSE_HI = "#e8607a", "#ffb0bc"
LEAF = "#58b868"
STEEL, STEEL_HI, STEEL_LO = "#9aa8c8", "#dfe6f4", "#5d6a90"
WOOD, WOOD_LO = "#b07040", "#7a4a28"
WHITE = "#fffdf6"

def bevel_block(s, x, y, col, hi, lo, n=5):
    s.rect(x, y, n, n, lo); s.rect(x, y, n - 1, n - 1, hi); s.rect(x + 1, y + 1, n - 2, n - 2, col)

# ---------------- classic set ----------------
def c_music():
    s = Sprite()
    s.poly([(8, 4), (19, 2), (19, 6), (8, 8)], GOLD)          # beam
    s.rect(8, 6, 2, 12, GOLD); s.rect(17, 4, 2, 12, GOLD)      # stems
    s.ellipse(6.5, 18.5, 3.2, 2.4, LAV); s.ellipse(15.5, 16.5, 3.2, 2.4, LAV)
    s.put(5, 17, LAV_HI); s.put(14, 15, LAV_HI); s.put(9, 4, GOLD_HI); s.put(10, 4, GOLD_HI)
    return s

def c_games():
    s = Sprite()
    for x, y in [(3, 9), (8, 9), (13, 9), (8, 14)]:            # T piece
        bevel_block(s, x, y, LAV, LAV_HI, LAV_LO)
    for x, y in [(13, 14), (18, 14), (13, 19), (18, 19)]:      # O piece
        bevel_block(s, x, y, GOLD, GOLD_HI, GOLD_LO)
    for x, y in [(15, 2), (15, 7 - 5)]:
        pass
    bevel_block(s, 18, 4, SKY, SKY_HI, SKY_LO); bevel_block(s, 18, 9, SKY, SKY_HI, SKY_LO)
    return s

def c_library():
    s = Sprite()
    s.rect(3, 15, 18, 5, SKY); s.rect(3, 15, 18, 1, SKY_HI); s.rect(18, 16, 3, 3, WHITE)   # bottom book
    s.rect(5, 10, 16, 5, LAV); s.rect(5, 10, 16, 1, LAV_HI); s.rect(17, 11, 3, 3, WHITE)   # middle
    s.rect(4, 5, 15, 5, ROSE); s.rect(4, 5, 15, 1, ROSE_HI); s.rect(15, 6, 3, 3, WHITE)    # top
    s.rect(7, 5, 1, 5, GOLD); s.rect(8, 10, 1, 5, GOLD); s.rect(6, 15, 1, 5, GOLD)          # spine bands
    return s

def c_folders():
    s = Sprite()
    s.rect(2, 6, 8, 3, GOLD_LO)                                 # tab
    s.rect(2, 8, 20, 13, GOLD_LO)                               # back
    s.poly([(4, 11), (23, 11), (21, 21), (2, 21)], GOLD)        # front flap
    s.rect(5, 12, 16, 1, GOLD_HI)
    s.rect(13, 13, 2, 5, LAV_LO); s.ellipse(12, 18, 2, 1.5, LAV_LO); s.rect(14, 13, 3, 1, LAV_LO)  # note
    return s

def c_bluetooth():
    s = Sprite()
    s.ellipse(11.5, 11.5, 9.5, 10, SKY)
    s.ellipse(9, 7, 3, 2, SKY_HI)
    ink = WHITE
    s.line(11, 4, 11, 19, ink, 2)
    s.line(12, 4, 16, 8, ink, 2); s.line(16, 8, 7, 15, ink, 2)
    s.line(12, 19, 16, 15, ink, 2); s.line(16, 15, 7, 8, ink, 2)
    return s

def c_settings():
    s = Sprite()
    cx = cy = 11.5
    for k in range(8):
        a = k * math.pi / 4
        s.rect(round(cx + 8.2 * math.cos(a) - 1.5), round(cy + 8.2 * math.sin(a) - 1.5), 3, 3, STEEL)
    s.ellipse(cx, cy, 7.5, 7.5, STEEL); s.ellipse(cx - 1, cy - 1, 5.5, 5.5, STEEL_HI); s.ellipse(cx, cy, 5.5, 5.5, STEEL)
    s.ellipse(cx, cy, 3, 3, GOLD); s.put(10, 10, GOLD_HI)
    return s

# ---------------- relic set ----------------
def r_music():   # golden lyre
    s = Sprite()
    s.line(5, 3, 5, 14, GOLD, 2); s.line(18, 3, 18, 14, GOLD, 2)
    s.ellipse(11.5, 15.5, 7.5, 5.5, GOLD); s.ellipse(11.5, 14.5, 5, 3.5, LAV_LO)
    s.rect(4, 3, 16, 2, GOLD_HI)
    for x in (9, 11, 13, 15): s.rect(x, 5, 1, 9, WHITE)
    s.rect(9, 19, 6, 2, GOLD_LO); s.put(4, 2, GOLD_HI); s.put(19, 2, GOLD_HI)
    return s

def r_games():   # crystal block stack
    s = Sprite()
    for x, y, c in [(3, 14, (SKY, SKY_HI, SKY_LO)), (8, 14, (SKY, SKY_HI, SKY_LO)), (13, 14, (LAV, LAV_HI, LAV_LO)),
                    (18, 14, (LAV, LAV_HI, LAV_LO)), (8, 9, (GOLD, GOLD_HI, GOLD_LO)), (13, 9, (LAV, LAV_HI, LAV_LO)),
                    (13, 4, (GOLD, GOLD_HI, GOLD_LO)), (3, 19, (ROSE, ROSE_HI, "#a83a50")), (8, 19, (SKY, SKY_HI, SKY_LO)),
                    (13, 19, (SKY, SKY_HI, SKY_LO)), (18, 19, (GOLD, GOLD_HI, GOLD_LO))]:
        bevel_block(s, x, y, *c)
    return s

def r_library():  # open tome
    s = Sprite()
    s.poly([(1, 7), (11, 9), (11, 21), (1, 18)], LAV_LO); s.poly([(22, 7), (12, 9), (12, 21), (22, 18)], LAV_LO)
    s.poly([(2, 6), (11, 8), (11, 19), (2, 16)], WHITE); s.poly([(21, 6), (12, 8), (12, 19), (21, 16)], WHITE)
    for k in range(3):
        s.line(4, 10 + 2 * k, 9, 11 + 2 * k, STEEL); s.line(14, 11 + 2 * k, 19, 10 + 2 * k, STEEL)
    s.rect(11, 6, 2, 15, GOLD); s.put(11, 4, LAV); s.put(12, 3, LAV_HI)
    return s

def r_folders():  # treasure chest
    s = Sprite()
    s.rect(3, 11, 18, 10, WOOD); s.poly([(3, 11), (5, 5), (19, 5), (21, 11)], WOOD_LO)
    s.rect(3, 10, 18, 2, GOLD); s.rect(3, 19, 18, 2, GOLD_LO)
    s.rect(6, 5, 2, 16, GOLD); s.rect(16, 5, 2, 16, GOLD)
    s.rect(10, 11, 4, 4, GOLD_HI); s.rect(11, 13, 2, 2, GOLD_LO)
    s.put(7, 6, GOLD_HI); s.put(17, 6, GOLD_HI)
    return s

def r_bluetooth():  # floating crystal with rune
    s = Sprite()
    s.poly([(12, 1), (19, 9), (12, 20), (5, 9)], LAV)
    s.poly([(12, 1), (12, 20), (5, 9)], LAV_HI)
    s.poly([(12, 3), (15, 9), (12, 17)], LAV_LO)
    s.line(11, 6, 11, 14, WHITE); s.line(11, 6, 13, 8, WHITE); s.line(13, 8, 10, 11, WHITE)
    s.line(11, 14, 13, 12, WHITE); s.line(13, 12, 10, 9, WHITE)
    s.ellipse(12, 22, 4, 1, SKY)
    return s

def r_settings():  # cog with red gem
    s = c_settings()
    s.ellipse(11.5, 11.5, 3.2, 3.2, ROSE); s.put(10, 10, ROSE_HI); s.put(11, 10, WHITE)
    s.ring(11.5, 11.5, 3.3, 4.2, GOLD)
    return s

def r_notes():  # two beamed eighth notes (v0.3 Music option A)
    s = Sprite()
    s.poly([(7, 4), (21, 1), (21, 5), (7, 8)], GOLD); s.line(7, 5, 20, 2, GOLD_HI)
    s.rect(7, 6, 2, 13, GOLD_LO); s.rect(19, 3, 2, 13, GOLD_LO)
    s.ellipse(5.5, 18.5, 3.6, 2.8, LAV); s.ellipse(17.5, 15.5, 3.6, 2.8, LAV)
    s.put(4, 17, LAV_HI); s.put(16, 14, LAV_HI)
    return s

def r_note_disc():  # single eighth note on a sky disc (v0.3 Music option B)
    s = Sprite()
    s.ellipse(11.5, 11.5, 10.5, 10.5, SKY_LO); s.ellipse(11.5, 11.5, 9.5, 9.5, SKY); s.ellipse(9.5, 8.5, 4, 3, SKY_HI)
    s.rect(12, 4, 2, 12, WHITE); s.poly([(13, 4), (18, 8), (18, 11), (13, 7)], WHITE)
    s.ellipse(10.5, 16.5, 3.4, 2.6, GOLD); s.put(9, 15, GOLD_HI)
    return s

def r_headphones():  # headphones (v0.3 Music option C)
    s = Sprite()
    s.ring(11.5, 12, 8, 10, STEEL); s.clear(0, 12, 24, 12)
    s.ring(11.5, 12, 9, 9.6, STEEL_HI); s.clear(0, 12, 24, 12)
    s.rect(1, 12, 6, 9, LAV_LO); s.rect(2, 13, 4, 7, LAV); s.put(3, 14, LAV_HI)
    s.rect(17, 12, 6, 9, LAV_LO); s.rect(18, 13, 4, 7, LAV); s.put(19, 14, LAV_HI)
    return s

def r_nowplaying():  # golden disc with a play mark (v0.3 carousel)
    s = Sprite()
    s.ellipse(11.5, 11.5, 10.5, 10.5, GOLD_LO); s.ellipse(11.5, 11.5, 9.5, 9.5, GOLD)
    s.ellipse(11.5, 11.5, 7.5, 7.5, LAV_LO); s.ellipse(10.5, 10.5, 6, 6, LAV)
    s.poly([(9, 7), (17, 12), (9, 17)], WHITE)
    s.put(5, 5, GOLD_HI); s.put(6, 4, GOLD_HI); s.put(4, 6, GOLD_HI)
    return s

SETS = {
    "classic": [c_music, c_games, c_library, c_folders, c_bluetooth, c_settings],
    "relic": [r_music, r_games, r_library, r_folders, r_bluetooth, r_settings],
}
LABELS = ["Music", "Games", "Library", "Folders", "BT", "Setup"]   # <= 7 chars fit a tile
