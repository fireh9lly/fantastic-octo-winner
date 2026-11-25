# amuletOS mods: four-way D-pad main menu (step 1)

Mods for [amuletOS](https://github.com/dharma-dingo/amuletOS) (custom firmware for the Hidizs AP30), built on
v0.3. Files here mirror amuletOS's own layout, so they drop into an amuletOS checkout.

## What it does

The v0.3 main menu is a sideways carousel of five cards. This replaces it with **one item per D-pad
direction**:

| Direction | Item |
|---|---|
| Up | Now Playing (greyed out while nothing is playing, as before) |
| Right | Music |
| Down | Games |
| Left | Blockz |

- **Tap** a direction: its tile highlights.
- **Tap the same direction again within 350 ms**: it opens.
- Tapping a different direction moves the highlight and starts over. Any other key cancels a pending double-tap.
- A still opens the highlighted item. Start still opens Settings.

Everything works with one thumb. Only one face button can be read at a time on the AP30 (all eight share one
resistor ladder), so no combos are used.

Library is dropped from the home screen; it is reachable from Music.

## Files

| File | What | Status |
|---|---|---|
| `art/dpad_menu.py` | Menu pictures: one full-screen image per highlighted item, written to the carousel's image ids (16, 14, 18, 20, and 8 for Now Playing greyed). Stock's menu paint code is unchanged. | Done, previewed |
| `game/dpad.h`, `game/dpad.c` | Tap / double-tap logic. Freestanding C, 72 bytes on the Cortex-M3. | Done, tested |
| `game/test/test_dpad.c` | PC tests: timing window, re-arming, cancel, tick wrap. | Passing |
| `game/device/m21_dpad.c` | Module 21 glue: reads stock's 10 ms tick, updates the menu index, says whether to open. | Draft, compiles (164 B, no data) |

Preview: [`docs/dpad_menu_preview.png`](docs/dpad_menu_preview.png). Regenerate:

```sh
AMULETOS=/path/to/amuletOS python3 art/dpad_menu.py --preview OUTDIR    # menu_u/r/d/l.png, no device font needed
cc -I game game/test/test_dpad.c game/dpad.c -o test_dpad && ./test_dpad
```

## Still to do (needs the stock firmware file)

The patch wiring needs a disassembly of module 21 from the official V1.7.8 `HIFIYF18.IMG`, which this session
cannot download. Until then nothing here should be flashed.

1. **New `menu_dpad` patch in `tools/patch_code.py`**, applied after `menu_carousel`:
   - Up/Down (0x03081CDE, now `b 0x03081D74`), Right (0x03081CF8) and Left (0x03081D24) press events call
     `menu_dir(dir)`. Return 0: branch to the carousel's repaint (0x03081CD6). Return 1: branch to the A path.
   - Find which register holds the event word at each site, so key repeats (0x3000xxxx) are ignored.
   - Find the A case's address in the service switch (0x030819E4).
   - Call `menu_other_key` from the A / B / Start / wheel cases.
2. **Check the RAM words** at 0x0309FFE8..0x0309FFF3 are free (assumed, like the carousel's 0x0309FFE4).
3. **Build:** add `m21_dpad.c` and `dpad.c` to the `extend_module.py --module 21` step, `menu_dpad` to the
   `patch_code.py` list, and `art/dpad_menu.py`'s images to the reskin step.
4. **On device:** single taps only highlight; double-taps open at a normal pace; scrolling never opens by
   accident; A, B and Start still work; music keeps playing.
