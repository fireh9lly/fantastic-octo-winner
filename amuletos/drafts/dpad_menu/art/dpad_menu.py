#!/usr/bin/env python3
"""Four-way D-pad main menu art for amuletOS (replaces the v0.3 carousel cards).

One item per direction. A single tap highlights that direction's tile, a second tap on the same direction opens
it. Stock's main menu paints one full-screen image per selected position, so the menu needs one image per
direction (plus a variant with Now Playing greyed out while nothing is playing). The pictures go to the same image
ids the carousel used, so the stock paint code is unchanged.

Run from an amuletOS checkout (it imports art/pocket.py):

  python art/dpad_menu.py OUTDIR [FONT_DIR]     images NNN.png for build_reskin.py
  python art/dpad_menu.py --preview OUTDIR      PC preview (no device font needed: built from art/font.py)
"""
import os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AMU = Path(os.environ.get("AMULETOS", HERE.parents[2]))      # amuletOS tree (holds art/pocket.py): amuletos/
sys.path.insert(0, str(AMU / "art"))
import pocket as P                                           # noqa: E402
from pocket import W, H, INK, WHITE, GRAPE, SKY, GOLD, TEAL, BERRY   # noqa: E402
from zeal import Canvas, mix                                 # noqa: E402

# ---------- layout ----------
# Direction slots, in the order the device code uses (game/dpad.h: DPAD_UP, DPAD_RIGHT, DPAD_DOWN, DPAD_LEFT).
# Each slot names a carousel item, so the stock tile actions are reused unchanged.
UP, RIGHT, DOWN, LEFT = range(4)
ITEMS = {                     # slot -> (label, icon, accent, carousel item index)
    UP:    ("Now Playing", P.NOW_PLAYING, GRAPE, 0),
    RIGHT: ("Music",       P.MUSIC,       SKY,   1),
    DOWN:  ("Games",       P.GAMES,       TEAL,  3),
    LEFT:  ("Blockz",      P.BLOCKZ,      GOLD,  2),
}
# image painted when carousel item k is highlighted (the carousel's full-screen ids, m21_ext.c menu_art; stock paint
# is unchanged). Indexed by ITEM, not by direction: Up = item 0 -> 16, Right = 1 -> 14, Left = 2 -> 18, Down = 3 -> 20.
STATES = [16, 14, 18, 20]
NP_OFF_STATE = 8              # Up highlighted, Now Playing greyed (stock's unused grid image, as in the carousel)

TILE, GAP = 52, 5             # tile size and gap around the centre cell
CX, CY = W // 2, 42 + (3 * 52 + 2 * 5) // 2  # plus centre: top tile at y 42, under the status strip (y 0..33)
OFF_INK, OFF_ACCENT = "#a9adb8", "#c9ccd6"

def tile_xy(slot):
    o = TILE + GAP
    dx, dy = {UP: (0, -o), RIGHT: (o, 0), DOWN: (0, o), LEFT: (-o, 0)}[slot]
    return CX - TILE // 2 + dx, CY - TILE // 2 + dy

def dpad_glyph(cv, x, y, lit, accent, s=6):
    """the centre cell: a small cross with the highlighted arm in the item's colour (teaches the control)"""
    arms = {UP: (1, 0), RIGHT: (2, 1), DOWN: (1, 2), LEFT: (0, 1)}
    for (gx, gy) in [(1, 1)] + list(arms.values()):
        cv.rect(x + gx * 3 * s, y + gy * 3 * s, 3 * s, 3 * s, INK)
    for slot, (gx, gy) in arms.items():
        c = accent if slot == lit else WHITE
        cv.rect(x + gx * 3 * s + 2, y + gy * 3 * s + 2, 3 * s - 4, 3 * s - 4, c)
    cv.rect(x + 3 * s + 2, y + 3 * s + 2, 3 * s - 4, 3 * s - 4, "#c9ccd6")

def menu(sel, np_off=False):
    """sel: highlighted slot. np_off: Now Playing greyed out (player not running)."""
    cv = Canvas(W, H)
    P.screen(cv, 34)
    P.status(cv)
    for slot, (label, ic, accent, _item) in ITEMS.items():
        x, y = tile_xy(slot)
        off = np_off and slot == UP
        on = slot == sel
        if on:      # highlighted: grows 4 px each side, coloured fill, hard shadow in the accent
            P.frame(cv, x - 4, y - 4, TILE + 8, TILE + 8, mix(accent, WHITE, 0.82),
                    OFF_ACCENT if off else accent, r=6)
            P.icon(cv, ic, x + (TILE - 48) // 2, y + (TILE - 48) // 2, 3, fade=0.45 if off else 0.0, off=off)
        else:
            P.frame(cv, x, y, TILE, TILE, WHITE, r=6)
            P.icon(cv, ic, x + (TILE - 32) // 2, y + (TILE - 32) // 2, 2, fade=0.72 if off else 0.5, off=off)
    label, _ic, accent, _item = ITEMS[sel]
    off = np_off and sel == UP
    g = 5 * 9                                                   # centre glyph size (s = 6)
    dpad_glyph(cv, CX - g // 2, CY - g // 2, sel, OFF_ACCENT if off else accent, s=5)
    P.text_c(cv, label, H - 21, OFF_INK if off else INK)        # label row under the plus
    # corner hints (the empty quadrants)
    hint = "#9a9fad"
    P.text(cv, "1 tap", 14, 46, hint); P.text(cv, "select", 14, 62, hint)
    P.text(cv, "2 taps", W - 14 - P.textw("2 taps"), 46, hint)
    P.text(cv, "open", W - 14 - P.textw("open"), 62, hint)
    return cv

def images():
    """{image id: Canvas}: one per highlighted slot, plus Up highlighted with Now Playing greyed (nothing playing).
    Step 1 keeps one greyed image, as the carousel did: on the other three the small Now Playing tile stays in
    colour."""
    out = {STATES[item]: menu(slot) for slot, (_l, _i, _a, item) in ITEMS.items()}
    out[NP_OFF_STATE] = menu(UP, np_off=True)
    return out

def preview_font(path):
    """build a font1.bin with amuletOS's tall ASCII glyphs (art/font.py), for previews without the device font"""
    import font
    _f0, f1 = font.patch_fonts(bytes(128 * 32), bytes(128 * 33), "tall")
    path.mkdir(parents=True, exist_ok=True)
    (path / "font1.bin").write_bytes(f1)

def main():
    args = sys.argv[1:]
    preview = "--preview" in args
    args = [a for a in args if a != "--preview"]
    out = Path(args[0] if args else "build/art_dpad")
    out.mkdir(parents=True, exist_ok=True)
    if preview:
        preview_font(out / "font")
        P.FONT_DIR = out / "font"
        for slot in range(4):
            menu(slot).image(2).save(out / f"menu_{'urdl'[slot]}.png")
        menu(UP, np_off=True).image(2).save(out / "menu_u_np_off.png")
        print("wrote preview to", out)
        return
    if len(args) > 1:
        P.FONT_DIR = Path(args[1])
    for idx, cv in images().items():
        cv.image(1).save(out / f"{idx:03d}.png")
    print("wrote D-pad menu images", sorted(images()), "to", out)

if __name__ == "__main__":
    main()
