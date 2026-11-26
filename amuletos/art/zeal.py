"""amuletOS pixel-art helpers: Zeal palettes, original 5x7 font, 148x120 canvas.

Ported from the design mockups (claude.ai artifact "AP30 Screen Mockups").
Everything is drawn on the native 148x120 grid and scaled 2x to 296x240.
"""
import math
import numpy as np
from PIL import Image

W, H = 148, 120

THEMES = {
    "zeal": dict(bg1="#acd2f4", bg2="#8fbaec", panel="#fffdf6", shade="#e4eaf2", border="#283c88",
                 text="#121a40", accent="#d9a02a", dim="#6a7cb0", well="#121838",
                 lav="#c6b2f4", lavInk="#7d5bc9"),
}

# Original 5x7 glyphs, rows top to bottom, bit 4 = left column.
F = {"A":[14,17,17,31,17,17,17],"B":[30,17,17,30,17,17,30],"C":[14,17,16,16,16,17,14],"D":[30,17,17,17,17,17,30],
     "E":[31,16,16,30,16,16,31],"F":[31,16,16,30,16,16,16],"G":[14,17,16,23,17,17,15],"H":[17,17,17,31,17,17,17],
     "I":[14,4,4,4,4,4,14],"J":[7,2,2,2,2,18,12],"K":[17,18,20,24,20,18,17],"L":[16,16,16,16,16,16,31],
     "M":[17,27,21,21,17,17,17],"N":[17,17,25,21,19,17,17],"O":[14,17,17,17,17,17,14],"P":[30,17,17,30,16,16,16],
     "Q":[14,17,17,17,21,18,13],"R":[30,17,17,30,20,18,17],"S":[15,16,16,14,1,1,30],"T":[31,4,4,4,4,4,4],
     "U":[17,17,17,17,17,17,14],"V":[17,17,17,17,17,10,4],"W":[17,17,17,21,21,21,10],"X":[17,17,10,4,10,17,17],
     "Y":[17,17,10,4,4,4,4],"Z":[31,1,2,4,8,16,31],
     "0":[14,17,19,21,25,17,14],"1":[4,12,4,4,4,4,14],"2":[14,17,1,2,4,8,31],"3":[31,2,4,2,1,17,14],
     "4":[2,6,10,18,31,2,2],"5":[31,16,30,1,1,17,14],"6":[6,8,16,30,17,17,14],"7":[31,1,2,4,8,8,8],
     "8":[14,17,17,14,17,17,14],"9":[14,17,17,15,1,2,12],
     " ":[0]*7,".":[0,0,0,0,0,12,12],":":[0,12,12,0,12,12,0],"/":[1,1,2,4,8,16,16],"-":[0,0,0,14,0,0,0],
     "%":[24,25,2,4,8,19,3],"'":[4,4,8,0,0,0,0],"!":[4,4,4,4,4,0,4],"?":[14,17,1,2,4,0,4],
     "+":[0,4,4,31,4,4,0],",":[0,0,0,0,12,4,8]}

def rgb(c):
    if isinstance(c, tuple): return c
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))

def mix(a, b, k):
    a, b = rgb(a), rgb(b)
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))

class Canvas:
    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.px = np.zeros((h, w, 3), np.uint8)

    def rect(self, x, y, w, h, c):
        x, y, w, h = int(x), int(y), int(w), int(h)
        x0, y0, x1, y1 = max(0, x), max(0, y), min(self.w, x + w), min(self.h, y + h)
        if x1 > x0 and y1 > y0:
            self.px[y0:y1, x0:x1] = rgb(c)

    def glyph(self, g, x, y, c, s=1):
        for r in range(7):
            for col in range(5):
                if g[r] & (16 >> col):
                    self.rect(x + col * s, y + r * s, s, s, c)

    def text(self, s, x, y, c, scale=1, keep_case=False):
        """keep_case: draw the lowercase glyphs in FL where there is one (else the capital); default all caps"""
        for ch in (s if keep_case else s.upper()):
            self.glyph(FL.get(ch) or F.get(ch.upper(), F["?"]), x, y, c, scale)
            x += 6 * scale
        return x

    def image(self, scale=2):
        im = Image.fromarray(self.px)
        return im.resize((self.w * scale, self.h * scale), Image.NEAREST) if scale != 1 else im

# lowercase 5x7 glyphs (x-height 5 rows), only the ones the OS name needs ("amuletOS", owner 2026-11-11)
FL = {"a": [0, 0, 14, 1, 15, 17, 15], "m": [0, 0, 26, 21, 21, 21, 21], "u": [0, 0, 17, 17, 17, 19, 13],
      "l": [12, 4, 4, 4, 4, 4, 14], "e": [0, 0, 14, 17, 31, 16, 14], "t": [8, 8, 28, 8, 8, 9, 6]}

def tw(s, scale=1):
    return len(s) * 6 * scale - scale
