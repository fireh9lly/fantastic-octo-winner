#!/usr/bin/env python3
"""The owner's orange theme on black (2026-11-27): the images amuletOS draws itself, replacing art/pocket.py's.

A test-build look, kept simple on purpose (owner: "don't worry too much about the icons etc for now - we're going to
design a really good one together"). Colours: black screens, their dark theme's orange status band, brown rules and
selection, white text, the bright orange accent of their orange theme. Icons: the smooth flat icons of their orange
theme (its tools/design.py, by Claude in an earlier session; same 64-unit drawing, 8x supersampled), plus Now Playing
and Blockz drawn the same way. Menu labels in Inter (SIL Open Font Licence; /usr/share/fonts or INTER_FONT).
Device text stays in the stock font (build.sh no longer applies the tall font).

Same image ids and layout as art/pocket.py, so game/device/npui.c, playlists.c and gbprobe.c line up; their colours
are in game/device/theme.h (THEME below must match). Stock images not drawn here are recoloured by
art/recolor.py ... orange.

  python art/orange.py OUTDIR
"""
import math, os, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H, S = 296, 240, 8
THEME = dict(bg=0x000000, panel=0x141414, band=0xd66000, rule=0x943e00, head=0x632900, text=0xffffff, dim=0x9a9a9a,
             accent=0xff8200, track=0x3a3a3a, rowline=0x292929, sel=0x943e00, off=0x3a3a3a)   # = theme.h
C = {k: ((v >> 16) & 255, (v >> 8) & 255, v & 255) for k, v in THEME.items()}
FONTS = [os.environ.get("INTER_FONT", ""), "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(px):
    for f in FONTS:
        if f and os.path.exists(f):
            return ImageFont.truetype(f, px)
    sys.exit("no label font found: set INTER_FONT to Inter-Bold.otf (or install fonts-inter)")


# ---------- icons: the orange theme's design.py drawing (64-unit grid), plus play and blocks ----------
def icon(k, fg, bg, size):
    z = S * size / 64
    im = Image.new("RGB", (size * S, size * S), bg)
    D = ImageDraw.Draw(im)
    p = lambda *a: [v * z for v in a]
    def rr(a, r, c=fg): D.rounded_rectangle(p(*a), r * z, fill=c)
    def el(x, y, r, c=fg): D.ellipse(p(x - r, y - r, x + r, y + r), fill=c)
    def pg(pts, c=fg): D.polygon([(x * z, y * z) for x, y in pts], fill=c)
    if k == "music":
        el(18, 48, 9); el(46, 42, 9); rr((22, 14, 27, 48), 1); rr((50, 8, 55, 42), 1)
        pg([(22, 14), (55, 6), (55, 17), (22, 25)])
    elif k == "games":
        rr((4, 18, 60, 48), 15); rr((14, 30, 28, 35), 1, bg); rr((18.5, 25.5, 23.5, 39.5), 1, bg)
        el(43, 37, 3.6, bg); el(50, 28, 3.6, bg)
    elif k == "books":
        rr((8, 10, 20, 54), 2); rr((23, 16, 35, 54), 2); pg([(38, 15), (48, 12), (59, 51), (49, 54)])
        for a in ((8, 17, 20, 20), (8, 44, 20, 47), (23, 23, 35, 26), (23, 44, 35, 47)):
            rr(a, 0, bg)
    elif k == "play":                                    # Now Playing: a disc with a play mark
        el(32, 32, 28); el(32, 32, 22, bg); pg([(26, 19), (46, 32), (26, 45)])
    elif k == "blocks":                                  # Blockz: a stack of four rounded blocks
        for x, y in ((22, 8), (8, 22), (22, 22), (36, 22), (8, 36), (36, 36), (22, 36), (50, 36)):
            rr((x + 1, y + 1, x + 13, y + 13), 3)
    return im.resize((size, size), Image.LANCZOS)


ITEMS = [("Now Playing", "play"), ("Music", "music"), ("Blockz", "blocks"), ("Games", "games"), ("Library", "books")]
STATES = [16, 14, 18, 20, 22]                              # = art/pocket.py: menu position -> image id
GREY_STATES = {0: 8, 4: 24}                                # Now Playing greyed (nothing loaded)


def canvas(c="bg"):
    return Image.new("RGB", (W, H), C[c])


def band(im, h=32):
    """status band: stock draws its icons and our track counter on it"""
    D = ImageDraw.Draw(im)
    D.rectangle((0, 0, W - 1, h), fill=C["band"]); D.rectangle((0, h + 1, W - 1, h + 2), fill=C["rule"])
    return im


def rrect(im, box, r, c):
    """rounded rectangle, 8x supersampled"""
    x0, y0, x1, y1 = box
    t = Image.new("RGB", ((x1 - x0) * S, (y1 - y0) * S), C["bg"])
    ImageDraw.Draw(t).rounded_rectangle((0, 0, t.width - 1, t.height - 1), r * S, fill=c)
    mask = Image.new("L", t.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, t.width - 1, t.height - 1), r * S, fill=255)
    im.paste(t.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0), mask.resize((x1 - x0, y1 - y0), Image.LANCZOS))


def text_c(im, s, y, col, px):
    D = ImageDraw.Draw(im)
    f = font(px)
    w = D.textlength(s, font=f)
    D.text(((W - w) / 2, y), s, font=f, fill=col)


def menu_card(sel, np_off=False):
    title, k = ITEMS[sel]
    n = len(ITEMS)
    off = np_off and sel == 0
    im = band(canvas())
    CX, CY, CS = (W - 136) // 2, 44, 136
    for d, x in ((-1, 16), (1, W - 16 - 40)):            # neighbours, smaller
        j = (sel + d) % n
        dim = np_off and j == 0
        im.paste(icon(ITEMS[j][1], C["off"] if dim else C["accent"], C["bg"], 40), (x, CY + CS // 2 - 20))
    D = ImageDraw.Draw(im)
    for x, left in ((64, True), (W - 70, False)):        # chevrons
        D.polygon([(x + (6 if left else 0), CY + CS // 2 - 7), (x + (0 if left else 6), CY + CS // 2),
                   (x + (6 if left else 0), CY + CS // 2 + 7)], fill=C["accent"])
    rrect(im, (CX, CY, CX + CS, CY + CS), 22, C["off"] if off else C["accent"])
    tile = C["off"] if off else C["accent"]
    ic = icon(k, (90, 90, 90) if off else (0, 0, 0), tile, 100)
    im.paste(ic, (CX + 18, CY + 18))
    text_c(im, title, 190, C["dim"] if off else C["text"], 24)
    x0 = (W - (n * 8 + (n - 1) * 8)) // 2
    for i in range(n):
        D.rounded_rectangle((x0 + i * 16, 226, x0 + i * 16 + 7, 233), 2,
                            fill=(C["off"] if off else C["accent"]) if i == sel else (58, 58, 58))
    return im


def frame(im, x, y, w, h, r=8, shadow=None):
    """2 px accent outline, dark panel fill (npui.c clears inside with TH_PANEL)"""
    if shadow:
        rrect(im, (x + 4, y + 4, x + w + 4, y + h + 4), r, shadow)
    rrect(im, (x, y, x + w, y + h), r, C["accent"])
    rrect(im, (x + 2, y + 2, x + w - 2, y + h - 2), r - 2, C["panel"])


def now_playing():
    """geometry = art/pocket.py now_playing() (npui.c draws into these fills; cover is stock's 116x116 at (17, 46))"""
    im = band(canvas())
    frame(im, 13, 42, 124, 124, shadow=C["rule"])
    frame(im, 146, 42, 138, 124)
    frame(im, 21, 172, 254, 58)
    return im


def default_art():
    im = Image.new("RGB", (116, 116), C["panel"])
    im.paste(icon("music", C["accent"], C["panel"], 72), (22, 22))
    return im


def list_bg():
    """stock lists and Playlists / Games (playlists.c, gbprobe.c paint the same): header text 34..59, rows of 23 px
    from 61"""
    im = band(canvas(), 32)
    D = ImageDraw.Draw(im)
    D.rectangle((0, 35, W - 1, 58), fill=C["head"]); D.rectangle((0, 59, W - 1, 60), fill=C["rule"])
    for y in (83, 106, 129, 152, 175, 198):
        D.line((0, y, W - 1, y), fill=C["rowline"])
    D.rectangle((0, 221, W - 1, H - 1), fill=C["rule"])
    return im


def selection_bar(w):
    im = Image.new("RGB", (w, 22), C["sel"])
    ImageDraw.Draw(im).rectangle((0, 0, 3, 21), fill=C["accent"])
    return im


# Music menu row icons (stock ids; +10 = highlighted set): art/pocket.py's 8x8 glyphs, for now
from pocket import LIST_GLYPHS                              # noqa: E402  (same folder)


def list_icons():
    out = {}
    for n, (rows, _) in list(LIST_GLYPHS.items()) + [(222, LIST_GLYPHS[232])]:
        for m, tile, col in ((n, C["bg"], C["accent"]), (n + 10, C["sel"], C["text"])):
            if n == 222 and m != n:
                continue
            im = Image.new("RGB", (24, 24), tile)
            D = ImageDraw.Draw(im)
            for r, row in enumerate(rows):
                for c, ch in enumerate(row):
                    if ch == "k":
                        D.rectangle((4 + c * 2, 4 + r * 2, 5 + c * 2, 5 + r * 2), fill=col)
            out[m] = im
    return out


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/art_orange")
    out.mkdir(parents=True, exist_ok=True)
    save = lambda im, i: im.save(out / f"{i:03d}.png")
    for sel, idx in enumerate(STATES):
        save(menu_card(sel), idx)
    for sel, idx in GREY_STATES.items():
        save(menu_card(sel, np_off=True), idx)
    save(now_playing(), 26); save(default_art(), 277)
    save(Image.new("RGB", (128, 16), C["panel"]), 69); save(Image.new("RGB", (296, 16), C["bg"]), 28)
    save(list_bg(), 159); save(selection_bar(296), 184); save(selection_bar(255), 185); save(band(canvas()), 89)
    for n, im in list_icons().items():
        save(im, n)
    print("wrote the orange theme's screens to", out)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
