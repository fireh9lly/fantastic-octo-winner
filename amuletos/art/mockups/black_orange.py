#!/usr/bin/env python3
"""Black-and-orange round (take 3): textured highlight bars, home, Now Playing, kit. Builds on shapes.py.
PC renders only."""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageChops
import shapes as m
from shapes import P, txt, tw, hx, mix, comp, finish, almond, U, BLACK, BOLD, SEMI, MED, MONO

OUT = os.environ.get('OUT', 'out4')
W, H = m.W, m.H

BG, CHAR, GREY = hx('0F0E0D'), hx('1E1B19'), hx('77706A')
CREAM, ORANGE, DEEP = hx('F1ECE1'), hx('FF7A1A'), hx('D9560B')
PINK, ULTRA, LILAC, CHART = m.PINK, hx('3E5BEA'), m.LILAC, m.CHART
m.LINE = CREAM
m.PAPER = CREAM

def canvas(bg=BG): return Image.new('RGBA', (P(W), P(H)), bg)

def status(cv, vol=31, bat=0.7, text=None, dim=None, track=None, acc=None):
    """clock left; volume bar + number (the wheel only ever updates this, no pop-up); battery icon"""
    text, dim, track, acc = text or CREAM, dim or GREY, track or CHAR, acc or ORANGE
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 10, 9, '12:41', 8.5, text, MONO)
    d.rectangle([P(184), P(7.3), P(186.6), P(10.7)], fill=dim)
    d.polygon([(P(186.6), P(7.3)), (P(190), P(5.2)), (P(190), P(12.8)), (P(186.6), P(10.7))], fill=dim)
    d.rectangle([P(195), P(7.5), P(239), P(10.5)], fill=track)
    d.rectangle([P(195), P(7.5), P(195 + 44 * vol / 100), P(10.5)], fill=acc)
    txt(d, 244, 9, str(vol), 8.5, text, MONO)
    d.rectangle([P(264), P(5), P(282), P(13)], outline=dim, width=P(1))
    d.rectangle([P(283), P(7.5), P(284.6), P(10.5)], fill=dim)
    d.rectangle([P(265.8), P(6.8), P(265.8 + 14.4 * bat), P(11.2)], fill=dim)

# ---------------------------------------------------------------- the highlight: a plain bar with a printed texture
def hbar(cv, x0, y0, x1, y1, tex='dots', col=ORANGE, tcol=DEEP):
    w, h = P(x1 - x0), P(y1 - y0)
    lay = Image.new('RGBA', (w, h), col)
    d = ImageDraw.Draw(lay)
    if tex == 'dots':
        r, k = P(1.15), P(5.5)
        for j, y in enumerate(range(-k, h + k, k)):
            for x in range(-k + (k // 2 if j % 2 else 0), w + k, k):
                d.ellipse([x - r, y - r, x + r, y + r], fill=tcol)
    elif tex == 'lines':
        k, t = P(5.5), P(1.3)
        for x in range(-h, w + k, k): d.line([(x, h), (x + h, 0)], fill=tcol, width=t)
    elif tex == 'waves':
        k, t, a, per = P(5.2), P(1.2), P(1.1), P(7)
        for y0_ in range(k // 2, h + k, k):
            d.line([(x, y0_ + a * math.sin(2 * math.pi * x / per)) for x in range(-4, w + 4, 2)], fill=tcol, width=t,
                   joint='curve')
    comp(cv, lay, P(x0), P(y0))

# ---------------------------------------------------------------- the pet: one species that grows and takes on what it eats
DIETS = {
    'mixed':  dict(belly=CREAM, pattern='stripes', pcol=ULTRA, tips='star', tcol=PINK, crest=None, pupil='round', lashes=5),
    'loud':   dict(belly=CREAM, pattern='stripes', pcol=BG, tips='star', tcol=CREAM, crest=DEEP, pupil='slit', lashes=0),
    'soft':   dict(belly=LILAC, pattern='dots', pcol=CREAM, tips='dot', tcol=LILAC, crest=None, pupil='round', lashes=7),
    'bright': dict(belly=PINK, pattern='dots', pcol=ORANGE, tips='star', tcol=CHART, crest=None, pupil='round', lashes=5),
    'plain':  dict(belly=CREAM, pattern=None, pcol=None, tips='star', tcol=ORANGE, crest=None, pupil='round', lashes=5),
}

def pet(cv, cx, cy, s, stage=4, diet='mixed', opn=1.0, look=(0, 0), body=ORANGE):
    """1 egg, 2 hatchling, 3 young (legs), 4 grown (feelers); diet decides belly, pattern, tips, crest, pupil"""
    D = DIETS[diet]
    cx, cy, s = P(cx), P(cy), P(s)
    u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.05))
    if stage == 1:
        d.ellipse([*u(-0.52, -0.66), *u(0.52, 0.74)], fill=body)
        d.line([u(-0.5, 0.08), u(-0.3, -0.06), u(-0.12, 0.1), u(0.06, -0.06), u(0.24, 0.1), u(0.5, -0.04)], fill=BG,
               width=lw, joint='curve')
        return
    if stage == 2:
        d.ellipse([*u(-0.44, -0.62), *u(0.44, 0.26)], fill=body)
        almond(cv, *u(0, -0.2), s * 0.5, s * 0.26, ORANGE if body != ORANGE else DEEP, look, 'round', opn)
        zz = [u(-0.56, 0.16)] + [u(-0.56 + k * 0.14, 0.16 if k % 2 == 0 else 0.02) for k in range(1, 9)]
        d.polygon(zz + m.catmull([u(0.56, 0.16), u(0.5, 0.58), u(0, 0.8), u(-0.5, 0.58), u(-0.56, 0.16)], 8)[1:], fill=CREAM)
        return
    for g in (-1, 1):
        d.line([u(g * 0.3, 0.55), u(g * 0.44, 0.98)], fill=CREAM, width=lw)
        d.line([u(g * 0.44, 0.98), u(g * 0.6, 0.98)], fill=CREAM, width=lw)
        if stage >= 4:
            droop = D['tips'] == 'dot'
            pts = [u(g * (0.22 + 0.26 * t ** 1.3), -0.62 - (0.34 * t if not droop else 0.3 * math.sin(t * 2.4)))
                   for t in [i / 11 for i in range(12)]]
            d.line(pts, fill=CREAM, width=lw, joint='curve')
            m.stalk(d, pts[-2], pts[-1], lw, D['tcol'], s * (0.14 if D['tips'] == 'star' else 0.09), star=D['tips'] == 'star')
    if stage >= 4 and D['crest']:
        for x, hgt in ((-0.28, 0.86), (0, 1.02), (0.28, 0.86)):
            d.polygon([u(x - 0.11, -0.62), u(x, -hgt), u(x + 0.11, -0.62)], fill=D['crest'])
    box = [*u(-0.7, -0.75), *u(0.7, 0.65)]
    d.chord(box, 180, 360, fill=body)
    d.chord(box, 0, 180, fill=D['belly'])
    if stage >= 4 and D['pattern']:
        lay = Image.new('RGBA', cv.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
        if D['pattern'] == 'stripes':
            for k in range(5):
                y = 0.12 + k * 0.11
                ld.rectangle([*u(-0.7, y), *u(0.7, y + 0.05)], fill=D['pcol'])
        else:
            for j, y in enumerate((0.22, 0.38, 0.52)):
                for i in range(-3, 4):
                    x = i * 0.2 + (0.1 if j % 2 else 0)
                    ld.ellipse([*u(x - 0.04, y - 0.04), *u(x + 0.04, y + 0.04)], fill=D['pcol'])
        mk = Image.new('L', cv.size, 0); ImageDraw.Draw(mk).chord(box, 0, 180, fill=255)
        lay.putalpha(ImageChops.multiply(lay.getchannel('A'), mk)); cv.alpha_composite(lay)
    almond(cv, *u(0, -0.05), s * 0.92, s * 0.46, DEEP if body == ORANGE else ORANGE, look, D['pupil'], opn,
           lashes=D['lashes'] if stage >= 4 else 3)

# ---------------------------------------------------------------- home: the pet looks where you point
def home():
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    m.blob(d, 148, 126, 78, 80, CHAR, 14, 0.07)
    pet(cv, 148, 130, 56, 4, 'mixed', 1, look=(1, 0))
    for label, x, y in (('now playing', 148, 30), ('games', 148, 228), ('settings', 37, 128)):
        txt(d, x, y, label, 12, GREY, h='m')
    hbar(cv, 236, 119, 288, 137, 'dots')
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 262, 128, 'music', 13, BG, h='m')
    status(cv)
    return cv

# ---------------------------------------------------------------- now playing
def now_playing(progress=0.43):
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    m.blob(d, 70, 114, 52, 50, ORANGE, 11, 0.08)
    cv.paste(m.cover(P(100)), (P(18), P(30)))
    status(cv)
    X = 134
    txt(d, X, 38, '03/12 · FLAC 24/96', 8, GREY, MONO)
    txt(d, X, 61, 'Soft', 23, CREAM)
    txt(d, X, 85, 'Machinery', 23, CREAM)
    txt(d, X, 106, 'Pale Fauna', 13, ORANGE, BOLD)
    txt(d, X, 121, 'Lantern Hours', 11, GREY, MED)
    m.glyph(d, 'shuffle', X + 7, 141, 13, ORANGE)
    m.glyph(d, 'repeat', X + 31, 141, 13, mix(GREY, BG, 0.4))
    m.glyph(d, 'heart', X + 54, 141, 13, ORANGE)
    y, x0, x1 = 198, 16, 282
    fx = x0 + (x1 - x0) * progress
    d.line([(P(fx), P(y)), (P(x1), P(y))], fill=mix(GREY, BG, 0.3), width=P(1.2))
    hbar(cv, x0, y - 3, fx, y + 3, 'lines')
    d = ImageDraw.Draw(cv, 'RGBA')
    almond(cv, P(fx), P(y), P(16), P(9), ORANGE, (1, 0))
    pet(cv, 262, y - 19, 19, 4, 'mixed', 1, look=(-1, 0))
    txt(d, x0, 220, '1:42', 8.5, CREAM, MONO)
    txt(d, x1, 220, '-2:13', 8.5, GREY, MONO, h='r')
    txt(d, 92, 220, 'NEXT', 8, GREY, MONO)
    txt(d, 118, 220, 'Moth Radio', 9.5, CREAM, SEMI)
    return cv

# ---------------------------------------------------------------- scrolling lists
MARKS = ['circle', 'moon', 'tri', 'square', 'pill', 'heart']
def mark(d, k, x, y, c):
    X, Y, r = P(x), P(y), P(4.3)
    if k == 'circle': d.ellipse([X - r, Y - r, X + r, Y + r], fill=c)
    elif k == 'moon': d.chord([X - r, Y - r, X + r, Y + r], 90, 270, fill=c)
    elif k == 'tri': d.polygon([(X - r, Y + r), (X, Y - r), (X + r, Y + r)], fill=c)
    elif k == 'square': d.rectangle([X - r * 0.85, Y - r * 0.85, X + r * 0.85, Y + r * 0.85], fill=c)
    elif k == 'pill': d.rounded_rectangle([X - r * 1.2, Y - r * 0.6, X + r * 1.2, Y + r * 0.6], radius=r * 0.6, fill=c)
    else: m.glyph(d, 'heart', x, y, 10, c)

def menu(title, rows, sel, tex, crumb=None, values=None, y0=80, pitch=26, look=(-0.8, 0.6)):
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv)
    if crumb: txt(d, 14, 25, crumb, 7.5, GREY, MONO, track=1)
    txt(d, 14, 44, title, 30, CREAM)
    pet(cv, 262, 46, 19, 4, 'mixed', 1, look=look)
    d = ImageDraw.Draw(cv, 'RGBA')
    for i, label in enumerate(rows):
        y = y0 + i * pitch
        on = i == sel
        if on:
            hbar(cv, 10, y - 11, 278, y + 11, tex); d = ImageDraw.Draw(cv, 'RGBA')
        fg = BG if on else CREAM
        if values is None:
            mark(d, MARKS[i % 6], 22, y, BG if on else (ORANGE if i % 2 == 0 else CREAM))
            txt(d, 36, y, label, 15, fg, BOLD)
            if on: txt(d, 270, y, '12', 8.5, BG, MONO, h='r')
        else:
            txt(d, 18, y, label, 14, fg, BOLD)
            v = values[i]
            if on: v = f'‹  {v}  ›'
            txt(d, 270, y, v, 11.5, BG if on else GREY, MED, h='r')
    d.line([(P(287), P(y0 - 10)), (P(287), P(y0 + pitch * (len(rows) - 1) + 10))], fill=CHAR, width=P(1.2))
    t0 = y0 - 10 + (sel / max(1, len(rows))) * pitch * len(rows)
    d.rectangle([P(285.5), P(t0), P(288.5), P(t0 + 22)], fill=ORANGE)
    return cv

def music_list():
    return menu('music', ['all songs', 'artists', 'albums', 'genres', 'playlists', 'favourites'], 2, 'dots')

def look_settings():
    cv = menu('look', ['colours', 'highlight', 'creature', 'eye follows you', 'album art'], 1, 'waves', crumb='SETTINGS',
              values=['black & orange', 'waves', 'moon', 'on', 'square'], y0=78, pitch=25)
    d = ImageDraw.Draw(cv, 'RGBA')
    # colour swatches beside the theme name
    x = 270 - tw('black & orange', 11.5, MED) - 24
    d.rectangle([P(x), P(73), P(x + 9), P(83)], fill=BG, outline=GREY, width=P(1))
    d.rectangle([P(x + 11), P(73), P(x + 20), P(83)], fill=ORANGE)
    # the three textures, current one marked
    for i, (tex, name) in enumerate((('dots', 'DOTS'), ('lines', 'LINES'), ('waves', 'WAVES'))):
        bx = 18 + i * 88
        hbar(cv, bx, 205, bx + 74, 217, tex)
        d = ImageDraw.Draw(cv, 'RGBA')
        txt(d, bx + 37, 228, name, 7, CREAM if tex == 'waves' else GREY, MONO, h='m', track=1)
        if tex == 'waves': d.rectangle([P(bx - 2), P(203), P(bx + 76), P(219)], outline=CREAM, width=P(1))
    return cv

# ---------------------------------------------------------------- swap the creature
SPECIES = [('moon', None), ('arch', (ORANGE, CREAM, DEEP)), ('totem', (ORANGE, CREAM, DEEP)),
           ('dome', (CREAM, ORANGE, DEEP)), ('star', (ORANGE, CREAM, DEEP)), ('dandelion', (CREAM, ORANGE, DEEP))]
def picker(sel=0):
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv)
    txt(d, 14, 32, 'pick a creature', 16, CREAM)
    for i, (k, cols) in enumerate(SPECIES):
        cx0, cy0 = 10 + (i % 3) * 96, 46 + (i // 3) * 86
        on = i == sel
        if on: d.rectangle([P(cx0), P(cy0), P(cx0 + 92), P(cy0 + 82)], fill=CHAR)
        ccx, ccy = cx0 + 46, cy0 + 34
        if k == 'moon': pet(cv, ccx, ccy, 22, 4, 'plain', 1 if on else 0, look=(0, 0.3))
        else: m.creature(cv, k, ccx, ccy, 22, cols, opn=1 if on else 0, **({'bg': CHAR if on else BG} if k == 'arch' else {}))
        d = ImageDraw.Draw(cv, 'RGBA')
        if on:
            hbar(cv, cx0, cy0 + 66, cx0 + 92, cy0 + 82, 'dots'); d = ImageDraw.Draw(cv, 'RGBA')
        txt(d, ccx, cy0 + 74, k, 11, BG if on else GREY, BOLD, h='m')
    txt(d, 14, 229, 'starts as an egg · grows on what you play', 8.5, GREY, MED)
    return cv

# ---------------------------------------------------------------- the pet's page
def pet_page():
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv)
    m.blob(d, 76, 132, 64, 70, CHAR, 31, 0.07)
    pet(cv, 76, 134, 52, 4, 'mixed', 1, look=(0.5, -0.1))
    X = 152
    txt(d, X, 36, 'moon', 26, CREAM)
    txt(d, X, 56, 'GROWN · STAGE 4 OF 5', 7, GREY, MONO, track=0.6)
    txt(d, X, 76, 'has eaten', 9.5, GREY, MED)
    txt(d, X, 93, '41 h 12 m', 18, ORANGE)
    txt(d, X, 115, 'DIET', 7, GREY, MONO, track=1)
    segs = [(0.38, ORANGE, 'techno'), (0.27, PINK, 'dream pop'), (0.2, ULTRA, 'jazz'), (0.15, GREY, 'other')]
    x = X
    for f, c, _ in segs:
        w = 132 * f; d.rectangle([P(x), P(123), P(x + w - 1.2), P(131)], fill=c); x += w
    for i, (f, c, name) in enumerate(segs):
        lx, ly = X + (i % 2) * 70, 144 + (i // 2) * 14
        d.rectangle([P(lx), P(ly - 3), P(lx + 6), P(ly + 3)], fill=c)
        txt(d, lx + 10, ly, f'{name} {round(f * 100)}%', 8.5, CREAM, MED)
    txt(d, X, 178, 'grew stripes from jazz,', 8.5, GREY, MED)
    txt(d, X, 190, 'star feelers from dream pop', 8.5, GREY, MED)
    txt(d, X, 214, 'NEXT CHANGE IN 6 H', 7, ORANGE, MONO, track=0.6)
    return cv

# ---------------------------------------------------------------- growing up, and how diet shows
def growing():
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 12, 12, 'GROWING UP', 7, GREY, MONO, track=1)
    for i, (st, name) in enumerate(((1, 'egg'), (2, 'hatchling'), (3, 'young'), (4, 'grown'))):
        cx = 40 + i * 72
        pet(cv, cx, 52, 24, st, 'plain', 1, look=(0, 0.2))
        txt(d, cx, 92, name, 9.5, CREAM, SEMI, h='m')
    for i in range(3):
        x = 40 + i * 72 + 30
        d.polygon([(P(x), P(49)), (P(x + 5), P(52)), (P(x), P(55))], fill=GREY)
    txt(d, 12, 118, 'WHAT IT EATS CHANGES IT', 7, GREY, MONO, track=1)
    for i, (diet, name) in enumerate((('loud', 'loud & fast'), ('soft', 'soft & slow'), ('bright', 'bright & poppy'))):
        cx = 52 + i * 96
        pet(cv, cx, 170, 30, 4, diet, 1, look=(0, 0.2))
        txt(d, cx, 224, name, 9.5, CREAM, SEMI, h='m')
    return cv

# ---------------------------------------------------------------- the kit
def kit():
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 12, 12, 'COLOUR', 7, GREY, MONO, track=1)
    for i, (c, name) in enumerate(((BG, 'black'), (CHAR, 'char'), (GREY, 'grey'), (CREAM, 'cream'), (ORANGE, 'orange'),
                                   (DEEP, 'deep'))):
        x = 12 + i * 46
        d.rectangle([P(x), P(22), P(x + 40), P(46)], fill=c, outline=CHAR if c == BG else None, width=P(1))
        txt(d, x, 55, name, 8, CREAM, MED)
    txt(d, 12, 74, 'HIGHLIGHT', 7, GREY, MONO, track=1)
    for i, tex in enumerate(('dots', 'lines', 'waves')):
        y = 92 + i * 26
        hbar(cv, 12, y - 11, 196, y + 11, tex); d = ImageDraw.Draw(cv, 'RGBA')
        txt(d, 22, y, 'albums', 15, BG, BOLD)
        txt(d, 188, y, '12', 8.5, BG, MONO, h='r')
        txt(d, 208, y, tex.upper(), 7.5, CREAM, MONO, track=1)
    txt(d, 12, 176, 'TYPE', 7, GREY, MONO, track=1)
    txt(d, 12, 204, 'music', 26, CREAM)
    txt(d, 106, 198, 'Soft Machinery', 12, CREAM, BOLD)
    txt(d, 106, 214, '1:42 · FLAC 24/96', 8.5, GREY, MONO)
    return cv

SCREENS = [('home', home, 'Home: the pet looks where you point'),
           ('now_playing', now_playing, 'Now Playing: it watches the song go by'),
           ('music_list', music_list, 'A list: highlight bar with dots'),
           ('look', look_settings, 'Settings > Look (highlight set to waves)'),
           ('picker', picker, 'Swap the creature'),
           ('pet', pet_page, 'The pet\'s page'),
           ('growing', growing, 'It grows, and changes with what it eats'),
           ('kit', kit, 'The kit')]

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    shots = []
    for name, fn, cap in SCREENS:
        im = finish(fn()); im.save(f'{OUT}/{name}.png'); shots.append((im, cap)); print(name)
    Z, M, CH = 2, 24, 30
    cf = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17)
    rows = (len(shots) + 1) // 2
    sheet = Image.new('RGB', (M + 2 * (W * Z + M), M + rows * (H * Z + CH + M)), (44, 42, 46))
    sd = ImageDraw.Draw(sheet)
    for i, (im, cap) in enumerate(shots):
        x, y = M + (i % 2) * (W * Z + M), M + (i // 2) * (H * Z + CH + M)
        sheet.paste(im.resize((W * Z, H * Z), Image.NEAREST), (x, y))
        sd.text((x, y + H * Z + 7), cap, font=cf, fill=(235, 228, 240))
    sheet.save(f'{OUT}/sheet.png')
