#!/usr/bin/env python3
"""amuletOS "Pocket" look (owner, 2026-11-11; mockups https://claude.ai/artifact/2jDKSjE2kojxqMMU5mB4Nf):
clean Game Boy Pocket style instead of the v0.1 pixel-art panels. White screen with a faint dot grid whose
dots carry a very light rainbow (a still frame of the mockups' shimmer: stock screens only redraw on change),
2 px ink frames, hard colour shadows, flat 16x16 icons, text in the device's own tall font.

Draws at the native 296x240 (no 2x grid). Boot (000) and shutdown (002) keep the v0.1 art.

  python art/pocket.py OUTDIR [FONT_DIR] [STOCK_PNG_DIR]
"""
import os, sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zeal import Canvas, rgb, mix          # noqa: E402

W, H = 296, 240
INK, WHITE, SCREEN, DOT = "#23252e", "#ffffff", "#fbfbf8", "#e6e7ed"
TRACK, DIM = "#dfe1e8", "#7d8291"
GRAPE, SKY, GOLD, BERRY, BERRY_D, TEAL, KIWI = "#7353e0", "#4b9ae8", "#f4bf2a", "#e2457a", "#a52d5a", "#1fb0a6", "#52b95f"
RAINBOW = ["#ffa3c4", "#ffd57f", "#aef0b9", "#94d4ff", "#c9adff"]
TINT = "#e9e3fb"                                  # pale grape: list selection (stock list text stays dark)

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "build/v029"

# ---------- device font ----------
_f1 = None
def font1():
    global _f1
    if _f1 is None:
        _f1 = (FONT_DIR / "font1.bin").read_bytes()
    return _f1

def adv(ch):
    if ch == " ": return 4
    b = font1()[ord(ch) * 33 + 32]
    return b - 0x80 if b > 0x80 else 8

def textw(s, k=1): return sum(adv(c) for c in s) * k

def text(cv, s, x, y, col, k=1):
    f, c = font1(), rgb(col)
    for ch in s:
        if ch != " ":
            o = ord(ch) * 33
            for r in range(16):
                v = f[o + 2 * r] << 8 | f[o + 2 * r + 1]
                for b in range(16):
                    if v & (0x8000 >> b):
                        cv.rect(x + b * k, y + r * k, k, k, c)
        x += adv(ch) * k
    return x

def text_c(cv, s, y, col, k=1, x0=0, x1=W):
    text(cv, s, x0 + (x1 - x0 - textw(s, k)) // 2, y, col, k)

# ---------- ground, frames ----------
def rainbow(t):
    t = t % 1.0 * len(RAINBOW)
    i = int(t)
    return mix(RAINBOW[i], RAINBOW[(i + 1) % len(RAINBOW)], t - i)

def screen(cv, y0=0, y1=H):
    """white screen with a 2 px dot every 8 px; the dots carry a faint diagonal rainbow"""
    cv.rect(0, y0, W, y1 - y0, SCREEN)
    for y in range(y0 - y0 % 8 + 3, y1, 8):
        for x in range(3, W, 8):
            cv.rect(x, y, 2, 2, mix(DOT, rainbow((x + y) / 220), 0.32))

def corner_inset(r, i):
    """pixels left out at the start of row i (0 = outermost) of a quarter circle of radius r"""
    if r <= 0 or i >= r: return 0
    dy = r - i - 0.5
    return max(0, int(r - (r * r - dy * dy) ** 0.5 + 0.5))

def rrect(cv, x, y, w, h, r, c):
    if r <= 0:
        cv.rect(x, y, w, h, c); return
    for i in range(h):
        k = corner_inset(r, min(i, h - 1 - i))
        cv.rect(x + k, y + i, w - 2 * k, 1, c)

def frame(cv, x, y, w, h, fill=WHITE, shadow=None, r=0):
    """2 px ink outline; r: corner radius (owner build 34: Now Playing outlines rounded like the screen)"""
    if shadow:
        rrect(cv, x + 4, y + 4, w, h, r, shadow)
    rrect(cv, x, y, w, h, r, INK)
    rrect(cv, x + 2, y + 2, w - 4, h - 4, max(0, r - 2), fill)

def status(cv, h=32):
    """plain white status band (stock draws its icons and our counter on it) with a 2 px ink rule"""
    cv.rect(0, 0, W, h, WHITE)
    cv.rect(0, h, W, 2, INK)

# ---------- icons (16x16, from the mockups) ----------
PAL = {"k": INK, "w": WHITE, "p": GRAPE, "b": SKY, "y": GOLD, "r": BERRY, "R": BERRY_D, "t": TEAL, "g": KIWI}
NOW_PLAYING = [
    ".....kkkkkk.....", "...kkppppppkk...", "..kppppppppppk..", ".kppppppppppppk.",
    ".kppppwwppppppk.", "kpppppwwwppppppk", "kpppppwwwwpppppk", "kpppppwwwwwppppk",
    "kpppppwwwwwppppk", "kpppppwwwwpppppk", "kpppppwwwppppppk", ".kppppwwppppppk.",
    ".kppppppppppppk.", "..kppppppppppk..", "...kkppppppkk...", ".....kkkkkk....."]
MUSIC = [   # owner's pick: B, a note on a disc
    ".....kkkkkk.....", "...kkbbbbbbkk...", "..kbbbbbbbbbbk..", ".kbbbbbbbwwbbbk.",
    ".kbbbbbbbwbwbbk.", "kbbbbbbbbwbbwbbk", "kbbbbbbbbwbbwbbk", "kbbbbbbbbwbwbbbk",
    "kbbbbbbbbwbbbbbk", "kbbbbbbbbwbbbbbk", "kbbbbbbyyybbbbbk", ".kbbbbyyyybbbbk.",
    ".kbbbbyyybbbbbk.", "..kbbbbbbbbbbk..", "...kkbbbbbbkk...", ".....kkkkkk....."]
LIBRARY = [
    "................", "...kkkkkkkkkk...", "...kRrrrrrrrk...", "...kRrrrrrrrk...",
    "...kRrwwwwwrk...", "...kRrwkkkwrk...", "...kRrwwwwwrk...", "...kRrrrrrrrk...",
    "...kRrrrrrrrk...", "...kRrrrrrrrk...", "...kRrrrrrrrk...", "...kRrrrrrrrk...",
    "...kRrrrrrrrk...", "...kkwwwwwwwk...", "...kkkkkkkkkk...", "................"]

def _blockz():
    g = [["."] * 16 for _ in range(16)]
    for cx, cy, c in ((2, 1, "p"), (1, 2, "p"), (2, 2, "p"), (3, 2, "p"), (0, 3, "r"), (1, 3, "t"), (2, 3, "t"), (3, 3, "y")):
        for y in range(4):
            for x in range(4):
                edge = x in (0, 3) or y in (0, 3)
                g[cy * 4 + y][cx * 4 + x] = "k" if edge else ("w" if (x, y) == (1, 1) else c)
    return ["".join(r) for r in g]
BLOCKZ = _blockz()

# Games (build 54, owner's pick B of three): a white creature with raised arms on an ink tile, RetroArch in spirit,
# our own drawing
GAMES = [
    "................", ".kkkkkkkkkkkkkk.", ".kwkkwkkkkwkkwk.", ".kwkkkwkkwkkkwk.",
    ".kwkkwwwwwwkkwk.", ".kwwwwwwwwwwwwk.", ".kkwkkwwwwkkwkk.", ".kkwkkwwwwkkwkk.",
    ".kkwwwwwwwwwwkk.", ".kkkwwwwwwwwkkk.", ".kkkwwkkkkwwkkk.", ".kkwwkkkkkkwwkk.",
    ".kwwkkkkkkkkwwk.", ".kkkkkkkkkkkkkk.", ".kkkkkkkkkkkkkk.", "................"]

def grey(c):
    r, g, b = rgb(c)
    v = round(0.3 * r + 0.59 * g + 0.11 * b)
    return (v, v, v)

def icon(cv, rows, x, y, k=1, fade=0.0, off=False):
    """off: greyed out (unavailable item)"""
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch in PAL:
                col = grey(PAL[ch]) if off else PAL[ch]
                cv.rect(x + c * k, y + r * k, k, k, mix(col, WHITE, fade) if fade else col)

# ---------- main menu carousel (menu position -> image 016, 014, 018, 020, 022) ----------
# Build 54: Games after Blockz (owner). There is no spare full-screen image, so Games takes 020 (was the Music card
# with a greyed Now Playing side icon; the Music card now always shows it in colour).
ITEMS = [("Now Playing", NOW_PLAYING, GRAPE), ("Music", MUSIC, SKY), ("Blockz", BLOCKZ, GOLD), ("Games", GAMES, TEAL),
         ("Library", LIBRARY, BERRY)]
STATES = [16, 14, 18, 20, 22]

def chevron(cv, x, y, left):
    for r, w in enumerate((1, 2, 3, 3, 2, 1)):
        for c in range(w):
            cx = (2 - c) if left else c
            cv.rect(x + cx * 2, y + r * 2, 2, 2, INK)

OFF_INK, OFF_ACCENT = "#a9adb8", "#c9ccd6"
GREY_STATES = {0: 8, 4: 24}   # Now Playing greyed (nothing loaded): stock's unused grid image 8, old tile 5

def menu_card(sel, np_off=False):
    """np_off: the Now Playing item is greyed out (player not running; np_helpers.c menu_art picks these)"""
    title, ic, accent = ITEMS[sel]
    n = len(ITEMS)
    off = np_off and sel == 0
    cv = Canvas(W, H)
    screen(cv, 34)
    status(cv)
    # build 54 (owner: menu sat high, room below): card 136 (was 104), icon 7x (was 5x), dots 8 px near the bottom
    CX, CY, CS = (W - 136) // 2, 42, 136
    for d, x in ((-1, 20), (1, W - 20 - 32)):
        j = (sel + d) % n
        icon(cv, ITEMS[j][1], x, CY + CS // 2 - 16, 2, fade=0.72 if np_off and j == 0 else 0.58, off=np_off and j == 0)
    chevron(cv, 62, CY + CS // 2 - 6, True); chevron(cv, W - 62 - 6, CY + CS // 2 - 6, False)
    frame(cv, CX, CY, CS, CS, WHITE, OFF_ACCENT if off else accent)
    icon(cv, ic, CX + 12, CY + 12, 7, fade=0.45 if off else 0.0, off=off)
    text_c(cv, title, 188, OFF_INK if off else INK, 2)
    x0 = (W - (n * 8 + (n - 1) * 8)) // 2
    for k in range(n):
        cv.rect(x0 + k * 16, 226, 8, 8, (OFF_INK if off else accent) if k == sel else "#c9ccd6")
    return cv

# ---------- Now Playing (026) and its cover placeholder (277) ----------
# geometry shared with game/device/npui.c (cover is stock's 116x116 at (17, 46))
R_NP = 8                                               # Now Playing frame corner radius

def now_playing():
    cv = Canvas(W, H)
    screen(cv, 34)
    status(cv)
    frame(cv, 13, 42, 124, 124, WHITE, GRAPE, R_NP)    # cover frame: 2 px ink, 2 px white, cover 17..132 / 46..161
    frame(cv, 146, 42, 138, 124, r=R_NP)               # artist / album: text x 154..278
    frame(cv, 21, 172, 254, 58, r=R_NP)                # title, bar, times: fill x 23..272, y 174..227 (build 34:
    return cv                                          #  in from the screen's round bottom corners)

def default_art():
    cv = Canvas(116, 116)
    for y0, y1, c in ((0, 32, "#23255e"), (32, 52, "#4b3fa8"), (52, 68, GRAPE), (68, 80, "#f07b6c"),
                      (80, 88, "#f6a85b"), (88, 116, TEAL)):
        cv.rect(0, y0, 116, y1 - y0, c)
    cv.rect(66, 48, 32, 32, "#ffd57f")
    cv.rect(0, 88, 116, 4, "#94d4ff"); cv.rect(12, 98, 48, 4, "#aef0b9"); cv.rect(68, 106, 36, 4, "#aef0b9")
    return cv

def strip(w):
    cv = Canvas(w, 16); cv.rect(0, 0, w, 16, WHITE); return cv

# ---------- lists (159 background, 184/185 selection bars), plain background (089) ----------
def list_bg():
    cv = Canvas(W, H)
    status(cv, 33)                                      # stock: header text at 34..59, rows of 23 px from 61
    cv.rect(0, 35, W, 24, "#f2f3f6"); cv.rect(0, 59, W, 2, INK)
    cv.rect(0, 61, W, 160, WHITE)
    for y in (83, 106, 129, 152, 175, 198):
        for x in range(10, 286, 4):
            cv.rect(x, y, 2, 1, TRACK)
    cv.rect(0, 221, W, 2, INK)
    screen(cv, 223)
    return cv

def selection_bar(w):
    cv = Canvas(w, 22)
    cv.rect(0, 0, w, 22, TINT)
    cv.rect(0, 0, 4, 22, GRAPE)
    return cv

def plain_bg():
    cv = Canvas(W, H); screen(cv, 34); status(cv); return cv

# ---------- volume overlay (336 + n) ----------
def volume(n):
    cv = Canvas(W, H)
    screen(cv, 34); status(cv)
    frame(cv, 48, 60, 200, 120, WHITE, GRAPE)
    text_c(cv, "Volume", 70, DIM, 1, 48, 248)
    text_c(cv, str(n), 92, INK, 3, 48, 248)
    bx, by, segs = 68, 152, 20
    for k in range(segs):
        on = n >= (k + 1) * 5
        half = not on and n > k * 5
        cv.rect(bx + k * 8, by, 6, 12, GRAPE if on else TRACK)
        if half: cv.rect(bx + k * 8, by + 6, 6, 6, GRAPE)
    return cv

# ---------- status screens: USB (003), charging (004-007), DAC (017), updating (437) ----------
def card_screen(title, draw=None):
    cv = Canvas(W, H)
    screen(cv)
    frame(cv, 58, 50, 180, 140, WHITE, GRAPE)
    if draw: draw(cv)
    text_c(cv, title, 160, INK, 1, 58, 238)
    return cv

def usb_screen():
    def d(cv):
        cv.rect(98, 92, 40, 20, INK); cv.rect(100, 94, 36, 16, "#c9ccd6")          # plug body
        cv.rect(138, 96, 16, 12, INK); cv.rect(140, 98, 12, 8, WHITE)
        cv.rect(143, 100, 2, 2, INK); cv.rect(147, 100, 2, 2, INK)
        cv.rect(72, 101, 26, 2, INK)                                              # cable
        cv.rect(166, 80, 56, 40, INK); cv.rect(168, 82, 52, 32, SKY)              # screen
        cv.rect(188, 120, 12, 6, INK); cv.rect(180, 126, 28, 2, INK)
    return card_screen("USB", d)

def charging(level):
    def d(cv):
        cv.rect(98, 84, 96, 44, INK); cv.rect(194, 96, 6, 20, INK)
        cv.rect(100, 86, 92, 40, WHITE)
        cols = [BERRY, GOLD, KIWI]
        for k in range(level):
            cv.rect(104 + k * 29, 90, 26, 32, cols[min(level, 3) - 1])
    return card_screen("Charging", d)

def dac_screen():
    return card_screen("DAC", lambda cv: icon(cv, MUSIC, 116, 70, 4))

def updating():
    return card_screen("Updating...", lambda cv: icon(cv, NOW_PLAYING, 116, 70, 4))

# ---------- stock's small icons on dark tiles (list rows etc.): glyph kept, tile made light ----------
def lighten_icon(a, n):
    """a: stock RGB array whose corner pixel is the dark tile colour. Glyph = pixels away from it."""
    a = a.astype(float)
    bg = a[0, 0]
    d = np.sqrt(((a - bg) ** 2).sum(2))
    alpha = np.clip(d / max(d.max(), 1), 0, 1)
    glyph = a[alpha > 0.6].mean(0) if (alpha > 0.6).any() else np.array([255, 255, 255.])
    r, g, b = glyph
    if 237 <= n <= 246 or (r > g + 40 and r > b + 40):           # orange set / warm: selected or playing
        col, tile = rgb(GRAPE), rgb(TINT)
    elif b > r + 40:                                              # blue set
        col, tile = rgb(SKY), rgb(WHITE)
    else:                                                         # white / grey glyphs
        col, tile = rgb(INK), rgb(WHITE)
    out = np.array(tile, float)[None, None, :] * (1 - alpha[..., None]) + np.array(col, float)[None, None, :] * alpha[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)

# ---------- Music menu row icons (mockup MusicList: 8x8 glyphs, 2x, one colour per item) ----------
LIST_GLYPHS = {   # stock id (normal set; +10 = the highlighted set): glyph, colour
    227: (["kk......", "kkkk....", "kkkkkk..", "kkkkkkkk", "kkkkkkkk", "kkkkkk..", "kkkk....", "kk......"], GRAPE),  # Now playing
    228: (["....kk..", "....kkk.", "....k.kk", "....k..k", "....k...", ".kkkk...", "kkkkk...", ".kkk...."], SKY),    # All Music
    229: (["..kkkk..", "..kkkk..", "..kkkk..", "...kk...", ".kkkkkk.", "kkkkkkkk", "kkkkkkkk", "kkkkkkkk"], BERRY),  # Artist
    230: (["..kkkk..", ".kkkkkk.", "kkk..kkk", "kk.kk.kk", "kk.kk.kk", "kkk..kkk", ".kkkkkk.", "..kkkk.."], TEAL),   # Album
    231: (["kkkk....", "kkkkk...", "kk.kkk..", "kkkkkkk.", ".kkkkkkk", "..kkkkk.", "...kkk..", "....k..."], "#d99a10"),  # Genre
    232: (["kkk.....", "kkkkkkkk", "k......k", "k......k", "k......k", "k......k", "kkkkkkkk", "........"], KIWI),   # Directory
    234: ([".kk..kk.", "kkkkkkkk", "kkkkkkkk", "kkkkkkkk", ".kkkkkk.", "..kkkk..", "...kk...", "........"], BERRY),  # Favorites
    235: (["..kkkkk.", ".k....kk", "k....kkk", "k.......", ".......k", "kkk....k", "kk....k.", ".kkkkk.."], INK),    # Update
    236: (["kk.kkkkk", "kk.kkkkk", "........", "kk.kkkkk", "kk.kkkkk", "........", "kk.kkk..", "kk.kkk.."], GRAPE),  # Playlists
}

def list_icons():
    """24x24 row icons: glyph in the item colour on white, and on the selection tint for the highlighted set"""
    out = {}
    for n, (rows, col) in LIST_GLYPHS.items():
        for m, tile in ((n, WHITE), (n + 10, TINT)):
            cv = Canvas(24, 24); cv.rect(0, 0, 24, 24, tile)
            for r, row in enumerate(rows):
                for c, ch in enumerate(row):
                    if ch == "k": cv.rect(4 + c * 2, 4 + r * 2, 2, 2, col)
            out[m] = cv
    rows = LIST_GLYPHS[232][0]                             # blue set folder (stock's is a filled tile)
    cv = Canvas(24, 24); cv.rect(0, 0, 24, 24, WHITE)
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "k": cv.rect(4 + c * 2, 4 + r * 2, 2, 2, SKY)
    out[222] = cv
    return out

def dark_icons(stock):
    """small stock images (<= 40 px) drawn on a dark tile, except pure-black colour keys"""
    for f in sorted(os.listdir(stock)):
        if not (f.endswith(".png") and f[:3].isdigit()): continue
        n = int(f[:3])
        a = np.asarray(Image.open(os.path.join(stock, f)).convert("RGB"))
        h, w, _ = a.shape
        if w <= 40 and h <= 40 and a.mean() < 90 and tuple(a[0, 0]) != (0, 0, 0):
            yield n, lighten_icon(a, n)

def main():
    global FONT_DIR
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/art_pocket")
    if len(sys.argv) > 2: FONT_DIR = Path(sys.argv[2])
    stock = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "build/img_stock"
    out.mkdir(parents=True, exist_ok=True)
    save = lambda cv, i: cv.image(1).save(out / f"{i:03d}.png")
    for sel, idx in enumerate(STATES):
        save(menu_card(sel), idx)
    for sel, idx in GREY_STATES.items():                  # 8 unused by stock; 20 / 24 = old tiles 4 / 5
        save(menu_card(sel, np_off=True), idx)
    save(now_playing(), 26); save(default_art(), 277)
    save(strip(128), 69); save(strip(296), 28)
    save(list_bg(), 159); save(selection_bar(296), 184); save(selection_bar(255), 185); save(plain_bg(), 89)
    for n in range(101):
        save(volume(n), 336 + n)
    save(usb_screen(), 3)
    for lv, i in enumerate((4, 5, 6, 7)):
        save(charging(lv), i)
    save(dac_screen(), 17); save(updating(), 437)
    for n, cv in list_icons().items():                     # Music menu rows (mockup MusicList)
        save(cv, n)
    k = 0
    for n, a in dark_icons(stock):
        if not (out / f"{n:03d}.png").exists():
            Image.fromarray(a).save(out / f"{n:03d}.png"); k += 1
    print(f"wrote Pocket screens and {k} light icons to", out)

if __name__ == "__main__":
    main()
