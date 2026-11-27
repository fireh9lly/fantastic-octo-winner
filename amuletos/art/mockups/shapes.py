#!/usr/bin/env python3
"""UI mock-up building blocks (296x240 screen): flat blobs, painted strokes, almond eyes, symmetrical one-eyed
beings. Its own main renders the paper-background round (take 2). PC renders only: drawn at 4x, scaled down and
rounded to RGB565 like the real screen."""
import math, random, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
S = 4
W, H = 296, 240
def P(v): return int(round(v * S))

FI = '/usr/share/fonts/opentype/inter/'
BLACK, BOLD, SEMI, MED = (FI + 'InterDisplay-Black.otf', FI + 'InterDisplay-Bold.otf', FI + 'InterDisplay-SemiBold.otf',
                          FI + 'InterDisplay-Medium.otf')
MONO = '/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf'
_fc = {}
def font(px, f=BLACK):
    if (px, f) not in _fc: _fc[(px, f)] = ImageFont.truetype(f, P(px))
    return _fc[(px, f)]

def hx(s): s = s.lstrip('#'); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
def mix(a, b, t): return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3)) + (255,)

PAPER, INK = hx('F1ECE1'), hx('161414')
VERM, ULTRA, PINK, OCHRE = hx('EE4B2B'), hx('2C46D8'), hx('F49AC1'), hx('F2B33D')
MOSS, LILAC, CHART, PEACH = hx('2E7A4E'), hx('B9A5F0'), hx('D5E35A'), hx('F6B48C')
GREY = mix(INK, PAPER, 0.45)
LINE = INK     # colour of limbs and stalks drawn outside a body (set per background)

# ---------------------------------------------------------------- geometry
def catmull(pts, n=14, closed=False):
    out, L = [], len(pts)
    for i in (range(L) if closed else range(L - 1)):
        p0 = pts[(i - 1) % L] if closed else pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[(i + 1) % L]
        p3 = pts[(i + 2) % L] if closed else pts[min(i + 2, L - 1)]
        for k in range(n):
            t = k / n; t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed: out.append(pts[-1])
    return out

def blob_pts(cx, cy, rx, ry, seed, amp=0.09, rot=0.0):
    rnd = random.Random(seed)
    terms = [(k, rnd.uniform(0.4, 1.0) * amp * (2.4 / k), rnd.uniform(0, 6.283)) for k in (2, 3, 4, 5)]
    ca, sa, pts = math.cos(rot), math.sin(rot), []
    for i in range(300):
        th = 6.2832 * i / 300
        r = 1 + sum(a * math.sin(k * th + ph) for k, a, ph in terms)
        x, y = rx * r * math.cos(th), ry * r * math.sin(th)
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts

def blob(d, cx, cy, rx, ry, col, seed, amp=0.09, rot=0.0):
    d.polygon(blob_pts(P(cx), P(cy), P(rx), P(ry), seed, amp, rot), fill=col)

def daub(im, pts, width, col, seed=1, dry=0.5):
    """a painted brush stroke along pts (1x coords): bristles that start and stop unevenly"""
    rnd = random.Random(seed)
    c = catmull([(P(x), P(y)) for x, y in pts], 30)
    Ls = [0.0]
    for i in range(1, len(c)): Ls.append(Ls[-1] + math.hypot(c[i][0] - c[i - 1][0], c[i][1] - c[i - 1][1]))
    tot = Ls[-1]
    N = []
    for i in range(len(c)):
        a, b = c[max(0, i - 1)], c[min(len(c) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]; l = math.hypot(dx, dy) or 1
        N.append((-dy / l, dx / l))
    Wd = P(width)
    nb = max(8, int(Wd / P(0.9)))
    bw = int(Wd / nb * 1.7) + 1
    d = ImageDraw.Draw(im, 'RGBA')
    for b in range(nb):
        o = (b + 0.5) / nb - 0.5
        e = abs(o) * 2
        t0 = rnd.uniform(0, 0.02 + 0.07 * e ** 2)
        t1 = 1 - rnd.uniform(0, 0.03 + 0.22 * e ** 1.5) * (0.5 + dry)
        gaps = []
        if rnd.random() < dry * 0.5:
            g = rnd.uniform(0.6, 0.92); gaps.append((g, g + rnd.uniform(0.03, 0.1)))
        sh = rnd.uniform(-1, 1) * 9
        cb = tuple(max(0, min(255, int(col[i] + sh))) for i in range(3)) + (255,)
        seg = []
        for (x, y), l, (nx, ny) in zip(c, Ls, N):
            t = l / tot
            if t < t0 or t > t1 or any(g0 < t < g1 for g0, g1 in gaps):
                if len(seg) > 1: d.line(seg, fill=cb, width=bw, joint='curve')
                seg = []; continue
            w = Wd * (0.86 + 0.14 * math.sin(math.pi * t)) * (1 + 0.05 * math.sin(t * 11 + b * 1.3))
            seg.append((x + nx * o * w, y + ny * o * w))
        if len(seg) > 1: d.line(seg, fill=cb, width=bw, joint='curve')

def comp(cv, im, x, y):
    x, y = int(x), int(y)
    sx, sy, dx, dy = max(0, -x), max(0, -y), max(0, x), max(0, y)
    w, h = min(im.width - sx, cv.width - dx), min(im.height - sy, cv.height - dy)
    if w > 0 and h > 0: cv.alpha_composite(im.crop((sx, sy, sx + w, sy + h)), (dx, dy))

CAP = 0.727
def txt(d, x, y, s, px, fill, f=BLACK, h='l', track=0.0):
    """x, y in 1x; y is the middle of the capitals"""
    F = font(px, f)
    by = P(y) + P(px) * CAP / 2
    if not track:
        d.text((P(x), by), s, font=F, fill=fill, anchor=h + 's'); return
    wid = sum(F.getlength(ch) for ch in s) + P(track) * (len(s) - 1)
    X = P(x) - (wid / 2 if h == 'm' else wid if h == 'r' else 0)
    for ch in s:
        d.text((X, by), ch, font=F, fill=fill, anchor='ls'); X += F.getlength(ch) + P(track)

def tw(s, px, f=BLACK): return font(px, f).getlength(s) / S

# ---------------------------------------------------------------- eyes and creatures (4x coords inside)
def eye(d, cx, cy, r, iris, opn=1.0, look=(0, 0), pupil='round', lid=None, ir=0.58):
    lw = max(2, int(r * 0.16))
    if opn <= 0.02:
        R = r * 0.95
        d.arc([cx - R, cy - R * 1.25, cx + R, cy + R * 0.65], 28, 152, fill=INK, width=lw)
        for a in (55, 90, 125):
            t = math.radians(a)
            x0, y0 = cx + R * math.cos(t), cy - R * 0.3 + R * 0.95 * math.sin(t)
            d.line([(x0, y0), (x0 + R * 0.28 * math.cos(t), y0 + R * 0.28 * math.sin(t))], fill=INK, width=lw)
        return
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PAPER)
    rr = r * ir
    lx, ly = look[0] * (r - rr) * 0.85, look[1] * (r - rr) * 0.85
    ix, iy = cx + lx, cy + ly
    d.ellipse([ix - rr, iy - rr, ix + rr, iy + rr], fill=iris)
    pr = rr * 0.52
    if pupil == 'round':
        d.ellipse([ix - pr, iy - pr, ix + pr, iy + pr], fill=INK)
    elif pupil == 'slit':
        d.ellipse([ix - pr * 0.36, iy - pr * 1.5, ix + pr * 0.36, iy + pr * 1.5], fill=INK)
    elif pupil == 'goat':
        d.rounded_rectangle([ix - pr * 1.5, iy - pr * 0.42, ix + pr * 1.5, iy + pr * 0.42], radius=pr * 0.42, fill=INK)
    elif pupil == 'ring':
        d.ellipse([ix - pr * 1.25, iy - pr * 1.25, ix + pr * 1.25, iy + pr * 1.25], fill=INK)
        q = pr * 0.62; d.ellipse([ix - q, iy - q, ix + q, iy + q], fill=iris)
        q = pr * 0.28; d.ellipse([ix - q, iy - q, ix + q, iy + q], fill=INK)
    elif pupil == 'star':
        pts = []
        for i in range(8):
            a = -math.pi / 2 + i * math.pi / 4; q = pr * (1.35 if i % 2 == 0 else 0.42)
            pts.append((ix + q * math.cos(a), iy + q * math.sin(a)))
        d.polygon(pts, fill=INK)
    g = rr * 0.17
    d.ellipse([ix - pr * 0.55 - g, iy - pr * 0.6 - g, ix - pr * 0.55 + g, iy - pr * 0.6 + g], fill=PAPER)
    if opn < 1 and lid:
        h = -r + 2 * r * (1 - opn)        # lid edge, relative to the centre
        a = math.degrees(math.asin(max(-1, min(1, -h / r))))
        d.chord([cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1], 180 + a, 360 - a, fill=lid)
        w = math.sqrt(max(0, r * r - h * h))
        d.line([(cx - w, cy + h), (cx + w, cy + h)], fill=INK, width=lw)

def body(d, cx, cy, s, half, col, n=14):
    full = half + [(-x, y) for (x, y) in reversed(half[1:-1])]
    d.polygon(catmull([(cx + x * s, cy + y * s) for x, y in full], n, closed=True), fill=col)

def mirror(fn):
    for g in (-1, 1): fn(g)

def U(cx, cy, s): return lambda x, y: (cx + x * s, cy + y * s)

def mouth(d, cx, cy, s, kind, col=INK, bg=None):
    u = U(cx, cy, s); lw = max(2, int(s * 0.06))
    if kind == 'fangs':
        d.line([u(-0.24, 0), u(0.24, 0)], fill=col, width=lw)
        mirror(lambda g: d.polygon([u(g * 0.06, 0), u(g * 0.17, 0), u(g * 0.115, 0.13)], fill=PAPER))
    elif kind == 'teeth':
        x0, y0 = u(-0.26, -0.07); x1, y1 = u(0.26, 0.09)
        d.rounded_rectangle([x0, y0, x1, y1], radius=s * 0.05, fill=INK)
        for k in range(4):
            a, _ = u(-0.22 + k * 0.115, 0); b, _ = u(-0.22 + k * 0.115 + 0.09, 0)
            d.rectangle([a, y0 + s * 0.03, b, y0 + s * 0.09], fill=PAPER)
    elif kind == 'zig':
        pts = [u(-0.26 + k * 0.065, 0.04 * (1 if k % 2 else -1)) for k in range(9)]
        d.line(pts, fill=col, width=lw, joint='curve')
    elif kind == 'o':
        x0, y0 = u(-0.07, -0.06); x1, y1 = u(0.07, 0.08); d.ellipse([x0, y0, x1, y1], fill=col)
    elif kind == 'line':
        d.line([u(-0.14, 0), u(0.14, 0)], fill=col, width=lw)

def horned(d, cx, cy, s, c, opn=1.0, look=(0, 0)):
    """egg body, curved horns, fangs, spots. c = (body, accent, iris)"""
    bd, ac, ir = c; u = U(cx, cy, s)
    mirror(lambda g: d.polygon([u(g * 0.18, -0.6), u(g * 0.5, -0.58), u(g * 0.66, -0.86), u(g * 0.58, -1.04),
                                u(g * 0.46, -0.82)], fill=ac))
    body(d, cx, cy, s, [(0, -0.74), (0.4, -0.7), (0.7, -0.4), (0.8, 0.08), (0.7, 0.56), (0.42, 0.86), (0, 0.9)], bd)
    mirror(lambda g: d.rounded_rectangle([*u(g * 0.32 - 0.15, 0.82), *u(g * 0.32 + 0.15, 1.0)], radius=s * 0.06, fill=ac))
    for x, y, r in ((0.56, 0.2, 0.07), (0.46, 0.4, 0.045)):
        mirror(lambda g, x=x, y=y, r=r: d.ellipse([*u(g * x - r, y - r), *u(g * x + r, y + r)], fill=ac))
    eye(d, *u(0, -0.16), s * 0.4, ir, opn, look, 'round', bd)
    mouth(d, *u(0, 0.44), s, 'fangs')

def squid(d, cx, cy, s, c, opn=1.0, look=(0, 0)):
    bd, ac, ir = c; u = U(cx, cy, s)
    lw = int(s * 0.17)
    for k, x0 in enumerate((-0.62, -0.31, 0, 0.31, 0.62)):
        g = 0 if x0 == 0 else math.copysign(1, x0)
        pts = [u(x0 + g * 0.06 * t + 0.07 * math.sin(t * 5.5) * (g if g else 1) * (0 if g == 0 else 1), 0.1 + 0.82 * t)
               for t in [i / 16 for i in range(17)]]
        d.line(pts, fill=bd, width=lw, joint='curve')
        ex, ey = pts[-1]; q = lw / 2; d.ellipse([ex - q, ey - q, ex + q, ey + q], fill=bd)
    body(d, cx, cy, s, [(0, -0.92), (0.5, -0.86), (0.82, -0.46), (0.88, 0.04), (0.76, 0.24), (0, 0.24)], bd)
    for x in (0.18, 0.5):
        mirror(lambda g, x=x: d.ellipse([*u(g * x - 0.075, 0.04), *u(g * x + 0.075, 0.19)], fill=ac))
    eye(d, *u(0, -0.4), s * 0.37, ir, opn, look, 'goat', bd)

def boxy(d, cx, cy, s, c, opn=1.0, look=(0, 0)):
    bd, ac, ir = c; u = U(cx, cy, s)
    lw = max(2, int(s * 0.07))
    mirror(lambda g: (d.line([u(g * 0.28, -0.46), u(g * 0.5, -0.86)], fill=INK, width=lw),
                      d.ellipse([*u(g * 0.5 - 0.1, -0.96), *u(g * 0.5 + 0.1, -0.76)], fill=ac)))
    mirror(lambda g: d.ellipse([*u(g * 0.86 - 0.13, 0.12), *u(g * 0.86 + 0.13, 0.5)], fill=ac))
    d.rounded_rectangle([*u(-0.74, -0.52), *u(0.74, 0.9)], radius=s * 0.34, fill=bd)
    eye(d, *u(0, -0.02), s * 0.38, ir, opn, look, 'ring', bd)
    mouth(d, *u(0, 0.58), s, 'teeth')

def flower(d, cx, cy, s, c, opn=1.0, look=(0, 0)):
    bd, ac, ir = c; u = U(cx, cy, s)
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        px, py = u(0.66 * math.cos(a), 0.66 * math.sin(a)); r = s * 0.3
        d.ellipse([px - r, py - r, px + r, py + r], fill=ac)
    r = s * 0.68; d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bd)
    eye(d, cx, cy - s * 0.05, s * 0.44, ir, opn, look, 'star', bd)
    mouth(d, *u(0, 0.5), s, 'o')

def pillar(d, cx, cy, s, c, opn=1.0, look=(0, 0)):
    bd, ac, ir = c; u = U(cx, cy, s)
    top = catmull([u(-0.56, 0.0), u(-0.56, -0.5), u(-0.4, -0.86), u(0, -0.96), u(0.4, -0.86), u(0.56, -0.5), u(0.56, 0.0)], 12)
    zz = [u(0.56, 0.92)] + [u(0.56 - k * 0.14, 0.92 if k % 2 == 0 else 0.74) for k in range(1, 9)]
    d.polygon(top + zz, fill=bd)
    lw = max(2, int(s * 0.06))
    ex, ey = u(0, -0.44); r = s * 0.36
    for a in (-150, -120, -90, -60, -30):
        t = math.radians(a)
        d.line([(ex + r * 1.1 * math.cos(t), ey + r * 1.1 * math.sin(t)), (ex + r * 1.42 * math.cos(t), ey + r * 1.42 * math.sin(t))],
               fill=INK, width=lw)
    mirror(lambda g: d.rectangle([*u(g * 0.3 - 0.05, 0.12), *u(g * 0.3 + 0.05, 0.62)], fill=ac))
    eye(d, ex, ey, r, ir, opn, look, 'slit', bd)
    mouth(d, *u(0, 0.3), s, 'o')

def crowned(d, cx, cy, s, c, opn=1.0, look=(0, 0)):
    bd, ac, ir = c; u = U(cx, cy, s)
    d.polygon([u(-0.13, -0.5), u(0, -1.0), u(0.13, -0.5)], fill=ac)
    mirror(lambda g: d.polygon([u(g * 0.32, -0.48), u(g * 0.58, -0.9), u(g * 0.56, -0.42)], fill=ac))
    mirror(lambda g: d.rectangle([*u(g * 0.36 - 0.07, 0.6), *u(g * 0.36 + 0.07, 0.98)], fill=INK))
    body(d, cx, cy, s, [(0, -0.56), (0.52, -0.54), (0.86, -0.2), (0.92, 0.28), (0.62, 0.72), (0, 0.78)], bd)
    eye(d, *u(0, 0.02), s * 0.5, ir, opn, look, 'round', bd, ir=0.62)
    mouth(d, *u(0, 0.62), s, 'zig')

# ---------------------------------------------------------------- stranger beings: flat, symmetrical, one almond eye
def almond(cv, cx, cy, w, h, iris, look=(0, 0), pupil='round', opn=1.0, lashes=0, brow=False):
    """an outlined almond eye; w, h in 4x px at full open; opn squeezes it shut"""
    d = ImageDraw.Draw(cv, 'RGBA')
    lw = max(2, int(h * 0.075))
    hh = h * max(opn, 0.0)
    def lid(sign, hgt): return [(cx + x, cy + sign * hgt / 2 * (1 - (2 * x / w) ** 2)) for x in np.linspace(-w / 2, w / 2, 48)]
    if opn <= 0.05:
        d.line(lid(1, h * 0.35), fill=INK, width=lw, joint='curve')
        for x in (-0.22, 0, 0.22):
            px, py = cx + x * w, cy + h * 0.35 / 2 * (1 - (2 * x) ** 2)
            d.line([(px, py), (px + x * w * 0.25, py + h * 0.22)], fill=INK, width=lw)
        return
    pts = lid(-1, hh) + lid(1, hh)[::-1]
    pad = int(w)
    lay = Image.new('RGBA', (pad * 2, pad * 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ox, oy = cx - pad, cy - pad
    ld.polygon([(x - ox, y - oy) for x, y in pts], fill=PAPER)
    r = h * 0.4
    ix, iy = pad + look[0] * (w / 2 - r) * 0.7, pad + look[1] * h * 0.12
    ld.ellipse([ix - r, iy - r, ix + r, iy + r], fill=iris)
    pr = r * 0.5
    if pupil == 'round': ld.ellipse([ix - pr, iy - pr, ix + pr, iy + pr], fill=INK)
    elif pupil == 'slit': ld.ellipse([ix - pr * 0.34, iy - pr * 1.6, ix + pr * 0.34, iy + pr * 1.6], fill=INK)
    elif pupil == 'ring':
        ld.ellipse([ix - pr * 1.3, iy - pr * 1.3, ix + pr * 1.3, iy + pr * 1.3], fill=INK)
        q = pr * 0.7; ld.ellipse([ix - q, iy - q, ix + q, iy + q], fill=iris)
        q = pr * 0.3; ld.ellipse([ix - q, iy - q, ix + q, iy + q], fill=INK)
    m = Image.new('L', lay.size, 0); ImageDraw.Draw(m).polygon([(x - ox, y - oy) for x, y in pts], fill=255)
    lay.putalpha(ImageChops.multiply(lay.getchannel('A'), m))
    comp(cv, lay, ox, oy)
    d.line(pts + [pts[0]], fill=INK, width=lw, joint='curve')
    for k in range(lashes):
        x = (k + 0.5) / lashes - 0.5
        px, py = cx + x * w * 0.8, cy - hh / 2 * (1 - (2 * x * 0.8) ** 2)
        d.line([(px, py), (px + x * w * 0.18, py - h * 0.28)], fill=INK, width=lw)
    if brow:
        d.arc([cx - w * 0.5, cy - h * 1.05, cx + w * 0.5, cy + h * 0.15], 205, 335, fill=INK, width=lw)

def stalk(d, a, b, lw, end=None, r=0, col=INK, star=False):
    d.line([a, b], fill=LINE, width=lw)
    if end is not None:
        if star:
            pts = []
            for i in range(8):
                t = -math.pi / 2 + i * math.pi / 4; q = r * (1.0 if i % 2 == 0 else 0.32)
                pts.append((b[0] + q * math.cos(t), b[1] + q * math.sin(t)))
            d.polygon(pts, fill=end)
        else: d.ellipse([b[0] - r, b[1] - r, b[0] + r, b[1] + r], fill=end)

def totem(cv, cx, cy, s, c, opn=1.0, look=(0, 0)):
    """a stack of blocks: wedge, eye block, half disc, one feeler"""
    a, b, e = c; u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.055))
    stalk(d, u(0, -0.74), u(0, -0.98), lw, LINE, s * 0.06)
    d.pieslice([*u(-0.44, -1.18), *u(0.44, -0.3)], 180, 360, fill=e)
    d.rectangle([*u(-0.5, -0.32), *u(0.5, 0.5)], fill=b)
    d.polygon([u(-0.48, 0.5), u(0.48, 0.5), u(0.66, 1.0), u(-0.66, 1.0)], fill=a)
    for x in (-0.24, 0, 0.24):
        d.ellipse([*u(x - 0.05, 0.7), *u(x + 0.05, 0.8)], fill=INK)
    almond(cv, *u(0, 0.09), s * 0.8, s * 0.42, e if e != b else a, look, 'round', opn)

def moon(cv, cx, cy, s, c, opn=1.0, look=(0, 0)):
    """a disc split in two colours, thin legs, star-tipped feelers"""
    a, b, e = c; u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.05))
    for g in (-1, 1):
        pts = [u(g * (0.22 + 0.2 * t ** 1.4), -0.62 - 0.36 * t) for t in np.linspace(0, 1, 12)]
        d.line(pts, fill=LINE, width=lw, joint='curve')
        stalk(d, pts[-2], pts[-1], lw, OCHRE if a != OCHRE else PINK, s * 0.14, star=True)
        stalk(d, u(g * 0.3, 0.55), u(g * 0.44, 0.98), lw)
        d.line([u(g * 0.44, 0.98), u(g * 0.6, 0.98)], fill=LINE, width=lw)
    d.chord([*u(-0.7, -0.75), *u(0.7, 0.65)], 180, 360, fill=a)
    d.chord([*u(-0.7, -0.75), *u(0.7, 0.65)], 0, 180, fill=b)
    almond(cv, *u(0, -0.05), s * 0.92, s * 0.46, e, look, 'round', opn, lashes=5)

def arch(cv, cx, cy, s, c, opn=1.0, look=(0, 0), bg=PAPER):
    """an arch on striped legs"""
    a, b, e = c; u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA')
    d.pieslice([*u(-0.72, -0.86), *u(0.72, 0.58)], 180, 360, fill=a)
    d.rectangle([*u(-0.72, -0.15), *u(0.72, 1.0)], fill=a)
    for k in range(4):
        y0 = 0.3 + k * 0.18
        d.rectangle([*u(-0.72, y0), *u(0.72, y0 + 0.09)], fill=b)
    d.pieslice([*u(-0.28, 0.2), *u(0.28, 0.76)], 180, 360, fill=bg)
    d.rectangle([*u(-0.28, 0.48), *u(0.28, 1.01)], fill=bg)
    almond(cv, *u(0, -0.3), s * 0.82, s * 0.42, e, look, 'slit', opn, brow=True)

def star(cv, cx, cy, s, c, opn=1.0, look=(0, 0)):
    """a four-point star with a disc and an eye in the middle"""
    a, b, e = c; u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA')
    pts = []
    for i in range(64):
        t = 2 * math.pi * i / 64
        r = 0.36 + 0.64 * abs(math.cos(2 * t)) ** 3
        pts.append(u(r * math.cos(t - math.pi / 2), r * math.sin(t - math.pi / 2)))
    d.polygon(pts, fill=a)
    r = s * 0.5; d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=b)
    almond(cv, cx, cy, s * 0.76, s * 0.4, e, look, 'ring', opn)

def dandelion(cv, cx, cy, s, c, opn=1.0, look=(0, 0)):
    """a soft body with a fan of thin stems ending in dots"""
    a, b, e = c; u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.045))
    cols = [b, e, OCHRE, b, e, OCHRE, b]
    for k in range(7):
        t = math.radians(-90 + (k - 3) * 22)
        stalk(d, u(0, -0.2), u(0.86 * math.cos(t), -0.2 + 0.8 * math.sin(t)), lw, cols[k] if k != 3 else LINE, s * 0.075)
    body(d, cx, cy, s, [(0, -0.3), (0.42, -0.24), (0.6, 0.16), (0.5, 0.7), (0.22, 0.98), (0, 1.0)], a)
    almond(cv, *u(0, 0.24), s * 0.7, s * 0.36, e, look, 'round', opn)

def dome(cv, cx, cy, s, c, opn=1.0, look=(0, 0)):
    """a half disc with a stripe and three long legs"""
    a, b, e = c; u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA'); lw = max(2, int(s * 0.055))
    for x1 in (-0.7, 0, 0.7):
        stalk(d, u(x1 * 0.4, 0.2), u(x1, 0.94), lw, LINE, s * 0.07)
    d.pieslice([*u(-0.8, -0.9), *u(0.8, 0.7)], 180, 360, fill=a)
    d.rectangle([*u(-0.8, -0.1), *u(0.8, 0.2)], fill=b)
    almond(cv, *u(0, -0.4), s * 0.7, s * 0.38, e, look, 'round', opn, lashes=3)

def beast(cv, cx, cy, s, c, opn=1.0, look=(0, 0)):
    """wide body, crescent horns, two-tone"""
    a, b, e = c; u = U(cx, cy, s); d = ImageDraw.Draw(cv, 'RGBA')
    for g in (-1, 1):
        d.polygon(catmull([u(g * 0.3, -0.42), u(g * 0.62, -0.6), u(g * 0.9, -1.0), u(g * 0.98, -0.52), u(g * 0.62, -0.3)], 8,
                          closed=True), fill=b)
    body(d, cx, cy, s, [(0, -0.56), (0.5, -0.5), (0.86, -0.12), (0.84, 0.46), (0.5, 0.8), (0, 0.84)], a)
    d.chord([*u(-0.86, -0.2), *u(0.86, 1.6)], 180, 360, fill=b)   # lower half in the second colour
    almond(cv, *u(0, -0.12), s * 0.9, s * 0.46, e, look, 'round', opn)
    for x in (-0.32, -0.16, 0, 0.16, 0.32):
        d.rectangle([*u(x - 0.035, 0.48), *u(x + 0.035, 0.62)], fill=INK)

def creature(cv, kind, cx, cy, s, cols, opn=1.0, look=(0, 0), **kw):
    fn = {'totem': totem, 'moon': moon, 'arch': arch, 'star': star, 'dandelion': dandelion, 'dome': dome,
          'beast': beast}[kind]
    fn(cv, P(cx), P(cy), P(s), cols, opn, look, **kw)

# ---------------------------------------------------------------- shared bits
def canvas(bg, w=W, h=H): return Image.new('RGBA', (P(w), P(h)), bg)

def finish(cv):
    im = cv.resize((cv.width // S, cv.height // S), Image.LANCZOS).convert('RGB')
    a = np.asarray(im).astype(np.uint16)
    r, g, b = a[..., 0] >> 3, a[..., 1] >> 2, a[..., 2] >> 3
    return Image.fromarray(np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.uint8))

def status(cv, fg=INK, vol=31, bat=0.7):
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 10, 9, '12:41', 8.5, fg, MONO)
    txt(d, 248, 9, f'VOL {vol}', 8.5, fg, MONO, h='r')
    d.rounded_rectangle([P(256), P(5), P(279), P(13)], radius=P(4), fill=mix(fg, PAPER if fg == INK else INK, 0.7))
    d.rounded_rectangle([P(256), P(5), P(256 + 23 * bat), P(13)], radius=P(4), fill=fg)
    d.ellipse([P(281), P(7.5), P(284), P(10.5)], fill=fg)

def cover(sz):
    im = Image.new('RGBA', (sz, sz), OCHRE)
    d = ImageDraw.Draw(im, 'RGBA')
    d.polygon(blob_pts(sz * 0.42, sz * 0.66, sz * 0.46, sz * 0.38, 4, 0.1), fill=ULTRA)
    r = sz * 0.15; d.ellipse([sz * 0.76 - r, sz * 0.24 - r, sz * 0.76 + r, sz * 0.24 + r], fill=VERM)
    lay = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
    daub(lay, [(sz * 0.06 / S, sz * 0.2 / S), (sz * 0.3 / S, sz * 0.13 / S), (sz * 0.55 / S, sz * 0.19 / S)], sz * 0.07 / S, INK, 9)
    im.alpha_composite(lay)
    eye(d, sz * 0.42, sz * 0.64, sz * 0.13, PINK, 1, (0.3, -0.2), 'round')
    return im

def glyph(d, kind, x, y, s, c):
    cx, cy, s = P(x), P(y), P(s); t = max(2, int(s * 0.13))
    if kind == 'shuffle':
        for a, b in (((-0.4, -0.24), (0.26, 0.24)), ((-0.4, 0.24), (0.26, -0.24))):
            d.line([(cx + a[0] * s, cy + a[1] * s), (cx + b[0] * s, cy + b[1] * s)], fill=c, width=t)
            hx_, hy = cx + b[0] * s, cy + b[1] * s
            d.polygon([(hx_ + s * 0.16, hy), (hx_ - s * 0.04, hy - s * 0.15), (hx_ - s * 0.04, hy + s * 0.15)], fill=c)
    elif kind == 'repeat':
        d.rounded_rectangle([cx - s * 0.4, cy - s * 0.24, cx + s * 0.36, cy + s * 0.24], radius=s * 0.2, outline=c, width=t)
        d.polygon([(cx + s * 0.06, cy - s * 0.4), (cx + s * 0.28, cy - s * 0.24), (cx + s * 0.06, cy - s * 0.08)], fill=c)
    elif kind == 'heart':
        r = s * 0.2
        d.ellipse([cx - 2 * r, cy - s * 0.28, cx, cy - s * 0.28 + 2 * r], fill=c)
        d.ellipse([cx, cy - s * 0.28, cx + 2 * r, cy - s * 0.28 + 2 * r], fill=c)
        d.polygon([(cx - 2 * r + 1, cy - s * 0.28 + r * 1.2), (cx + 2 * r - 1, cy - s * 0.28 + r * 1.2), (cx, cy + s * 0.38)], fill=c)

# ---------------------------------------------------------------- home A: collage of blobs, creatures wake when pointed at
def home_collage():
    cv = canvas(PAPER)
    daub(cv, [(16, 214), (90, 150), (180, 96), (282, 40)], 30, OCHRE, seed=3, dry=0.7)
    d = ImageDraw.Draw(cv, 'RGBA')
    blob(d, 26, 30, 20, 16, LILAC, 8)
    blob(d, 278, 222, 15, 13, CHART, 12)
    # now playing (up)
    blob(d, 150, 60, 74, 33, PINK, 3, 0.07)
    sz = P(44); cvr = cover(sz)
    m2 = Image.new('L', (sz, sz), 0); ImageDraw.Draw(m2).polygon(blob_pts(sz / 2, sz / 2, sz * 0.48, sz * 0.48, 30, 0.05), fill=255)
    cv.paste(cvr, (P(104) - sz // 2, P(60) - sz // 2), m2)
    txt(d, 132, 53, 'now playing', 13, INK)
    txt(d, 132, 68, 'Soft Machinery', 9.5, mix(INK, PINK, 0.35), SEMI)
    # settings (left), asleep
    blob(d, 52, 134, 44, 56, MOSS, 5, 0.08)
    creature(cv, 'totem', 52, 120, 27, (OCHRE, LILAC, PINK), opn=0)
    txt(d, 52, 176, 'settings', 12, PAPER, h='m')
    # games (down), asleep
    blob(d, 150, 206, 72, 29, VERM, 9, 0.08)
    creature(cv, 'dome', 106, 203, 21, (OCHRE, PINK, ULTRA), opn=0)
    txt(d, 172, 206, 'games', 16, PAPER, h='m')
    # music (right): highlighted, awake, a little bigger
    blob(d, 241, 133, 54, 66, ULTRA, 21, 0.08)
    creature(cv, 'arch', 241, 122, 34, (PINK, VERM, OCHRE), opn=1, look=(-0.3, 0.2), bg=ULTRA)
    txt(d, 241, 182, 'music', 16, PAPER, h='m')
    # centre: which way is lit
    for (dx, dy, on) in ((0, -1, 0), (1, 0, 1), (0, 1, 0), (-1, 0, 0)):
        r = 3 if on else 2
        d.ellipse([P(148 + dx * 9 - r), P(133 + dy * 9 - r), P(148 + dx * 9 + r), P(133 + dy * 9 + r)], fill=ULTRA if on else GREY)
    status(cv)
    return cv

# ---------------------------------------------------------------- home B: one big eye, on black
def home_eye():
    cv = canvas(INK)
    d = ImageDraw.Draw(cv, 'RGBA')
    blob(d, 148, 128, 80, 82, ULTRA, 14, 0.07)
    creature(cv, 'moon', 148, 130, 60, (VERM, PINK, OCHRE), opn=1, look=(1, 0))
    dim = mix(PAPER, INK, 0.5)
    txt(d, 148, 30, 'now playing', 12, dim, h='m')
    txt(d, 148, 228, 'games', 12, dim, h='m')
    txt(d, 36, 128, 'settings', 12, dim, h='m')
    lay = Image.new('RGBA', cv.size, (0, 0, 0, 0))
    daub(lay, [(236, 130), (262, 127), (290, 129)], 21, PINK, seed=5, dry=0.6)
    cv.alpha_composite(lay)
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 262, 128, 'music', 13, INK, h='m')
    status(cv, PAPER)
    return cv

# ---------------------------------------------------------------- now playing
def now_playing(progress=0.43):
    cv = canvas(PAPER)
    d = ImageDraw.Draw(cv, 'RGBA')
    blob(d, 84, 108, 60, 56, PINK, 11, 0.08)
    sz = P(100); cv.paste(cover(sz), (P(18), P(30)))
    status(cv)
    X = 134
    txt(d, X, 38, '03/12 · FLAC 24/96', 8, GREY, MONO)
    txt(d, X, 61, 'Soft', 23, INK)
    txt(d, X, 85, 'Machinery', 23, INK)
    txt(d, X, 106, 'Pale Fauna', 13, VERM, BOLD)
    txt(d, X, 121, 'Lantern Hours', 11, GREY, MED)
    glyph(d, 'shuffle', X + 7, 141, 13, ULTRA)
    glyph(d, 'repeat', X + 31, 141, 13, mix(INK, PAPER, 0.7))
    glyph(d, 'heart', X + 54, 141, 13, VERM)
    # progress: painted where it has played, a pencil line where it hasn't
    y, x0, x1 = 198, 16, 282
    fx = x0 + (x1 - x0) * progress
    d.line([(P(fx), P(y)), (P(x1), P(y))], fill=INK, width=P(1.4))
    lay = Image.new('RGBA', cv.size, (0, 0, 0, 0))
    daub(lay, [(x0, y + 0.5), ((x0 + fx) / 2, y - 0.6), (fx, y + 0.3)], 8, VERM, seed=2, dry=0.35)
    cv.alpha_composite(lay)
    d = ImageDraw.Draw(cv, 'RGBA')
    eye(d, P(fx), P(y), P(6.5), ULTRA, 1, (1, 0), 'round')
    creature(cv, 'dandelion', 263, y - 20, 20, (ULTRA, PINK, CHART), opn=1, look=(-1, 0))
    txt(d, x0, 220, '1:42', 8.5, INK, MONO)
    txt(d, x1, 220, '-2:13', 8.5, GREY, MONO, h='r')
    txt(d, 92, 220, 'NEXT', 8, GREY, MONO)
    txt(d, 118, 220, 'Moth Radio', 9.5, INK, SEMI)
    return cv

def volume(level=0.62):
    cv = now_playing()
    cv.alpha_composite(Image.new('RGBA', cv.size, PAPER[:3] + (140,)))
    d = ImageDraw.Draw(cv, 'RGBA')
    blob(d, 148, 118, 84, 82, ULTRA, 21, 0.07)
    creature(cv, 'star', 148, 96, 50, (PINK, OCHRE, VERM), opn=level, look=(0, 0))
    txt(d, 148, 166, '31', 30, PAPER, h='m')
    txt(d, 148, 188, 'VOLUME', 7.5, mix(PAPER, ULTRA, 0.35), MONO, h='m', track=1.2)
    return cv

# ---------------------------------------------------------------- list
ROWS = ['all songs', 'artists', 'albums', 'genres', 'playlists', 'favourites']
def music_list(sel=2):
    cv = canvas(ULTRA)
    d = ImageDraw.Draw(cv, 'RGBA')
    status(cv, PAPER)
    txt(d, 14, 42, 'music', 30, PAPER)
    creature(cv, 'arch', 258, 44, 22, (PINK, VERM, OCHRE), opn=1, look=(-0.8, 0.6), bg=ULTRA)
    marks = [(OCHRE, 'circle'), (PINK, 'moon'), (VERM, 'tri'), (LILAC, 'square'), (CHART, 'pill'), (PINK, 'heart')]
    for i, label in enumerate(ROWS):
        y = 80 + i * 27
        if i == sel:
            lay = Image.new('RGBA', cv.size, (0, 0, 0, 0))
            daub(lay, [(30, y + 1), (120, y - 1), (236, y + 1)], 20, PINK, seed=7, dry=0.55)
            cv.alpha_composite(lay); d = ImageDraw.Draw(cv, 'RGBA')
        c, k = marks[i]
        x, r = P(20), P(4.5)
        Y = P(y)
        if k == 'circle': d.ellipse([x - r, Y - r, x + r, Y + r], fill=c)
        elif k == 'moon': d.chord([x - r, Y - r, x + r, Y + r], 90, 270, fill=c)
        elif k == 'tri': d.polygon([(x - r, Y + r), (x, Y - r), (x + r, Y + r)], fill=c)
        elif k == 'square': d.rectangle([x - r * 0.85, Y - r * 0.85, x + r * 0.85, Y + r * 0.85], fill=c)
        elif k == 'pill': d.rounded_rectangle([x - r * 1.2, Y - r * 0.6, x + r * 1.2, Y + r * 0.6], radius=r * 0.6, fill=c)
        else: glyph(d, 'heart', 20, y, 10, c)
        fg = INK if i == sel else PAPER
        txt(d, 36, y, label, 15, fg, BOLD)
        if i == sel: txt(d, 274, y, '12', 8.5, PAPER, MONO, h='r')
    d.line([(P(287), P(70)), (P(287), P(224))], fill=mix(PAPER, ULTRA, 0.65), width=P(1))
    d.ellipse([P(284), P(112), P(290), P(128)], fill=PINK)
    return cv

# ---------------------------------------------------------------- the kit
def kit():
    cv = canvas(PAPER)
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 10, 11, 'COLOUR', 7.5, GREY, MONO, track=1)
    for i, c in enumerate([VERM, PINK, PEACH, OCHRE, CHART, MOSS, ULTRA, LILAC, INK]):
        blob(d, 22 + i * 31, 32, 12, 11, c, 40 + i, 0.1)
    txt(d, 10, 56, 'PAINT', 7.5, GREY, MONO, track=1)
    for i, (c, s) in enumerate(((VERM, 1), (ULTRA, 4), (OCHRE, 6))):
        daub(cv, [(12 + i * 96, 76), (50 + i * 96, 71), (92 + i * 96, 75)], 14, c, seed=s, dry=0.6)
    d = ImageDraw.Draw(cv, 'RGBA')
    txt(d, 10, 98, 'BEINGS', 7.5, GREY, MONO, track=1)
    beings = [('arch', (PINK, VERM, OCHRE), 1, (0, 0)), ('moon', (VERM, PINK, OCHRE), 1, (0.6, 0)),
              ('totem', (OCHRE, LILAC, PINK), 1, (0, 0)), ('star', (PINK, OCHRE, VERM), 1, (0, 0)),
              ('dandelion', (ULTRA, PINK, CHART), 1, (-0.5, 0)), ('dome', (OCHRE, PINK, ULTRA), 1, (0.4, 0)),
              ('beast', (MOSS, CHART, VERM), 1, (0, 0))]
    for i, (k, c, o, lk) in enumerate(beings):
        creature(cv, k, 21 + i * 41.5, 136, 19, c, opn=o, look=lk)
    txt(d, 10, 178, 'TYPE', 7.5, GREY, MONO, track=1)
    txt(d, 10, 204, 'music', 26, INK)
    txt(d, 104, 198, 'Soft Machinery', 12, INK, BOLD)
    txt(d, 104, 214, '1:42 · FLAC 24/96', 8.5, GREY, MONO)
    return cv

SCREENS = [('home_collage', home_collage, 'Home A: blobs; only the pointed-at one is awake'),
           ('home_eye', home_eye, 'Home B: one big eye looks where you point'),
           ('now_playing', now_playing, 'Now Playing'),
           ('volume', volume, 'Volume: the eye opens as it gets louder'),
           ('music_list', music_list, 'A list (Music, Albums highlighted)'),
           ('kit', kit, 'The kit')]

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    shots = []
    for name, fn, cap in SCREENS:
        im = finish(fn()); im.save(f'{OUT}/{name}.png'); shots.append((im, cap)); print(name)
    Z, M, CH = 2, 24, 30
    cf = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17)
    sheet = Image.new('RGB', (M + 2 * (W * Z + M), M + 3 * (H * Z + CH + M)), (34, 32, 38))
    sd = ImageDraw.Draw(sheet)
    for i, (im, cap) in enumerate(shots):
        x, y = M + (i % 2) * (W * Z + M), M + (i // 2) * (H * Z + CH + M)
        sheet.paste(im.resize((W * Z, H * Z), Image.NEAREST), (x, y))
        sd.text((x, y + H * Z + 7), cap, font=cf, fill=(235, 228, 240))
    sheet.save(f'{OUT}/sheet.png')
