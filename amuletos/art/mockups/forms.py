#!/usr/bin/env python3
"""The pet's five adult forms on the mood map (bright/dark x calm/intense, plus neutral), the two-headed sapling,
the pet page (take 4). Builds on black_orange.py. PC renders only."""
import math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
import black_orange as m3
from black_orange import m, P, txt, tw, hx, mix, comp, finish, almond, U, BLACK, BOLD, SEMI, MED, MONO
from black_orange import BG, CHAR, GREY, CREAM, ORANGE, DEEP, PINK, ULTRA, LILAC, canvas, status, hbar

OUT = os.environ.get('OUT', 'out5')
W, H = m.W, m.H
YELLOW = hx('FFD84A')

# ---------------------------------------------------------------- small parts
def leaf(d, bx, by, ang, L, wd, col):
    side = [(t * L, wd / 2 * math.sin(math.pi * t) ** 0.8) for t in np.linspace(0, 1, 18)]
    pts = side + [(x, -y) for x, y in reversed(side[1:-1])]
    ca, sa = math.cos(ang), math.sin(ang)
    d.polygon([(bx + x * ca - y * sa, by + x * sa + y * ca) for x, y in pts], fill=col)

def star_pts(x, y, r, n=4, inner=0.32):
    pts = []
    for i in range(2 * n):
        t = -math.pi / 2 + i * math.pi / n; q = r * (1.0 if i % 2 == 0 else inner)
        pts.append((x + q * math.cos(t), y + q * math.sin(t)))
    return pts

def tip(d, kind, x, y, r, col):
    if kind == 'star': d.polygon(star_pts(x, y, r), fill=col)
    elif kind == 'dot': d.ellipse([x - r * 0.65, y - r * 0.65, x + r * 0.65, y + r * 0.65], fill=col)
    elif kind == 'flower':
        for i in range(5):
            t = -math.pi / 2 + i * 2 * math.pi / 5; q = r * 0.5; px, py = x + q * math.cos(t), y + q * math.sin(t)
            d.ellipse([px - r * 0.42, py - r * 0.42, px + r * 0.42, py + r * 0.42], fill=col)
        d.ellipse([x - r * 0.28, y - r * 0.28, x + r * 0.28, y + r * 0.28], fill=ORANGE)
    elif kind == 'drop':
        q = r * 0.55
        d.ellipse([x - q, y - q + r * 0.3, x + q, y + q + r * 0.3], fill=col)
        d.polygon([(x - q * 0.92, y + r * 0.1), (x, y - r * 0.85), (x + q * 0.92, y + r * 0.1)], fill=col)

# ---------------------------------------------------------------- moon: young stages and five adults
MOON = {
    'neutral':        dict(belly=CREAM, pat='stripes', pcol=DEEP, tips='star', tcol=CREAM, crest=None, pupil='round', lashes=5, opn=1.0, droop=False),
    'bright_intense': dict(belly=YELLOW, pat='zigzag', pcol=ORANGE, tips='star', tcol=YELLOW, crest=('spikes', YELLOW), pupil='round', lashes=0, opn=1.0, droop=False),
    'bright_calm':    dict(belly=PINK, pat='dots', pcol=CREAM, tips='flower', tcol=PINK, crest=None, pupil='round', lashes=7, opn=0.78, droop=True),
    'dark_intense':   dict(belly=DEEP, pat='stripes', pcol=BG, tips=None, tcol=None, crest=('horns', CREAM), pupil='slit', lashes=0, opn=1.0, droop=False),
    'dark_calm':      dict(belly=ULTRA, pat='dots', pcol=LILAC, tips='drop', tcol=LILAC, crest=None, pupil='round', lashes=7, opn=0.55, droop=True),
}

def moon(cv, cx, cy, s, stage=4, form='neutral', opn=1.0, look=(0, 0)):
    F = MOON[form]
    cx, cy, s = P(cx), P(cy), P(s)
    u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.05))
    if stage == 1:
        d.ellipse([*u(-0.52, -0.66), *u(0.52, 0.74)], fill=ORANGE)
        d.line([u(-0.5, 0.08), u(-0.3, -0.06), u(-0.12, 0.1), u(0.06, -0.06), u(0.24, 0.1), u(0.5, -0.04)], fill=BG,
               width=lw, joint='curve')
        return
    if stage == 2:
        d.ellipse([*u(-0.44, -0.62), *u(0.44, 0.26)], fill=ORANGE)
        almond(cv, *u(0, -0.2), s * 0.5, s * 0.26, DEEP, look, 'round', opn)
        zz = [u(-0.56, 0.16)] + [u(-0.56 + k * 0.14, 0.16 if k % 2 == 0 else 0.02) for k in range(1, 9)]
        d.polygon(zz + m.catmull([u(0.56, 0.16), u(0.5, 0.58), u(0, 0.8), u(-0.5, 0.58), u(-0.56, 0.16)], 8)[1:], fill=CREAM)
        return
    adult = stage >= 4
    for g in (-1, 1):
        d.line([u(g * 0.3, 0.55), u(g * 0.44, 0.98)], fill=CREAM, width=lw)
        d.line([u(g * 0.44, 0.98), u(g * 0.6, 0.98)], fill=CREAM, width=lw)
        if form == 'dark_intense' and adult:
            d.polygon([u(g * 0.37, 0.76), u(g * 0.54, 0.7), u(g * 0.4, 0.84)], fill=CREAM)   # spurs
        if adult and F['tips']:
            if F['droop']:
                pts = [u(g * (0.22 + 0.42 * t), -0.62 - 0.3 * math.sin(t * 2.5)) for t in np.linspace(0, 1, 14)]
            else:
                pts = [u(g * (0.22 + 0.26 * t ** 1.3), -0.62 - 0.34 * t) for t in np.linspace(0, 1, 12)]
            d.line(pts, fill=CREAM, width=lw, joint='curve')
            tip(d, F['tips'], *pts[-1], s * 0.15, F['tcol'])
        if adult and F['crest'] and F['crest'][0] == 'horns':
            d.polygon(m.catmull([u(g * 0.22, -0.6), u(g * 0.5, -0.78), u(g * 0.62, -1.06), u(g * 0.74, -0.7), u(g * 0.48, -0.5)], 8,
                                closed=True), fill=F['crest'][1])
    if adult and F['crest'] and F['crest'][0] == 'spikes':
        for x, hgt in ((-0.3, 0.88), (0, 1.04), (0.3, 0.88)):
            d.polygon([u(x - 0.11, -0.62), u(x, -hgt), u(x + 0.11, -0.62)], fill=F['crest'][1])
    box = [*u(-0.7, -0.75), *u(0.7, 0.65)]
    d.chord(box, 180, 360, fill=ORANGE)
    d.chord(box, 0, 180, fill=F['belly'] if adult else CREAM)
    if adult and F['pat']:
        lay = Image.new('RGBA', cv.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
        if F['pat'] == 'stripes':
            for k in range(5):
                y = 0.12 + k * 0.11; ld.rectangle([*u(-0.7, y), *u(0.7, y + 0.05)], fill=F['pcol'])
        elif F['pat'] == 'zigzag':
            for y in (0.2, 0.42):
                ld.line([u(-0.7 + k * 0.14, y + (0.06 if k % 2 else -0.06)) for k in range(11)], fill=F['pcol'], width=int(s * 0.07),
                        joint='curve')
        else:
            for j, y in enumerate((0.22, 0.38, 0.52)):
                for i in range(-3, 4):
                    x = i * 0.2 + (0.1 if j % 2 else 0)
                    ld.ellipse([*u(x - 0.045, y - 0.045), *u(x + 0.045, y + 0.045)], fill=F['pcol'])
        mk = Image.new('L', cv.size, 0); ImageDraw.Draw(mk).chord(box, 0, 180, fill=255)
        lay.putalpha(ImageChops.multiply(lay.getchannel('A'), mk)); cv.alpha_composite(lay)
    o = opn * (F['opn'] if adult else 1.0)
    almond(cv, *u(0, -0.05), s * 0.92, s * 0.46, DEEP, look, F['pupil'] if adult else 'round', o,
           lashes=F['lashes'] if adult else 3)

# ---------------------------------------------------------------- the two-headed sapling
SAP = {
    'neutral':        dict(leaf=CREAM, lw=0.42, extra=None, ecol=None, pupil='round', opn=1.0, lashes=0),
    'bright_intense': dict(leaf=YELLOW, lw=0.26, extra='blossom', ecol=YELLOW, pupil='round', opn=1.0, lashes=0),
    'bright_calm':    dict(leaf=PINK, lw=0.6, extra='flower', ecol=PINK, pupil='round', opn=0.78, lashes=5),
    'dark_intense':   dict(leaf=CREAM, lw=0.2, extra='thorns', ecol=CREAM, pupil='slit', opn=1.0, lashes=0),
    'dark_calm':      dict(leaf=LILAC, lw=0.5, extra='willow', ecol=LILAC, pupil='round', opn=0.55, lashes=5),
}

def sapling(cv, cx, cy, s, stage=4, form='neutral', opn=1.0, look=(0, 0), look2=None):
    """roots for feet, one trunk forking into two heads, one eye each"""
    F = SAP[form] if stage >= 4 else SAP['neutral']
    look2 = look if look2 is None else look2
    cx, cy, s = P(cx), P(cy), P(s)
    u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.05))
    if stage == 1:       # seed with a crack and a first leaf
        leaf(d, *u(0, -0.5), -math.pi / 2 - 0.5, s * 0.42, s * 0.2, CREAM)
        d.ellipse([*u(-0.42, -0.5), *u(0.42, 0.62)], fill=ORANGE)
        d.line([u(0, -0.5), u(-0.08, -0.28), u(0.06, -0.1), u(-0.04, 0.06)], fill=BG, width=lw)
        return
    for g in (-1, 1):    # roots
        pts = [u(g * 0.5 * t, 0.86 + 0.14 * math.sin(t * 2.2)) for t in np.linspace(0, 1, 10)]
        d.line(pts, fill=CREAM, width=lw, joint='curve')
    d.line([u(0, 0.86), u(0, 1.0)], fill=CREAM, width=lw)
    if stage == 2:       # sprout: one stem, one closed head, two leaves
        d.line([u(0, 0.9), u(0, -0.1)], fill=ORANGE, width=int(s * 0.12))
        for g in (-1, 1): leaf(d, *u(0, 0.45), -math.pi / 2 + g * 1.0, s * 0.4, s * 0.2, CREAM)
        r = s * 0.28; d.ellipse([cx - r, cy - s * 0.32 - r, cx + r, cy - s * 0.32 + r], fill=ORANGE)
        almond(cv, cx, cy - s * 0.32, s * 0.36, s * 0.19, DEEP, look, 'round', opn)
        return
    hr = 0.21 if stage == 3 else 0.3
    hx_ = 0.36 if stage == 3 else 0.44
    hy = -0.36 if stage == 3 else -0.46
    tw_ = int(s * (0.12 if stage == 3 else 0.17))
    d.line([u(0, 0.92), u(0, 0.12)], fill=ORANGE, width=tw_)
    for g in (-1, 1):
        br = m.catmull([u(0, 0.18), u(g * 0.12, 0.0), u(g * hx_ * 0.8, hy + 0.2), u(g * hx_, hy)], 8)
        d.line(br, fill=ORANGE, width=int(tw_ * 0.75), joint='curve')
        if stage >= 4:
            leaf(d, *u(g * 0.02, 0.5), -math.pi / 2 + g * 1.15, s * 0.42, s * F['lw'] * 0.5, F['leaf'])
            if F['extra'] == 'thorns':
                for t in (0.35, 0.65):
                    px, py = br[int(t * (len(br) - 1))]
                    d.polygon([(px - s * 0.06, py + s * 0.02), (px + g * s * 0.18, py - s * 0.12), (px + s * 0.06, py + s * 0.05)], fill=F['ecol'])
    heads = [(-1, look), (1, look2)]
    for g, lk in heads:
        hxp, hyp = u(g * hx_, hy); r = s * hr
        if stage >= 4:
            sprout_a = -math.pi / 2 + g * 0.55
            if F['extra'] == 'willow':
                for k in (-0.6, 0, 0.6):
                    px, py = hxp + k * r, hyp + r * 0.6
                    pts = [(px + g * k * s * 0.05 * t, py + s * 0.62 * t) for t in np.linspace(0, 1, 6)]
                    d.line(pts, fill=F['ecol'], width=lw)
                    tip(d, 'drop', *pts[-1], s * 0.08, F['ecol'])
            elif F['extra'] == 'thorns':     # a curved horn on each head
                d.polygon(m.catmull([(hxp + g * r * 0.1, hyp - r * 0.8), (hxp + g * r * 0.6, hyp - r * 1.2),
                                     (hxp + g * r * 0.75, hyp - r * 1.75), (hxp + g * r * 1.0, hyp - r * 0.95),
                                     (hxp + g * r * 0.75, hyp - r * 0.5)], 8, closed=True), fill=F['ecol'])
            elif F['extra'] in ('blossom', 'flower'):
                tip(d, 'star' if F['extra'] == 'blossom' else 'flower', hxp + g * r * 0.55, hyp - r * 1.05, s * 0.17, F['ecol'])
            else:
                leaf(d, hxp + g * r * 0.3, hyp - r * 0.85, sprout_a, s * 0.3, s * F['lw'] * 0.38, F['leaf'])
        d.ellipse([hxp - r, hyp - r, hxp + r, hyp + r], fill=ORANGE)
        almond(cv, hxp, hyp, r * 1.45, r * 0.74, DEEP, lk, F['pupil'], opn * F['opn'], lashes=F['lashes'])

# ---------------------------------------------------------------- panels
QUADS = [('bright_calm', 74, 62, 'bright & calm'), ('bright_intense', 222, 62, 'bright & intense'),
         ('dark_calm', 74, 176, 'dark & calm'), ('dark_intense', 222, 176, 'dark & intense'), ('neutral', 148, 119, 'neutral')]

def adults(draw, title):
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    d.line([(P(34), P(119)), (P(258), P(119))], fill=CHAR, width=P(1.2))
    d.line([(P(148), P(18)), (P(148), P(226))], fill=CHAR, width=P(1.2))
    txt(d, 148, 10, 'BRIGHT', 7, GREY, MONO, h='m', track=1)
    txt(d, 148, 233, 'DARK', 7, GREY, MONO, h='m', track=1)
    txt(d, 6, 119, 'CALM', 7, GREY, MONO, track=1)
    txt(d, 291, 119, 'INTENSE', 7, GREY, MONO, h='r', track=0.6)
    txt(d, 8, 10, title, 7, ORANGE, MONO, track=1)
    d.ellipse([P(148 - 30), P(119 - 30), P(148 + 30), P(119 + 30)], fill=BG)
    for form, x, y, name in QUADS:
        draw(cv, x, y, 24, 4, form, 1, (0, 0.2))
        d = ImageDraw.Draw(cv, 'RGBA')
        txt(d, x + (34 if form == 'neutral' else 0), y + (0 if form == 'neutral' else 37), name, 9.5, CREAM, SEMI,
            h='l' if form == 'neutral' else 'm')
    return cv

def moon_adults(): return adults(moon, 'MOON')
def sapling_adults():
    return adults(lambda cv, x, y, s, st, f, o, lk: sapling(cv, x, y, s, st, f, o, (0.6, 0.2), (-0.6, 0.2)), 'SAPLING')

def growing():
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    for row, (name, fn, labels) in enumerate((('MOON', moon, ('egg', 'hatchling', 'young')),
                                             ('SAPLING', sapling, ('seed', 'sprout', 'young')))):
        y = 58 + row * 106
        txt(d, 10, y - 46, name, 7, ORANGE, MONO, track=1)
        for i, lab in enumerate(labels):
            x = 30 + i * 52
            fn(cv, x, y, 19, i + 1, 'neutral', 1 if i else 0, (0, 0.2))
            d = ImageDraw.Draw(cv, 'RGBA')
            txt(d, x, y + 32, lab, 9, CREAM, SEMI, h='m')
        d.polygon([(P(166), P(y - 4)), (P(172), P(y)), (P(166), P(y + 4))], fill=GREY)
        cx = 234
        for form, ox, oy in (('bright_calm', -26, -20), ('bright_intense', 26, -20), ('dark_calm', -26, 20),
                             ('dark_intense', 26, 20), ('neutral', 0, 0)):
            fn(cv, cx + ox, y + oy, 9.5, 4, form, 1, (0, 0.2))
        d = ImageDraw.Draw(cv, 'RGBA')
        txt(d, cx, y + 40, 'adult: one of five', 9, CREAM, SEMI, h='m')
    txt(d, 10, 229, 'the adult form comes from where its food sat on the mood map', 8, GREY, MED)
    return cv

def pet_page():
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv)
    m.blob(d, 74, 134, 62, 70, CHAR, 31, 0.07)
    moon(cv, 74, 138, 50, 4, 'bright_intense', 1, look=(0.6, -0.1))
    d = ImageDraw.Draw(cv, 'RGBA')
    X = 150
    txt(d, X, 34, 'moon', 26, CREAM)
    txt(d, X, 54, 'ADULT · BRIGHT & INTENSE', 6.8, ORANGE, MONO, track=0.5)
    txt(d, X, 74, '41 h 12 m', 15, CREAM)
    txt(d, X + tw('41 h 12 m', 15) + 5, 74, 'eaten', 9.5, GREY, MED)
    # its diet on the mood map
    x0, y0, x1, y1 = 160, 102, 262, 196
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    for qx0, qy0, qx1, qy1, pct, dom in ((x0, y0, mx - 1, my - 1, 22, 0), (mx + 1, y0, x1, my - 1, 46, 1),
                                          (x0, my + 1, mx - 1, y1, 12, 0), (mx + 1, my + 1, x1, y1, 20, 0)):
        if dom: hbar(cv, qx0, qy0, qx1, qy1, 'dots')
        else: d.rectangle([P(qx0), P(qy0), P(qx1), P(qy1)], fill=CHAR)
        d = ImageDraw.Draw(cv, 'RGBA')
        txt(d, qx1 - 3, qy0 + 6, f'{pct}%', 7, BG if dom else GREY, MONO, h='r')
    rnd = random.Random(5)
    for _ in range(70):
        q = rnd.random()
        cx_, cy_ = (0.45, -0.4) if q < 0.46 else (-0.45, -0.4) if q < 0.68 else (0.45, 0.45) if q < 0.88 else (-0.45, 0.45)
        px = mx + max(-0.95, min(0.95, cx_ + rnd.gauss(0, 0.22))) * (x1 - x0) / 2
        py = my + max(-0.92, min(0.92, cy_ + rnd.gauss(0, 0.22))) * (y1 - y0) / 2
        r = P(1.1); d.ellipse([P(px) - r, P(py) - r, P(px) + r, P(py) + r], fill=CREAM)
    txt(d, mx, y0 - 6, 'BRIGHT', 6.5, GREY, MONO, h='m', track=0.8)
    txt(d, mx, y1 + 7, 'DARK', 6.5, GREY, MONO, h='m', track=0.8)
    txt(d, x0 - 3, my, 'CALM', 6.5, GREY, MONO, h='r', track=0.5)
    txt(d, x1 + 3, my, 'INT.', 6.5, GREY, MONO, track=0.5)
    txt(d, X, 214, 'each dot is a track it ate', 8, GREY, MED)
    txt(d, X, 229, 'A GALLERY · START NEW PET', 6.8, CREAM, MONO, track=0.4)
    return cv

PICK = [('moon', 'moon'), ('arch', (ORANGE, CREAM, DEEP)), ('sapling', 'sapling'),
        ('dome', (CREAM, ORANGE, DEEP)), ('star', (ORANGE, CREAM, DEEP)), ('dandelion', (CREAM, ORANGE, DEEP))]
def picker(sel=2):
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv)
    txt(d, 14, 32, 'pick a creature', 16, CREAM)
    for i, (k, cols) in enumerate(PICK):
        cx0, cy0 = 10 + (i % 3) * 96, 46 + (i // 3) * 86
        on = i == sel
        if on: d.rectangle([P(cx0), P(cy0), P(cx0 + 92), P(cy0 + 82)], fill=CHAR)
        ccx, ccy = cx0 + 46, cy0 + 34
        lk = (0, 0.3)
        if k == 'moon': moon(cv, ccx, ccy, 22, 4, 'neutral', 1 if on else 0, lk)
        elif k == 'sapling': sapling(cv, ccx, ccy + 1, 23, 4, 'neutral', 1 if on else 0, (0.5, 0.3), (-0.5, 0.3))
        else: m.creature(cv, k, ccx, ccy, 22, cols, opn=1 if on else 0, **({'bg': CHAR if on else BG} if k == 'arch' else {}))
        d = ImageDraw.Draw(cv, 'RGBA')
        if on:
            hbar(cv, cx0, cy0 + 66, cx0 + 92, cy0 + 82, 'dots'); d = ImageDraw.Draw(cv, 'RGBA')
        txt(d, ccx, cy0 + 74, k, 11, BG if on else GREY, BOLD, h='m')
    txt(d, 14, 229, 'starts as an egg or a seed · grows on what you play', 8.5, GREY, MED)
    return cv

def home_sapling():
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    m.blob(d, 148, 126, 78, 80, CHAR, 14, 0.07)
    sapling(cv, 148, 128, 60, 4, 'neutral', 1, look=(1, 0))
    d = ImageDraw.Draw(cv, 'RGBA')
    for label, x, y in (('now playing', 148, 30), ('games', 148, 228), ('settings', 37, 128)):
        txt(d, x, y, label, 12, GREY, h='m')
    hbar(cv, 236, 119, 288, 137, 'dots')
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 262, 128, 'music', 13, BG, h='m')
    status(cv)
    return cv

SCREENS = [('moon_adults', moon_adults, 'Moon: five adult forms, placed on the mood map'),
           ('sapling_adults', sapling_adults, 'Sapling: the same five'),
           ('growing', growing, 'Growing up: young stages, then one of five adults'),
           ('pet', pet_page, 'The pet\'s page: what it ate, on the mood map'),
           ('picker', picker, 'Swap the creature (sapling highlighted)'),
           ('home_sapling', home_sapling, 'Home with the sapling: both heads look where you point')]

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
