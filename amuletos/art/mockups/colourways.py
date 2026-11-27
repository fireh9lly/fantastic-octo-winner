#!/usr/bin/env python3
"""Five colourways (the creature recoloured through each), the whaleian, the gallery, Settings > Look (take 5).
Builds on shapes.py, black_orange.py and forms.py. PC renders only."""
import math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
import forms as m4
from forms import m, m3, P, txt, tw, hx, mix, comp, finish, almond, U, BLACK, BOLD, SEMI, MED, MONO, leaf, star_pts
from black_orange import hbar

OUT = os.environ.get('OUT', 'out6')
W, H = m.W, m.H
YELLOW, PINK, ULTRA, LILAC = hx('FFD84A'), m.PINK, hx('3E5BEA'), m.LILAC
INK = m.INK

def theme(name, bg, panel, text, dim, bars, texs, bartext, body, light, deep, line, sclera, marks):
    return dict(name=name, bg=hx(bg), panel=hx(panel), text=hx(text), dim=hx(dim), bars=[hx(c) for c in bars],
                texs=[hx(c) for c in texs], bartext=hx(bartext), body=hx(body), light=hx(light), deep=hx(deep),
                line=hx(line), sclera=hx(sclera), marks=[hx(c) for c in marks])

THEMES = {
    'black': theme('black & orange', '0F0E0D', '1E1B19', 'F1ECE1', '77706A', ['FF7A1A'], ['D9560B'], '0F0E0D',
                   'FF7A1A', 'F1ECE1', 'D9560B', 'F1ECE1', 'F1ECE1', ['FF7A1A', 'F1ECE1']),
    'paper': theme('paper & orange', 'F1ECE1', 'E2DACB', '151313', '8C857C', ['FF7A1A'], ['DE5E0E'], '151313',
                   'FF7A1A', '151313', 'D9560B', '151313', 'FFFDF8', ['FF7A1A', '151313']),
    'eva':   theme('eva', '2B1846', '3D2563', 'EFE8FA', '9C88BE', ['8EF03C'], ['62C21C'], '2B1846',
                   '8EF03C', 'FF8A2B', '6B3FA8', 'EFE8FA', 'F4EEFF', ['8EF03C', 'FF8A2B']),
    'aqua':  theme('aqua', 'CFE6EE', 'BCDAE5', '21425F', '6E8FA6', ['56C8CE'], ['3BAAB1'], '21425F',
                   '4C7FD6', 'F2FAFC', '21425F', '21425F', 'FFFFFF', ['4C7FD6', '3BAAB1']),
    'candy': theme('candy', '6A43D3', '5A36BC', 'FFF6EC', 'C6B4F6', ['FF7BC0', 'FFD84A', '6FE3C1', 'FF8A3D'],
                   ['DD559E', 'DDB52A', '45C29F', 'DD6A1E'], '1A1230', 'FF7BC0', 'FFD84A', '1A1230', 'FFF6EC', 'FFF6EC',
                   ['FF7BC0', 'FFD84A', '6FE3C1', 'FF8A3D']),
}
T = {}
def use(name):
    T.clear(); T.update(THEMES[name]); m.LINE = T['line']; m.PAPER = T['sclera']
def C(c): return T[c] if isinstance(c, str) else c
def canvas(): return Image.new('RGBA', (P(W), P(H)), T['bg'])

def status(cv, vol=31, bat=0.7):
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 10, 9, '12:41', 8.5, T['text'], MONO)
    txt(d, 248, 9, f'VOL {vol}', 8.5, T['dim'], MONO, h='r')
    d.rectangle([P(256), P(5), P(279), P(13)], fill=T['panel'])
    d.rectangle([P(256), P(5), P(256 + 23 * bat), P(13)], fill=T['bars'][0])
    d.rectangle([P(280.5), P(7.5), P(282.5), P(10.5)], fill=T['dim'])

def bar(cv, x0, y0, x1, y1, tex, k=0):
    hbar(cv, x0, y0, x1, y1, tex, T['bars'][k % len(T['bars'])], T['texs'][k % len(T['texs'])])
    return ImageDraw.Draw(cv, 'RGBA')

def tip(d, kind, x, y, r, col):
    if kind == 'flower':
        for i in range(5):
            t = -math.pi / 2 + i * 2 * math.pi / 5; px, py = x + r * 0.5 * math.cos(t), y + r * 0.5 * math.sin(t)
            d.ellipse([px - r * 0.42, py - r * 0.42, px + r * 0.42, py + r * 0.42], fill=col)
        d.ellipse([x - r * 0.28, y - r * 0.28, x + r * 0.28, y + r * 0.28], fill=T['body'])
    else: m4.tip(d, kind, x, y, r, col)

# ---------------------------------------------------------------- moon (recoloured by the theme)
MOON = {
    'neutral':        dict(belly='light', pat='stripes', pcol='deep', tips='star', tcol='light', crest=None, pupil='round', lashes=5, opn=1.0, droop=False),
    'bright_intense': dict(belly=YELLOW, pat='zigzag', pcol='body', tips='star', tcol=YELLOW, crest=('spikes', YELLOW), pupil='round', lashes=0, opn=1.0, droop=False),
    'bright_calm':    dict(belly=PINK, pat='dots', pcol='sclera', tips='flower', tcol=PINK, crest=None, pupil='round', lashes=7, opn=0.78, droop=True),
    'dark_intense':   dict(belly='deep', pat='stripes', pcol='bg', tips=None, tcol=None, crest=('horns', 'line'), pupil='slit', lashes=0, opn=1.0, droop=False),
    'dark_calm':      dict(belly=ULTRA, pat='dots', pcol=LILAC, tips='drop', tcol=LILAC, crest=None, pupil='round', lashes=7, opn=0.55, droop=True),
}

def moon(cv, cx, cy, s, stage=4, form='neutral', opn=1.0, look=(0, 0)):
    F = MOON[form]
    cx, cy, s = P(cx), P(cy), P(s)
    u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.05))
    if stage == 1:
        d.ellipse([*u(-0.52, -0.66), *u(0.52, 0.74)], fill=T['body'])
        d.line([u(-0.5, 0.08), u(-0.3, -0.06), u(-0.12, 0.1), u(0.06, -0.06), u(0.24, 0.1), u(0.5, -0.04)], fill=T['bg'],
               width=lw, joint='curve')
        return
    if stage == 2:
        d.ellipse([*u(-0.44, -0.62), *u(0.44, 0.26)], fill=T['body'])
        almond(cv, *u(0, -0.2), s * 0.5, s * 0.26, T['deep'], look, 'round', opn)
        zz = [u(-0.56, 0.16)] + [u(-0.56 + k * 0.14, 0.16 if k % 2 == 0 else 0.02) for k in range(1, 9)]
        d.polygon(zz + m.catmull([u(0.56, 0.16), u(0.5, 0.58), u(0, 0.8), u(-0.5, 0.58), u(-0.56, 0.16)], 8)[1:], fill=T['light'])
        return
    adult = stage >= 4
    for g in (-1, 1):
        d.line([u(g * 0.3, 0.55), u(g * 0.44, 0.98)], fill=T['line'], width=lw)
        d.line([u(g * 0.44, 0.98), u(g * 0.6, 0.98)], fill=T['line'], width=lw)
        if form == 'dark_intense' and adult:
            d.polygon([u(g * 0.37, 0.76), u(g * 0.54, 0.7), u(g * 0.4, 0.84)], fill=T['line'])
        if adult and F['tips']:
            if F['droop']: pts = [u(g * (0.22 + 0.42 * t), -0.62 - 0.3 * math.sin(t * 2.5)) for t in np.linspace(0, 1, 14)]
            else: pts = [u(g * (0.22 + 0.26 * t ** 1.3), -0.62 - 0.34 * t) for t in np.linspace(0, 1, 12)]
            d.line(pts, fill=T['line'], width=lw, joint='curve')
            tip(d, F['tips'], *pts[-1], s * 0.15, C(F['tcol']))
        if adult and F['crest'] and F['crest'][0] == 'horns':
            d.polygon(m.catmull([u(g * 0.22, -0.6), u(g * 0.5, -0.78), u(g * 0.62, -1.06), u(g * 0.74, -0.7), u(g * 0.48, -0.5)], 8,
                                closed=True), fill=C(F['crest'][1]))
    if adult and F['crest'] and F['crest'][0] == 'spikes':
        for x, hgt in ((-0.3, 0.88), (0, 1.04), (0.3, 0.88)):
            d.polygon([u(x - 0.11, -0.62), u(x, -hgt), u(x + 0.11, -0.62)], fill=C(F['crest'][1]))
    box = [*u(-0.7, -0.75), *u(0.7, 0.65)]
    d.chord(box, 180, 360, fill=T['body'])
    d.chord(box, 0, 180, fill=C(F['belly']) if adult else T['light'])
    if adult and F['pat']:
        lay = Image.new('RGBA', cv.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(lay); pc = C(F['pcol'])
        if F['pat'] == 'stripes':
            for k in range(5):
                y = 0.12 + k * 0.11; ld.rectangle([*u(-0.7, y), *u(0.7, y + 0.05)], fill=pc)
        elif F['pat'] == 'zigzag':
            for y in (0.2, 0.42):
                ld.line([u(-0.7 + k * 0.14, y + (0.06 if k % 2 else -0.06)) for k in range(11)], fill=pc, width=int(s * 0.07), joint='curve')
        else:
            for j, y in enumerate((0.22, 0.38, 0.52)):
                for i in range(-3, 4):
                    x = i * 0.2 + (0.1 if j % 2 else 0)
                    ld.ellipse([*u(x - 0.045, y - 0.045), *u(x + 0.045, y + 0.045)], fill=pc)
        mk = Image.new('L', cv.size, 0); ImageDraw.Draw(mk).chord(box, 0, 180, fill=255)
        lay.putalpha(ImageChops.multiply(lay.getchannel('A'), mk)); cv.alpha_composite(lay)
    almond(cv, *u(0, -0.05), s * 0.92, s * 0.46, T['deep'], look, F['pupil'] if adult else 'round',
           opn * (F['opn'] if adult else 1.0), lashes=F['lashes'] if adult else 3)

# ---------------------------------------------------------------- the whaleian: front-on whale on its tail
WHALE = {
    'neutral':        dict(belly='light', pleat='body', spout=3, tips='drop', tcol='light', tusk=False, pupil='round', lashes=0, opn=1.0, droop=False),
    'bright_intense': dict(belly=YELLOW, pleat='body', spout=5, tips='star', tcol=YELLOW, tusk=False, pupil='round', lashes=0, opn=1.0, droop=False),
    'bright_calm':    dict(belly=PINK, pleat='sclera', spout=5, tips='flower', tcol=PINK, tusk=False, pupil='round', lashes=6, opn=0.78, droop=True),
    'dark_intense':   dict(belly='deep', pleat='bg', spout=0, tips=None, tcol=None, tusk=True, pupil='slit', lashes=0, opn=1.0, droop=False),
    'dark_calm':      dict(belly=ULTRA, pleat=LILAC, spout=5, tips='drop', tcol=LILAC, tusk=False, pupil='round', lashes=6, opn=0.55, droop=True),
}
WHALE_HALF = [(0, -0.6), (0.5, -0.58), (0.72, -0.32), (0.72, 0.08), (0.56, 0.4), (0.3, 0.6), (0.15, 0.7), (0.34, 0.78),
              (0.64, 0.82), (0.9, 0.99), (0.52, 1.01), (0.16, 0.92), (0, 0.86)]

def whale(cv, cx, cy, s, stage=4, form='neutral', opn=1.0, look=(0, 0)):
    F = WHALE[form] if stage >= 4 else WHALE['neutral']
    cx, cy, s = P(cx), P(cy), P(s)
    u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.05))
    if stage == 1:       # a drop
        q = s * 0.55
        d.ellipse([cx - q, cy - q + s * 0.25, cx + q, cy + q + s * 0.25], fill=T['body'])
        d.polygon([(cx - q * 0.93, cy + s * 0.05), (cx, cy - s * 0.85), (cx + q * 0.93, cy + s * 0.05)], fill=T['body'])
        r = s * 0.1; d.ellipse([cx - q * 0.5 - r, cy + s * 0.1 - r, cx - q * 0.5 + r, cy + s * 0.1 + r], fill=T['sclera'])
        return
    if stage == 2:       # a calf: round, tiny tail, no spout
        body = [(x * 0.62, y * 0.62 + 0.28) for x, y in WHALE_HALF]
        m.body(d, cx, cy, s, body, T['body'])
        almond(cv, *u(0, 0.12), s * 0.5, s * 0.26, T['deep'], look, 'round', opn)
        return
    n = F['spout'] if stage >= 4 else 2
    for k in range(n):
        a = math.radians(-90 + (k - (n - 1) / 2) * (26 if n > 2 else 34))
        sx = math.cos(a)
        if F['droop']:      # water falling back down
            pts = [u(sx * 0.75 * t, -0.6 - 0.42 * math.sin(t * math.pi * 0.85) + 0.1 * t) for t in np.linspace(0, 1, 14)]
        else:               # a fountain: up, then curling out
            pts = [u(sx * 0.55 * t ** 1.5, -0.6 - 0.48 * math.sin(t * math.pi * 0.62) * (1 - abs(sx) * 0.3)) for t in np.linspace(0, 1, 14)]
        d.line(pts, fill=T['line'], width=int(lw * 1.4), joint='curve')
        if stage >= 4 and F['tips']: tip(d, F['tips'], *pts[-1], s * 0.12, C(F['tcol']))
        else: tip(d, 'drop', *pts[-1], s * 0.09, T['line'])
    if stage >= 4 and F['tusk']:
        d.polygon([u(-0.08, -0.58), u(0, -1.08), u(0.08, -0.58)], fill=T['line'])
        for y in (-0.68, -0.8, -0.92):
            d.line([u(-0.06, y + 0.04), u(0.05, y - 0.03)], fill=T['bg'], width=max(1, lw // 2))
    for g in (-1, 1):
        leaf(d, *u(g * 0.62, 0.22), math.pi / 2 - g * 0.95, s * 0.42, s * 0.2, T['body'])
    m.body(d, cx, cy, s, WHALE_HALF, T['body'])
    if stage >= 4:
        lay = Image.new('RGBA', cv.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
        ld.ellipse([*u(-0.46, -0.04), *u(0.46, 0.7)], fill=C(F['belly']))
        for x in (-0.3, -0.15, 0, 0.15, 0.3):
            ld.line([u(x, 0.04), u(x * 0.8, 0.66)], fill=C(F['pleat']), width=max(2, int(s * 0.04)))
        mk = Image.new('L', cv.size, 0)
        full = WHALE_HALF + [(-x, y) for (x, y) in reversed(WHALE_HALF[1:-1])]
        ImageDraw.Draw(mk).polygon(m.catmull([(cx + x * s, cy + y * s) for x, y in full], 14, closed=True), fill=255)
        mk2 = Image.new('L', cv.size, 0); ImageDraw.Draw(mk2).rectangle([0, 0, cv.width, u(0, 0.62)[1]], fill=255)
        lay.putalpha(ImageChops.multiply(ImageChops.multiply(lay.getchannel('A'), mk), mk2)); cv.alpha_composite(lay)
        d = ImageDraw.Draw(cv, 'RGBA')
    d.arc([*u(-0.52, -0.42), *u(0.52, 0.04)], 25, 155, fill=INK, width=lw)
    almond(cv, *u(0, -0.3), s * 0.8, s * 0.42, T['deep'], look, F['pupil'] if stage >= 4 else 'round',
           opn * (F['opn'] if stage >= 4 else 1.0), lashes=F['lashes'] if stage >= 4 else 0)

# ---------------------------------------------------------------- sapling (recoloured)
SAP = {
    'neutral':        dict(leaf='light', lw=0.42, extra=None, ecol=None, pupil='round', opn=1.0, lashes=0),
    'bright_intense': dict(leaf=YELLOW, lw=0.26, extra='blossom', ecol=YELLOW, pupil='round', opn=1.0, lashes=0),
    'bright_calm':    dict(leaf=PINK, lw=0.6, extra='flower', ecol=PINK, pupil='round', opn=0.78, lashes=5),
    'dark_intense':   dict(leaf='light', lw=0.2, extra='thorns', ecol='line', pupil='slit', opn=1.0, lashes=0),
    'dark_calm':      dict(leaf=LILAC, lw=0.5, extra='willow', ecol=LILAC, pupil='round', opn=0.55, lashes=5),
}
def sapling(cv, cx, cy, s, stage=4, form='neutral', opn=1.0, look=(0, 0), look2=None):
    F = SAP[form] if stage >= 4 else SAP['neutral']
    look2 = look if look2 is None else look2
    cx, cy, s = P(cx), P(cy), P(s)
    u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.05)); B = T['body']
    if stage == 1:
        leaf(d, *u(0, -0.5), -math.pi / 2 - 0.5, s * 0.42, s * 0.2, T['light'])
        d.ellipse([*u(-0.42, -0.5), *u(0.42, 0.62)], fill=B)
        d.line([u(0, -0.5), u(-0.08, -0.28), u(0.06, -0.1), u(-0.04, 0.06)], fill=T['bg'], width=lw)
        return
    for g in (-1, 1):
        d.line([u(g * 0.5 * t, 0.86 + 0.14 * math.sin(t * 2.2)) for t in np.linspace(0, 1, 10)], fill=T['line'], width=lw, joint='curve')
    d.line([u(0, 0.86), u(0, 1.0)], fill=T['line'], width=lw)
    if stage == 2:
        d.line([u(0, 0.9), u(0, -0.1)], fill=B, width=int(s * 0.12))
        for g in (-1, 1): leaf(d, *u(0, 0.45), -math.pi / 2 + g * 1.0, s * 0.4, s * 0.2, T['light'])
        r = s * 0.28; d.ellipse([cx - r, cy - s * 0.32 - r, cx + r, cy - s * 0.32 + r], fill=B)
        almond(cv, cx, cy - s * 0.32, s * 0.36, s * 0.19, T['deep'], look, 'round', opn)
        return
    hr, hx_, hy = (0.21, 0.36, -0.36) if stage == 3 else (0.3, 0.44, -0.46)
    tw_ = int(s * (0.12 if stage == 3 else 0.17))
    d.line([u(0, 0.92), u(0, 0.12)], fill=B, width=tw_)
    for g in (-1, 1):
        br = m.catmull([u(0, 0.18), u(g * 0.12, 0.0), u(g * hx_ * 0.8, hy + 0.2), u(g * hx_, hy)], 8)
        d.line(br, fill=B, width=int(tw_ * 0.75), joint='curve')
        if stage >= 4:
            leaf(d, *u(g * 0.02, 0.5), -math.pi / 2 + g * 1.15, s * 0.42, s * F['lw'] * 0.5, C(F['leaf']))
            if F['extra'] == 'thorns':
                for t in (0.35, 0.65):
                    px, py = br[int(t * (len(br) - 1))]
                    d.polygon([(px - s * 0.06, py + s * 0.02), (px + g * s * 0.18, py - s * 0.12), (px + s * 0.06, py + s * 0.05)], fill=C(F['ecol']))
    for g, lk in ((-1, look), (1, look2)):
        hxp, hyp = u(g * hx_, hy); r = s * hr
        if stage >= 4:
            if F['extra'] == 'willow':
                for k in (-0.6, 0, 0.6):
                    px, py = hxp + k * r, hyp + r * 0.6
                    pts = [(px + g * k * s * 0.05 * t, py + s * 0.62 * t) for t in np.linspace(0, 1, 6)]
                    d.line(pts, fill=C(F['ecol']), width=lw); tip(d, 'drop', *pts[-1], s * 0.08, C(F['ecol']))
            elif F['extra'] == 'thorns':
                d.polygon(m.catmull([(hxp + g * r * 0.1, hyp - r * 0.8), (hxp + g * r * 0.6, hyp - r * 1.2), (hxp + g * r * 0.75, hyp - r * 1.75),
                                     (hxp + g * r * 1.0, hyp - r * 0.95), (hxp + g * r * 0.75, hyp - r * 0.5)], 8, closed=True), fill=C(F['ecol']))
            elif F['extra'] in ('blossom', 'flower'):
                tip(d, 'star' if F['extra'] == 'blossom' else 'flower', hxp + g * r * 0.55, hyp - r * 1.05, s * 0.17, C(F['ecol']))
            else:
                leaf(d, hxp + g * r * 0.3, hyp - r * 0.85, -math.pi / 2 + g * 0.55, s * 0.3, s * F['lw'] * 0.38, C(F['leaf']))
        d.ellipse([hxp - r, hyp - r, hxp + r, hyp + r], fill=B)
        almond(cv, hxp, hyp, r * 1.45, r * 0.74, T['deep'], lk, F['pupil'], opn * F['opn'], lashes=F['lashes'])

SPECIES = {'moon': moon, 'whaleian': whale, 'sapling': sapling}
FORMS = [('egg', 1, 'neutral'), ('hatchling', 2, 'neutral'), ('young', 3, 'neutral'), ('neutral', 4, 'neutral'),
         ('bright & calm', 4, 'bright_calm'), ('bright & intense', 4, 'bright_intense'), ('dark & calm', 4, 'dark_calm'),
         ('dark & intense', 4, 'dark_intense')]
PET = ('moon', 4, 'bright_intense')

def draw_pet(cv, x, y, s, look=(0, 0), opn=1.0, sp=None):
    k, st, f = sp or PET
    SPECIES[k](cv, x, y, s, st, f, opn, look)

def silhouette(cv, fn, colour):
    lay = Image.new('RGBA', cv.size, (0, 0, 0, 0)); fn(lay)
    sil = Image.new('RGBA', cv.size, colour); sil.putalpha(lay.getchannel('A')); cv.alpha_composite(sil)

# ---------------------------------------------------------------- lists, themed
MARKS = ['circle', 'moon', 'tri', 'square', 'pill', 'heart']
def mark(d, k, x, y, c):
    X, Y, r = P(x), P(y), P(4.3)
    if k == 'circle': d.ellipse([X - r, Y - r, X + r, Y + r], fill=c)
    elif k == 'moon': d.chord([X - r, Y - r, X + r, Y + r], 90, 270, fill=c)
    elif k == 'tri': d.polygon([(X - r, Y + r), (X, Y - r), (X + r, Y + r)], fill=c)
    elif k == 'square': d.rectangle([X - r * 0.85, Y - r * 0.85, X + r * 0.85, Y + r * 0.85], fill=c)
    elif k == 'pill': d.rounded_rectangle([X - r * 1.2, Y - r * 0.6, X + r * 1.2, Y + r * 0.6], radius=r * 0.6, fill=c)
    else: m.glyph(d, 'heart', x, y, 10, c)

def menu(title, rows, sel, tex, crumb=None, values=None, y0=80, pitch=26, show_pet=True, look=(-0.8, 0.6)):
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv)
    if crumb: txt(d, 14, 25, crumb, 7.5, T['dim'], MONO, track=1)
    txt(d, 14, 44, title, 30, T['text'])
    if show_pet: draw_pet(cv, 262, 46, 19, look); d = ImageDraw.Draw(cv, 'RGBA')
    for i, label in enumerate(rows):
        y = y0 + i * pitch
        on = i == sel
        if on: d = bar(cv, 10, y - 11, 278, y + 11, tex, k=i)
        fg = T['bartext'] if on else T['text']
        if values is None:
            mk = T['marks'][i % len(T['marks'])]
            mark(d, MARKS[i % 6], 22, y, T['bartext'] if on else mk)
            txt(d, 36, y, label, 15, fg, BOLD)
            if on: txt(d, 270, y, '12', 8.5, fg, MONO, h='r')
        else:
            txt(d, 18, y, label, 14, fg, BOLD)
            v = values[i]
            txt(d, 270, y, f'‹  {v}  ›' if on else v, 11.5, fg if on else T['dim'], MED, h='r')
    d.line([(P(287), P(y0 - 10)), (P(287), P(y0 + pitch * (len(rows) - 1) + 10))], fill=T['panel'], width=P(1.2))
    t0 = y0 - 10 + (sel / max(1, len(rows))) * pitch * len(rows)
    d.rectangle([P(285.5), P(t0), P(288.5), P(t0 + 22)], fill=T['bars'][0])
    return cv

MUSIC = ['all songs', 'artists', 'albums', 'genres', 'playlists', 'favourites']
def colourway(name, tex):
    def f():
        use(name); return menu('music', MUSIC, 2, tex)
    return f

def look_page():
    use('black')
    cv = menu('look', ['colours', 'highlight', 'creature', 'show creature', 'eye follows you', 'album art'], 0, 'lines',
              crumb='SETTINGS', values=['black & orange', 'mix', 'moon  ›', 'on', 'on', 'square'], y0=74, pitch=22)
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 14, 203, 'COLOURWAYS', 7, T['dim'], MONO, track=1)
    for i, k in enumerate(['black', 'paper', 'eva', 'aqua', 'candy']):
        th = THEMES[k]; x = 14 + i * 55
        d.rectangle([P(x), P(211), P(x + 47), P(230)], fill=th['bg'], outline=T['panel'] if k == 'black' else None, width=P(1))
        for j, c in enumerate(th['bars'][:4] if k == 'candy' else [th['bars'][0]]):
            w = 30 / (4 if k == 'candy' else 1)
            d.rectangle([P(x + 9 + j * w), P(217), P(x + 9 + (j + 1) * w), P(224)], fill=c)
        if k == 'black': d.rectangle([P(x - 2), P(209), P(x + 49), P(232)], outline=T['text'], width=P(1))
    return cv

# ---------------------------------------------------------------- gallery
MET = {'egg': '12 OCT', 'hatchling': '14 OCT', 'young': '19 OCT', 'neutral': '28 OCT', 'bright & calm': '9 NOV',
       'bright & intense': '22 NOV'}
def gallery(sel=5, species='moon'):
    use('black')
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv)
    txt(d, 14, 31, 'gallery', 18, T['text'])
    txt(d, 150, 32, f'{len(MET)} OF 8 MET', 7, T['dim'], MONO, h='m', track=0.6)
    txt(d, 282, 31, f'‹  {species}  ›', 11.5, T['text'], SEMI, h='r')
    for i, (name, st, form) in enumerate(FORMS):
        x0, y0 = 10 + (i % 4) * 70, 46 + (i // 4) * 86
        on, met = i == sel, name in MET
        if on: d.rectangle([P(x0), P(y0), P(x0 + 66), P(y0 + 82)], fill=T['panel'])
        fn = lambda c, st=st, form=form, x0=x0, y0=y0: SPECIES[species](c, x0 + 33, y0 + 28, 18, st, form, 1, (0, 0.2))
        if met: fn(cv)
        else: silhouette(cv, fn, mix(T['panel'], T['dim'], 0.3))
        d = ImageDraw.Draw(cv, 'RGBA')
        if on: d = bar(cv, x0, y0 + 56, x0 + 66, y0 + 82, 'dots')
        fg = T['bartext'] if on else (T['text'] if met else T['dim'])
        txt(d, x0 + 33, y0 + 64, name if met else '???', 7.5, fg, SEMI, h='m')
        txt(d, x0 + 33, y0 + 75, MET.get(name, 'not met yet'), 6.3, fg if on else T['dim'], MONO, h='m', track=0.3)
    txt(d, 14, 229, 'A  keep this form    START  new pet', 7, T['dim'], MONO, track=0.6)
    return cv

def gallery_choose():
    cv = gallery()
    cv.alpha_composite(Image.new('RGBA', cv.size, T['bg'][:3] + (200,)))
    d = ImageDraw.Draw(cv, 'RGBA')
    d.rectangle([P(18), P(40), P(278), P(212)], fill=T['panel'])
    moon(cv, 66, 122, 34, 4, 'bright_intense', 1, (0.5, 0))
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 118, 62, 'moon', 22, T['text'])
    txt(d, 118, 81, 'BRIGHT & INTENSE', 7, T['bars'][0], MONO, track=0.8)
    txt(d, 118, 95, 'met 22 Nov 2026', 9.5, T['dim'], MED)
    for i, opt in enumerate(['keep this form', 'start a new pet', 'back']):
        y = 128 + i * 24
        if i == 0: d = bar(cv, 110, y - 10, 270, y + 10, 'waves')
        txt(d, 120, y, opt, 12.5, T['bartext'] if i == 0 else T['text'], BOLD)
    txt(d, 118, 200, 'it stops changing until you pick again', 7.8, T['dim'], MED)
    return cv

# ---------------------------------------------------------------- creature picker with the whaleian
def picker(sel=5):
    use('black')
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv)
    txt(d, 14, 32, 'pick a creature', 16, T['text'])
    ORANGE, CREAM, DEEP = T['body'], T['light'], T['deep']
    picks = [('moon', None), ('arch', (ORANGE, CREAM, DEEP)), ('sapling', None), ('dome', (CREAM, ORANGE, DEEP)),
             ('star', (ORANGE, CREAM, DEEP)), ('whaleian', None)]
    for i, (k, cols) in enumerate(picks):
        cx0, cy0 = 10 + (i % 3) * 96, 46 + (i // 3) * 86
        on = i == sel
        if on: d.rectangle([P(cx0), P(cy0), P(cx0 + 92), P(cy0 + 82)], fill=T['panel'])
        ccx, ccy = cx0 + 46, cy0 + 34
        if k == 'moon': moon(cv, ccx, ccy, 22, 4, 'neutral', 1 if on else 0, (0, 0.3))
        elif k == 'sapling': sapling(cv, ccx, ccy + 1, 23, 4, 'neutral', 1 if on else 0, (0.5, 0.3), (-0.5, 0.3))
        elif k == 'whaleian': whale(cv, ccx, ccy + 2, 23, 4, 'neutral', 1 if on else 0, (0, 0.3))
        else: m.creature(cv, k, ccx, ccy, 22, cols, opn=1 if on else 0, **({'bg': T['panel'] if on else T['bg']} if k == 'arch' else {}))
        d = ImageDraw.Draw(cv, 'RGBA')
        if on: d = bar(cv, cx0, cy0 + 66, cx0 + 92, cy0 + 82, 'dots')
        txt(d, ccx, cy0 + 74, k, 11, T['bartext'] if on else T['dim'], BOLD, h='m')
    txt(d, 14, 229, 'or none: hide the creature in Settings > Look', 8.5, T['dim'], MED)
    return cv

QUADS = [('bright_calm', 74, 62, 'bright & calm'), ('bright_intense', 222, 62, 'bright & intense'),
         ('dark_calm', 74, 176, 'dark & calm'), ('dark_intense', 222, 176, 'dark & intense'), ('neutral', 148, 119, 'neutral')]
def whale_adults():
    use('black')
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    d.line([(P(34), P(119)), (P(258), P(119))], fill=T['panel'], width=P(1.2))
    d.line([(P(148), P(18)), (P(148), P(226))], fill=T['panel'], width=P(1.2))
    txt(d, 148, 10, 'BRIGHT', 7, T['dim'], MONO, h='m', track=1)
    txt(d, 148, 233, 'DARK', 7, T['dim'], MONO, h='m', track=1)
    txt(d, 6, 119, 'CALM', 7, T['dim'], MONO, track=1)
    txt(d, 291, 119, 'INTENSE', 7, T['dim'], MONO, h='r', track=0.6)
    txt(d, 8, 10, 'WHALEIAN', 7, T['bars'][0], MONO, track=1)
    d.ellipse([P(118), P(89), P(178), P(149)], fill=T['bg'])
    for form, x, y, name in QUADS:
        whale(cv, x, y, 24, 4, form, 1, (0, 0.2))
        d = ImageDraw.Draw(cv, 'RGBA')
        txt(d, x + (34 if form == 'neutral' else 0), y + (0 if form == 'neutral' else 37), name, 9.5, T['text'], SEMI,
            h='l' if form == 'neutral' else 'm')
    return cv

# ---------------------------------------------------------------- home and Now Playing with the pet's real forms
def home(name='black', sp=None):
    use(name)
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    m.blob(d, 148, 126, 78, 80, T['panel'], 14, 0.07)
    if sp and sp[0] == 'sapling': sapling(cv, 148, 128, 60, sp[1], sp[2], 1, (1, 0))
    else: draw_pet(cv, 148, 130, 56, (1, 0), sp=sp)
    d = ImageDraw.Draw(cv, 'RGBA')
    for label, x, y in (('now playing', 148, 30), ('games', 148, 228), ('settings', 37, 128)):
        txt(d, x, y, label, 12, T['dim'], h='m')
    d = bar(cv, 236, 119, 288, 137, 'dots')
    txt(d, 262, 128, 'music', 13, T['bartext'], h='m')
    status(cv)
    return cv

def now_playing(name='black', progress=0.43):
    use(name)
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    m.blob(d, 70, 114, 52, 50, T['bars'][0], 11, 0.08)
    cv.paste(m.cover(P(100)), (P(18), P(30)))
    status(cv)
    X = 134
    txt(d, X, 38, '03/12 · FLAC 24/96', 8, T['dim'], MONO)
    txt(d, X, 61, 'Soft', 23, T['text'])
    txt(d, X, 85, 'Machinery', 23, T['text'])
    txt(d, X, 106, 'Pale Fauna', 13, T['bars'][0], BOLD)
    txt(d, X, 121, 'Lantern Hours', 11, T['dim'], MED)
    m.glyph(d, 'shuffle', X + 7, 141, 13, T['bars'][0])
    m.glyph(d, 'repeat', X + 31, 141, 13, mix(T['dim'], T['bg'], 0.4))
    m.glyph(d, 'heart', X + 54, 141, 13, T['bars'][0])
    y, x0, x1 = 198, 16, 282
    fx = x0 + (x1 - x0) * progress
    d.line([(P(fx), P(y)), (P(x1), P(y))], fill=mix(T['dim'], T['bg'], 0.3), width=P(1.2))
    d = bar(cv, x0, y - 3, fx, y + 3, 'lines')
    almond(cv, P(fx), P(y), P(16), P(9), T['bars'][0], (1, 0))
    draw_pet(cv, 262, y - 19, 19, (-1, 0))
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, x0, 220, '1:42', 8.5, T['text'], MONO)
    txt(d, x1, 220, '-2:13', 8.5, T['dim'], MONO, h='r')
    txt(d, 92, 220, 'NEXT', 8, T['dim'], MONO)
    txt(d, 118, 220, 'Moth Radio', 9.5, T['text'], SEMI)
    return cv

def growing():
    """young stages of all three species, then one of five adults"""
    use('black')
    cv = canvas()
    d = ImageDraw.Draw(cv, 'RGBA')
    rows = (('MOON', moon, ('egg', 'hatchling', 'young')), ('SAPLING', sapling, ('seed', 'sprout', 'young')),
            ('WHALEIAN', whale, ('drop', 'calf', 'young')))
    for r, (name, fn, labels) in enumerate(rows):
        y = 40 + r * 72
        txt(d, 8, y - 30, name, 6.5, T['bars'][0], MONO, track=1)
        for i, lab in enumerate(labels):
            x = 30 + i * 50
            fn(cv, x, y, 14.5, i + 1, 'neutral', 1 if i else 0, (0, 0.2))
            d = ImageDraw.Draw(cv, 'RGBA')
            txt(d, x, y + 24, lab, 8, T['text'], SEMI, h='m')
        d.polygon([(P(166), P(y - 4)), (P(172), P(y)), (P(166), P(y + 4))], fill=T['dim'])
        for form, ox, oy in (('bright_calm', -26, -16), ('bright_intense', 26, -16), ('dark_calm', -26, 16),
                             ('dark_intense', 26, 16), ('neutral', 0, 0)):
            fn(cv, 232 + ox, y + oy, 8, 4, form, 1, (0, 0.2))
        d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 8, 230, 'adult at 20 h of listening · form re-decided every 10 h after that', 7.6, T['dim'], MED)
    return cv

SCREENS = [('look', look_page, 'Settings > Look: colourways, highlight mix, hide creature'),
           ('gallery', gallery, 'Gallery: every form met, and when (moon page)'),
           ('gallery_choose', gallery_choose, 'Gallery: keep a form, or start a new pet'),
           ('picker', picker, 'New pet: the whaleian replaces the dandelion'),
           ('whale_adults', whale_adults, 'Whaleian: its five adult forms'),
           ('cw_black', colourway('black', 'lines'), 'Colourway: black & orange'),
           ('cw_paper', colourway('paper', 'dots'), 'Colourway: paper & orange'),
           ('cw_eva', colourway('eva', 'waves'), 'Colourway: EVA'),
           ('cw_aqua', colourway('aqua', 'lines'), 'Colourway: aqua'),
           ('cw_candy', colourway('candy', 'dots'), 'Colourway: candy')]

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
