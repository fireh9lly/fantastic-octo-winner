#!/usr/bin/env python3
"""Automatic Zeal recolour for every stock image not hand-drawn.

Neutral greys map onto a navy-tinted ramp (black -> deep navy, light grey -> cream);
warm beige/tan (the Hidizs accent) maps onto gold, and its pale tints (selection
highlights) onto a lavender tint. Other hues (coloured SDK icons) are kept.

  python art/recolor.py STOCK_PNG_DIR HANDMADE_DIR OUTDIR [pocket|orange]

orange (owner's orange theme on black, art/orange.py): the mapping of their dark theme (its tools/dark.py): images
with a light background get their neutrals inverted (white -> near black, dark greys -> light), stock's blue
highlights turn into the brown selection colour and the Hidizs tan into orange; dark images and small icons (status
band, list rows: up to 48 px) keep their look and only the tan turns orange.
"""
import os, sys
import numpy as np
from PIL import Image

def hexrgb(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)

GREY = [(0.00, "#0c1030"), (0.15, "#121a40"), (0.40, "#33447e"), (0.65, "#7d8cb8"),
        (0.85, "#d4dcec"), (0.93, "#fffdf6"), (1.00, "#ffffff")]
WARM = [(0.00, "#5a3a10"), (0.45, "#a8701c"), (0.68, "#d9a02a"), (0.80, "#ecc672"),
        (0.88, "#e6dcf6"), (1.00, "#f4f0fd")]

# Pocket look (art/pocket.py): greys onto ink -> white, the Hidizs warm accent onto grape
POCKET_GREY = [(0.00, "#16171d"), (0.15, "#23252e"), (0.40, "#4a4e5c"), (0.65, "#7d8291"),
               (0.85, "#dfe1e8"), (0.93, "#ffffff"), (1.00, "#ffffff")]
POCKET_WARM = [(0.00, "#2e2070"), (0.45, "#5a40c0"), (0.68, "#7353e0"), (0.80, "#a993f0"),
               (0.88, "#e9e3fb"), (1.00, "#f4f1fe")]

def ramp(stops, v):
    xs = np.array([s for s, _ in stops]); cs = np.array([hexrgb(c) for _, c in stops])
    out = np.empty(v.shape + (3,))
    for ch in range(3):
        out[..., ch] = np.interp(v, xs, cs[:, ch])
    return out

def recolor(a):
    f = a.astype(float) / 255
    mx, mn = f.max(2), f.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    lum = 0.3 * f[..., 0] + 0.59 * f[..., 1] + 0.11 * f[..., 2]
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    warm = (sat >= 0.08) & (sat < 0.55) & (r >= g) & (g >= b) & (r - b > 0.05)
    neutral = sat < 0.08
    out = f * 255
    out[neutral] = ramp(GREY, lum[neutral])
    out[warm] = ramp(WARM, lum[warm])
    # pure black / white may be colour keys (transparent) in stock icons: keep them exact
    key = np.all(a == 0, axis=2) | np.all(a == 255, axis=2)
    out[key] = a[key]
    return np.clip(out, 0, 255).astype(np.uint8)

ORANGE = np.array([255, 130, 0.])
SEL = np.array([148, 62, 0.])                                                # art/orange.py "sel"

def recolor_orange(a):
    f = a.astype(float)
    tan = np.clip((f[..., 0] - f[..., 2] - 20) / 50, 0, 1)[..., None]       # dark.py: how warm (Hidizs tan)
    l = f.mean(2, keepdims=True)
    h, w = a.shape[:2]
    light = (0.3 * f[..., 0] + 0.59 * f[..., 1] + 0.11 * f[..., 2]).mean() > 140
    if light and max(w, h) > 48:                    # panels and backgrounds: invert the neutrals
        v = np.where(l >= 234, np.clip((l - 240) * 2.4, 0, 36), np.clip((234 - l) * 1.1, 0, 255))
        neutral = np.repeat(v, 3, 2)
        blue = np.clip((f[..., 2] - f[..., 0] - 40) / 60, 0, 1)[..., None]  # stock's blue highlights -> selection
        neutral = neutral * (1 - blue) + SEL * (l / 200).clip(0.6, 1.2) * blue
    else:                                           # dark images, and small icons (status band, list rows) as stock
        neutral = f
    out = neutral * (1 - tan) + ORANGE * (l / 255 * 1.4).clip(0.35, 1) * tan
    return np.clip(out, 0, 255).astype(np.uint8)

def main():
    global GREY, WARM, recolor
    src, hand, out = sys.argv[1:4]
    if sys.argv[4:5] == ["pocket"]:
        GREY, WARM = POCKET_GREY, POCKET_WARM
    elif sys.argv[4:5] == ["orange"]:
        recolor = recolor_orange
    os.makedirs(out, exist_ok=True)
    done = {f for f in os.listdir(hand) if f.endswith(".png")}
    n = 0
    for f in sorted(os.listdir(src)):
        if not (f.endswith(".png") and f[:3].isdigit()) or f in done:
            continue
        a = np.asarray(Image.open(os.path.join(src, f)).convert("RGB"))
        Image.fromarray(recolor(a)).save(os.path.join(out, f)); n += 1
    print(f"recoloured {n} images into {out}")

if __name__ == "__main__":
    main()
