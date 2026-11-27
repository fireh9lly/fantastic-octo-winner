# Custom AP30 firmware: plan

A custom firmware for the Hidizs AP30 "Music Boy", forked from [amuletOS](https://github.com/dharma-dingo/amuletOS)
v0.3 and rebased onto Hidizs's official **V1.8.3**. It is its own project now: no compatibility with amuletOS updates
is kept.

Status: **Step 1 builds and runs on the owner's player** (build 14, 2026-11-27). Everything after it is still a
plan, apart from the early draft noted under [Step 2](#step-2-four-way-home-menu). Firmware addresses come from disassembling the official
images with amuletOS's tools (`tools/ap30fw.py`, `tools/fwdis.py`) and Capstone. They are facts about the code,
but none has been tested on hardware.

Never commit Hidizs firmware images (`HIFIYF18.IMG`, `HIFIYF23.IMG`) or anything extracted from them.

## Decisions so far

| Topic | Decision |
|---|---|
| Base firmware | **V1.8.3** (`HIFIYF23.IMG`): Hidizs's gapless FLAC and other fixes come with it. Every amuletOS patch address is re-found (Step 1). |
| Controls everywhere | **A direction moves the highlight; A selects; B goes back. No double-tap anywhere.** |
| Home menu | Up Now Playing · Right Music · Down Games (Blockz inside) · Left Settings (Bluetooth inside) |
| Visualiser | Own full-screen view; also in USB DAC mode; Winamp-inspired styles incl. Geiss-style Plasma |
| Crossfade | Dropped (needs two decoders at once; impossible here). Fade substitute declined. |
| Mood playlists | 2D mood map (calm↔intense × dark↔bright), A plays a cell, tracks play from the start |
| Mood analysis | PC script on Linux x86_64 using Essentia's arousal/valence and voice/instrumental models |
| E-reader | Repurposed as **D-pad adventures** only |
| Look | Flat colour and cut-out blobs, no gloss; textured highlight bars; black & orange by default ([Look and feel](#look-and-feel-decided-2026-11-27)) |
| Colourways | Five, after the AP30's colourways: black & orange, paper & orange, EVA, aqua, candy. SD-card theme packs later |
| Pet | A one-eyed creature that eats your music: adult at 20 h of listening, five forms from the mood map, re-decided every 10 h, lockable from a gallery. Never hungry, never dies ([The pet](#the-pet)) |
| Music videos | Not planned (no video code in the firmware; would need a fully custom player) |

## Build order

1. [Port to V1.8.3](#step-1-port-to-v183) and rebuild amuletOS v0.3's features
2. [Four-way home menu](#step-2-four-way-home-menu)
3. [M3U engine v2](#step-3-m3u-engine-v2) + [mood map and Instrumentals](#step-4-mood-map-and-instrumentals)
4. [Visualiser](#step-5-visualiser): classic styles → USB DAC mode → Plasma → SD presets
5. [Colourways, the pet, sleep timer, D-pad adventures, small extras](#step-6-themes-sleep-timer-adventures-extras)
6. [Playback screen, gapless FLAC, MP3 gapless research](#step-7-playback-options-and-gapless)

Each step ends with a flashable image and an on-device check. Recovery if a flash goes wrong: hold a D-pad
corner + A + B while plugging in USB (BootROM loader mode), then restore with `tools/rkwrite.py`.

---

## Look and feel (decided 2026-11-27)

Mock-ups: [`docs/design/ui/overview.png`](docs/design/ui/overview.png), plus one PNG per screen at the real
296×240 in the same folder, drawn by [`art/mockups/overview.py`](art/mockups/README.md). They are PC renders only.
They came out of a mood board: patterned wooden face blocks, Masayoshi Hanawa's monster figures, a Memphis-pattern
candy bowl, patchwork vinyl cubes, a neon resin table and sun-face cosmetics.

- **Style:**
  - flat colour: no gloss, outlines or drop shadows;
  - organic cut-out blobs and plain rectangles;
  - big lowercase headings;
  - small monospace text for times, track numbers and formats.
  The mock-ups use Inter Display and JetBrains Mono as stand-ins until we design our own fonts.
- **Colourways** (Settings › Look › colours), modelled on the AP30's colourways. Hex values are in `THEMES` in
  `art/mockups/colourways.py`.

  | Colourway | Background | Highlight and details |
  |---|---|---|
  | **black & orange** (default) | near-black | orange, cream text |
  | paper & orange | off-white | orange highlight, black details |
  | EVA | deep purple | slime green highlight, orange accents |
  | aqua | pale blue | aqua highlight, soft blue, navy text; low contrast, easy on the eyes |
  | candy | the candy bowl's purple | pink, yellow, mint and orange taking turns |

- **Highlight on scrolling menus:** a plain rectangle in the highlight colour, printed in a darker shade with dots,
  diagonal lines or waves, after the candy bowl. Settings › Look › highlight:
  - **mix** (default): each list gets one of the three at random;
  - dots, lines or waves: always that one;
  - plain: no texture.

  Still open: whether mix picks again every time a screen opens, or keeps one per screen.
- **The creature** ([the pet](#the-pet)) appears on most screens:
  - in the middle of the home screen;
  - in the corner of lists, looking at the highlighted row;
  - at the end of Now Playing's progress line, watching the playhead.

  Its eye looks where you point. Settings › Look can turn that off ("eye follows you") or hide the creature
  ("show creature").
- **Creatures take the colourway's colours.** It is the same creature through a different lens; the gallery does not
  record colours.
- **Settings › Look rows:** colours, highlight, creature (opens the gallery), show creature, eye follows you,
  album art (square or blob).
- **On the device:**
  - Blobs, bars, textures and fixed labels are pre-drawn images.
  - Text that changes (titles, artists, list rows) needs our own smooth text drawing, since the stock font is 1-bit.
    That is part of the font work.
  - The creature is drawn from small parts at paint time: body, belly pattern, feelers or crest, one eye per look
    direction. There is no image per combination.
  - Colourways are palette tables used when drawing, plus pre-drawn images per colourway. Flash room comes from
    the [image audit](#step-6-themes-sleep-timer-adventures-extras): drawing the volume pop-up in code frees about
    14 MB.

---

## Step 1: Port to V1.8.3

- V1.8.3 has the same 113 modules, but **module 0 grew by 0x4D0**. That shifts every overlay's run address
  (0x030815C4 → 0x03081A94) and much of module 0. 96 modules changed.
- **Module 33** (core-A music engine) grew by 0xEE4 and **module 76** (core-B FLAC decoder, `hifi_flacdec.c`)
  by 0x47C. This is Hidizs's gapless FLAC; module 33 must be re-traced.
- Method:
  - Re-find each amuletOS patch site in V1.8.3 (overlay shifts are mechanical; module 0 and 33 need matching by code
    pattern).
  - Update `tools/patch_code.py`, the hooks and the device C files (`game/stock.h` addresses).
  - Rebuild. The patcher checks original bytes, so every wrong address fails at build time.
- Done when: v0.3's features (carousel, Now Playing, Blockz, Game Boy, playlists, settings kept, English) behave as
  on V1.7.8.
- All V1.7.8 addresses below must be re-found the same way.

**Progress (2026-11-26):**
- Done: amuletOS v0.3 imported, builds on Linux (`build.sh`, `BUILDING.md`).
- Done: **reproduces the v0.3 release byte for byte** from the official V1.7.8 with the pinned GCC 13.3.1
  (`tools/get_toolchain.sh`).
- Done: **address translation.**
  - `tools/xlate.py` matches functions between the images: 3,828 exact, 494 aligned, 57 unmatched of 4,379.
  - `tools/port_inventory.py` covers all 265 uses (`docs/port/v183_addresses.tsv`).
  - Special cases: the 14 stock-game exits (pattern), the music-menu table pointers (by value), the
    layout gaps (Now Playing slot still exactly 0x758 B, Game Boy sound ring still fits).
- Done: **every patch site verified.** `tools/port_patches.py`: of 78 patches, 53 have identical original bytes,
  25 are equivalent after relocation (calls and literals retargeted), 0 differ.
- Done: **trial build on V1.8.3 runs end to end** and the image passes the container checks.
- Done: **source converted to V1.8.3** (`tools/port_convert.py`).
  - **Fixed 2026-11-27:** the first pass's address pattern needed a word break right after the hex digits, so it
    skipped every C literal with a `u` suffix (`0x03057CC8u`): 105 uses in 12 device files, including every
    function call in `libscan.c`, `np_helpers.c` and `m21_ext.c`, never made it into the inventory. Comments on the same lines were converted, which hid it.
    With the pattern fixed, the inventory finds 321 address rows (was 262); the 262 old rows translate exactly as
    before, and 100 literals were converted (the new CHECK rows agree with literal evidence). Still unconverted on
    purpose: amuletOS's own top-of-RAM addresses (the resident-RAM rework) and the dev-only timing log.
  - Output named `HIFIYF23.IMG`; both versions' updaters look for `HIFIYF??.IMG`.
  - Default stamp 2620261101 (newer than V1.8.3's 2620231103).
  - `tools/resident.py` stops the build while the always-loaded code overlaps module 39.
- Done (2026-11-27): **resident-RAM rework; the V1.8.3 build runs end to end** (below).
- Done (2026-11-27): **review of the 120 CHECK addresses** (addresses inside functions Hidizs changed):
  `tools/port_review.py` → `docs/port/v183_check_review.tsv`. None left open:
  - 58 sit in patches whose original bytes the build compares (a wrong one stops the build);
  - 20 aren't in the image (old diagnostic hooks, superseded or dev-only patches) or appear only in comments;
  - 32 have identical normalised code in a window of up to 13 instructions around the old and the new address;
  - 10 checked by hand. The playlist hooks' 6 branch targets in the player init (module 33): same branches in both
    images; V1.8.3 only inserted a literal pool and added a clamp after the seek. Also `AudioClose` (V1.8.3 adds a
    reset of its pre-decode state at entry, same interface), `GameLeaveB`, the engine byte 0x0304A458, a module-22
    epilogue target and the dev-only audio-refill hook.
  - Not covered by address checks: struct offsets inside stock records (e.g. record +0xF2, sys +0x42) and function
    signatures. Every one met on the paths reviewed is unchanged (player init, library build, config load), but
    the device test is the real check.
- Done (2026-11-27): **first test build**: amuletOS v0.3 features + the USB DAC fix + the owner's orange theme on
  black (art/orange.py, game/device/theme.h, dark_text patches), stock font. Checklist: `docs/TEST_V183.md`.
  Owner: the icons and the stock pixel font are stand-ins; better icons, themes and fonts get designed together
  later.
- **Works on the owner's player (2026-11-27, build 14, stamp 2620271114):** installed and running. Owner: "it
  works", though some of the design decisions are off; to revisit together (icons, fonts, theme, layout) before
  the next feature steps. Next image needs build 15 or higher.

**Obstacle found: resident RAM.** amuletOS keeps always-loaded code in "slot 2" above the highest overlay.
- That overlay is **module 39, the music-library builder** (122 KB). It ends at 0x0309F7CC on V1.7.8 but at
  **0x0309FC9C on V1.8.3** (the +0x4D0 shift).
- The free top of RAM shrinks from ~2,030 B to **~850 B** (0x0309FCA0–0x0309FFEF; 0x0309FFF0 is stock's reset magic).
- The only other unclaimed RAM is 11 KB between module 0's code and the overlay window, which stock uses as a
  working area (e.g. volume info at 0x0307E710 on V1.7.8).
- v0.3 needs ~1,640 B there:

  | Part | Size |
  |---|---|
  | USB-name hook | 56 B |
  | Now Playing loader | 28 B |
  | Playlist step | ~270 B |
  | Library-scan skip | ~1,100 B |
  | Tables | ~190 B |

**Fix (amuletOS's own pattern from build 37, when carousel helpers moved out of slot 2 into module 21's
extension):** keep resident only what can be called from anywhere or must survive a library build; move the
rest into extensions of the overlay modules that call them.
- `lib_force` → module 31 extension.
- `cfg_boot_write` → module 1 extension.
- Fingerprint computing (`fp_compute`/`fp_ensure`, the bulk) → module 5 extension, run *before* the build.
  Module 5 (the build window) sits directly below module 39 and stays intact during a build. Anything appended
  after it doesn't, so the post-build "mark fingerprint valid + save config" step becomes a small resident stub.
- `cfg_write` (hooks SaveSysConfig in module 0, callable anytime) stays resident but only copies the stored
  fingerprint.
- Estimated resident total ≈ 700 B: it fits, with little spare.

**Done (2026-11-27), as built:**

| RAM | Contents |
|---|---|
| 0x0309FC9C..0x0309FCD4 | slot 2: USB-name hook (56 B) |
| 0x0309FCD4..0x0309FF20 | slot 2: helpers (588 B): Now Playing loader, playlist step + player-init stubs, library-scan resident part |
| 0x0309FF20..0x0309FF28 | free (8 B) |
| 0x0309FF28..0x0309FFC0 | playlist table (152 B, unchanged) |
| 0x0309FFC0..0x0309FFD8 | library-scan fingerprint FP (unchanged) |
| 0x0309FFD8..0x0309FFE8 | Now Playing scroll state, carousel position (unchanged) |
| 0x0309FFE8..0x0309FFF0 | free (8 B); 0x0309FFF0 stock reset magic |

- **Library scan split** (`libscan.c` resident, `libscan_ovl.c` + `.S` overlay, shared `libscan.h`):
  - the fingerprint work (compute, compare, flash fallback) is a code-only overlay in **module slot 44**
    (empty, and nothing in stock loads it: the task table maps tasks 4/5/7 to empty slots 13/28/29, so those are
    out; amuletOS v0.3's Now Playing overlay sits in 28, reachable only if stock's two TaskSwitch(5) calls, in
    modules 23 and 32, are), linked at **0x03081DF4**, the end of module 5, where stock itself loads modules
    39 and 7. Module 5 only uses that RAM during and after the build, and the module loader always copies afresh
    from flash (0x030686FA: no "already loaded" cache), so:
  - resident `lib_gate` (module 5's hook, 64 B) = load overlay → `lib_check` → stock Build → Post(0x18D) → load
    overlay again (the build overwrote it) → `lib_done` (fingerprint of the card as built, as v0.3 did);
  - `cfg_write` / `cfg_boot_write` share one body; `lib_force` is two stores.
  - Dropped from v0.3: the config save's flash re-read when RAM lost the fingerprint. Every boot sets RAM
    (module 1 loads slot 2, then rewrites block 0 through `cfg_boot_write`, 0x03082C80..0x03082CBA), and the worst
    case is one extra library build, as stock. PC test updated; all PC tests pass.
- Size tricks that got it under: shared bodies, and RAM records reached through absolute symbols (`amu_fp`,
  `amu_rec`, `amu_plt`), so GCC uses short offsets instead of a shared `0x...000` base with 4-byte instructions.
- `tools/build_overlay.py --entry` checks the overlay's entry table sits at its run address.
- **Dev-only timing log** (timing.c, gbprobe's Timing row) stops with `#error`: its 52 B gap below slot 2 is gone
  and slot 2 has no room for its hooks. Re-plan if needed (an overlay or the canary-checked dead code below).
- **Spare: 16 B in total.** New resident features need room from somewhere first: move the playlist hooks out
  (M3U v2 replaces them), or reclaim dead module-0 code after the canary build. The top 2 KB of the 11 KB stock
  working area (0x03080B6C..0x0308136C) has no literal references at all: a candidate, also only after a canary
  test.
- Longer term, find dead stock code in module 0 to free more resident room for later features (M3U v2 state,
  sleep timer, etc.).
- **Dead-code scan (2026-11-26):** ~11.9 KB in 106 module-0 functions on V1.8.3 (11.1 KB on V1.7.8) have no
  reference anywhere in the firmware image:
  - checked: branches from every module, stored pointers anywhere in the whole image at 2-byte alignment
    (incl. flash tables outside code.bin), pc-relative address computations, fall-through;
  - known indirect functions (audio refill and DMA-completion callbacks, SysTick ISR, screen flush) come out live;
  - stock's old blit routines come out dead, matching amuletOS's own manual finding.

  Not used in Step 1. Before reclaiming any of it: a **canary build** puts a tiny "I was called" logger at each
  candidate's entry, viewable on the device. Use the player normally for a few days; only never-called functions
  get reused.

## Step 2: Four-way home menu

| Direction | Item |
|---|---|
| Up | Now Playing (greyed while nothing is playing) |
| Right | Music |
| Down | Games: Blockz becomes the first row of the Games screen (gbprobe.c, task 20) |
| Left | Settings (stock task 10, page 4) |

A direction highlights its tile instantly; **A opens it**; Start is free.

**Firmware (V1.7.8, module 21):**
- The key event stays in **r4** through every handler (GetKey 0x03062FA6).
- Direction events pass through three branch stubs:
  - **0x03081C56** (Up/Down, press + repeat)
  - **0x03081C58** (Right)
  - **0x03081C5A** (Left)
- Repaint: 0x03081CD6 (Post 0x2D). A path: **0x03081C40** (closes the volume pop-up, else runs tile action 0x0308188E
  on the index at 0x03023B94).

**Patch:**
- All three stubs go to one handler.
  - It ignores repeats (`r4 >> 28 != 4`).
  - It maps the low bits to a direction (0x10 Up, 0x04 Right, 0x20 Down, 0x08 Left).
  - It sets the index and branches to repaint.
- A keeps stock's path.
- Settings tile: the Library case (0x03081976) becomes `bl menu_settings` + the routine's epilogue, with
  `menu_settings` = TaskSwitch(10, &4).
- Pictures, first version: one full-screen image per highlighted item, reusing the carousel's image ids (16, 14,
  18, 20; 8 = Now Playing greyed). Stock's paint code is unchanged.
- Target look ([Look and feel](#look-and-feel-decided-2026-11-27), mock-up `01_home.png`): the pet in the middle
  looks toward the highlighted label, which sits on the highlight bar. That needs our own paint code drawing the
  creature from parts.

**Bluetooth in Settings:**
- The Bluetooth chip runs its own firmware; the main firmware only has the stock Bluetooth page (task 10,
  page 3).
- amuletOS already intercepts Settings › Game (text id 0x110) in `hooks/settings_game.S`. That row opens Bluetooth
  instead.
- It is relabelled by rewriting English text record 0x110 (fixed 0x112-byte UTF-16 slot; English block at
  0x48EC + 2 × 0x14896) to "Bluetooth" (stock id 0xAA has the same word).

**Early draft (`drafts/dpad_menu/`) is superseded:**
- `art/dpad_menu.py`, `game/dpad.*` and `game/device/m21_dpad.c` predate these decisions: Left = Blockz,
  double-tap, Start = Settings.
- `m21_dpad.c` also writes a tag at **0x0309FFF0, which holds stock's reset magic**. Free words above the
  carousel's 0x0309FFE4 are 0x0309FFE8..EF only.
- Redo them in this step; the art script's layout and preview approach can be kept.

## Step 3: M3U engine v2

amuletOS's reader (`game/device/pl_core.c`, `exfat.c`) is kept for parsing. It already handles:
- `.m3u` / `.m3u8`, UTF-8 incl. 4-byte characters, BOM, LF/CRLF;
- `#EXTM3U` / `#EXTINF`;
- paths relative to the playlist (`../`, `./`), from the card root (`/…`) and Windows-style (`X:\…`, `\`);
- missing files (skipped).

| Limit today | v2 |
|---|---|
| First 24 tracks per playlist (all resolved up front into a 152 B RAM table at 0x0309FF28) | **Lazy:** keep only position state (~24 B); at each track change read and resolve just the next line. No length limit, no "Loading…" |
| 24 playlists, `/_Playlists/` only | List pages past 24; subfolders show as groups (e.g. `/_Playlists/Auto/`) |
| Case-insensitive for a–z only | Use the exFAT volume's up-case table: accented/non-Latin names match |
| Order fixed | Shuffle with no repeats and no RAM list (full-period permutation: seed + counter); repeat off/one/all; Prev walks back |
| Lost on power-off | Playlist + entry + shuffle state saved in the config block |

- **Finding entry N:** scan the file. Large generated playlists also get `Name.m3u8.idx` (4-byte byte offset per
  entry) for direct access.
- **Now Playing** shows `Playlist name · 12/340`.
- **Tests:** extend `game/test/test_playlists.c` with every path style, CRLF/BOM, 4-byte UTF-8, accent case
  mismatches, missing entries, a 10,000-entry playlist with and without `.idx`, shuffle visiting every entry once.
- **Device check:** open time for 5,000 entries, track-change latency, resume after power cycle.

## Step 4: Mood map and Instrumentals

Inspired by Sony's SensMe Channels, but a 2D map instead of named channels.

**PC script `mood_map.py`** (Linux x86_64; `pip install essentia-tensorflow`, ffmpeg):
1. Find audio files on the card; cache results in `/_Mood/analysis.csv` keyed by path + size + mtime, so re-runs
   only analyse new files.
2. Decode with ffmpeg (FLAC, MP3, AAC/ALAC, APE, WMA, OGG, WAV, DSD); analyse three 30 s excerpts (25/50/75 %).
3. Run Essentia's **arousal/valence** models (MTG, trained on emoMusic/DEAM): arousal = calm→intense,
   valence = dark→bright. Run the **voice/instrumental** classifier on the same embeddings.
4. Spread each axis by percentile within the library, so the map fills evenly.
5. `/_Mood/overrides.csv` pins tracks (energy, mood, instrumental yes/no); BPM/MOOD tags can be hints.
6. Write a 9 × 7 grid:
   - `cell_X_Y.m3u8` with the ~100 tracks nearest each cell centre, plus `cell_X_Y_instr.m3u8`;
   - `map.txt` with per-cell counts;
   - `.idx` files for the large playlists.
   Paths are relative to each playlist file.
7. Write `/_Playlists/Auto/Instrumentals.m3u8`: a track counts only if **all three excerpts** score ≥ 0.8
   instrumental.
8. Write `mood_map.html`, an interactive scatter of the library (instrumentals outlined), for checking before
   copying.
9. Write the compact quadrant lookup that [the pet](#the-pet) reads at each track change.

Fallback without Essentia: key (major/minor) + brightness + tempo scoring.

**Limits:**
- Lyrics are ignored.
- The instrumental classifier struggles with choirs, vocal samples and spoken intros.
- Essentia's code is AGPL-3.0 and the models are CC BY-NC-SA 4.0: fine for personal use.

**Device: Mood map screen** (from Music):
- 9 × 7 grid, dots sized by track count, tinted in theme colours.
- D-pad moves the cursor (hold to glide).
- **A plays** the cell (shuffled).
- Start toggles instrumentals-only.
- Select toggles "drift" (each next track from a neighbouring cell).
- B goes back. The cursor position is remembered.

**Verification:** ~50 well-known tracks first; extremes must land in the right corners.

## Step 5: Visualiser

**Where the audio comes from: no audio-path hooks needed.**
- **Music playback (V1.7.8):**
  - On each refill (0x030661A4), the decoder hands over a fresh buffer (codec call 0xA, 0x0308EAE8). Its pointer
    and length (32-bit words, stereo L/R) are stored at **0x03022EB8 / 0x03022EC8**, and DMA channel 5 plays it from
    there.
  - Samples are MSB-aligned, so `>> 16` gives s16 for every source.
  - Player record `*(0x030483D0)`: +0x08 sample rate, +0x9C bit depth; valid only while the player runs.
- **USB DAC mode (V1.8.3, module 11 `USBAudio.c`):** two 2 KB halves at 0x0302F06C; the half being played is at
  **pointer 0x03025F7C / length 0x03025F80**; 16-bit.
- The visualiser copies ~512 samples per frame from whichever is active. DMA only reads that memory, so reading
  alongside is safe.

**Memory budget ≤ 40 KB** so one build fits both modes:
- Music mode: ~58 KB above modules 33/34 (the region amuletOS's Game Boy emulator used).
- USB mode: only modules 9/11/12 load, leaving ~100 KB of overlay window free for code; check whether module 12's
  64 KB working area is in use during USB *audio*.

**Opening it:**
- Now Playing's **Up/Down are unused** by stock (events fall through to 0x03083EEA). They cycle Cover ⇄ styles.
  Left/Right skip, A play/pause, wheel volume, B back.
- In USB DAC mode, hook the USB screen the same way; the caption shows the sample rate (no track info over USB).
- Select = next preset within a style.

**Styles** (148×120 8-bit indexed, scaled 2×; 30 fps; full-screen push ≈ 5 ms):

| Style | Inspired by | Notes |
|---|---|---|
| Spectrum | Winamp built-in / vis_classic | 32–48 bars, slow-falling peak caps, fire and line looks |
| Oscilloscope | Winamp built-in | dots / lines / solid, auto-gain |
| Waterfall | spectrogram plugins | one FFT row per frame |
| Plasma | Geiss | see below |
| SD presets | MilkDrop | `/_Vis/*.txt`: zoom, rotation, warp, decay, wave mode, palette, driven by bass/mid/treble; no reflash for new looks |
| Ring scope / starfield | AVS | starfield speeds up on beats |

- **Beat detection:** bass energy vs its running average, firing on a large jump.
- **Palettes** follow the theme; Game Boy greens optional for any style; album-cover palette in music mode.

**Plasma, from Ryan Geiss's "How 'Geiss' Worked":**
- Each frame: draw the waveform, then warp the image.
- The warp samples a 2×2 cluster with weights summing to 256, then `>> 8`.
- **Carry the 8 discarded bits into the next pixel** (keeps brightness, gives the grain).
- New motion snaps in on a strong beat.
- Unroll 2 pixels per loop.
- Geiss's per-pixel warp map (6 B/pixel) doesn't fit. Instead use a coarse mesh (~19×16 points), interpolated per
  8×8 cell with fixed-point adds: ~25–30 cycles/pixel ≈ 2.5 ms/frame.
- Two 148×120 8-bit frames ≈ 35 KB. Drop to 132×108 or 120×96 if memory is short.

**Unknown:** what DSD files put in the buffer (PCM or DoP; DoP would look like noise).

**Order:** spectrum/scope/waterfall with PC GIF previews → device (music) → USB DAC mode → Plasma → SD presets.

## Step 6: Themes, sleep timer, adventures, extras

**Themes:** the five colourways in [Look and feel](#look-and-feel-decided-2026-11-27): black & orange, paper &
orange, EVA (colours only, no logos or artwork), aqua, candy. They replace the earlier list (Classic Game Boy, Cute
pink, Black & orange, EVA-01, Light, Dark).
- Pre-rendered images (menu, Now Playing frame, lists, volume overlays, icons) are rendered by the art pipeline per
  theme. Code-drawn colours read a theme table in RAM.
- Flash is tight:
  - V1.8.3 uses 28.9 MB of a ~30 MB slot;
  - a theme is ~2–2.5 MB;
  - 124 of the 478 images are full-screen, many belonging to stock screens no longer shown.
  Audit and reclaim them. Settings swaps image ids (stock paint reads ids from RAM).
- **Image audit (V1.8.3, 2026-11-26):**

  | Images | Count | Flash |
  |---|---|---|
  | **Volume pop-up, one full screen per step 0–100 (ids 336–436)** | 101 | **14.0 MB of 18.4 MB** |
  | Leftover recording art: mic animation 310–323, MIC REC / LINE IN 116/117, record screen 107, mic icons 223/233/243 | 20 | 413 KB |
  | Leftover FM radio art: 7-segment digits + MHZ 294–305, dial 306–308, Manual/Preset 175/177 | 17 | 127 KB |

  - **Drawing the volume pop-up in code** (one small ring + number, themed colours) frees ~14 MB: room for all six
    themes several times over.
  - The recording/radio screens themselves are empty modules (tasks 4, 5, 7 → modules 13, 28, 29 have no code), but
    check that no live code draws these ids before reusing their space.
- Later: SD theme packs (`/_Themes/<name>/`) via a hook in stock's image loader.
- PC previews: done for all five colourways (`docs/design/ui/13_colourway_*.png` to `17_*`).

**Sleep timer:**
- Stock has one (10–120 min, auto-off) on the system tick.
- Add:
  - Start on Now Playing opens a picker;
  - "end of track" and "end of album/playlist";
  - 30 s volume fade-out;
  - countdown in the status bar.

**D-pad adventures:**
- Choose-your-own-adventure stories in `/_Adventures/*.txt`: `# page` headers, body text, up to four choice lines
  tagged `^ > v <` with a target page.
- Choices are drawn around a mini D-pad: a direction highlights a choice, **A follows it**, B goes back a page.
- Progress is saved per story; music keeps playing; opened from Games.
- Ships with one short original sample story.

**Remove the stock e-reader** (D-pad adventures get their own module):
- Module 30, task 8: 7.3 KB of flash.
- **One 382-byte module-0 function that only the e-reader calls.** That's resident RAM back, almost half of what
  V1.8.3 squeezed out. Check for stored pointers to it before reuse (calls found: only from module 30).
- Task 8 becomes a free screen slot for our own modules.

**Screen off without the backlight-only glow:**
- Today "screen off" only cuts the backlight. The LCD keeps showing the last frame, which is visible under room
  light (owner's photo: clock and volume ring readable on a dark screen).
- Fix: draw a black frame before cutting the backlight; redraw on wake.
- Later, once the panel controller is identified (its init table is in flash, LcdInterface.c), also send the
  display-off/sleep commands to save power.

**Wheel click = power key:**
- The wheel click is the key that turns the screen off today: almost certainly the GPIO2 pin 5 key (stock code
  0x001, checked first by the key decoder).
- Planned:
  - screen on: click = play/pause;
  - screen off: click = wake only (no accidental pause);
  - screen-off gesture: owner's choice pending (double-click recommended);
  - hold = stock power-off, unchanged.
- Auto screen-off timer stays.

**Smaller extras:**
- **Wheel click = play/pause.** The click is most likely the GPIO2 pin 5 key, which combines with face buttons.
  Confirm with a key-test screen.
- **Lyrics view:** stock already contains `MusicLrc.c` (.lrc); surface it as a Now Playing view.
- **Per-output volume:** 3.5 mm 61 mW vs 4.4 mm 137 mW; jack detect GPIO2 pin 8 / GPIO0 pin 13. Remembered volume
  per jack plus a safe start volume.
- **Full-screen album art:** stock decodes cover JPEGs (module 18, 116×116 today).
- Finer brightness steps (PWM0), a screen-off "pocket mode", accurate battery % and time remaining, a clock face.

### The pet

This replaces the earlier "Peak" idea, which sulked when unfed, and its mock-ups (`docs/design/pet_mockup_v2.png`,
`pet_mockup_v3.png`, `peak_mockup_v4.png`, `art/pet.py`). Mock-ups: `docs/design/ui/05_gallery.png` to `12_*`.

A flat, symmetrical, one-eyed creature that eats the music you play and changes with it.
- **It never gets hungry, upset or dies.** It only responds to what you listen to.
- **Species** (pick one when starting a new pet; the mock-ups show six):
  - **moon**: a disc split in two colours, thin legs, two feelers;
  - **whaleian**: a front-on whale standing on its tail with its fluke for feet, flippers, throat grooves on its
    belly and a spout. The player's mascot is a whale;
  - **sapling**: roots for feet and one trunk forking into two heads, one eye each. When you point, both heads look;
    on the forms screen they look at each other;
  - **arch, dome, star**: drawn as adults only so far. Their young stages and five forms still need designing.
- **Growing up:** three young stages, then adult at **20 hours of listening**.

  | Species | Young stages |
  |---|---|
  | moon | egg → hatchling → young |
  | sapling | seed → sprout → young |
  | whaleian | drop → calf → young |

- **Five adult forms from the mood map** ([Step 4](#step-4-mood-map-and-instrumentals): calm ↔ intense,
  dark ↔ bright):
  - Each track's listening time is added to that track's quadrant, using its mood scores in `/_Mood/`. Tracks
    with no score count as neutral.
  - A quadrant with a clear lead decides the form; if none leads, the form is neutral. The threshold is still to be
    tuned (for example 40 %).
  - Every species uses the same visual language, so the forms read alike across species:

  | Form | Look | Moon | Sapling | Whaleian |
  |---|---|---|---|---|
  | bright & intense | yellow, spikes and stars, eye wide open | spiky crest, zigzag belly | yellow blossoms, narrow leaves | big spout with star tips |
  | bright & calm | pink, flowers, drooping lines, long lashes, relaxed lid | flower feelers, pink spotted belly | pink flowers, round leaves | falling spout with flowers, pink belly |
  | dark & intense | horns or thorns, slit pupil, dark stripes | horns, striped belly, spurs | thorns, a horn on each head | narwhal tusk, no spout |
  | dark & calm | blue and lilac, drops, drooping, heavy lids | drooping feelers with drops, blue belly | weeping lilac strands | drooping spout with drops, blue belly |
  | neutral | plain | cream belly, plain stripes | cream leaves | plain spout |

- **Drifting:** an adult's form is decided again after **every 10 hours of listening**, from that block's quadrant
  shares. It changes in steps, not gradually, until you lock it in the gallery.
- **Gallery** (Settings › Look › creature):
  - One page per species; Left and Right switch species. Each page shows the species' eight forms (three young,
    five adult).
  - Forms you have met show the date you first met them. The others are silhouettes marked ???.
  - It keeps every form from every pet.
  - A on a met form offers: **keep this form**, **start a new pet**, or back.
    - Keep this form: the pet takes that form and stops drifting until you pick again.
    - Start a new pet: opens the species picker; the new pet starts at its first stage.
- **Pet page:** its name, stage or form, hours eaten, and what it ate as dots on a small mood map with each
  quadrant's share. Where it sits in the menus is still open: Games, as planned for Peak, or Settings › Look.
- **On the device:**
  - Counting needs each track's quadrant when the track changes. Plan:
    - the PC mood tool also writes a compact lookup from a file's first cluster to its quadrant;
    - the always-loaded track-change hook (amuletOS's `pl_step_hook`) reads it and adds the seconds listened to
      one of five counters.

    Peak's ring of recent tracks is not enough for 10-hour blocks.
  - Pet state is about 32 B (species, stage, form, lock, hours, the five counters for the current block). It is
    saved in the system config flash block next to the library fingerprint.
  - The gallery (forms met and their dates) lives on the SD card and is written only when a new form appears.
  - Dates come from the player's date/time clock.

## Step 7: Playback options and gapless

- New **Playback** screen (own module), reached from Settings and Now Playing's Select options. Saved in the config
  block.
  - Gapless On/Off
  - MP3 gapless (greyed until it works)
  - Playlist shuffle/repeat
  - DAC filter and gain (moved from stock Settings)
- **Gapless FLAC:** Hidizs's V1.8.3 implementation, exposed as an option.
- **MP3 gapless (research):**
  1. A gapless MP3 transition path. Unknown: needs changes to the core-B MP3 decoder (no source) or the engine.
  2. Trimming the LAME/Xing encoder delay/padding + 529-sample decoder delay by adjusting the buffer
     pointer/length. Easy.

---

## USB DAC: phones can't see it (found and fixed 2026-11-27: fix 3 works on the phone)

- **DAC mode is a separate chip.** In USB DAC mode the AP30 enumerates as **0bda:4a35 "Realtek AP30"** (high
  speed, owner's Linux laptop), not as the RKNano. The RKNano's own USB-audio driver (module 11, 071b:3205,
  UAC1 16-bit/48 kHz) is SDK leftover and unused on this hardware. File transfer is the RKNano (071b:3203).
- **Symptom on the owner's Xiaomi 14 Ultra (Android 16):**
  - the phone enters host mode (root hubs created, Type-C partner seen, 1.5 A) but no device ever enumerates;
  - file transfer works with the same cable (cable end B on the player);
  - the laptop logs `device descriptor read/64, error -110` / `-71`, `not accepting address`, then `attempt
    power cycle`, then success. Phones don't power-cycle the port.
- Pins as read from the code: GPIO0.14 = USB switch (1 RKNano, set at boot; 0 Realtek); GPIO1.4 = audio power;
  GPIO2.1 = headphone amp (low = on); GPIO1.0 = set 0 on DAC entry, 1 on DAC exit (only if still plugged in) and at
  the end of other USB sessions. It is **not** the Realtek's power or reset (fix 2 below).
- **The RKNano is on the bus during the question.** Module 10 runs every USB session and calls UsbDevInit
  (0x03068D90: soft-disconnect, core reset, connect). The question (module 9, 0x03084A60) then blocks for up to
  ~60 s, so the host's requests time out (`-110`). Picking File transfer lets the stack answer, and the host's
  next retry finds 071b:3203.
- **Picking DAC swaps devices with no gap:** the switch moves the lines from the connected RKNano to the Realtek, so
  the host sees no unplug. The laptop finds the Realtek on its next retry: stock firmware, 12:52, two `-71` and then
  the Realtek on the next attempt, no power cut. Later runs only looked like they needed the power cut, because the
  `-71` from the switch ended attempt 2 and the kernel power-cycles before attempt 3.
- **Wrong fixes, built and tested:**
  - fix 1 (build 11): Realtek "on" (GPIO1.0 = 0), 600 ms, then the switch. Theory: the chip boots too late.
  - fix 2 (build 12): after the switch, GPIO1.0 = 1 for 600 ms, then 0. Theory: the chip needs a reset. The laptop
    enumerated the Realtek inside those 600 ms, so GPIO1.0 doesn't turn it off.
- **Phone capture (build 12, logcat + `dumpsys usb` every second over Wireless debugging):**
  - DAC: host mode for 53 s, no device ever attached.
  - File transfer: 071b:3203 attached about 3 s after plug-in, as address 3, so one failed try came first.
  - So the phone retries during the question, but it never notices the swap to the Realtek.
- **Fix 3, `tools/dac_handover.py`: WORKS.** The owner's Xiaomi 14 Ultra sees the DAC (build 13, orange theme,
  2026-11-27).
  - The RKNano soft-disconnects first, with the same write module 10 uses on eject: DCTL 0x60080804 |= 2.
  - Then 800 ms with nothing on the bus, then the stock switch to the Realtek. The host sees an unplug and then a
    new DAC.
  - The next plug-in reconnects the RKNano as usual. 61 bytes in blocks 2 and 4. Refuses fix-1/2 images.
  - Still to check:
    - file transfer still works after a DAC session (it should: UsbDevInit clears SftDiscon at every plug-in);
    - the laptop now finds the DAC without errors;
    - fold the patch into the main amuletOS build (`build.sh`) when that builds again.
- **Consequences for other plans:**
  - the visualiser in USB DAC mode can't use the RKNano audio buffers: the audio goes PC → Realtek, probably
    straight to the DAC. It needs the board's I2S wiring; otherwise drop the idea;
  - the USB mode question (File transfer / DAC) becomes a D-pad chooser: Left = File transfer, Right = DAC, A to
    confirm.

## Hardware reference

| Part | Notes |
|---|---|
| SoC | Rockchip RKNano: two Cortex-M3 cores (~200 MHz; core A UI + engine, core B decoders), ~640 KB core-A RAM, ~2 KB free |
| Screen | 2.0" IPS 296×240 RGB565; framebuffer 0x03006688, stride 592; PWM0 backlight |
| Input | 8 face buttons on one resistor ladder (one at a time; lowest wins); volume wheel = quadrature encoder (GPIO2 0/9); GPIO2 pin 5 key (likely the wheel click) |
| Audio | CS43198 DAC (5 filters incl. NOS, low/high gain), RT6863 amp; 3.5 mm SE + 4.4 mm BAL; native DSD256, PCM 24/192 |
| Bluetooth | 5.3, separate chip with its own firmware; codecs not published |
| USB-C | mass storage + USB DAC mode |
| Battery | 1200 mAh, ADC channel 0, charger detect GPIO2 pin 3 |
| Storage | eMMC (~216 MB user) + microSD up to 256 GB (exFAT) |
| Hidden stock features | lyrics (`MusicLrc.c`), JPEG covers + picture viewer, e-book reader |
| Not present | FM radio, recording, line-in, video: SDK strings only, no code |

## Sources

- [amuletOS](https://github.com/dharma-dingo/amuletOS): `docs/HARDWARE.md`, `docs/HANDOFF.md`, `docs/DEVLOG.md`
- [Hidizs download center](https://www.hidizs.net/pages/download-center) (V1.7.8 and V1.8.3 firmware), [AP30 product page](https://www.hidizs.net/products/hidizs-ap30-music-boy-the-truly-wearable-palm-sized-hi-res-music-player)
- [Essentia models](https://essentia.upf.edu/models.html), [essentia-tensorflow](https://pypi.org/project/essentia-tensorflow/), [arousal/valence model](https://replicate.com/mtg/music-arousal-valence/readme)
- [SensMe (Wikipedia)](https://en.wikipedia.org/wiki/SensMe), [Sony help guide](https://helpguide.sony.net/apmig/walkman_i-manuals/e-series/eng/contents/04/01/01/01.html)
- [vis_classic](https://github.com/WACUP/vis_classic), [MilkDrop](https://www.geisswerks.com/milkdrop/milkdrop.html), [How 'Geiss' Worked](https://geisswerks.com/geiss/secrets.html), [AVS (Wikipedia)](https://Www.Wikipedia.org/wiki/Advanced_Visualization_Studio)
