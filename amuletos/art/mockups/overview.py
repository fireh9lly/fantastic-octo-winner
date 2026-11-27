#!/usr/bin/env python3
"""Render the current UI design into docs/design/ui/: one PNG per screen at the real 296x240 (colours rounded to
RGB565) and overview.png with every screen at 2x. PC mock-ups only; nothing here runs on the player.

    python3 art/mockups/overview.py [OUT_DIR]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image, ImageDraw, ImageFont
import colourways as cw, forms as fm, black_orange as bo
from shapes import finish, W, H

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'docs', 'design', 'ui')

def black(fn):
    def f():
        cw.use('black')          # resets the shared line and eye colours the older rounds expect
        return fn()
    return f

SCREENS = [
    ('01_home', lambda: cw.home('black'), 'Home: the pet looks where you point'),
    ('02_home_sapling', lambda: cw.home('black', ('sapling', 4, 'neutral')), 'Home with the sapling as the pet'),
    ('03_now_playing', lambda: cw.now_playing('black'), 'Now Playing: the pet watches the playhead'),
    ('04_look', cw.look_page, 'Settings > Look'),
    ('05_gallery', cw.gallery, 'Gallery: every form met, and when'),
    ('06_gallery_choose', cw.gallery_choose, 'Gallery: lock a form, or start a new pet'),
    ('07_picker', cw.picker, 'New pet: pick a species'),
    ('08_pet', black(fm.pet_page), 'The pet\'s page: what it ate, on the mood map'),
    ('09_growing', cw.growing, 'Growing up, all three species'),
    ('10_moon_adults', black(fm.moon_adults), 'Moon: five adult forms'),
    ('11_sapling_adults', black(fm.sapling_adults), 'Sapling: five adult forms'),
    ('12_whaleian_adults', cw.whale_adults, 'Whaleian: five adult forms'),
    ('13_colourway_black', cw.colourway('black', 'lines'), 'Colourway: black & orange (default)'),
    ('14_colourway_paper', cw.colourway('paper', 'dots'), 'Colourway: paper & orange'),
    ('15_colourway_eva', cw.colourway('eva', 'waves'), 'Colourway: EVA'),
    ('16_colourway_aqua', cw.colourway('aqua', 'lines'), 'Colourway: aqua'),
    ('17_colourway_candy', cw.colourway('candy', 'dots'), 'Colourway: candy'),
    ('18_kit', black(bo.kit), 'Kit: black & orange colours, highlight textures, type'),
    ('19_list_scroll', cw.list_scroll, 'Scrolling: the highlight stops at row 4, two entries stay visible below'),
    ('20_fast_scroll', cw.fast_scroll, 'Start + wheel: fast scroll, a letter at a time'),
]

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    shots = []
    for name, fn, cap in SCREENS:
        im = finish(fn()); im.save(os.path.join(OUT, f'{name}.png'), optimize=True); shots.append((im, cap))
        print(name)
    Z, M, CH, COLS = 2, 24, 30, 3
    cf = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17)
    rows = (len(shots) + COLS - 1) // COLS
    sheet = Image.new('RGB', (M + COLS * (W * Z + M), M + rows * (H * Z + CH + M)), (44, 42, 46))
    sd = ImageDraw.Draw(sheet)
    for i, (im, cap) in enumerate(shots):
        x, y = M + (i % COLS) * (W * Z + M), M + (i // COLS) * (H * Z + CH + M)
        sheet.paste(im.resize((W * Z, H * Z), Image.NEAREST), (x, y))
        sd.text((x, y + H * Z + 7), cap, font=cf, fill=(235, 228, 240))
    sheet.save(os.path.join(OUT, 'overview.png'), optimize=True)
    print('overview', sheet.size)
