#!/usr/bin/env python3
"""Main menu screens (stock images 014, 016, 018, 020, 022, 024: one per selected tile).

Stock layout (296x240): status strip y 0-32 (stock draws time/battery there in dark
text, so it stays light), tiles in 2 rows x 3 columns: x 0-97 / 99-196 / 198-295,
y 34-135 / 137-239. Drawn on the 148x120 grid and scaled 2x.

  python art/main_menu.py OUTDIR [classic|relic]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zeal import Canvas, THEMES, W, H, mix, tw, rgb
from icons import SETS, LABELS, N

# library/menu screens use Zeal's palace blue-green variant (from the mockups)
T = dict(THEMES["zeal"], bg1="#c2e8de", bg2="#a4d8cc", border="#1d4f74", dim="#5a8a94", shade="#dcefe9")
# image index drawn when tile 0..5 is selected (measured from stock's highlights:
# 016 top-left, 014 top-middle, 018 top-right, 022 bottom-left, 020 bottom-middle, 024 bottom-right)
STATES = [16, 14, 18, 22, 20, 24]
COLS = [(0, 49), (49, 99), (99, 148)]      # 148-grid tile spans (x0, x1)
ROWS = [(17, 68), (68, 120)]
ARROW = [16, 24, 28, 30, 28, 24, 16]

def diamond_bg(cv, t, y0):
    for y in range(y0, H):
        for x in range(W):
            tx, ty = x & 7, y & 7
            m = abs(tx - 3.5) + abs(ty - 3.5)
            on = m <= 1.5 or (3 <= m <= 3.5 and ((x >> 3) + (y >> 3)) & 1)
            cv.rect(x, y, 1, 1, t["bg2"] if on else t["bg1"])

def panel(cv, x, y, w, h, t, sel):
    edge = t["accent"] if sel else t["border"]
    cv.rect(x + 1, y, w - 2, h, edge); cv.rect(x, y + 1, w, h - 2, edge)
    fill = mix(t["panel"], t["lav"], 0.28) if sel else t["panel"]
    cv.rect(x + 2, y + 2, w - 4, h - 4, fill)
    cv.rect(x + 2, y + h - 4, w - 4, 2, t["shade"]); cv.rect(x + w - 4, y + 2, 2, h - 4, t["shade"])
    cv.rect(x + 2, y + 2, w - 6, h - 6, fill)
    if sel:  # double gold frame
        cv.rect(x + 3, y + 3, w - 6, 1, t["accent"]); cv.rect(x + 3, y + h - 4, w - 6, 1, t["accent"])
        cv.rect(x + 3, y + 3, 1, h - 6, t["accent"]); cv.rect(x + w - 4, y + 3, 1, h - 6, t["accent"])

def blit_icon(cv, icon, x, y, ink):
    c, m = icon.outlined(ink)
    for yy in range(N):
        for xx in range(N):
            if m[yy, xx]:
                cv.rect(x + xx, y + yy, 1, 1, tuple(int(v) for v in c[yy, xx]))

def screen(iconset, sel, t=T):
    cv = Canvas()
    cv.rect(0, 0, W, 16, t["panel"]); cv.rect(0, 16, W, 1, t["border"])   # status strip, light for stock text
    diamond_bg(cv, t, 17)
    icons = [f() for f in SETS[iconset]]
    for k in range(6):
        (x0, x1), (y0, y1) = COLS[k % 3], ROWS[k // 3]
        px, py, pw, ph = x0 + 2, y0 + 2, x1 - x0 - 4, y1 - y0 - 4
        panel(cv, px, py, pw, ph, t, k == sel)
        ix = px + (pw - N) // 2
        blit_icon(cv, icons[k], ix, py + 5, t["text"])
        label = LABELS[k]
        lx = px + (pw - tw(label) + 1) // 2
        cv.text(label, lx, py + ph - 13, t["text"] if k == sel else t["dim"])
        if k == sel:
            cv.glyph(ARROW, px + 5, py + 5 + N // 2 - 3, t["lavInk"])
    return cv

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build/art"
    iconset = sys.argv[2] if len(sys.argv) > 2 else "classic"
    os.makedirs(out, exist_ok=True)
    for sel, idx in enumerate(STATES):
        screen(iconset, sel).image().save(os.path.join(out, f"{idx:03d}.png"))
    print(f"wrote main menu ({iconset}) to {out}")

if __name__ == "__main__":
    main()
