# amuletOS development log (the README until v0.3)

Music-first replacement firmware for the Hidizs AP30 Music Boy, themed after Chrono Trigger's Zeal and Schala. Spec: Notion → Retro Tech → "amuletOS (AP30 Custom Firmware): Product Spec".
Design mockups: https://claude.ai/artifact/REib6hwrurHvLUW9jQSEuJ

## Layout

- `firmware/` stock images from the Hidizs download center. Never commit or redistribute these.
- `tools/ap30fw.py` image tool: `info`, `verify`, `unpack`, `pack [--stamp HEX16]`
- `tools/rkread.py` read-only loader-mode client (backup); `tools/rkwrite.py` guarded loader-mode writer (recovery)
- `tools/build_hook.py` assembles a `hooks/*.S` hook into the code.bin 0x57B8C gap (proven NOT loaded at run time, needs a new location), redirects its BL, packs and verifies (`build_hook.py h0 2620071111000000` → `build/h0/HIFIYF18.IMG`)
- `tools/imgres.py` UI image section (ROCK26IMAGERES): `list`, `export` to PNG + index.json, `pack` back (byte-identical round trip). Pixels are raw big-endian RGB565
- `tools/inquiry.py` sends a live SCSI INQUIRY to a drive letter (reads D1 diagnostics, no admin)
- `tools/fwmap.py` function/string index; `tools/xref.py` caller trees; `tools/fwdis.py` annotated disassembly
- `docs/HARDWARE.md` M1 hardware notes
- `build/` scratch output (git-ignored)
- `design/` UI mockups

## Status (2026-11-07)

M0 tooling:
- [x] Header and section table decoded (6 groups, 6 populated sections)
- [x] CRC is Rockchip CRC32 (poly 0x04C10DB7, MSB first, init 0); reproduced 0x865CA47B
- [x] Unpack then pack of stock V1.7.8 is byte-identical; resized sections repack and verify
- [x] Stamp decoded: `YY YY DD MM BB 00 00 00` = BCD year (LE), day, month, build. V1.7.8 = `26 20 19 10 08`, device = `26 20 19 08 05`
- [x] Loader mode: hold a d-pad corner + A + B, plug USB → black screen, USB `2207:262D`, WinUSB via Zadig
- [x] Flash backup via `tools/rkread.py` (read-only rockusb). Flash reports 983040 sectors; sectors 974848+ refused (reserved), so the backup is LBA 0..974847 (476 MB)
- [x] Backup verified by a second identical read (SHA-256 89ee0673…98c66cb, see backup/SHA256SUMS)

## Flash layout (device dump, 2026-11-07)

| Offset | Contents |
|---|---|
| 0x00000000 | fw1: Aug build (stamp 2026-08-19, build 05), backup header @0x1B3C000 |
| 0x01C00000 | stale fragment of a Jul-23 build (build 00), partly overwritten |
| 0x01E00000 | fw2: same Aug build |
| 0x0E208000 | FAT32, 250 MB, hidden: probably system data / library DB (the review's "234 MB unidentified") |
| 0x10408000 | FAT32, 216 MB: user storage (D:), holds a deleted copy of the Aug update IMG |
| rest | erased (0xFF) |

The device never took V1.7.8.
- [x] Official V1.7.8 installed on the device via copy + reboot
- [x] **Gate 1a**: V1.7.8 with USB vendor `HIFI MP3` → `SCHALAOS` (code.bin 0x8234C/0x823D4/0x823F8), stamp `26 20 07 11 09`, flashed via copy + reboot, enumerates as "SCHALAOS USB MP3". No code-section signature or checksum.
- [x] **Gate 1b**: one instruction in module 12 (USB MSC overlay) at 0x03083952, `ldr r2,[pc,#0x1d8]` → `#0x1dc` (code.bin 0x8172A: 76→77), stamp build 10. Internal disk now enumerates as "SCHALAOS SD". **Gate 1 passed.**

M1:
- [x] **Recovery write path proven** (`tools/rkwrite.py wtest`): in loader mode, wrote a pattern to 64 free blank sectors (LBA 786432, inside the user FAT32), read back OK, restored 0xFF, re-read in a new session OK. Recovery = `rkwrite.py wl 0 <good image> --allow-any`.
- [x] Function naming / analysis setup (`tools/fwmap.py`, `tools/xref.py`)
- [ ] Audio path (DAC, amp, mute timing, play latency). In progress: DAC power-up runs on every music start; fixed waits ≈ 270 ms of the ~3 s. See docs/HARDWARE.md
- [x] Buttons + volume wheel: 8 face buttons on one ADC ladder (ch1) + 1 GPIO key; wheel = quadrature encoder on GPIO2 pins 0/9. Simultaneous face-button presses likely impossible in hardware (to measure). See docs/HARDWARE.md
- [x] Display (static part): 296×240 RGB565 RAM framebuffer, DMA to LCD FIFO 0x6009000C, panel driver chosen from a flash table at boot. Open: controller model, bus speed (measure on device)
- [x] Memory: ≈ 622 KB core A SRAM in use, ≈ 180 KB core B; the "whole image in RAM" model and the 16 KB free block were disproved on device by H0/H0a
- [x] Arm GNU Toolchain 13.3.Rel1 installed and verified (see docs/HARDWARE.md)
- [x] **Custom code runs (H1, 2026-11-07).** Hook loaded by stock's ModuleOverlay via empty module slot 2 into free RAM 0x0309F800, called from module 12's INQUIRY send: internal disk enumerates as "SCHALAOS ZEAL HOOK". (H0/H0a in the bare file gap failed: never loaded, address past the 640 KB RAM end.)
- [x] D1 diagnostics (build 13): CPU clock 200 MHz (USB mode); all 8 ladder buttons measured; **simultaneous face-button presses impossible** (series ladder, lowest wins)
- [ ] Play-path timing (next: owner's slow-motion video, then timestamp hooks)
- [ ] Music-mode clock
- Screen push time: **deferred to M2** (decided 2026-11-07), measured with amuletOS's own display driver. Stock's real flush path is indirect; the module-0 blits 0x03064F70/0x03064FD4 have no callers and do not set the panel window
- [ ] Power / battery / charging (read-only)
- [ ] docs/HARDWARE.md

## Code layout

- code.bin loads at 0x03050000. Word 1 = module count (113). Then 113 × 8 words: code load, code exec, code size, data load, data exec, data size, ZI exec, ZI size (load addresses are relative to 0x03050000 = code.bin offset 0).
- Module 0 = resident core: 0x2E300 bytes from code.bin 0x2988C, runs at 0x03050000; data runs at 0x03004000.
- Module 12 = USB mass storage: code runs at 0x03083610 (code.bin 0x813E8), INQUIRY blocks at 0x03036790 (internal) / 0x030367B4 (SD).

Device currently runs D1 (stock V1.7.8 + slot-2 diagnostic INQUIRY hook), stamp build 13. Next update must stamp build 14 or later. Read D1 with `python tools/inquiry.py D`.

## Release plan (owner, 2026-11-07)

- **v0.1: Zeal reskin of stock.** Stock audio engine and behaviour untouched; UI images restyled (boot splash, main menu icons, volume overlay, Now Playing, lists, status screens); stock Blockz reskinned; text colours patched. Layout stays stock.
- **v0.2 Blockz (owner, 2026-11-07):** replace stock's block game module (module 82) with our own C game loaded through its module-table entry, so stock's menu launches it and stock music keeps playing. Gameplay inspired by Apotris (modern feel: 7-bag, hold, ghost piece, several next previews, hard drop on Up, rotate on the wheel so move + rotate works, tunable DAS/ARR and lock delay); look inspired by Tetris DX (Game Boy Color era: bevelled blocks, framed side panel, 8x8 tiles, Zeal palette). Original name, code and art only. First step: study module 82's interface to stock (how a game module gets key events and draws). The main menu's Games tile becomes **"Blockz"** and launches it directly (no game list); the other stock games are dropped in v0.2.
- **v0.3 batch (owner, 2026-11-07):** (1) library scan skip at boot when the card is unchanged (fingerprint), Update library item later; (2) Blockz: wheel up = hold only, the wheel stops changing volume while Blockz runs, volume in the pause menu; (3) our own Now Playing screen (mockup look: big artist + title, album art, progress, play time); (4) the one-level carousel (Now Playing, Music, Blockz, Library; Start opens Settings). Each previewed on the PC before the device. The earlier speed items (play start from Folders, boot to music) follow after.
- **v0.3 Now Playing layout (owner, 2026-11-07): option A** (`art/np_options.py`, preview `build/np_preview`): status bar with track n/total and battery; stock-size 116x116 cover in a panel on the left; artist (accent) and album on the right, each wrapping over two lines in the 16 px tall font; a full-width band below with the title in double size, **scrolling when too long** (no title tag: the file name without its extension, owner), then the progress bar (lavender playhead) and elapsed / remaining time. Plan: keep stock's module 27 behaviour (keys, track changes, cover decode by module 18 into a 116x116 buffer) and replace its drawing; state sources traced (docs/HARDWARE.md, Now Playing internals). **Built in build 28** (not yet on device): `game/device/npui.c`, preview `python art/np_preview.py`. Lyrics mode shows the title instead of the lyric line.
- **v0.3 carousel and Music menu (owner, 2026-11-11):** carousel cards Now Playing, Music, Blockz, Library in one wrapping row; Left/Right move, Up/Down nothing, Start opens Settings (patch `menu_carousel`, position kept in RAM 0x0309FFE4). Music icon: B, a note on a disc (`art/icons.py r_note_disc`). Manual library update = an eighth Music-menu item "Update" (stock text 90, stock action 8, forced past the fingerprint; patch `music_update`). USB screen: arrow removed. Built in build 30. Build 33 (owner): fresh boot starts on Music; Now Playing is greyed out and inert while nothing is playing.
- **Pocket look (owner, 2026-11-11):** main experience to move from the pixel-art look to a clean Game Boy Pocket style: white screen, ink lines, GBC colour pops, and a very light rainbow shimmer moving through a faint pixel-dot grid; boot screen stays. Mockups (design pass 3): https://claude.ai/artifact/2jDKSjE2kojxqMMU5mB4Nf (main menu, Now Playing, Music list). Approved by the owner; built in build 30 (`art/pocket.py`). Device: the shimmer is a still frame (faint rainbow on the dot grid) because stock screens only redraw on change; motion possible later on our own screens. List selection is a pale grape bar (stock list text stays dark), not the mockup's inverted bar.
- **v0.21 (owner, 2026-11-07):** Blockz with background music: if a song is playing when Blockz opens, it keeps playing; otherwise Blockz plays the first track in `/_blockgame/` on the SD card (on loop). Needs the trace of stock's play-a-file path (docs/BLOCKZ.md, Background music).
- **v0.2 carousel (owner, 2026-11-07):** one level, no sub-menus. Items in order: **Now Playing, Music, Blockz, Library**. Start opens Settings (not a carousel item); Bluetooth and Folders move into Settings later. Each item opens its screen directly; until our own screens exist, Music and Library open stock's screens, which needs the call stock's menu makes for each (trace in module 21). Browsing inside Music/Library still has list levels (e.g. artist, albums, tracks); Back returns to the carousel position.
- **v0.2 Now Playing (owner, 2026-11-07):** v0.1 restyled the Now Playing images, but stock still draws its text at run time with its own font and positions, so the screen does not match the mockup. v0.2 replaces the Now Playing module (27) with our own window (same contract as Blockz) drawn like the mockup: status bar (track n/total, battery %), cover art, artist and album in the compact 6 px font, the song title in double size scrolling when long, progress bar with lavender playhead, elapsed and remaining time. **Content (owner, revised after build 17):** text is only **artist and song title, much bigger**; album art describes the album (no album line for now); play time; no genre, file name, disc or format. Stock's Now Playing currently shows genre and the MP3 file name. Stock's music engine keeps decoding; we read its playback state (tags, position, length, cover) and send its play/pause/next/prev commands. First step: find where module 27 gets those values and which calls it makes for the transport keys. Interim fallback if that is slow: patch the ASCII glyphs in stock's font section to our compact font (changes text on every stock screen, layout stays stock).
- **Later (≈ v0.2):** own UI code: compact 6px font, big scrolling titles, metadata browsing, new navigation, Blockz with wheel rotate.
- **Later (≈ v0.3):** speed work: play-start delay, boot to music, screen push timing.

Image section notes (V1.7.8): 478 images, 452 unique, 123 unique full screens. Most are unused Rockchip SDK leftovers (radio, recorder, video, blue theme). The AP30's own beige UI uses roughly: 000/002 boot and shutdown, 014–024 main menu states, 026/277 Now Playing art, 159/184/185 lists, 336–436 volume overlay (0–100), 003–007 USB and charging, 017 DAC, 437/438 updating, 451 clock.

## Themes (owner, 2026-11-07, future release)

Support theme development, ship with a handful. Stages: (1) now, the art pipeline is palette-driven (`art/zeal.py` THEMES), so extra palettes (the mockup's Schala, Kajar, Ocean Palace, renamed for public) are cheap, one theme baked per build; (2) with the patcher, a **theme pack** = palette JSON + optional NNN.png overrides, chosen at patch time, so anyone can make one; (3) with our own UI (v0.2+), themes load from internal storage and switch at run time in Settings.

## Public release concept (owner, 2026-11-07, for later)

Ship a **patcher, never a firmware image**: the user downloads official V1.7.8 from Hidizs; our tool verifies its SHA-256, applies our changes locally (art, recolour, code patches) and writes their own HIFIYF18.IMG with a newer stamp; install is the normal copy + restart (loader mode only documented for recovery). Primary installer: a static web patcher on GitHub Pages (runs in the browser, nothing uploaded, optional direct write to the device in Chrome); CLI for power users; GitHub Actions builds both. Also offer "back to stock" (official image, newer stamp). Before going public: rename away from Chrono Trigger names, strip diagnostic hooks, add a licence and disclaimer, scan git history for firmware, recruit testers on other units.

## Decisions

- Approach: hybrid. Keep stock's audio engine (decoders on core B, DAC tuning); replace UI, navigation, library and play-start path
- Scope: browse by metadata (Artist > Album > Track), M3U, fast play start, snappy nav, Blockz with background MP3; Game Boy emulation is M5
- Look: Zeal Sky default palette with lavender accents, compact 6px font, big scrolling titles, no transitions, diamond pattern, arrow cursor, boot splash with floating islands
- P0: sound within 300 ms of pressing play; every press redrawn within one frame; playable within 3 s of power-on

## Backlog (next version)

- **Play-start delay (owner, 2026-11-07):** the slow start (~3 s) happens when a song is started from **Folders** (file browser), not from **Music** (library). Points at the folder-mode path (directory scan / file count in the current folder, `0x0305ADA8`, re-navigation from the folder stack) rather than the DAC or decoder start. For v0.3.
- **Library update (owner, 2026-11-07):** stock forces a full "updating library" (~1 minute) even when nothing changed on the SD card. Plan (agreed 2026-11-07, for when we do this work):
  1. *Skip when unchanged (patch to stock):* after a successful build, save a card fingerprint (volume serial + space in use from the exFAT boot sector / FAT32 FSInfo, plus root entry count); at boot compare and skip the scan if equal. First step: trace what starts the scan (likely TaskSwitch to task 13 = module 5, MDBBuildWin; scanner = module 38) and the check before it.
  2. *Manual "Update library" item in Settings* for when music was added or the fingerprint misses a change.
  3. *Own library (v0.2+): incremental, in the background:* per-folder fingerprint (entry count + newest timestamp), re-read tags only in changed folders, scan while playing with a small status marker (P0: playable within 3 s of power-on).
  Why it is slow: ~8,400 tracks on the owner's card, every file opened for tags; library DB lives on the hidden internal partition (module 34 reads 2 KB records: +0 folder cluster, +4 file number, +0x400 name, +0x500 artist, +0x600 album, +0x700 genre).
  Observed 2026-11-07 (build 25): no scan at power-on that time; it started when Music was opened.
  **Step 1 done in build 27** (not yet on device): fingerprint skip, docs/HARDWARE.md "Library update trigger and scan skip". Until step 2 exists, a manual rebuild is Folders > other disk > Yes, then back to the SD card > Yes.
- **USB screen (owner, 2026-11-07):** remove the orange shape in the middle of the USB connected screen (image 003, `art/screens.py` usb_screen: most likely the accent-coloured arrow between the plug and the computer). The rest of the screen stays as is.
- **Stronger shimmer (owner asked, 2026-11-11; on hold):** options previewed in build/shimmer: A a still foil band (full-colour dots plus a light rainbow wash in a diagonal band, baked into the images), B a band sweeping across every few seconds on screens our code drives, C the whole dot grid cycling colour. Owner: hold off for now.
- **Boot version (owner, 2026-11-11):** the boot splash shows the current version and is updated as we go (`art/boot_splash.py OUTDIR VERSION`); builds 30/31 still showed v0.1, next build shows v0.3.
- **Song lists (owner, 2026-11-07, future):** at song level, stock's music navigation shows file names. Show the title tag instead (file name only when there is no tag), sorted by disc number, then track number, then file name.
- **Name: amuletOS (owner, 2026-11-11):** "amulet" lowercase, after Schala's / Marle's pendant (the owner's
  translucent teal AP30 looks like it); replaces SchalaOS. Boot splash: option A (the existing art and gem, white
  name; `art/boot_splash.py` default). Still to rename after build 35's test: code and docs, the USB vendor name
  (SCHALAOS -> AMULETOS, 8 characters; `tools/inquiry.py` checks it), the Notion spec, and the GitHub repo
  (rename dharma-dingo/schala-os, keeping history; owner's OK first).
- **M3U playlists (owner, 2026-11-11, next feature):** playlists already on the card in `/_Playlists/` (16 extended
  M3U8 files from the media drive F:\Listen\_Playlists: UTF-8, LF, `#EXTM3U` / `#PLAYLIST:` / `#EXTINF:-1,Title`
  lines, entries relative like `../Artist/Album/01 - Song.mp3`; 215 entries, 214 MP3 + 1 FLAC, all resolve, one
  non-ASCII path, longest 133 chars, at most 20 per playlist). Owner's choices: a **"Playlists" row in the Music
  menu** (stock text 86 "Playlists", unused) and **picking a playlist plays from track 1** in Now Playing; Next /
  Prev / track end move through it in order. Stock has no M3U support. Design (from the 2026-11-11 trace,
  HARDWARE.md "Now Playing keys"):
  1. **Playlists screen**: our own module in a free game slot (task 14, old Snake), opened by the new Music row:
     lists `/_Playlists/*.m3u*` (exFAT walk from Blockz, build 34), Pocket list look, Up/Down/A/B.
  2. **Resolve on pick**: parse the file, resolve each entry by walking its path from `/_Playlists/`: folder
     cluster + file number (= the file entry's directory slot + 1, confirmed) into a table in slot-2 RAM
     (6 B per entry, about 48 entries fit; playlists are at most 20).
  3. **Start like Folders**: stock's record prep, source 0x63 ("files", tags read from the file), record +0x34 /
     +0x38 = entry 1, +0 = count, +2 = 1, playlist flag on; TaskSwitch(3, {1, 0x46, our tag}) so Now Playing's
     init starts the player (and sets the engine byte Blockz misses).
  4. **One hook for Next / Prev / track end**: 0x0305E930's entry: when the playlist flag is on, step the index
     (wrap, shuffle flag rec+0xC), fill +0x34 / +0x38 from the table, return 0; else stock. The flag goes off when
     Now Playing starts any other playback (np_load sees an arg without our tag).
  File number semantics confirmed 2026-11-11 (HARDWARE.md: directory slot + 1, not a count).
  **Built in build 35** (HANDOFF row 35): playlists over 24 entries keep the first 24 (slot-2 room).
- **Folders play start and Next (owner, 2026-11-11: "attack that issue in full"):** stock's player init walks the
  whole card to turn the browser's card-wide index into a folder + file (HARDWARE.md "Player thread init"): the
  ~3 s start, and Next / track end continue with the next file card-wide. Plan: at the Folders play request take
  the folder cluster + file slot from the browser directly, skip the card-wide walk (as for playlists, build 36),
  and step within the folder (Next / Prev / end by directory slot). Needs resident code for a folder walker:
  build 37 freed 328 B of slot 2 by moving screen-only helpers into their modules (tools/extend_module.py).
- **Resume from the Now Playing card (idea, 2026-11-11):** after a reboot, stock's Music-menu "Now playing" resumes the last song from the saved resume point (sys+0x64, HARDWARE.md main menu notes). The carousel card could do the same instead of staying grey; not built.
- **Game Boy: DMG LCD look (owner, 2026-11-13, add-on to Game Boy support; "being very performance minded"):** like the
  RetroArch "improved Game Boy DMG shaders" (r/RetroArch post 1uj5vdl; owner's example: Nintendo - Game Boy.glslp):
  green-olive DMG palette, a visible pixel grid (darker gaps between pixels), slight LCD ghosting, olive border.
  On the AP30 there is no GPU: every effect is CPU work per pixel per frame, inside the 16.7 ms budget. Cheap to
  free: the palette (a 4-entry lookup we already do), the border (drawn once). Cheap: ghosting = average with the
  previous frame's pixel (one masked add per RGB565 pixel, needs a 46 KB previous-frame buffer we do not have
  room for yet; or blend only on change). The grid needs more than 1 screen pixel per Game Boy pixel: 1x
  (160x144) has no room for gaps, 2x does not fit 296x240; a 1.5x scale (240x216) gives every second pixel a
  gap line (uneven), so the grid look is the costly / uneven part. Precomputed per-shade tiles (scale + grid +
  colour baked into a lookup) keep it to table copies. Decide after the probe shows how much frame time is left.
- **Favourites (owner idea, 2026-11-07, future):** while browsing music, favourite a song, album or artist with one press; a Favorites section is added to the main carousel. A lean playlist implementation (no playlist editor needed).

- **Blockz controls (face buttons can't combine, measured by D1; now part of the v0.2 Blockz).** Stock has the same limit. Options discussed 2026-11-07: (1) rotate on the volume wheel; (2) hybrid, wheel rotates plus A/B rotate when no direction is held (preferred); (3) face buttons only with DAS kept through brief direction release (avoid); (4) the GPIO2 pin 5 key as an extra rotate. Owner: Up = fast (hard) drop; details to settle during the build. Also: adjustable DAS/ARR, wheel = piece control in game with volume in the pause menu, ADC thresholds at midpoints of measured values. Open: wheel position/ergonomics, and which physical button the GPIO key is.
