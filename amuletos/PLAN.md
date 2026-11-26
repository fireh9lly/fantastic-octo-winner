# Custom AP30 firmware: plan

A custom firmware for the Hidizs AP30 "Music Boy", forked from [amuletOS](https://github.com/dharma-dingo/amuletOS)
v0.3 and rebased onto Hidizs's official **V1.8.3**. It is its own project now: no compatibility with amuletOS updates
is kept.

Status: **planning only.** Nothing in this document has been built or run on a device yet, except the early
draft noted under [Step 2](#step-2-four-way-home-menu). Firmware addresses come from disassembling the official
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
| Themes | Six built in (Game Boy, Cute pink, Black & orange, EVA-01, Light, Dark), SD-card theme packs later |
| Music videos | Not planned (no video code in the firmware; would need a fully custom player) |

## Build order

1. [Port to V1.8.3](#step-1-port-to-v183) and rebuild amuletOS v0.3's features
2. [Four-way home menu](#step-2-four-way-home-menu)
3. [M3U engine v2](#step-3-m3u-engine-v2) + [mood map and Instrumentals](#step-4-mood-map-and-instrumentals)
4. [Visualiser](#step-5-visualiser): classic styles → USB DAC mode → Plasma → SD presets
5. [Themes, sleep timer, D-pad adventures, small extras](#step-6-themes-sleep-timer-adventures-extras)
6. [Playback screen, gapless FLAC, MP3 gapless research](#step-7-playback-options-and-gapless)

Each step ends with a flashable image and an on-device check. Recovery if a flash goes wrong: hold a D-pad
corner + A + B while plugging in USB (BootROM loader mode), then restore with `tools/rkwrite.py`.

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
- Now: mapping ~250 addresses to V1.8.3.

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
- Pictures: one full-screen image per highlighted item, reusing the carousel's image ids (16, 14, 18, 20; 8 =
  Now Playing greyed). Stock's paint code is unchanged.

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

**Themes:** Classic Game Boy (faded LCD greens, faint pixel grid), Cute pink (flowers + grids), Black & orange,
EVA-01 (purple + green; colours only, no logos/artwork), Light, Dark.
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
- PC previews of all six themes first.

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

**Smaller extras:**
- **Wheel click = play/pause.** The click is most likely the GPIO2 pin 5 key, which combines with face buttons.
  Confirm with a key-test screen.
- **Lyrics view:** stock already contains `MusicLrc.c` (.lrc); surface it as a Now Playing view.
- **Per-output volume:** 3.5 mm 61 mW vs 4.4 mm 137 mW; jack detect GPIO2 pin 8 / GPIO0 pin 13. Remembered volume
  per jack plus a safe start volume.
- **Full-screen album art:** stock decodes cover JPEGs (module 18, 116×116 today).
- Finer brightness steps (PWM0), a screen-off "pocket mode", accurate battery % and time remaining, a clock face.

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
