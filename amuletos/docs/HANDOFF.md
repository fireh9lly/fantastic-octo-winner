# amuletOS handoff (named SchalaOS until build 36)

State of the project at the end of 2026-11-07. Read this first, then `README.md` (status
checklist, release plan, decisions), `docs/HARDWARE.md` (every technical finding),
`docs/BLOCKZ.md` (v0.2 game spec) and the Notion product spec.

---

## 1. What it is, where things live

**amuletOS** is custom firmware for the **Hidizs AP30 Music Boy**: Rockchip RKNano (two
Cortex-M3 cores), CS43198 DAC, 296×240 RGB565 screen with rounded bezel corners, Game Boy-style
controls (d-pad, A, B, Start, Select, a volume wheel, power). Theme: the Kingdom of Zeal colours
(sky blue, cloud white, lavender, gold) in a Game Boy Color era style. 

| Thing | Where |
|---|---|
| Repo (local) | `C:\Users\Admin\claude\schala-os` (own git repo, branch `main`) |
| Repo (remote) | github.com/dharma-dingo/schala-os (private). Repo-local identity `dharma-dingo` with a noreply email. |
| Product spec | Notion → Retro Tech → "amuletOS (AP30 Custom Firmware): Product Spec" (page 411894f1713a81338dcbdb2ae963ced5) |
| Design mockups | claude.ai artifact "AP30 Screen Mockups" (REib6hwrurHvLUW9jQSEuJ). The boot splash and icon art were ported from it. |
| Stock firmware | `firmware/HIFIYF18.IMG` (V1.7.8). PC only, git-ignored, never commit or share. |
| Device backup | `backup/` (476 MB flash dump, verified twice, SHA-256 in `backup/SHA256SUMS`). PC only. |
| Zadig | `tools/zadig/` (WinUSB driver for loader mode). PC only. |
| Toolchain | Arm GNU Toolchain 13.3.Rel1 at `C:\Users\Admin\tools\arm-gnu-toolchain\...\bin` (`-mcpu=cortex-m3 -mthumb`) |
| Python | 3.12 with capstone, pyusb + libusb_package, numpy, Pillow. ffmpeg is installed. |

---

## 2. How to build, flash and recover

**Release (v0.3+):** `bash build/b60.sh` (the release build), then
`python tools/make_patch.py firmware/HIFIYF18.IMG build/v060/HIFIYF18.IMG build/release_v0.3` writes
`amuletos_patch.py` and `amuletOS-0.3-patcher.html` (the GitHub release assets). Never publish an IMG: it contains
Hidizs firmware. A new release needs a newer stamp than the last "back to stock" stamp (2620071161).


**Normal install (no special mode):** copy `HIFIYF18.IMG` to the top level of the AP30's
internal drive (the ~216 MB one, usually D:), eject, unplug, restart. The device installs it on
the next boot (the screen can stay black for a minute or two) and deletes the file. **The build
stamp must be newer than the installed one.**

- Stamp format: `YY YY DD MM BB 00 00 00`, BCD, year little-endian, then day, month, build.
  Today's builds use `26 20 07 11 BB`. Next free build number: **27** (`2620071127000000`).
- **Low battery makes the updater silently eat the file without flashing.** Charge first.
- Pressing **B on the USB-transfer screen drops USB** (goes back to the main menu).

**Loader mode (recovery / raw flash access):** unplug, hold power ~10 s, hold a d-pad corner + A
+ B *before* plugging in, keep holding ~3 s, let go. Screen stays black; device appears as USB
`2207:262D`. If Windows shows "Device Descriptor Request Failed", power off fully and replug.
Always send `python tools/rkread.py td` before the first read in a session.

- Read: `tools/rkread.py rl LBA COUNT OUT` (read-only tool, max 32 sectors per transfer).
- Write: `tools/rkwrite.py wl LBA FILE --allow-any` (every write is read back).
- Slots: fw1 at LBA 0, fw2 at LBA 0xF000. A slot on flash is the IMG **without** its CRC
  trailer, so a change confined to one 512-byte sector can be written directly into both slots
  (done twice on 2026-11-07: H0 → H0a, then back to stock). Full recovery: write a good image at
  LBA 0.

**Build tools:**

| Command | What it does |
|---|---|
| `tools/ap30fw.py info/verify/unpack/pack` | image container; byte-identical round trip; `pack --stamp HEX16` |
| `tools/build_hook.py NAME STAMP16` | assembles `hooks/*.S`, stores it in the code.bin gap, points **module slot 2** at it, redirects a BL, packs + verifies |
| `tools/imgres.py list/export/pack` | UI images (raw big-endian RGB565), byte-identical round trip |
| `tools/build_reskin.py BASE ART STAMP16 --out DIR` | overlays `NNN.png` replacements onto BASE's images and packs |
| `tools/inquiry.py D [--loop N --changes]` | live SCSI INQUIRY to the drive, no admin: build 36+ answers `AMULETOS | AP30 | 0.3` (builds 13-35: D1 diagnostics, `SCHALAOS | clock adc adc | D1`); check it before copying an image |
| `tools/fwmap.py`, `xref.py`, `fwdis.py` | function/string index, caller trees, annotated disassembly |

**Rebuilding v0.1 from scratch:**

```
python tools/ap30fw.py unpack firmware/HIFIYF18.IMG build/stock
python tools/build_hook.py d1 2620071113000000            # build/d1 (stock + D1 hook; builds 13-35)
python tools/build_hook.py amu 2620071136000000 --out build/amu   # build 36+: stock + amuletOS INQUIRY name (56 B)
python tools/imgres.py export build/stock/images.bin build/img_stock
python art/boot_splash.py build/art_v01
python art/screens.py build/art_v01
python art/menu_panels.py build/art_v01
python art/recolor.py build/img_stock build/art_v01 build/art_v01_auto
# merge: auto first, then hand-made on top
mkdir build/art_v01_all; cp build/art_v01_auto/*.png build/art_v01_all/; cp build/art_v01/*.png build/art_v01_all/
# v0.3 Pocket look (build 30+): replaces art_v01_all, keeps the v0.1 boot/shutdown images
python art/pocket.py build/art_pocket build/v029
python art/recolor.py build/img_stock build/art_pocket build/art_pocket_auto pocket
mkdir build/art_pocket_all; cp build/art_pocket_auto/*.png build/art_pocket/*.png build/art_pocket_all/; python art/boot_splash.py build/art_boot v0.3                  # boot/shutdown keep the v0.1 scene; version kept current
cp build/art_boot/000.png build/art_boot/002.png build/art_pocket_all/
python tools/build_helpers.py build/amu build/d1h game/device/np_helpers.c game/device/np_stub.S game/device/libscan.c
python tools/build_overlay.py build/d1h build/d1h_o game/device/npui.c --slot 28 --run 0x03083F0C --max 0x758 --at 0x5B400 --json npui.json
python tools/extend_module.py build/d1h_o build/d1h_e game/device/m21_ext.S game/device/m21_ext.c --module 21 --json e21.json
python tools/extend_module.py build/d1h_e build/d1h_e game/device/m22_ext.S game/device/m22_ext.c --module 22 --json e22.json
python tools/patch_code.py build/d1h_e build/d1h_np np_v4,np_hide_format,menu_games_to_blockz,lib_skip,menu_carousel,music_update,playlists
python tools/build_module.py build/d1h_np build/d1h_np_bz game/device/blockz.c --at 0x58800
python tools/build_module.py build/d1h_np_bz build/d1h_np_bz_pl game/device/playlists.c --module 86 --in-place --desc pl_desc --data-max 0xD00
python tools/build_reskin.py build/d1h_np_bz_pl build/art_pocket_all 26200711NN000000 --out build/v0NN --font tall
```

---

## 3. What happened, in order

### M0: tooling and backup
Container decoded (header, six sections, backup header, Rockchip CRC32 poly 0x04C10DB7). Stamp
decoded. Loader mode found and a full flash backup taken. Official V1.7.8 installed (the unit had
been on an August build).

### Gate 1: modified code runs (passed)
- 1a: USB vendor string changed in three places in code.bin → enumerated as "SCHALAOS USB MP3".
- 1b: one instruction in module 12 (USB storage) changed → internal disk answered as the SD card.
- No signature or code checksum exists on the update path.

### M1: hardware map (most of it)
- **Code layout:** code.bin loads at 0x03050000; 113 modules, each `code load/exec/size, data
  load/exec/size, ZI exec/size`; "load" addresses are file positions (minus 0x03050000).
- **Module loading:** `ModuleOverlay(n, type)` at 0x030683DE copies a module from **flash** to
  its run address (bit 0 code, bit 1 data, bit 2 zero ZI). The image is never loaded into RAM as a
  whole. **RAM ends at 0x030A0000 (640 KB).** Free: 0x0309F800–0x0309FFF0 (2 KB; 0x0309FFF0 holds
  reset magic).
- **H0/H0a failed:** code placed in the 16 KB zero gap in the file (code.bin 0x57B8C) was never
  loaded; its assumed RAM address was past the end of RAM. USB enumeration hung. Undone by
  single-sector loader-mode writes.
- **H1 passed (build 12):** empty **module slot 2** is loaded by stock in 21 places, including
  USB start right after module 12. Pointing slot 2 at bytes in the file gap with run address
  0x0309F800 makes stock load our code itself. The internal disk enumerated as "SCHALAOS ZEAL
  HOOK". **This is the proven way to run our own code.**
- **D1 (build 13):** diagnostics in the disk's INQUIRY name, read live with `inquiry.py`.
  - CPU clock **200 MHz** (USB mode); system clock variable at `*(0x030065C0 + 0x18)`.
  - Battery ADC ch0 ≈ 0x372 (≈ 4.3 V on USB).
  - All 8 face buttons share one ADC ladder (ch1). Measured: Right 0, Up ~119, Left ~240,
    Down 364, Select ~490, Start ~670, B (exits USB, inferred 700–849), A ~854, idle 1023.
  - **Two face buttons pressed together read as one** (series ladder, lowest value wins:
    Right > Up > Left > Down > Select > Start > B > A). Hardware limit. Only the wheel (GPIO
    quadrature encoder) and one GPIO key (GPIO2 pin 5, unidentified button) can combine with a
    face button.
- **Screen push timing deferred to M2:** stock's real flush path is indirect; the obvious blit
  routines have no callers. DMA controller, SysTick (unused on core A, usable as a cycle counter)
  and the fill/text routines are documented in HARDWARE.md.
- **Play delay:** static analysis found ~270 ms of fixed DAC power-up waits of the ~3 s; the rest
  is untraced. Deferred to ≈ v0.3 (owner has no smartphone for slow-motion video; firmware
  timestamp hooks are the plan when we get there).

### Re-scope (owner)
"Get v0.1 stylistically correct and playing music with some block." Deep latency work moves to
≈ v0.3. Release plan in README.

### v0.1: Zeal reskin of stock (built, on device)
- The UI images section (ROCK26IMAGERES) is 478 raw big-endian RGB565 images with a simple
  table; `imgres.py` exports/packs them losslessly.
- Static analysis of the image-draw functions (module 0, ~0x030646CE–0x03064D88) found the images
  the UI really uses; most of the 452 unique images are Rockchip SDK leftovers.
- Art pipeline in `art/` (all original, drawn on a 148×120 grid, scaled 2×): `zeal.py` (palette,
  5×7 font, canvas), `boot_splash.py` (000 boot, 002 goodbye), `icons.py` (24×24 relic icons with
  auto outline), `menu_panels.py` (main menu as art-book panels), `screens.py` (volume 336–436,
  list 159, highlight bars 184/185, plain 089, Now Playing 026, default art 277, USB 003, charging
  004–007, DAC 017, updating 437), `recolor.py` (automatic Zeal recolour of every other image;
  pure black/white kept as possible colour keys).
- Rule used everywhere: stock draws **dark text** on top at run time, so text areas stay light
  (cream panels); colour lives in frames, margins and patterns.
- Owner feedback applied: "v0.1" was clipped by the rounded corner (moved in); the icon set chosen
  was **B, Zeal relics**; the menu became **art-book panels** (one big card per item with the
  neighbours peeking and a 2×3 position map) instead of the 6-tile grid; **subtitles removed**
  ("AI fluff"), titles only.
- **Menu image mapping (measured):** stock shows 016 for top-left (Music), 014 top-middle (Games),
  018 top-right (Library), 022 bottom-left (Folders), 020 bottom-middle (BT), 024 bottom-right
  (Setup). The first v0.1 build had these swapped; fixed in build 16.
- Not reskinned in v0.1: stock's games (they draw with fill colours in code, no images) and text
  colours (stock's dark text is readable on our panels).

### Builds made on 2026-11-07

| Build | Stamp | Content | Result |
|---|---|---|---|
| 09 | 26 20 07 11 09 | Gate 1a (vendor string) | passed |
| 10 | …10 | Gate 1b (INQUIRY swap) | passed |
| 11 | …11 | H0 / H0a (file gap) | USB hang; undone in loader mode |
| 12 | …12 | H1 (slot 2 hook) | passed |
| 13 | …13 | D1 diagnostics | passed, results above |
| 14 | …14 | D1 + boot/goodbye art | passed ("v0.1" clipped) |
| 15 | …15 | D1 + full v0.1 reskin | art-book "beautiful", menu order wrong |
| 16 | …16 | build 15 + menu mapping fix + no subtitles | passed (owner: menu panels and text OK) |
| 17 | …17 | build 16 + font style D (`--font bold1x`): ASCII glyphs in both stock fonts replaced | installed; font replaced everywhere but **too small to read** (owner): needs a bigger font |
| 18 | …18 | build 16 art + tall font (`--font tall`, `art/font_tall.py`) + Now Playing patches (`tools/patch_code.py np_hide_album_genre,np_title_not_filename`) | installed: font size right (owner); Now Playing showed artist + **file name** (0x03048450 is the file name), album/genre hidden; genre icon, white strips past the panel and format line still to fix |
| 19 | …19 | build 18 + Blockz test module T1 in module 82 (`tools/build_module.py build/d1np build/d1np_t1 game/device/test_module.c`) | superseded by 20 (never on device) |
| 20 | …20 | build 18 fixes: title tag on the scrolling line with file-name fallback (`np_title_tag`, hooks/np_title.S), format line hidden (`np_hide_format`), Now Playing art: only the artist icon, panels run off the edge so the line strips (069, 028) blend in; + Blockz T1 | installed: owner wants album back, artist overflows the box; Blockz not reachable (game list untouched) |
| 21 | …21 | slot-2 resident helpers after D1 (`tools/build_helpers.py`, `game/device/np_helpers.c`): artist wraps onto 2 lines, album on line 3, title with file-name fallback (`np_v2`); format hidden; **Games tile opens Blockz directly** (`menu_games_to_blockz`), panel relabelled BLOCKZ; Blockz T1 moved to code.bin 0x58800, quits to the main menu | passed: BLOCKZ tile and test screen work (owner); title right (could be bolder); artist wrap good; wants artist higher and album wrapped too |
| 22 | …22 | Now Playing: artist at y 49 and album at y 91, both wrapping over two lines (`np_v3`, helpers 500 B); **Blockz T2: the real game** (`game/device/blockz.c`: core + renderer via FillRect, SysTick 60 fps pacing, ADC directions, GetKey presses, wheel = hold) | Blockz runs and "everything else looks perfect" (owner); bug: random backtracks / sudden drops / shifted hard drops on about every other piece = raw ladder ADC caught mid-sweep |
| 23 | …23 | Blockz: ladder reading accepted only after 16 ms stable (debounce); read-only INFO page (pause, then Left) showing stock's play state for v0.21 | better but same issues (owner); worst right after a hard drop: Up's release sweeps through Left/Down, and rubber pads can make sweeps slower than 16 ms |
| 24 | …24 | Blockz: direction-aware ladder debounce (release sweeps up the ladder: 80 ms; press 24 ms, Down 40 ms; to idle 16 ms), host test `game/test/test_ladder.c` | superseded by 25 (never on device) |
| 25 | …25 | **v0.21 attempt**: `game/device/bgmusic.c` (if nothing plays: find /_blockgame/ on SD via stock FindFirst/FindNext, random track via the play record + player thread, shuffle-loop by watching the record, stop on exit; MUSIC panel status, INFO lines BG/BX) + build 24's debounce | movement "great" (owner; d-pad hardware itself is poor). Music did not start in Blockz on the first try; no library scan had run at power-on, it started only when Music was opened afterwards. MUSIC panel: **EMPTY** (folder found by name, stock folder count 0). Stock's own Files browser also shows /_blockgame/ empty (folder recreated 16:20 by the owner's sync; likely an exFAT layout stock's folder code mishandles), while Music lists and plays the file |
| 26 | …26 | v0.21: when stock's folder count is 0, take the folder's tracks from the library database (records +0 folder cluster, +4 file number) | built and verified on PC (`build/v026`); not on device |
| 27 | …27 | **v0.3 part 1.** Library scan skip (`game/device/libscan.c` in slot 2, patch `lib_skip`): module 5 builds only when the exFAT SD card's fingerprint (serial, cluster count, root directory hash without access times, allocation bitmap hash) differs from the one saved after the last build; fingerprint kept in config block 0 at +0x300; Folders "Update Library?" Yes always rebuilds. Blockz: Select = hold, wheel = volume (VOL readout), exit via Start > Quit. Includes build 26 | host test `test_libscan` (18 cases) passes; image diff vs 26 = only the expected sites; not on device |
| 28 | …28 | **v0.3 Now Playing, layout A** (owner): `game/device/npui.c` as a code-only overlay in module slot 28 (run 0x03083F0C, 1860 of 1880 B), loaded by `np_load` (slot 2) from module 27's init; patch `np_v4` (replaces np_v3): artist 2 lines + album 3 lines in the right panel, double-size title scrolling when too long (file name without extension when untagged), times m:ss / -m:ss, counter n/total, own progress bar; art 026 without the right-panel icons. Includes build 27 | PC preview of the real hook code (`art/np_preview.py`) good; image diff vs 27 = only the expected sites; copied to device (hash verified). Owner: Music and Now Playing "came through great"; corners cut by the rounded screen bezel (inset in 29); Blockz timer ~1.5x fast; Blockz music still not starting (keeps already-playing music fine) |
| 29 | …29 | Now Playing panels and text inset from the rounded screen corners (right panel ends at x 290 with its own border, bottom band x 6..290 / y 168..232, counter at x 18); Blockz: library fallback bounded by the library track count sys+0x2E instead of TotalFiles(filter, 3) (counts the current folder, likely why music never started); INFO page row CK (SysTick LOAD, stock clock variable, CTRL) and row TM (ms since Blockz opened by SysTick vs by the music position, and their ratio x1000) to measure the fast timer | built and checked on PC; not on device |
| 30 | …30 | **Pocket look** (owner, mockups https://claude.ai/artifact/2jDKSjE2kojxqMMU5mB4Nf): `art/pocket.py` draws menu cards, Now Playing frames, cover placeholder, lists, volume, USB/charging/DAC/updating on a white screen with a faint iridescent dot grid; stock's dark list-icon tiles made light (glyph kept); other images recoloured with `recolor.py ... pocket`; boot/shutdown keep v0.1. `npui.c` in Pocket colours and frame positions. **One-level carousel** (`menu_carousel`: Now Playing, Music, Blockz, Library; Start = Settings) with Music icon B. **Music menu Update** (`music_update`: 8th item, forced rebuild). USB arrow gone. Includes build 29 | packed images and code diff vs 29 as expected; PC preview of Now Playing good; copied to device (hash verified). Owner: Start did not open Settings (menu hook was on event 0x20000100; a Start press is 0x40000100); first Music visit rebuilt the library (expected: the firmware install resets the config block that holds the fingerprint) |
| 31 | …31 | Main menu: Start press (event 0x40000100) opens Settings: the key dispatch fallthrough (m21 0x03081B8A) goes to `menu_key_more` in slot 2 (Start -> 0x03081BA6, else exit) | built, code diff vs 30 as expected; copied to device (hash verified). Owner: Blockz crashes on open (first build with build 29's Blockz changes on the device) |
| 32 | …32 | Blockz crash fixes (suspected causes, both from build 29): the INFO clock check read the play-state pointer 0x030483D0 at open, which lives in the music engine's RAM (module 33 ZI) and is garbage when nothing has played since boot: now read only while the player runs and only if it points into RAM; the library fallback read up to all ~8400 records in one call (seconds blocked): now 24 records per service call in the background (MUSIC panel SCAN). Boot splash shows v0.3 | built; code diff vs 31 = Blockz only, images vs 30 = 000 only; not on device |
| 33 | …33 | Main menu (owner): fresh boot starts on Music, not Now Playing; the Now Playing card is greyed out and does nothing while the player thread is not running (stock's Now Playing opened on an empty record and showed an error). `menu_art` (slot 2) swaps module 21's tile-table image ids in RAM (0x03023B64 + 8k + 4) at menu entry: greyed cards 8 / 20 / 24 (`art/pocket.py GREY_STATES`) for 16 / 14 / 22; `menu_np` = the Now Playing tile action. Slot 2 was 44 B over: the unused v0.2 Now Playing helpers (np_v2 / np_v3) were removed (in git up to e86d06a). Includes build 32 | built; code diff vs 32 only at the slot-2 call sites (moved helpers) plus menu sites; images vs 32 = 008, 020, 024 only; copied to device (hash verified; build 32 never went on). Owner: no Blockz crash with or without music; MUSIC ON with music playing; timer right (20 s = 20 s against a phone; TM ratio 0.999); no library rebuild after a power cycle (scan skip confirmed); Blockz own music: EMPTY |
| 34 | …34 | **Blockz music:** owner's SD card checked on the PC: `/_blockgame/` = cluster 0x000A0C32 (Windows LCN 0xA0C30), one file (Classic Theme.mp3). Stock's folder iterator gave the root's directory info, so the count and the library search found nothing (EMPTY); `bgmusic.c` now walks the exFAT card itself with the scan skip's raw sector read (root -> "_blockgame" entry set -> first cluster -> files with an extension in stock's audio filter), 4 sectors per service call (SCAN); library-database search removed; host test `game/test/test_bgwalk.c`. **Now Playing (owner photo of 33):** stock's three 128 px info-line clears (image 69 at x 168, y 91/112/133) ran past the right panel's border (white bars): first one now `np_clear_info` (panel text area), the other two removed; frames get 8 px rounded corners (`art/pocket.py R_NP`); bottom band in from the screen's round bottom corners (x 21..274, title/times/bar follow). **Music menu icons** from the mockup (8x8 glyphs, 2x, item colours; normal set 227-235, highlighted +10); Favorites gets the heart (234), Update refresh arrows (235). Includes build 33 | built; walk host test passes; code diff vs 33 = slot-2 table (2 icon ids), m27 call sites (overlay grew), m28, m82; images vs 33 = 026, list icons only; copied to device (hash verified). Owner: Blockz own music still does not start (tabled for now) |
| 35 | …35 | **M3U playlists:** Music menu row "Playlists" (9th entry, text 86, action 0x50: m22 select exit 0x0308197E -> `pl_menu_exit`, TaskSwitch(19)) opens the **Playlists screen = module 86** (task 19, a stock game nobody reaches; installed in place: `build_module.py --module 86 --in-place --desc pl_desc --data-max 0xD00`; `game/device/playlists.c` + `exfat.c` + `pl_core.c`): lists `/_Playlists/*.m3u*`, A resolves the entries (folder cluster + directory slot + 1) into the slot-2 table (`pl_table.h`, 0x0309FF28, 24 entries) and starts entry 1 like Folders (record source 0x63, TaskSwitch(3, {1, 0x46, 0x504C})). Song changes: 0x0305E930's entry -> `pl_step_hook` / `pl_step` (np_helpers.c): while the record is on the table's current entry, Next / Prev / track end (and shuffle) move along the table. Slot 2 is now full (20 B spare). **Blockz music, second attempt:** tracks of /_blockgame/ by directory slot into the same table, shuffled; start copies Now Playing's init including `*(u8 *)0x030483C8 = 1` (missing in 25-34); the player moves on by itself; reshuffle when it stops. Host tests `test_playlists.c` (simulated card), `test_bgwalk.c` (slots); `game/pc/pl_card.c` + `tools/pl_truth.py` check the resolver on the real card: all 16 playlists, 215 of 215 entries resolved, identical to the independent reader; 257..1376 sector reads per playlist (sets the "Loading" time on the device) | built; code diff vs 34 = hook sites, moved slot-2 call sites, m2, m82, m86; images vs 34 = 236, 246 only; copied to device (hash verified). Owner: picking a playlist loads forever (stuck in Loading, needs a power-off); Playlists screen black with white text, no icons |
| 36 | …36 | **Playlist start fix:** the player thread's init (m33 0x0308DDD0), for source 0x63, sets the record total from 0x0308DD48(3) = TotalFiles(filter, 3) of the *current Folders folder* and seeks with 0x0305E85C(record, index, ...) (TotalFiles again, 0x0305AE16 card-wide index -> folder, FindNext to the file), overwriting cluster / file number; with the browser's state stale that hung (build 35) or played nothing (Blockz). Hooks at m33 0x0308DF12 (`pl_init_count`) and 0x0308DFB8 (`pl_init_seek`) skip both while `pl_active` (record on the playlist table's current entry). **Playlists screen** drawn with FillRect only (Pocket list layout, icon, text from the font bitmaps): stock image / text calls showed black in this game-task window. **amuletOS:** boot splash option A (name in new lowercase glyphs), the D1 diagnostics hook replaced by `hooks/amu_inq.S` (static INQUIRY "AMULETOS AP30 0.3", 56 B instead of 140; frees slot 2), new base `build/amu`, docs and code renamed. Slot 2: 16 B spare | built; host tests pass; code diff vs 35 = moved slot-2 call sites, m2, m33 (2 hooks), m86; images = 000, 002; copied to device (hash verified). Owner: boot good, playlists start quickly; Music menu icons missing (stock never drew them, build 37); asked about Directory List (removed in 37). INQUIRY confirmed AMULETOS AP30 0.3 |
| 37 | …37 | **Room for screen code:** `tools/extend_module.py` copies a screen module's code into donor file space (stock game module 100, 13 KB, unreachable; its table entry then opens Playlists) and links our extension right after it at the module's own run addresses. Main menu helpers (`m21_ext.S/.c`: carousel, grey Now Playing) and the Music menu table + Playlists exit (`m22_ext.S/.c`) moved out of slot 2: slot 2 now 1448 B of helpers, 328 B free (for the Folders fix). **Music menu icons:** stock never drew the table's icon ids; both row-text calls (m22 0x03081F54, 0x03082034) go to `m22_row_text`: icon at x 8 (highlighted set on the selected row), text 26 px right. **Directory List removed** from the Music menu (owner; the Library card is the folder browser): 8 rows | built; host tests pass; code diff vs 36 = moved slot-2 call sites, m2 smaller, m21 / m22 relocated with extensions, m100 entry; no image changes; copied to device (hash verified; device answered AMULETOS AP30 0.3 on build 36). Owner: icons in; all text Chinese (the install reset the language) |
| 38 | …38 | **Settings survive installs** (`keep_settings`, m1 0x030821B4): after an update the boot config load skipped reading the saved block (FWUP path) and fell back to defaults: Chinese, library rebuild after every install. Now it reads the block like a normal boot (HARDWARE.md "Settings across a firmware install") | built; code diff vs 37 = that one branch; copied to device (hash verified) |
| 39 | …39 | **Always English** (`english`, m1 0x03082306): the boot config load sets the language to English instead of the saved one (amuletOS art is English-only; after 37's reset the owner was stuck in Chinese menus). Owner asked for an update rather than finding Language in Chinese | built; image diff vs 38 = that instruction, stamp, checksums; copied to device (hash verified) |
| 40 | …40 | **B in Now Playing opens the main menu** (`np_back_home`, m27 0x030838E2): stock went back to the folder browser (Folders, playlists, Blockz) or the Music list by source; now B takes the Menu key's path (TaskSwitch(10)) after its popup checks. Owner confirmed 39: English, Blockz music plays | built; image diff vs 39 = that branch, stamp, checksums; copied to device (hash verified) |
| 41 | …41 | **Game Boy probe** (owner: "Run the probe"): Peanut-GB (MIT, game/third_party/peanut_gb) + a 1 KB ROM page cache (`game/device/gb_core.c`, host test `game/test/test_gb.c`) in `game/device/gbprobe.c`, task 20 (module 87; code in the file space of stock games 87..99 via `build_module.py --span`, -O2, 24.9 KB). Opened by a temporary ninth Music menu row "Games" (text 9, action 0x51). Lists /_gb/*.gb, runs at 1x, shows FPS, ms per frame (emulate / draw with stock Window + Pixel / push with stock flush 0x0306558A), page loads, raw ADC, GPIO key, held buttons, last key event; hold Select 1.5 s quits. "Test core B memory" row reads 0x01000000 and write-tests 0x0102E000 from core A. Memory: state + 36 pages at 0x03090800..0x0309F7C0 (only module 39, the library builder, loads there), 18 pages after the module code up to 0x0308BF84; music may keep playing. No sound, no saves | built; copied to device (hash verified); SD card /_gb/: Tetris, Kirby 2, FFA (all Color-only hacks), Super Mario Land, The Frog for Whom the Bell Tolls, Embers of Mana |
| 42 | …42 | **Game Boy probe, faster drawing.** Owner on 41 (Super Mario Land): FPS 29.7, EMU 13.1, DRAW 15.0, PUSH 5.2 ms a frame, 54 pages, 0 loads, "slow, laggy" (33 ms a frame = every frame twice as long as allowed). 42: lines written straight into stock's framebuffer (rows 0..189 at 0x03006688, 190.. at 0x0306FD50, stride 592, mirrored, pixel pairs swapped) and marked dirty with one Window() per frame; Peanut sprite sorting off (`PEANUT_GB_HIGH_LCD_ACCURACY 0`, host frames identical on Mario Land and Frog); MHz shown from SysTick LOAD and stock's clock word 0x030065D8 (is the core below 200 MHz outside USB?) | built; copied to device (hash verified) |
| 43 | …43 | **Probe Benchmark row.** Owner on 42 (Mario): FPS 49.6, EMU 13.3, DRAW 1.4, PUSH 5.2 ms, MHZ 200, CLK 200. The PC runs a Mario frame in 0.09 ms (150x faster; 20-40x expected) and Mario makes only ~2,000 ROM reads a frame, so the callback is not it. "Benchmark" measures with the DWT cycle counter, interrupts off: cycles per loop iteration with the loop in the overlay window / the probe region / the stack, cycles per read in the probe region / data window / framebuffer / overlay window, the window loop with interrupts on (time taken by other threads), and whether music plays. Also: DMG LCD look added to the README backlog (owner) | built; copied to device (hash verified) |
| 44 | …44 | **Benchmark timed with SysTick.** Owner on 43: all Benchmark values 0: the DWT cycle counter does not run on this chip. 44 times each span (interrupts off, each under one 10 ms tick) from SysTick VAL, which counts at the core clock; the interrupts-on loop uses the tick time | built; copied to device (hash verified) |
| 45 | …45 | **Benchmark one step per service call.** Owner on 44: "Error 17998584" right after Benchmark (not a code the probe sets: its state was overwritten during the run). 45 runs the 8 steps one per service call, drawing results as they come, the riskiest last (loop copied into the probe region, then onto the stack); the screen shows "step n of 8", the error screen the step reached | built; copied to device (hash verified). Owner: froze at "step 6 of 8" = running code from 0x03090900 hangs (region is data-only) |
| 46 | …46 | **Probe: push without the second pass.** Owner on 45 Benchmark (cycles, interrupts off; music off): loop 4.0, read region 5.0, data 5.0, screen 5.0, window 5.7; loop with interrupts on 4.0: memory is normal speed and nothing else takes time, so EMU 13.3 ms is Peanut's real cost (the PC-ratio alarm was wrong). Flush 0x0306558A pushes rows < 190 through panel ops[5], then for rows >= 190 busy-waits ~1 ms (0x03065B58(1)) and pushes again; stock blit 0x03064F70 itself starts DMA and returns. 46: Game Boy picture at y 44..187 (was 48..191) so frames take only the first pass; bottom line shows ops[5]'s address (to see whether it waits for the DMA) | built; copied to device (hash verified) |
| 47 | …47 | **Probe: background screen push.** Owner on 46 (Mario): FPS 55 still / 49 moving, PUSH 3.2 ms (was 5.2), OP 03080FED. ops[5] = module 4 (panel driver, resident at 0x03080E9C) 0x03080FEC: window 0x03080F28, command 0x0306DE9C(0, 6), DMA channel 0x030614F8, DMA 0x03061524 to LCD FIFO 0x6007002C with settings 0x0306E96C and completion 0x03080EAC (sets u16 0x03023B44 = 1), then waits for that flag. 47 does the same without the wait (full-width rows 44..187); the next push or stock flush waits for the flag first. Top line now EMU / DRAW / PUSH / WAIT | tested: Mario 59.6 fps (EMU 13.2, DRAW 1.4, PUSH 0.0, WAIT 0.0), no tearing |
| 48 | …48 | **Probe: sound test.** Owner on 47 (Mario): FPS 59.6, EMU 13.2, DRAW 1.4, PUSH 0.0, WAIT 0.0, no tearing (full speed). Owner chose sound next. New list row **Sound test**: stops the music player if it runs, powers the DAC up as MusicInit does when it is off, sets 48 kHz (CodecRate + I2S 24-bit), plays a 375 Hz triangle at -24 dB through stock's audio DMA (channel 5 -> I2S1 FIFO, stock's settings block, two 1024-frame buffers chained from our completion handler), unmutes the amp (GPIO2 pin 1 low), 1 s left only then 1 s right only, then mutes and stops. Screen: DMA completions (about 94 a second), late refills, music was playing, DAC was on, channel busy, volume. docs/HARDWARE.md "Sound output" | built; copied to device (hash verified) |
| 49 | …49 | **Sound test: register snapshots.** Owner on 48: heard nothing; DMA 984 completions in 2 s (94 a second expected: words taken ~10x too fast, so the I2S clock is wrong and the DAC likely mutes on it), late 23, music was playing 0, DAC was on 1, channel busy 0, volume 56. Order of our calls checked against stock (I2S init itself releases reset 4 = I2S1 and sets its clock via 0x0305257C). 49 reads 41 audio registers (I2S1, DMA channel 5, GPIO data, CRU 0x00..0x2C / 0x80..0x8C / 0xC0..0xC4, GRF 0xBC, stock clock block 0x030065C0) at the test's start (stock: start a song first) and 0.5 s into the tone; Down shows 4 register pages; summary adds the measured buffer period (21333 us expected) | built; copied to device (hash verified) |
| 50 | …50 | **Game sound.** Owner on 49 (a song playing first): "Buffer every 21333 us", 94 completions in 2 s = exactly 48 kHz (48's 984 = the I2S clock wrong after skipping the DAC power-up because the flag said on); late 28 (the 4 Hz screen redraw stalled the refills: audible stutter). 50: DAC power-up always; **minigb_apu** (MIT, game/third_party/minigb_apu, from the Peanut-GB repo's examples, owner approved the download) on Peanut-GB's sound hooks (`GBX_SOUND`), host test writes OUT.ppm.wav (Mario: notes 392 / 328 Hz, peak 22435); ring of 8 x 256 frames (16 KB) in the music engine's code window 0x0308BF84 (player stopped; m33 / m34 code reloaded with ModuleOverlay on close), completion handler starts the next chunk and clears the finished one; games paced by the sound clock (a frame whenever <= 768 frames are queued; its 803 samples rendered first). Tone test on the same ring, refilled in the handler. Stats: EMU / DRAW / SND ms, LATE chunks a second, STAT = stats redraw ms. **B in Now Playing fixed:** build 40 sent it to task 10 (Settings: the playback options; B there came back, B opened them again; owner "stuck there for a while", hold B = stock's TaskSwitch(0) got out); `np_back_home` now branches to the hold-B path | built; copied to device (hash verified) |
| 51 | …51 | **Sound level, stalls, wheel.** Owner on 50: Sound test inaudible, game sound "soooo quiet", maybe choppy; FPS 59.7, EMU 13.2, DRAW 1.4, SND 1.9, LATE 6..25 a second, STAT 62.5 ms; wheel did nothing in games; music after the game fine. 51: samples MSB-aligned (s16 << 16; 50's << 8 = 48 dB down); stats = 2 lines drawn straight into the framebuffer from a glyph cache (font 2, 0x20..0x5F, read once at game start) and pushed as rows 0..41 by a background DMA (no stock FillRect / flush): FPS / LATE / LOADS / VOL, EMU / DRAW / SND / STAT; the wheel (GetKey 0x40000400 up / 0x40000200 down, as Now Playing) sets sys+0x12 and SetVolume, amp kept on above 0 | tested: Sound test good (left then right); wheel works in games; no stats lines on screen; Super Mario Land crackles when Mario moves |
| 52 | …52 | **Crackle, stats.** Owner on 51: crackle in Super Mario Land that follows movement (scrolling: the frame runs over its 16.7 ms and the sound queue drains); stats lines never showed. 52: frame skip when behind: at a frame start, fewer than SKIP_BELOW (704) sound frames queued past the playing chunk means emulate without drawing (Peanut direct.frame_skip with display.frame_skip_count = 0; no push; PC test: a skipped frame costs about half); sound queue SND_MARGIN 768 -> 960 (20 ms; ring limit 960 + 803 <= 7 chunks); stats no longer pushed on their own: the next game frame's push starts at row 0 instead of 44; line 1 now FPS / LATE / SKIP / LOADS (VOL dropped). test_gb prints emulation ms a frame, GBX_SKIP=1 for frame skip | built; copied to device (hash verified); tested: sound "perfect", gameplay feels right (Super Mario Land, Embers of Mana); still no stats |
| 53 | …53 | **Full-height DMG picture, no stats** (owner: ditch stats, picture full-ish screen, DMG look; picked from PC mockups: full height 266 x 240, "DMG soft + grid"). `game/device/gb_scale.h`: 160 x 144 to 266 x 240 nearest neighbour, centred (x 15..280, light side bars), palette c4cfa1 / 8b956d / 4d533c / 1f1f1f; the second column / row of each 2-wide / 2-tall Game Boy pixel is 35% toward the lightest shade (grid); one pass per Game Boy pixel writes both rows. The core hands over shades (pal = 0..3). Screen push in two parts as stock's flush: rows 0..189, then ~1 ms after that DMA finishes rows 190..239 with their own window, started from the line callback (push_service) so nothing waits. Stats code removed. test_gb writes OUT.ppm.full.ppm through gb_scale.h (240 rows covered, matches the mockup). Drawing is ~2.8x the pixels of 1x, so more frames may be skipped | built; copied to device (hash verified); tested: owner prefers stretched; Pokemon Red stutters (sound and picture); the Games menu item was not in this build |
| 54 | …54 | **Games on the main menu, bigger menu, stretched picture, Pokemon stutter.** Main menu: five cards, Now Playing, Music, Blockz, Games, Library (`menu_carousel`: stock's dead tile code 0x03081996 calls m21_ext.c `menu_games` = TaskSwitch(20); Left = +4 of 5; m21_ext.S wraps over five). Games icon: owner's pick B of three (white creature with raised arms on an ink tile, teal accent). No spare full-screen image, so Games takes 020 (was the Music card with a greyed Now Playing side icon; Music now always shows it in colour); `menu_art` sets all five image ids. Cards bigger (owner: menu sat high): card 136 px (was 104), icon 7x (was 5x), title at y 188, dots 8 px at y 226. Music menu: the temporary Games row is gone (8 items). Game Boy: stretched to 296 x 240 (owner). Pokemon stutter: cartridge RAM was reserved up front from the page cache (32 KB left 11 of 43 pages for 1 MB ROM: 175+ loads a second on the PC); now taken 1 KB at a time on first write (unwritten reads 0xFF): Pokemon Red 1.7 loads a second, 2 pages written in the PC run. Images changed vs 53: 008, 014, 016, 018, 020, 022, 024 only | built; copied to device (hash verified); tested: Games card opens the list (owner) |
| 55 | …55 | **Games list: Emu and Built-in** (owner: "one list, two sections, Emu heading vs Built-in heading"). `gbprobe.c` list rows: heading "Emu", the /_gb ROMs (or "No SD card" / "No _gb folder" / "No games"), heading "Built-in", the 13 stock games still in the firmware (tasks 14, 16..18, 34..42: Retro Block Puzzle, Box Pusher, Brick Breaker, Block Shooter, Gold Catch, Sky Shooter, Bubble Pop, Chinese Checkers, Frog Crossing, Block Puzzle+, Space Battle, Chinese Chess, Mole Hunt; names from text.bin, HARDWARE.md "Stock games"). The cursor skips headings; A on a stock game = TaskSwitch(task, zero arg); the row is kept in big_t (`keep`, tagged) so a game comes back to it. `games_back`: the 14 exit calls of those games go to task 20 instead of the stock list (task 10 page 7, which still lists the reused tasks). Test rows (Sound test, core B memory, Benchmark) removed (owner). Screen title "Games". No image changes | built |
| 56 | …56 | **Settings > Game opens the Games screen** (`settings_game`, hooks/settings_game.S). Stock's item (text 0x110) opened the stock game list, which also lists the games on reused tasks (21..32 would jump into the middle of gbprobe.c). The Settings key handler's enter step (m32 0x0308247C) now branches to a stub that does TaskSwitch(20) for 0x110 and runs stock's enter routine (0x03081C8E) for every other item. The stub sits in the launch code of the stock games on tasks 21..31; the menu cases of the task 21..32 games (table 0x03083770) point at the task-20 case, so the list opens the Games screen for those if it is ever reached. Plain label kept ("Game") | built; code diff vs 55 = m32 only (the hook, 12 case offsets, the 38-byte stub); tests pass; copied to device (hash verified; build 55 never went on, 56 includes it) |
| 57 | …57 | **v0.4 timing log** (owner: start v0.4; plan: measure before fixing, no phone video). Slot 2 `timing.c` `tlog_hook` + `timing.S` stubs log events with stock's 10 ms tick (0x0302288C) into a 22-entry ring at 0x0309F700..0x0309F7C0 (top of the library builder region; gbprobe U_END lowered to 0x0309F700): tag 2 ModuleOverlay (module, type), 3 player thread init m33 0x0308DDD0, 4 Audio Start m33 0x0308C8EE (both patched in the image, `patch_code.py timing`), 6 first audio refill (0x030661A4) after 3/4 = first sound, 7 track step (np_stub.S pl_step_hook), 8 main menu opened (first = boot time; m21_ext.c). Module 0 sites (ModuleOverlay 0x030683DE, refill 0x030661A4) run before slot 2 loads at boot, so m22_ext.c patches them in RAM when the Music menu draws (only if they still hold stock bytes; interrupts off; away from the boot path in case a module 0 write ever faults). `extend_module.py` passes slot-2 symbols as `H_<name>`. Readout: Games list last row "Timing" (boot to menu, start to sound, each event in ms from the latest start = Now Playing load (module 27) or a track step). Slot 2: 1720 B (56 B free); TaskSwitch hook and microsecond times dropped to fit. No image changes | built; copied to device (hash verified)  owner: opening the Music menu started a library update with the hooks live; the log at 0x0309F700 is inside the library builder's code (module 39 code runs 0x03081924..0x0309F7CC), so log writes hit code being run: unsafe, replaced by 58 |
| 58 | …58 | **Timing log moved out of the library builder.** Log now in the 52 B between module 39's code end (0x0309F7CC) and slot 2 (0x0309F800): no module uses it and no literal in code.bin points there. Packed: [0] 0x544C << 16 | count, [1] boot tick | armed << 31, 11 entries tick (20 bits) | tag << 20 | module << 24. gbprobe U_END back to 0x0309F7C0. Same hooks and readout as 57 | built; tested (owner): play from a list: Load 27 and Load 33 at 0, Music init 30, Audio start 550, Load 34 550, first sound 660 ms after the Now Playing load; Next: track step, Audio start, Load 34 at 0, Load 41 and Load 71 at 10, first sound 100 ms. So stock's path from Now Playing to the first refill is fast; the slow part is before Now Playing loads or after the first refill. Boot 250.1 s is wrong (log survived a restart) |
| 59 | …59 | **Timing: key press marker, freeze, boot fix.** TaskSwitch hook back (`t_task`, installed with the others from the Music menu; slot 2 1772 B, 4 B free): a start = TaskSwitch to Now Playing (screen 3) or a track step; the first sound freezes the log until the next start (moving to the Timing screen no longer pushes the start out of the 11-entry ring); main menu only sets the boot time, the first after power-on (tick went backwards = new power-up). Readout start = screen 3 or a track step | built; copied to device (hash verified) |
| 60 | …60 | **amuletOS v0.3 release** (owner: "get this ready for release", call it v0.3, experimental Game Boy OK, hidden test shortcuts OK). No test items in views: the Timing row, timing hooks and the slot-2 logger are dev-only (`-DAMU_TIMING=1` for build_helpers / extend_module / build_module, plus timing.c timing.S and the `timing` patch); slot 2 back to 1448 B. Blockz's info page stays (hidden: Left while paused). Boot screen and USB name already say 0.3. Patchers (`tools/make_patch.py`, `patcher/`): browser page + Python script, input must be official V1.7.8 (SHA-256 c7601873...), output must be this build (3cfeeac7...); patch = our code / art / font as data, 231 recoloured images as one 65536-entry table, 76 lightened list icons as ops, 6 KB of moved stock code as copies from the user's file (48 B of instruction-sized fragments left as data); 511 KB compressed. "Back to stock" = the official file re-stamped 2620071161 with its CRC (ap30fw verify passes). Both tested in the browser and in Python | built; copied to device (hash verified = the patcher output) |

### v0.2 planning (Blockz)
- Owner wants stock's block game **replaced** by our own: Apotris-inspired feel, Tetris DX
  (Game Boy Color) look, original name/code/art. **Sprint 40 lines first.**
- Research: Apotris' source is no longer public; its wiki gives modes, DAS/ARR presets, 1–5
  previews, skins. The SRS guideline (tetris.wiki) gives exact kick tables, 7-bag, hold, 0.5 s
  lock delay with 15 move resets. All captured in `docs/BLOCKZ.md`.
- Owner's picks: **1 next preview; no line-clear or entry delay ("fluid and fast"); Up = hard
  drop; A = rotate clockwise, B = counter-clockwise; wheel up = hold; Select quits to menu (as in
  stock games); Start = pause**. Handling defaults: DAS Fast (9f), ARR Fast (1f), soft drop
  Instant.
- Stock game interface mapped (HARDWARE.md, "UI window / game module interface") — see §6.

---

## 4. Current state

- **Device:** build 16 (v0.1 reskin + D1 diagnostics) was copied to the internal drive; the owner
  restarts to install. Build 15 was confirmed working before that. Next stamp: build 17.
- **Repo:** pushed through `5536755`; later commits (handoff, v0.2 game core) are local only (ask
  before pushing).
- **v0.2 game core (2026-11-07, later session):** §6.3 step 3 done on the PC: `game/core.c`,
  `game/render.c`, tests (87 checks), bot preview and a playable browser build. See
  `docs/BLOCKZ.md` "Status". Next: owner plays `build/game_preview/play.html`
  (`python game/build.py web`), then §6.3 step 1 (minimal device test module) and step 2.
- **Notion:** spec updated with Gate 1, M1 findings (corrected memory model, buttons, 200 MHz),
  release plan (v0.1 reskin, v0.2 own UI and Blockz, v0.3 speed), Blockz requirement.
- **Memory (assistant):** project, owner preferences and feedback files are up to date.

---

## 5. Decisions and owner preferences

- Hybrid approach: keep stock's audio engine (decoders on core B, DAC tuning), replace the UI,
  navigation, library and play-start path over time.
- Release plan: **v0.1** Zeal reskin of stock · **v0.2** own UI (ES-DE-style carousel, Start
  opens Settings, compact font, metadata browsing) + Blockz (Games tile becomes
  **"Blockz"** and launches it directly; other stock games dropped) · **v0.3** speed (play
  start, boot to music, screen timing) · M5 Game Boy emulation (note: direction + A/B is
  impossible on the face buttons; would need the wheel/GPIO key).
- Look: Zeal Sky default, lavender accents, diamond pattern, arrow cursor, bevelled blocks, 2×
  pixel scale, keep content ~12 px from screen corners.
- **Plain labels only; no flavour text or themed copy** (theme lives in art and palette).
- Themes: support theme development, ship a handful. Palette-driven now → theme packs at patch
  time → runtime switching with our own UI.
- **Public release concept:** ship a **web patcher**, never a firmware image. The user downloads
  official V1.7.8 from Hidizs; the patcher verifies its SHA-256, applies our changes locally and
  writes their own image with a newer stamp; install is the normal copy + restart. CLI for power
  users, GitHub Actions builds both, "back to stock" option. Before public: rename away from
  Chrono Trigger names, strip diagnostic hooks, licence + disclaimer, scan git history for
  firmware, testers on other units.
- Working style with the owner: **lead every reply with their next physical action** when there is one;
  ask before flashing and before each push; no smartphone (no video); wants design input early, with
  choices as buttons; terse is fine.

---

## 6. Guidance for building out

### 6.1 Finish v0.1
1. Confirm build 16 on the device: each menu panel matches what opens; check Now Playing, a list,
   volume, USB screen for text overlapping frames (stock text positions were inferred).
2. Fix anything that overlaps by adjusting `art/screens.py` panels; rebuild with the next stamp.
3. Optional polish: the "Chinese prompt after updates" (settings likely reset by each update;
   find where settings live in the hidden FAT32 volume at flash 0x0E208000); patch text colours if
   any stock beige text remains.
4. For a clean v0.1 without diagnostics, build from `build/stock` instead of `build/d1`.

### 6.2 v0.2 Blockz: architecture
- **Replace module 82's table entry** (code.bin offset 8 + 32×82). Stock's menu loads module 82
  through ModuleOverlay when the game is chosen, so our module runs in its place and stock's music
  keeps playing.
- Our module must follow the window contract stock uses for every UI screen:
  - code runs at 0x030815C4 (the overlay window);
  - **data runs at 0x03023B48 and must begin with the window descriptor**
    `{0, 0, tick, service, paint, init, deinit}`; ZI follows the data;
  - **space:** keep code below 0x0308BF84 (music module 33 is resident there while music plays),
    i.e. ~43 KB; module 82 currently uses 4 KB code, 1 KB data, 0.8 KB ZI.
- Stock behaviour to mirror (from module 82): init calls 0x030664A2 then 0x03053822; deinit calls
  0x0306645A then 0x03065BC4; service reads `GetKey()` (0x03062FA6: event type in the top byte,
  key code in the low bits, codes as in §3) and returns 0 to keep running; **on Select it calls
  0x030680D4(0xA, &7) and returns −1, which closes the window back to the menu**; paint redraws
  according to message flags (post 0x03067ED4, test-and-clear 0x03067EF0); drawing uses the
  current colour at 0x03022DEC with fill 0x03064688(x0, y0, x1, y1) and text 0x03063E38(x, y,
  UTF-16 string). Entry points are collected in `game/stock.h`.
- **Where the module's bytes go in the file:** the 16 KB gap at code.bin 0x57B8C (slot 2's D1 hook
  uses the first 140 bytes; drop D1 or start after it). If the game outgrows 16 KB, extend
  code.bin and adjust the table (the packer already handles resized sections; verify on device).
- **Build tooling to add:** a linker script placing `.text` at 0x030815C4 and `.desc` + `.data`
  at 0x03023B48 (descriptor first) with `.bss` after; a `tools/build_module.py` that compiles
  (`arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -Os -ffreestanding -nostdlib`), extracts text and
  data, writes them into the gap, rewrites module 82's eight table words, then packs with
  `build_reskin.py`-style art (base `build/v01`) and verifies.

### 6.3 v0.2 Blockz: sequence
1. **Minimal device test module** following the contract above: draws a screen, reacts to keys,
   quits on Select. Expected failure mode if wrong: only launching the game crashes or hangs; the
   menu, music and copy-updates keep working. If the device hangs on launch, restart; if it
   boot-loops (not expected), use loader-mode recovery. Use D1's INQUIRY name to expose debug
   values if needed (e.g. last key event, tick count).
2. **Confirm the event types** from `GetKey()` (press, repeat, release, long press) by logging
   them; DAS/ARR need press and release, or a held-state query. If stock only reports presses and
   repeats, read the ADC ladder value directly (table at 0x03005A8C, ch1) once per frame and
   decode with midpoint thresholds between the measured values.
3. **Game core in portable C** (`game/core.c`): field (10×40), pieces and SRS states, kick tables
   from the spec, 7-bag, hold, ghost, gravity 1/60 G, lock delay 30 frames with 15 move resets,
   DAS/ARR/soft drop, Sprint timer, 40-line goal, top-out. Drive it with one input bitmask per
   frame so it is deterministic. Add unit tests (kicks, T-spin-free Sprint, bag fairness, lock
   resets) and a PC harness that renders frames to PNG or an HTML replay for review before
   flashing.
4. **Device shell:** tick and service call the core once per frame; paint draws only changed
   cells (stock's fill writes pixel by pixel, too slow for full redraws); find the real screen
   flush path (deferred item) if 60 fps needs it.
5. **Wheel = hold:** read the encoder counters (GPIO2 pins 0/9; step counts at 0x030226E4/E5,
   total at 0x030226E8) while the game runs, and stop the wheel changing volume during play.
6. **Look:** 11 px cells, well 110×220 centred, NEXT (1 preview) and HOLD panels, timer, lines
   left, PPS; bevelled guideline-coloured blocks tuned to the palette; ghost outline; plain labels.
   Reuse `art/zeal.py` colours; render a mock frame on PC for owner review first.
7. **Main menu:** relabel the Games panel "Blockz" and make the tile launch module 82 directly
   (patch the main menu's Games action, module 21); drop the other game modules later to free
   flash.

### 6.4 After that
- **Road to 1.0** (owner, 2026-11-14): Notion "amuletOS: Build Plan to 1.0" (sister of "Community Gripes vs Releases"): v0.4 Speed (timing log first), v0.5 Library (alpha testers start), v0.6 Conveniences, v0.7 Beta (8-hour soaks), 1.0 public patcher. Games continue in parallel. Gapless is not a 1.0 goal (owner, 2026-11-14: not feasible on this hardware).
- **Next build: Games on the main menu** (owner, 2026-11-14). Games gets its own carousel item right after
  Blockz: Now Playing, Music, Blockz, Games, Library. It opens the Game Boy list (module 87) straight from
  the menu, and the temporary "Games" row comes out of the Music menu. New menu icon: RetroArch-esque, a
  chunky pixel space-invader creature, white on the card. It must be our own drawing, not a copy of
  RetroArch's logo. Show the owner 2 or 3 icon options as a mockup before building. Touches `menu_carousel`
  (an extra item), the Music menu patch (the row comes out) and `art/pocket.py` (the icon).
- **Done 2026-11-14: all Game Boy ROMs on the card** (E: when mounted; 11 games in /_GB, Color-only copies removed). Was: copy every .gb from F:\roms\gb to the SD card's
  /_GB when the card is mounted. 4 of the 13 have header byte 0x143 = 0xC0 (Game Boy Color only) and stay greyed
  out: Final Fantasy Adventure (1 MB, a colour hack; the original is 256 KB), Kirby's Dream Land 2 (1 MB colour hack),
  My Friendly Little Island Deluxe (Color homebrew), Tetris (World) (Rev 1) (64 KB colour hack). Playing them needs
  Game Boy Color support in the core (Peanut-GB has none).
- v0.2 Now Playing (owner, 2026-11-07): v0.1 left stock's run-time text (font and positions) on
  Now Playing, so it doesn't match the mockup. Replace module 27 with our own window drawn like the
  mockup ("AP30 Screen Mockups", Now Playing): status bar, art panel, artist and album in
  the compact 6 px font (owner, revised: text = artist + song title only, much bigger; album art stands in for the
  album; play time; no genre, file name, disc or format), double-size scrolling track title, progress bar with lavender playhead,
  elapsed/remaining. Needs stock's playback state (tags, position, length, cover) and its transport
  calls; trace them from module 27. Reuses Blockz's module build tooling and renderer
  approach (own RGB565 drawing, dirty rects). Fallback: patch ASCII glyphs in stock's font section.
- v0.2 carousel (owner, 2026-11-07): one level, items Now Playing, Music, Blockz, Library;
  Start opens Settings; Bluetooth and Folders go under Settings later. Stock's Music and Library
  screens are opened directly until ours replace them (trace their launch calls in module 21).
- v0.2 own UI: an ES-DE-style carousel (true one-direction movement, Start opens Settings),
  compact 6 px font, scrolling titles, metadata browsing. Same window contract, replacing the main
  menu (module 21) and then the browser modules.
- Themes: move palettes into data files; theme packs at patch time; runtime switching later.
- Public release: the web patcher (see §5).
- v0.3 speed: play-start timestamps via hooks, keep the DAC powered while awake, keep the music
  path resident, boot straight to music.

### 6.5 Testing rhythm
Batch changes and review previews on the PC (render from the built image in RGB565 so colours are
exact); flash once per batch. Keep each build's stamp increasing; keep `build/` outputs to roll
back by copy-update. Never commit firmware, backups or the Zadig installer.
