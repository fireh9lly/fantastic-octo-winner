#!/usr/bin/env python3
"""v0.1 reskin screens: volume overlay, list and blank backgrounds, Now Playing,
default album art, USB / charging / DAC / updating screens.

Rule: stock draws dark text on top of these at run time, so every area where text
can appear stays light (cream panel); Zeal colour lives in frames, margins and
the status strip line. Drawn on the 148x120 grid, scaled 2x, except where a stock
image is not 2x-aligned (drawn at 1x then).

  python art/screens.py OUTDIR
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zeal import Canvas, THEMES, W, H, mix, tw, rgb
from icons import Sprite, N, LAV, LAV_HI, LAV_LO, GOLD, GOLD_HI, GOLD_LO, SKY, SKY_HI, SKY_LO, WHITE, STEEL
from main_menu import diamond_bg, panel, blit_icon, T as T_LIB
import boot_splash

T_SKY = THEMES["zeal"]                       # Now Playing / volume: sky blue

def status_strip(cv, t):
    cv.rect(0, 0, W, 16, t["panel"]); cv.rect(0, 16, W, 1, t["border"])

def soft_diamond(cv, t, y0, y1, a, b):
    """Low-contrast diamond so text stays readable on it."""
    for y in range(y0, y1):
        for x in range(W):
            tx, ty = x & 7, y & 7
            m = abs(tx - 3.5) + abs(ty - 3.5)
            cv.rect(x, y, 1, 1, b if m <= 1.5 else a)

# ---------- volume overlay: 336 + n, n = 0..100 ----------
def volume(n, t=T_SKY):
    cv = Canvas()
    status_strip(cv, t)
    diamond_bg(cv, t, 17)
    px, py, pw, ph = 22, 30, 104, 70
    panel(cv, px, py, pw, ph, t, False)
    cv.text("Volume", px + (pw - tw("Volume") + 1) // 2, py + 8, t["dim"])
    s = str(n)
    cv.text(s, px + (pw - tw(s, 3) + 1) // 2, py + 20, t["text"], 3)
    # 20 segments, one per 5 steps; partial segment shown as half height
    bx, by = px + 11, py + 48
    cv.rect(bx - 2, by - 2, 20 * 4 + 3, 10, t["border"])
    cv.rect(bx - 1, by - 1, 20 * 4 + 1, 8, t["shade"])
    full, part = divmod(n, 5)
    for k in range(20):
        x = bx + k * 4
        if k < full:
            cv.rect(x, by, 3, 6, t["accent"]); cv.rect(x, by, 3, 1, GOLD_HI)
        elif k == full and part:
            cv.rect(x, by + 3, 3, 3, t["lavInk"])
    cv.text("-", px + 4, by, t["border"]); cv.text("+", px + pw - 9, by, t["border"])
    return cv

# ---------- list background (159) and plain background (089) ----------
def list_bg(t=T_LIB):
    cv = Canvas(296, 240)      # 1x: rows are 23 px, not 2x-aligned
    cv.rect(0, 0, 296, 33, t["panel"]); cv.rect(0, 33, 296, 1, t["border"])
    cv.rect(0, 34, 296, 27, t["shade"]); cv.rect(0, 59, 296, 2, t["border"])          # header band
    for y in range(61, 222):
        cv.rect(0, y, 296, 1, t["panel"])
    for y in (83, 106, 129, 152, 175, 198):
        for x in range(8, 288, 4):
            cv.rect(x, y, 2, 1, t["shade"])                                               # dotted row rules
    cv.rect(0, 221, 296, 2, t["border"]); cv.rect(0, 223, 296, 17, t["shade"])         # footer band
    for x in range(0, 296, 8):                                                           # gold studs on bands
        cv.rect(x + 3, 36, 2, 2, mix(t["shade"], t["accent"], 0.5))
        cv.rect(x + 3, 236, 2, 2, mix(t["shade"], t["accent"], 0.5))
    return cv

def highlight_bar(w, t=T_LIB):
    cv = Canvas(w, 22)
    cv.rect(0, 0, w, 22, mix(t["panel"], t["lav"], 0.35))
    cv.rect(0, 0, w, 1, t["accent"]); cv.rect(0, 21, w, 1, t["accent"])
    cv.rect(0, 1, w, 1, GOLD_HI)
    return cv

def plain_bg(t=T_LIB):
    cv = Canvas()
    status_strip(cv, t)
    soft_diamond(cv, t, 17, H, t["panel"], mix(t["panel"], t["shade"], 0.7))
    return cv

# ---------- Now Playing (026) and default art (277, 116x116 at (10,34)) ----------
def small_icon(kind):
    s = Sprite()
    if kind == "artist":
        s.ellipse(11.5, 8, 3.5, 3.5, LAV); s.ellipse(11.5, 17, 6, 4, LAV_LO); s.put(10, 7, LAV_HI)
    elif kind == "album":
        s.ellipse(11.5, 11.5, 6.5, 6.5, SKY_LO); s.ellipse(11.5, 11.5, 2.5, 2.5, GOLD); s.put(9, 8, SKY_HI)
    else:
        for k, h in enumerate((4, 9, 6, 11, 7)):
            s.rect(6 + k * 3, 17 - h, 2, h, GOLD if k % 2 else LAV)
    return s

def now_playing(t=T_SKY):
    cv = Canvas()
    status_strip(cv, t)
    diamond_bg(cv, t, 17)
    panel(cv, 4, 18, 68, 68, t, False)                  # art frame: covers stock art at 10..126 / 23..132 px
    # info panel, inset from the screen edge (owner, build 28: the rounded screen corners cut it off);
    # game/device/npui.c draws artist / album inside it (x 152..280)
    panel(cv, 73, 18, 72, 68, t, False)
    # v0.3 layout A: artist and album text only (game/device/npui.c draws them), no icons
    # title / progress / time band, inset like the info panel: fill x 10..281, y 172..223 (npui.c TX0/TX1/TY0)
    panel(cv, 3, 84, 142, 32, t, False)
    return cv

def np_line_strip(w, t=T_SKY):
    """Now Playing text-line clear strips (069: 128x16 info lines, 028: 296x16 title line): plain panel fill."""
    cv = Canvas(w // 2, 8)
    cv.rect(0, 0, w // 2, 8, t["panel"])
    return cv

def default_art():
    """58x58 mini Zeal scene (night sky, floating island, pendant), scaled 2x to 116x116."""
    t = T_SKY
    cv = Canvas(58, 58)
    cv.rect(0, 0, 58, 58, t["border"])
    for i in range(18):
        cv.rect((i * 37 + 5) % 58, (i * 23 + 3) % 34, 1, 1, t["panel"] if i % 5 == 0 else t["dim"])
    boot_splash.island(cv, t, dict(x=29, y=30, w=21, h=10, p=0, spire=1, fall=1), 0)
    for x in range(0, 58, 2):
        h = 6 + round(2 * math.sin(x / 6)); cv.rect(x, 58 - h - 6, 2, h + 6, t["lav"])
    for x in range(0, 58, 2):
        h = 3 + round(2 * math.sin((x + 3) / 4)); cv.rect(x, 58 - h - 2, 2, h + 2, t["bg2"])
    for r, row in enumerate(boot_splash.GEM):
        for c, k in enumerate(row):
            if k != ".":
                cv.rect(36 + c, 4 + r, 1, 1, {"g": t["accent"], "H": "#ffffff", "h": t["bg1"], "d": mix(t["bg2"], t["border"], 0.45)}[k])
    for k in range(58):
        for x, y in ((k, 0), (k, 57), (0, k), (57, k)):
            cv.rect(x, y, 1, 1, t["accent"])
    return cv

# ---------- status screens ----------
def usb_screen(t=T_SKY):
    cv = Canvas()
    cv.rect(0, 0, W, H, t["border"])
    for i in range(40):
        cv.rect((i * 53 + 7) % W, (i * 29 + 11) % H, 1, 1, t["dim"])
    # plug
    cv.rect(26, 56, 18, 10, STEEL); cv.rect(26, 56, 18, 2, "#dfe6f4"); cv.rect(44, 58, 8, 6, "#cfd6e4")
    cv.rect(46, 59, 2, 1, t["border"]); cv.rect(49, 59, 2, 1, t["border"])
    cv.rect(10, 60, 16, 2, t["dim"])
    # (no arrow between plug and computer: owner, 2026-11-07)
    # computer
    cv.rect(80, 40, 52, 36, t["text"]); cv.rect(82, 42, 48, 32, t["bg1"]); cv.rect(82, 42, 48, 4, t["lav"])
    cv.rect(100, 76, 12, 6, t["dim"]); cv.rect(92, 82, 28, 3, t["dim"])
    cv.text("USB", (W - tw("USB", 2) + 1) // 2, 92, t["panel"], 2)
    return cv

def charging(level, t=T_SKY):
    cv = Canvas()
    cv.rect(0, 0, W, H, t["border"])
    bx, by, bw, bh = 44, 42, 56, 30
    cv.rect(bx - 2, by - 2, bw + 4, bh + 4, t["panel"]); cv.rect(bx, by, bw, bh, t["text"])
    cv.rect(bx + bw + 2, by + 9, 5, 12, t["panel"])
    cols = ["#e8607a", GOLD, "#58b868"]
    for k in range(level):
        cv.rect(bx + 3 + k * 18, by + 3, 15, bh - 6, cols[min(level, 3) - 1])
        cv.rect(bx + 3 + k * 18, by + 3, 15, 2, mix(cols[min(level, 3) - 1], "#ffffff", 0.5))
    return cv

def dac_screen(t=T_SKY):
    cv = Canvas()
    status_strip(cv, t)
    diamond_bg(cv, t, 17)
    cx, cy = 74, 66
    for y in range(H):
        for x in range(W):
            d = math.hypot(x - cx, y - cy)
            if d <= 30: cv.rect(x, y, 1, 1, t["panel"])
            if 27 <= d <= 30: cv.rect(x, y, 1, 1, t["accent"])
            if 30 < d <= 31.5: cv.rect(x, y, 1, 1, t["border"])
    cv.text("DAC", cx - tw("DAC", 2) // 2, cy - 7, t["border"], 2)
    return cv

def updating(t=T_SKY):
    cv = Canvas()
    cv.rect(0, 0, W, H, t["border"])
    for i in range(40):
        cv.rect((i * 53 + 7) % W, (i * 29 + 11) % 70, 1, 1, t["dim"])
    for r, row in enumerate(boot_splash.GEM):
        for c, k in enumerate(row):
            if k != ".":
                cv.rect(67 + c, 26 + r, 1, 1, {"g": t["accent"], "H": "#ffffff", "h": t["bg1"], "d": mix(t["bg2"], t["border"], 0.45)}[k])
    for s, y, col in (("Updating...", 56, t["panel"]), ("Don't power off!", 70, t["accent"])):
        cv.text(s, (W - tw(s) + 1) // 2, y, col)
    return cv

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build/art"
    os.makedirs(out, exist_ok=True)
    save = lambda cv, i, scale=2: cv.image(scale).save(os.path.join(out, f"{i:03d}.png"))
    for n in range(101):
        save(volume(n), 336 + n)
    save(list_bg(), 159, 1)
    save(highlight_bar(296), 184, 1); save(highlight_bar(255), 185, 1)
    save(plain_bg(), 89)
    save(now_playing(), 26)
    save(np_line_strip(128), 69); save(np_line_strip(296), 28)
    save(default_art(), 277)
    save(usb_screen(), 3)
    for lv, i in enumerate((4, 5, 6, 7)):
        save(charging(lv), i)
    save(dac_screen(), 17)
    save(updating(), 437)
    print("wrote screens to", out)

if __name__ == "__main__":
    main()
