# amuletOS hardware notes (AP30, stock V1.7.8)

Toolchain: Arm GNU Toolchain 13.3.Rel1 (arm-none-eabi-gcc 13.3.1), installed at
`C:\Users\Admin\tools\arm-gnu-toolchain\arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi\bin`
(SHA-256 of the zip verified against Arm's published value). Target flags: `-mcpu=cortex-m3 -mthumb`.

Working notes for M1. Addresses are run addresses unless marked `code.bin`.
Index: `python tools/fwmap.py build/<dir>/code.bin build/fwmap` then grep `functions.tsv` / `strings.tsv`;
caller trees: `python tools/xref.py <code.bin> build/fwmap/functions.tsv <ADDR> [depth]`.

## Code organisation

- code.bin loads at 0x03050000; 113 modules, each `code load/exec/size, data load/exec/size, ZI exec/size`.
- Module 0 = resident core, runs at 0x03050000 (0x2E300 bytes). Overlays share run addresses around 0x0308xxxx and are swapped in on demand.
- ARMCC output: most strings are addressed with `ADR` (PC-relative), not literal pools. Some functions load a register before `PUSH`, so prologue-based function detection can miss the first instruction (e.g. 0x03051F8E).
- Calls into 0x01000000+ go to mask ROM (SDK code baked into the chip).
- Two cores: decoders run on core B; core A sends `dec_open` etc. ("A 2 B send dec_open...") and waits with timeouts.

## Key functions

| Run address | Module | What it is |
|---|---|---|
| 0x03065B58 | 0 | `DelayMs(n)`: busy loop, n × (sysclk/3000) iterations of 3 cycles |
| 0x03065B34 | 0 | `DelayUs(n)`: sysclk / 1,000,000 × n |
| 0x030621FC | 0 | CS43198 register write `(reg24 in r0, value in r1)` |
| 0x03062270 | 0 | CS43198 register read |
| 0x030504EC / 0x03050562 | 0 | i2c_write / i2c_read |
| 0x03051F8E | 0 | DAC (re)start: clears state, writes reg 0x0B0000=0x1E, tail-jumps to power-up |
| 0x03051CB2 | 0 | CS43198 power-up sequence (regs 0x02xxxx, 0x05xxxx, 0x09xxxx, 0x0Bxxxx, 0x0Fxxxx, 0x18xxxx; waits 80 ms + 10 ms + 4×100 µs) |
| 0x0308DDD0 | 33 | `MusicInit`: calls DAC (re)start, waits 100 ms |
| 0x0308C8EE | 33 | "Audio Start" / file open, waits 80 ms |
| 0x0308E178 | 33 | AudioControl main (codec select by extension) |
| 0x0308FFBC… | 41–57 | per-format decoder front-ends (MP3, WMA, AAC, WAV, OGG, FLAC, ALAC, APE, DFF, DSF), each one module |
| 0x03083610 | 12 | USB mass storage; INQUIRY handler at 0x03083942 |
| 0x03082F4E | 11 | USB audio (also calls DAC (re)start) |

## Play latency (stock: ~3 s from pressing play to sound, owner report)

Fixed busy-waits found on the music start path: DAC power-up ≈ 90 ms + MusicInit 100 ms + Audio Start 80 ms ≈ **270 ms**.
Stock powers the DAC up from cold on every music start (MusicInit → 0x03051F8E → 0x03051CB2).
That leaves ~2.7 s unexplained. Suspects: overlay loads from flash (music + decoder modules), core B decoder start
and its handshakes, file open / tag parsing, library DB work. Next: owner's slow-motion video to split the 3 s,
then trace the overlay loader and the core B handshake.

**amuletOS design consequence:** keep the DAC/amp powered while the UI is awake, keep the music path resident
(no overlay swap on play), and never busy-wait on the UI core.

## Peripheral map (SDK hw_memap.h, confirmed by firmware use)

| Block | Base | Notes |
|---|---|---|
| SARADC | 0x400D0000 | DATA +0, STAS +4, CTRL +8 (ch in bits 0-2, start bit 4, IRQ bit 5) |
| TIMER | 0x400E0000 | |
| PWM0 / PWM1 | 0x400F0000 / 0x40100000 | PWM0 likely backlight |
| MAILBOX | 0x40110000 | core A ↔ core B; 78 functions use it |
| I2S1 | 0x40030000 | audio out (TXDR +0x24 per ReChord) |
| I2C0 | 0x40040000 | DAC control |
| GPIO0 / GPIO1 / GPIO2 | 0x40160000 / 0x40170000 / 0x50030000 | data +0, dir +4, int regs +0x30.. |
| CRU / GRF / PMU | 0x40180000 / 0x50010000 / 0x50020000 | clocks, pin mux, power |
| EMMC | 0x60030000 | AP30 storage is eMMC |
| LCD / VOP | 0x60090000 / 0x60070000 | display |

Interrupts: vector = 16 + SDK INT_ID (SRADC 36, MAILBOX0-3 25-28, I2S1 48, GPIO2/1/0 52/53/54). `IntRegister(id, fn)` = 0x03067088. Boot VTOR = 0x03050000, later a RAM copy at 0x03004000.

## Input: buttons and volume wheel

**ADC sampler.** A timer steps through 4 channels round-robin (0x030613BC), the conversion ISR (0x03061440) stores results in a table at 0x03005A8C (u16 per channel); getter 0x030614D6(ch). Only channels 0 and 1 are consumed.

**ADC ch0 = battery.** 0x03081E50 (boot) / 0x03065D66, 0x03065E02 (service): mV = raw × 2500 × 2 / 1024. Power off below 3300 mV when not charging, low warning below 3450 mV, "full" above 3964 mV; 4-entry level table at 0x03005758 for the 5-step icon. Charger detect on GPIO2 pin 3.

**ADC ch1 = all 8 face buttons on one resistor ladder** (decoder 0x03062CCC, 10-bit reading):

| ADC | code | | ADC | code |
|---|---|---|---|---|
| < 70 | 0x004 | | 442–559 | 0x002 |
| 100–183 | 0x010 | | 560–679 | 0x100 |
| 200–309 | 0x008 | | 700–849 | 0x040 |
| 320–429 | 0x020 | | 850–949 | 0x080 |
| ≥ 950 | none | | | |

Plus one key on **GPIO2 pin 5** (code 0x001), checked first.

**Measured on device (D1, 2026-11-07, raw 10-bit ch1, idle = 0x3FF):**

| Button | Raw | Stock code |
|---|---|---|
| Right | 0 | 0x004 |
| Up | 118–119 | 0x010 |
| Left | 240–242 | 0x008 |
| Down | 364 | 0x020 |
| Select | 486–492 | 0x002 |
| Start | 661–680 | 0x100 |
| B | not measured (exits USB mode); by elimination | 0x040 |
| A | 854–855 | 0x080 |

Start and A sit at stock's band edges; amuletOS should use midpoints between measured values. The volume wheel does not touch ch1.

**Simultaneous face-button presses cannot be read (confirmed).** Every pair reads as its lower-value member: Up+A → Up, Right+A → Right, Left+Select → Left, Up+Right → Right, Down+Start → Down, Select+Start → Select. Series ladder: priority Right > Up > Left > Down > Select > Start > B > A, so A is masked by any other face button. Inputs that can combine with a face button: the volume wheel (GPIO encoder) and the GPIO2 pin 5 key.

**Consequences.** Hardware limit, confirmed on device: one face button at a time. Blockz: rotate on the wheel (or the GPIO key) so move + rotate works. Game Boy: direction + A/B is impossible on the face buttons; A/B would have to move to the wheel / GPIO key.
Stock key timing (SDK AD_Key): 2-tick debounce, repeat after 20 ticks, then every 2 ticks.

**Volume wheel = quadrature encoder on GPIO2 pins 0 (A) and 9 (B)**, polled from the system timer: 0x030534AC configures the pins as inputs and compares A/B with the previous sample (0x0306FBCC / 0x03004144), counting steps per direction at 0x030226E5 / 0x030226E4 (total 0x030226E8). Responsiveness depends on the poll rate.

**Other GPIO:** GPIO2 pin 1 = amp enable/mute (driven at volume 0 and around audio start). GPIO2 pin 8 + GPIO0 pin 13 = jack detect (ORed, 50 ms debounce, posts message 0x25). GPIO0 pin 11 read by most UI modules (likely hold or headphone state).

**Volume path:** level → 0x0306242E (scale ×6) → one of three curves → CS43198 regs 0x090001/0x090002 (0x00 = 0 dB, 0xFF = mute).

**Display:** UI init sets the window to 0–295 × 0–239 (296×240 confirmed).

## Display

- Panel: **296×240, RGB565**, mounted rotated (the window code mirrors x: 295 − x).
- Stock draws into a **RAM framebuffer at 0x03006688** (row stride 592 bytes; pages of 190 rows plus a second path for the rest; double-buffer page select). Pixel write 0x03064DC4, software window/rotation 0x03064EA8.
- Frames reach the panel by **DMA into the LCD data FIFO at 0x6009000C** (LCD controller base 0x60090000, control at +4; 0x0E written before some transfers). Rectangle blits: 0x03064F70 / 0x03064FD4 (window, get DMA channel 0x030614F8, start DMA 0x03061524 with w×h/2 words).
- Stock "clear screen" (0x03064F2A) writes all 71,040 pixels one at a time through the CPU. Wasteful; amuletOS should fill by DMA.
- The panel driver is **chosen at boot from a table in flash** (`LcdDriverIndex`, LcdInterface.c, module 1 0x03081CC0): its function table is copied to 0x0306FD14 and `ops[1]` (init) is called. The panel's command sequence lives in that flash table, not in the code modules. Controller model not yet identified.
- 0x60070000 (SDK "VOP") is used as per-channel registers (channel × 0x34), more like a DMA engine than display timing.
- **Open (deferred to M2):** bus speed and full-frame push time. Stock's blit routines 0x03064F70 / 0x03064FD4 have no direct callers or stored pointers anywhere in the image, and their window routine 0x03064EA8 only updates software state (no panel command), so the live flush goes through an untraced indirect path (likely the panel-driver table from flash). DMA: DesignWare-style DMAC at 0x60000000 (ChEnReg +0x3A0, channels 0–4, allocator 0x030614F8), linked-list start 0x03061524 with up to 18 blocks of 0xFF8 words, descriptors at 0x03005AD4 + ch×0x1B0. **Correction:** SysTick is stock's system tick: 0x030621C8(ms) sets LOAD = clk * ms / 1000 - 1 and stock calls it with 10 (boot and after clock changes), the SysTick ISR (0x03067470) walks a callback list whose first entry increments the 10 ms counter at 0x0302288C. Sub-tick time: (LOAD - VAL) / (LOAD + 1) of 10 ms, clock-independent (used by Blockz for 60 fps pacing).

## Memory

- Core A SRAM in use: 0x03004000–0x0309F7CC (≈ 622 KB; chip likely 640 KB). Module 0: 185 KB code at 0x03050000, 6.6 KB data at 0x03004000, 120 KB ZI at 0x03005A8C (holds the framebuffer). Overlay code window 0x03080E9C–0x0309F7CC (≈ 120 KB).
- Core B region in use: 0x01000000–0x0102D184 (≈ 180 KB), decoders in modules 71–80.
- **Load model: DISPROVED on device (H0/H0a, 2026-11-07).** The ReChord-based assumption was: the boot ROM loads the whole code section contiguously into RAM, with code.bin offset 0 at 0x03050000. Module-table "load" addresses are therefore real RAM addresses, and overlays are copied from that in-RAM image on demand. RAM extends at least to the end of the loaded image (≈ 0x031D8714), well beyond the ≈ 622 KB the modules execute in.
- Runtime reuse of the loaded image: after boot, module 0 runs at 0x03050000, a heap/buffer area follows at 0x0307E300 (fixed-address globals, e.g. 0x0307E710 has 35 references), and overlays execute at 0x03080E9C–0x0309F7CC. Sources above that (module data and overlay sources from 0x030ABB8C up) must stay intact.
- **Free block: NOT usable.** code.bin 0x57B8C–0x5BB8C (16 KB of zeros) was assumed to sit in RAM at 0x030A7B8C. H0 (INQUIRY swap) and H0a (pure tail-call pass-through) both placed there and called from module 12's `bl usb_send` (0x03083978) hang USB enumeration: the device appears as 071B:3203 with no LUNs, then drops. A pass-through failing means our bytes are not at 0x030A7B8C at run time. Working model: modules are copied to their exec addresses individually and the gap is never loaded. Hooks must live inside a module that is loaded (e.g. module 12 itself or module 0 padding), or in a new module-table entry once the loader is traced.
- Mailbox send (core A → B): 0x0306DCD4(value, channel, slot), registers at 0x40110000 + ch×0x50 + {8,0x10,0x18,0x20}.

## Game Boy feasibility (M5) after M1 so far

| Question | Status |
|---|---|
| RAM | **Unknown again.** The >1 MB figure relied on the disproved load model; ≈ 622 KB core A in use; GB Color needs ~48 KB console RAM + bank cache |
| CPU clock | **200 MHz** in USB mode (D1, `*(0x030065C0+0x18)` = 0x0BEBC200). Music-mode clock still to check |
| Display push speed | Unknown. Measure a full-frame DMA blit on device |
| Simultaneous buttons | **Blocked on face buttons (measured).** Series ladder, lowest wins. Only the wheel and the GPIO key can combine with a face button |

## Flash and recovery

- Loader mode: d-pad corner + A + B while plugging USB → USB 2207:262D (BootROM rockusb, no `db` needed).
- 983040 sectors reported, 974848 readable (last 4 MB refused). fw1 at LBA 0, fw2 at 0x01E00000.
- Recovery proven: `tools/rkwrite.py wtest` (write, verify, restore in a free area). Real recovery: `rkwrite.py wl 0 <good image> --allow-any`.

## Open questions (also decide Game Boy feasibility)

- CPU clock (sysclk variable read by DelayMs at [*0x…+0x18])
- Total SRAM and what's free; can core B's RAM be used
- LCD interface and bus speed (Echo Mini shares the bus with flash)
- Key wiring: are simultaneous presses limited by hardware
- Amp (RT6863) enable/mute GPIO and timing

## Fonts (font0 / font1 sections, decoded 2026-11-07)

Stock draws all UI text at run time from two bitmap fonts covering the Unicode BMP, indexed
directly by code point (record n = U+n). Neither the v0.1 image reskin nor recolour touched them.

| Section | Size | Record | Glyph | Width byte |
|---|---|---|---|---|
| `font0.bin` | 2,104,326 B | 32 B | 12 rows x 16 bits, big-endian, bit 15 = left | byte 24 = 0x80 + advance (A = 0x87) |
| `font1.bin` | 2,169,862 B | 33 B | 16 rows x 16 bits | byte 32 = 0x80 + advance (A = 0x88) |

65536 records each, plus 7174 trailing bytes (not yet decoded). U+0000 is a box glyph.
**Fix chosen (owner, 2026-11-07): style D** = `art/font.py` `bold1x` (original 5x8-grid glyphs, upper and lower case; 16 px font in a bold 1x, 12 px font in regular 1x), applied by `build_reskin.py --font bold1x` from build 17. A data-only font fix is possible: overwrite the ASCII records (U+0020..U+007E) with original
glyphs and their advance widths. Still unknown: which screens use which font, and how stock lays
out text wider than its current advances (clipping or scrolling).

## Tasks (screens) and resident helpers, traced 2026-11-07

- `TaskSwitch(id, arg*)` 0x030680D4 stores the id at 0x030057C0 and copies 0x1C bytes of arg to +0x184. The task
  loader (0x030680AE) loads module `table[0x030057C0 + 0xC4 + 4*id]` with type 7; descriptor pointers at +4.
  Ids: 0 MainMenu (m21), 1 MediaLib (m22), 2 MediaBro (m23), 3 Music/Now Playing (m27), 6 Picture (m17),
  8 Ebook (m30), 9 Browser (m31), 10 Systemset + game list (m32), 11 USB (m9), 12 Charge (m6), 13 (m5),
  14.. games: task 14 + k = module 81 + k = text id 273 + k (game list launches 0xE..0x2B); see "Stock games"
  below. (Until build 55 this line said "14 Snake, 15 block game": m81's only strings are "Block_Game.c" and a copied
  "Snake KeyVal" log line, so 14 is the block game and 15 (m82, now Blockz) was Snake.)
- Main menu: focus index u16 at 0x03023B94; tile actions via tbb at 0x030818B0: 0 Music, **1 Games
  (0x03081960: TaskSwitch(10, &7) = game list)**, 2/3 task 9, 4/5 task 10 pages. Returning to the menu:
  TaskSwitch(0, &index). Build 21 makes tile 1 call TaskSwitch(15, 0).
- **Overlay data window:** every UI / game module's data + ZI start at 0x03023B48; stock module 98 uses 0xD12 B
  (data 0x64 + ZI 0xCAE), so at least that much is free for whichever module runs. Task -> module table at
  code.bin 0x5D410 (u32 per task): 0 m21, 1 m22, 2 m23, 3 m27, 4 m13, 5 m28, 6 m17, 7 m29, 8 m30, 9 m31, 10 m32,
  11 m9, 12 m6, 13 m5, 14..42 m81..m109 (task 19 = m86, the largest stock game, 13.8 KB: amuletOS Playlists).
- **Slot-2 RAM (build 36):** 0x0309F800 amuletOS INQUIRY hook (56 B; D1 diagnostics 0x8C B until build 35),
  0x0309F838.. helpers (np_helpers.c, np_stub.S, libscan.c; build 37: 1448 B, 328 B free below the table), 0x0309FF28 playlist table (pl_table.h, 152 B), 0x0309FFC0 libscan FP, 0x0309FFD8 npui scroll,
  0x0309FFE4 carousel index, 0x0309FFF0 stock reset magic.
- **Slot 2 is resident:** module 1 loads slot 2 (type 7) at boot while reading the system config
  (0x030827B0), and no module runs above 0x0309F7CC, so code linked into slot 2 at 0x0309F800 stays loaded.
  `tools/build_helpers.py` appends C helpers after the D1 hook (build 21: 384 B, slot size 0x20C of 0x7F0).

## Starting music (partial trace for v0.21, 2026-11-07)

- Music engine = module 33, entry `AudioControl(cmd, arg)` 0x0308BF84 (Now Playing calls it 14 times; e.g. cmd 0xF8
  after volume changes). Audio Start 0x0308C8EE loads module 34 (library/file info), 0x0308FB0A, opens the file with
  0x0308F810 (-1 = "Audio File Open Error", posts msg 0x4F).
- The player runs as a stock thread: handle at 0x030232BC, descriptor 0x030361A4. Running test:
  0x03057C7C(*0x030232BC, 0x030361A4) == 1 (stock block game uses the same check). Start (Now Playing init,
  0x03081774): 0x03057C38(0x030232BC); ModuleOverlay(33, 7); 0x03057B96(0x030232BC, 0x030361A4, window arg).
- Folder browser play request (m31 0x0308236A): music source record 0x03022F14: +0xF2 = source type (browser
  value from its context +0x89; module 34 treats 0x63 and 6 specially), path copy (0x80 UTF-16) to 0x03022BBA,
  +0x10 = 0x030056C0 (browser folder state), +6 = file index, 0x03080644 = context +0x197; then 0x03055304 copies the
  folder stack from the system config 0x03022894 (+0x79/+0x7D, depth +0x18B, cluster stack +0x81/+0x18D, +0x195,
  +0x5E, +0x19D..+0x1A5) into the record; then TaskSwitch(3, {index, 0x46}).
- Files are opened by directory cluster + index (0x030598E6, "file open err: clus = %d, index = %d"); record +0x34 =
  directory cluster, +0x38 = file number (1-based). File system sources: Common\FileSys\{dir,FDT,fat,file}.c.
- File system state (module 0): FS type byte 0x0307E710 (3 = exFAT, separate code paths), volume info 0x0307E71C
  (root cluster at +0x0D), current directory cluster 0x0307F250, depth 0x0307EFC8, per-level table 0x0307EFD0
  (71-byte entries, +0 total files, +2 ...). GotoRoot 0x0305B032(buf, type); type 1/2 = library (cluster 0),
  otherwise root cluster from the volume info. FindFirst 0x0305BBF6(find*, &dirclus, ext, type) / FindNext
  0x0305BBCA(...) wrap 0x0305B454(find*, next?, ext, type, [&dirclus, 3, type]); extension match 0x0305C800.
  Long name by (dir cluster, index): 0x0305C364(clus, idx, type, out16) on FAT, 0x0305B2D0 on exFAT (library
  scanner module 38 uses both with type 6). File count with the audio filter: 0x0305ADA8(0x030056EB, clus).
- Disk: system config 0x03022894 +0x0E = active disk (2 internal, 4 SD), +0x1F = SD present, 0x03053C88() == 1
  when the card is in, 0x03058526(disk) switches (MusicInit does this when the chosen disk has no files).
- Owner's card (2026-11-07): exFAT, 128 GB; /_blockgame/ holds "Classic Theme.mp3" (any audio file there should
  work: play the first in stock's file order).
- Folder browser internals (m31): listing (0x03081740) uses an iterator {dir cluster, index, count, ..., exFAT dir info
  0x2A B at +0x1C} with FindFirst/FindNext into a 32-byte entry (attr at +0x0B, 0x10 = directory); long names via
  0x0305C364 (FAT) or 0x0305B2D0(&exinfo, index-1, type, out) (exFAT). Folder counts: FAT files 0x0305BDF6,
  dirs 0x0305A6B4; exFAT files 0x0305BF7E(&exinfo, ...), dirs 0x0305A79E. Root cluster per disk: 0x0305B11A(disk).
  Browser state 0x03021EE8 (folder entries of 56 B: +0x14/+0x18 cluster, +0x24 flag), source byte 0x03024CA4.
- Music engine in folder mode counts files in the FS *current directory*: 0x0305ADA8(filter, 1); mode 3 is used for
  source 0x63. Resume/next re-navigates from the folder stack the play request carries (record +0xF4 depth,
  +0x100/+0x110 stacks), so v0.21 must fill that stack correctly.
- Library database: FlashRead(0x30001, offset, len, buf) = 0x03068194. Records: 2 KB each from sector sys+0x79
  (0x1400 on the owner's unit); +0 folder cluster, +4 file number, +0x400 name, +0x500 artist, +0x600 album,
  +0x700 genre. Sorted index of u16 record numbers from sector sys+0x7D (0x53420), read at
  ((stack[depth] + idx[depth]) << 1) by 0x03055304.
- Owner's /_blockgame/ (recreated by sync at 16:20): stock's Files browser lists it empty and the exFAT folder count
  returns 0, but the library scanner found the file and Music plays it (open by folder cluster + file number works).
- Still needed for v0.21: find /_blockgame/ on the SD card (disk select, root cluster, directory entry lookup),
  the browser's file indexing (which entries count, order), and the exact source-type value; then fill the record
  and start the thread without opening Now Playing. Plan: a debug log written to a file on the internal drive
  (stock FileWrite exists) to dump these structures after playing a file from Folders.

## Main menu keys (module 21, traced 2026-11-11)

- Service 0x030819E4 switches on GetKey's event word: 0x40000010 / 0x40000020 / 0x30000010 / 0x30000020 (Up, Down
  press and repeat) -> 0x03081CDE (index +-3); 0x40000004 / 0x30000004 (Right) -> 0x03081CF0; 0x40000008 /
  0x30000008 (Left) -> 0x03081D1C; 0x40000080 (A) -> tile action 0x0308188E (unless msg 1, the volume overlay, is
  up: then close it); 0x40000040 (B) closes the volume overlay; 0x40000200 / 0x40000400 (wheel) volume -/+;
  0x41000000 / 0x42000000 open system dialogs; 0x20000100 ran the Music action. A Start press (0x40000100) fell
  through to the exit at 0x03081B8A. Event types: 0x40 press, 0x30 repeat; 0x20 seen with Start's code (not a
  plain press). Tile actions 0x0308188E (tbb at 0x030818B4): 0 Music (task 1), 1 Games (task 10 page 7), 2 Browser
  mode 3 (task 9), 3 Browser mode 5 (Folders), 4 / 5 task 10 pages 3 (Bluetooth) / 4 (Setup). Init restores the
  index from its argument byte (or 3 when 0x03005984 == 3). Tile table in the data: {1, i, i, 0, image, text id}. The table is at 0x03023B64 (RAM, 6 x 8 B) and the card
  paint (0x03081E5E, on msg 0x2D) reads the image id from it each time, so swapping ids in RAM changes the card
  (build 33 greys Now Playing this way). Image 14's top 33 rows are also the header backdrop of many screens
  (drawn by modules 9, 21, 22, 23, 27, 31, 32); images 8, 20, 24 have no stock draws left (8 had none at all).
  Stock's Music-menu "Now playing" (m22 0x030817D0): player running -> TaskSwitch(3) back to it; else if sys+0x64
  (resume point) -> rebuild the music source record from the config and TaskSwitch(3); else open All Music.
- Music menu (module 22): table {icon image, text id, action} at data 0x03023B48 (7 entries, window descriptor
  right after at 0x03023B74); count 7 at 0x0308165A, 7 rows per page; select 0x0308170C dispatches on the action:
  5 -> 6, 0..4 tbb, 6, 7 Favorites, 8 = library update (0x030818BE: stop player, sys+0x42 = 1, TaskSwitch(13, {1})),
  9, 0x64. Stock ships no entry for 8; text 90 "Update" unused.
- Music menu row paint (m22 0x03081EB0, traced 2026-11-11): background image 159, rows at y = 0x3D + 23k (7 visible),
  selection bar image 184 on the selected row ([0x03023B90 +2] = selected visible row, +1 = first item shown),
  text from the table's text id at x = 15 (0x030644A0). **The table's icon ids are never drawn**: icons need a hook
  (draw the icon, move the text right). Action 6 "Directory List" = TaskSwitch(9, {1}): the folder browser in
  music mode (the main menu's Library card opens it in mode 3); its songs play as source 0x63 (slow Folders start).

## Now Playing keys (module 27, traced 2026-11-11)

- Service 0x03083688 switches on GetKey's event: Right press 0x40000004 -> 0x03083DCC (next), Left press
  0x40000008 -> 0x03083E4C (previous); Right/Left repeat 0x30000004 / 0x30000008 -> 0x03083B24 / 0x03083BA8 (seek).
  Next: if sys+0x199 (a seek mode) is set, AudioControl(0xF2, step) twice (prev: 0xF3); else clear 0x030483CA,
  set 0x030483CC = 1 and 0x030360E8 = 1, then AudioControl(0x109) (prev presumably 0x10A). AudioControl (m33
  0x0308BF84 = b.w 0x0308DBC2) switches on the command: 0x109 (next) -> 0x0308DD1C: AudioClose(1) (0x0308D86E),
  0x03062858(), 0x0308CC50(1), 0x03062858(), Post(0x109); 0x10A (prev) -> 0x030625A2 (untraced).
- 0x0308CC50(dir) (m33): play-mode switch on (*(0x030483D0 + 8))+0x1C (8 modes: repeat / shuffle; tbb), then
  0x0305EDC6(0x03022F14, dir).
- **0x0305EDC6(rec, n)** (resident, module 0): calls **0x0305E930(rec, +-1)** n times until it returns non-zero.
  0x0305E930 = one step of the music source record 0x03022F14: rec+2 (u16) current index 1-based, rec+0 (u16) total
  (wraps to 1), rec+0xC = 1: shuffle (random from the 10 ms tick, 0x03067D78(0x23)), rec+0xF2 source type: 0x63 ->
  0x0305EA5A, 6 -> 0x0305EB2A (folder / card-wide file lookup that sets rec+0x34 cluster, rec+0x38 number).
  **Playlist hook point:** 0x0305E930's entry.
- **All song changes share this path** (traced 2026-11-11): Now Playing Next = AudioControl(0x109, 1), Prev =
  AudioControl(0x109, -1) (m27 0x03083EAE; command 0x10A -> 0x030625A2 is just `bx lr`); track end = m33
  0x0308D9F2 0x0308CC50(1). 0x0308CC50 is the only caller of 0x0305EDC6, which is the only caller of 0x0305E930;
  then AudioStart (0x0308C8EE) opens the file the record names.
- 0x0305E930 tail (0x0305EB72): rec+6 = index; rec[0x100 + 2 * rec+0xF4] = index - 1; then by source type:
  0x63 -> 0x0305BD04(&rec+0x14, &rec+0x34, rec+0x10, 3) (stock's folder iterator over the card), 6 -> 0x0305EC3A,
  3 -> 0x0305EC90, **0..2 (library: All Music / Artist / Album) -> 0x0305ECF0**: record number = u16 FlashRead(
  0x30001, (rec+0xFC << 9) + 2 * (index + rec[0x110 + 2 * depth]) - 2), then 8 bytes of DB record
  (rec+0xF8 << 9) + n * 2048 -> **rec+0x34 = folder cluster, rec+0x38 = file number** (DB record +0 / +4), +0xC ->
  rec+0x48, +0x10 -> rec+0x4C, rec+0x44 = (+0x48 | +0x4C) != 0; returns 0 (r6) = success (0x0305EDC6 stops early on
  non-zero).
- **Now Playing init (m27 0x030815C4)**: arg block (TaskSwitch copy at 0x030057C0 + 0x184): u16[1] -> 0x0302283C;
  0x03081774(arg) = if the player thread is not running: ThreadDelete(0x030232BC), ModuleOverlay(33, 7),
  ThreadCreate(0x030232BC, 0x030361A4, arg); then **0x0308CFB8(1) = `*(u8 *)0x030483C8 = 1`** (first byte of the
  engine's state, m33 ZI). Blockz's own start (builds 25-34) skips that store: likely why it played nothing.
- **Player thread init (m33 0x0308DDD0, descriptor 0x030361A4 = {0, 0, init 0x0308DDD1, main 0x0308E179, deinit
  0x0308E799})**: arg[0] -> sys+0x5E (index); source 0x63: 0x0308DD48(3) = record total from 0x0305ADA8(filter, 3)
  (TotalFiles over the browser's current folder state 0x030056C0; 0 -> disk switching, msg 0xEE); then (0x63 or 6)
  0x0305E85C(record, sys+0x5E, mode, shuffle, filter): TotalFiles again, record+2 = index, 0x0305AE16(index, ...)
  (card-wide index -> folder: walks the card), 0x0305BD30 FindFirst + 0x0305BD04 FindNext up to the file -> record
  +0x34 / +0x38; mode 2 (play modes 0..2) keeps the index within the folder. Other sources skip both (library
  path: record+0xC = sys+0x67, +0x10 = 0x03005716). **This card-wide walk is the ~3 s Folders play start and why
  Next from Folders goes to an unrelated song.** Build 36 skips it for playlists (np_stub.S pl_init_count /
  pl_init_seek).
- Source-type branches (all `record+0xF2` reads): m0 RecPrepare (7), step 0x0305E930 (0x63 / 6 / 3 / 0..2),
  m22 / m23 (6), m27 0x03081F20 (non-0x63: tags from the library DB), 0x030824E8 / 0x030838E4 (Back: 0x63 -> browser,
  else Music menu with the list type), m31 (0x63 / 6), m33 init (above) and main 0x0308E3C6, m34 open type
  (6 -> 1 else 3), 0x0308FA16 (DB tags only when record+0x44 != 0), 0x0308FE9E. A new source value would take the
  library paths, so playlists keep 0x63.
- **File number = directory entry slot + 1** (checked 2026-11-11 on the owner's card, read raw on the PC): the
  record's +0x38 (and library DB record +4) is the 32-byte slot index of the file's 0x85 entry in its folder, plus
  1, counting deleted entries too; the open (0x030598E6, "clus = %d, index = %d") takes +0x38 - 1. Owner's card:
  /Big Star/#1 Record/ = cluster 0x000815CE, "04 - Thirteen" at slot 4 -> 5 (Blockz INFO CL 000815CE 00000005),
  while it is the 1st live file (Windows' listing) and 4th by name; /_blockgame/Classic Theme.mp3 at slot 0 -> 1.
  The card's folders are full of deleted Syncthing sync-conflict entries, so slot != file count.

## Settings across a firmware install (traced 2026-11-12, build 38)

- Module 1's boot config load (0x03082090) reads a reserved flash area with 0x0305EE54(1, 2, buf); bytes +0x3FC..
  +0x3FF == "FWUP" mark a just-installed update. That path (0x03082198) clears the marker (0x0305EE8E) and jumps to
  the CRC check at 0x0308214C *without* reading block 0 (0x0306D48E(0, buf, 0x800) at 0x03082140), so the CRC
  fails, the buffer is filled with 0xFF and every field takes its default: the language went back to Chinese and
  the library fingerprint was lost after each install. Patch `keep_settings`: the jump goes to 0x03082140.
- Language = saved block +0x10 (0x03082306 `ldrb.w r0, [sp, #0x40]`), checked (<= 0x14) and mapped through the
  enabled-language list into sys +0x10 (0 简体中文, 2 English). Patch `english` loads 2 instead (build 39). Settings
  changes save at once (m32 0x03083F04, SaveSysConfig(1)). The first-boot language prompt shows from the main menu
  while sys +0x2E5 != 0x55 (m21 0x030817D2).

## Library update trigger and scan skip (traced 2026-11-07, build 27)

- **sys +0x42 = "library needs update"**, set by: boot config load (m1 0x03082784 / 0x03082798: when the saved
  config's +0x2E9 is not 0x55AA, i.e. the last save was not SaveSysConfig(1)); main loop when card state
  0x03022880 == 1 (m0 0x03066DF8, then disk 4 and TaskSwitch(13) at once); card removed while on SD
  (m0 0x030666D6); Music tile when the library is from SD (+0x0F == 4) but card detect GPIO0 pin 11 reads 1
  (no card; m21 0x030818EA); card inserted while in Library (m22 0x030819B4); USB session with writes
  (m12 0x030836AC); Folders "Update Library?" Yes (text 120, shown when the chosen disk differs from +0x0F;
  m31 0x0308219E); internal disk format at boot (m1 0x030819F0); Settings resets (m32 0x03081B62/0x03081B98,
  0x03081BF0); stock block game. Everything ends in TaskSwitch(13) or in the Music tile's test
  (+0x42 == 1 -> TaskSwitch(13)).
- **Module 5 (MDBBuildWin)** service 0x03081740: if +0x42: clear +0x42 and +0x64, run the build
  0x03081628 (synchronous: +0x0F = +0x0E, modules 38/39/40, ends with SaveSysConfig(0)), post 0x18D; then
  TaskSwitch(target from its argument). 0x18D/0x18E/0x18F = recount free space of disk 2/3/4 (module 7 at
  0x03081924, results in 0x030041C8..0x030041DC; exFAT path reads the allocation bitmap).
- **System config persistence:** SaveSysConfig(f) = 0x0306D564: memset 0x800 buffer to 0xFF, +0x2E9 =
  f ? 0x55AA : 0, crc of 0x2F1 bytes at +0x2F1, copy 0x2F5 bytes, ModuleOverlay(2, 7), block write
  0x0306D500(0, buf, 0x800). Block read 0x0306D48E(n, buf, len) reads ceil(len/512) sectors. Boot loader
  (m1 0x03082090) reads block 0, checks crc (bad -> defaults, buffer 0xFF), copies fields, then rewrites block 0
  from that buffer (ModuleOverlay(2, 7) at 0x030827B0, write at 0x030827EA): bytes after 0x2F5 survive a good
  boot and are wiped by a reset to defaults. Block 0 is written only by these two.
- **exFAT volume info** (mount 0x030582A8, boot sector parse): 0x0307E710 FS type, +2 u16 sectors/cluster shift
  (boot+0x6D), +4 u16 bytes/sector shift (boot+0x6C); 0x0307E71C +0x0D root cluster, +0x1B cluster count,
  +0x1F cluster heap (absolute sector), +0x23 partition start, +0x2B FAT start, +0x2F percent in use.
  Raw sector read of the current disk: 0x03057CC8(lba, buf) (absolute LBA).
- **Scan skip (build 27, `game/device/libscan.c`, patch `lib_skip`):** m5 0x03081754 (clear, build, post) ->
  `lib_gate`: skip when the saved fingerprint equals the card's and the database has a first record;
  otherwise forget the fingerprint (save), build, post 0x18D, save the new fingerprint. Fingerprint of an exFAT
  SD card: serial (boot+0x64), cluster count, FNV-1a of the root directory's first cluster (up to 64 sectors;
  File entries without set checksum and access time), FNV-1a of the whole allocation bitmap. FAT, internal disk:
  no fingerprint, always build (stock). Stored at block 0 +0x300 {magic "SKF1", 4 words, ~magic} and in RAM
  0x0309FFC0 (above the slot-2 code). SaveSysConfig's write (m0 0x0306D5C0) -> `cfg_write` appends it; the boot
  rewrite (m1 0x030827EA) -> `cfg_boot_write` loads RAM from it; Folders Yes (m31 0x0308219E) -> `lib_force`.
  Misses: a file rewritten in place (same clusters) below the top level, e.g. a tag edit with padding. Manual
  rebuild: Folders, pick the other disk, Yes, then back to the SD card, Yes.

## Now Playing internals for layout A (traced 2026-11-07, build 28)

- **Play state:** `P = *(u32 **)0x030483D0`: P[0] = length ms, P[1] = position ms (+8/+0xC format values). Position
  also from 0x0308EA16(&ms). Message 0x39 = second tick (paint draws the position via 0x03057774(sec, &h, &m, &s)
  and 0x03082B0A(h, m, s, 0)), 0x3A = length known (0x03082B0A(..., 1)); 0x03082B0A builds "hh:mm:ss" and draws it
  with 0x03063E38 at (23, 203) / (223, 203) after clear image 0x21. 0x46 = progress: x = pos * 247 / len from 23,
  playhead images 0x124/0x125, columns from images 0x62/0x63 (info loaded in init into 0x03023BB8/88/A0).
- **Track counter:** 0x0308261A(n, total) draws "nnnn/tttt" with 0x03063E38 at (40, 10), after clear image 0x38.
- **Title line** (y 172..187, both modes): msg 0x43 (new title) clears image 0x1C, measures with 0x03063D52, if wider
  than 296 registers stock's text scroller 0x03064286(rect, ..., speed 0x1E) and posts 0x44; every paint while 0x44:
  0x030641EC(str) steps it. Mode 1 ([0x03023B6C] == 1) draws the lyric line (0x030248FC) on msg 0x49.
- **Status icons:** play state 0x1F/0x20 at (143, 6), 0x2D+n / 0x109+n at (183, 7), repeat 0x22..0x27 at (105, 10),
  battery 0x11E + *(u16 *)0x03022E94 at (209, 11). Background = image 0x1A (026) via 0x0306492A.
- **Cover:** module 18 decodes it straight into the framebuffer; m27 0x03082BFC sets width/height 0x74 (116) at
  0x03025160/0x0302515C and x 0x11 / y 0x2E at 0x03025164/0x03025168 (so 116x116 at (17, 46)); no cover: image
  0x115 (277) at (17, 46). Msg 0x115 = decode in progress (0x03054608 holds the screen flush meanwhile).
- **Drawing API:** framebuffer 0x03006688 (stride 592; 190 rows + 50 rows at 0x0306FD50; page 0x03022E48).
  FillRect 0x03064688(x0, y0, x1, y1) inclusive in colour *(u16 *)0x03022DEC = Window 0x03064EA8(x0, y0, x1, y1)
  then Pixel 0x03064DC4(colour) per pixel, row-major (we stream glyph bitmaps the same way). Font select
  0x030643A2(n): 1 = 12 px font0 (base *0x03022858), 2 = 16 px font1 (base *0x0302285C), current base at
  0x03022868; char width 0x03063BC6(ch) (adv byte > 0x80 -> byte - 0x80, else 6 / 8, CJK 12 / 16) plus letter
  spacing *(s16 *)0x03022E04; font1 glyph = 16 big-endian u16 rows at base + ch * 33, read with 0x0306535C(off,
  buf, n). Text 0x03063E38(x, y, str16), clipped text 0x03063F76(rect, rect, str16, mode).
- **Free code RAM while Now Playing runs:** 0x03083F0C (m27 end) .. 0x03084664 (module 18); modules 9 (FunUSB) and
  12 (USB storage) also use it but only in USB mode. Build 28 puts `game/device/npui.c` there as slot 28
  (`tools/build_overlay.py`), loaded by `np_load` (slot 2) at the end of m27's init. Title scroll state at RAM
  0x0309FFD8 (above slot 2, after libscan's 0x0309FFC0).
- Build 28 hooks (`np_v4`): init tail 0x03081654; info box 0x03082A2A / 0x03082A2E / 0x03082A90 / 0x03082AC6 /
  0x03082AE0 / 0x03082B04; title regions 0x0308344C (mode 1) and 0x03083478 (mode 0) -> np_title_new; scroller step
  0x0308350E -> np_title_step; times 0x03083114 / 0x0308341E -> np_time; counter 0x0308316A (clear) / 0x0308317A;
  progress 0x03083208 -> np_progress then on at 0x030833DA. Mode 1 now shows the title instead of lyrics.

## Stock Now Playing (module 27), traced 2026-11-07

- Window descriptor: tick 0x030823BE, service 0x03083688, paint 0x030835EC, init 0x030815C4, deinit 0x03081658.
- Text draw: 0x03063F76(rect*, rect*, str16, mode) in a rect {x0, y0, x1, y1}; 0x030644A0 draws a fallback when a
  string is empty; 0x030648EC clears a line area.
- Info box (0x030829AC): three lines in x 168..296 at y 91 / 112 / 133 from the tag record at 0x03048580:
  line 1 artist (+0x15E), line 2 album (+0x25C), line 3 genre (+0x35A), 0x40 UTF-16 chars each.
- Scrolling line at y 172..187 (0x03083422): one mode draws the long file name (0x030248FC, filled by 0x030639C2),
  the other the title buffer 0x03048450.
- Library record (module 34, 0x0308FA50): read from the hidden FAT volume; +0x400 (128 B) title -> 0x03048450,
  +0x500 artist -> 0x03048580+0x15E, +0x600 album -> +0x25C. A second path (0x0308FAF6) fills the title via 0x0305C364.
- **Title tag:** the tag reader (module 0, dispatcher 0x0306CD04, called by module 33 at play start after
  clearing the record with 0x03055B8A) writes title to record +0x60, artist +0x15E, album +0x25C (Vorbis
  "TITLE" match at 0x0306B1A4). 0x03048450 (library record +0x400) is the **file name**, not the title.
- Format line at (145, 60): string built at 0x030828E0, strip image 69 at 0x0308296E, text 0x03082996.
- Build 20 (`np_title_tag`): after line 1 the info box jumps to its epilogue, freeing 154 B of dead code at
  0x03082A30 for two helpers (hooks/np_title.S) that copy the file name into the title field when it is empty;
  mode 0 uses the title via literal 0x03083554, mode 1 via a call at 0x03083466.
- Build 18 patches (`tools/patch_code.py`): NOP the album and genre draws and their fallbacks; literal 0x030248FC at
  0x03083550 -> 0x03048450 so the scrolling line always shows the title. Unknown until tested: whether the title
  buffer is filled when playing from Folders.

## Module loading (ModuleOverlay)

- **RAM ends at 0x030A0000 (640 KB).** Stack top / initial SP = 0x03004000 (stack below module 0 data). Highest module run end = 0x0309F7CC (module 39). 0x0309FFF0 holds 4 magic words written before a reset (module 0 @0x03053DE8, read by module 1). **Free: 0x0309F800–0x0309FFF0 (2032 bytes)**, no literal in the image points there.
- `ModuleOverlay(n, type)` = **0x030683DE** (wrapper 0x030684E4, returns 0). Reads the 512-byte first sector of the code section from flash (base at `*0x03022864`, word 0 = 0x03050000), then table entry n at base + 8 + 32n, and copies **from flash**: type bit 0 code (cl → ce, cs), bit 1 data (dl → de, ds), bit 2 zero ZI (ze, zs). Copy routine 0x0306836A(flash offset, dst, len); flash byte read 0x03068194(0x30000, offset, len, buf). "Load" addresses are file positions (minus 0x03050000), never RAM.
- 0x0307E300 is a FAT sector cache (512 B buffer, +0x200 dirty flag, +0x204 cached sector), so module 0 cannot grow past 0x0307E300.
- **Empty slot 2 is loaded with type 7 in 21 places**, notably module 10's USB start (0x03081670 ModuleOverlay(12), 0x03081678 ModuleOverlay(2), then the handler). Pointing slot 2 at bytes in the file gap with run address 0x0309F800 makes stock load our code itself (`build_hook.py h1`). Empty slot 43 is loaded once (module 33).

## UI window / game module interface (for the v0.2 Blockz)

- Every UI screen and game is an overlay module whose **data section starts with a window descriptor**: `{0, 0, tick, service, paint, init, deinit}` (seen in modules 5, 6, 9, 17, 21 main menu, 27 Now Playing, 30, 32 settings, 81–111 games). Module 82 = stock Blockz ("LOCK PAUSE Level NEXT Score STOP Run"), module 81 = Snake. Module 82: code 0x1080 B at run 0x030815C4, data 0x3E8 B at 0x03023B48, ZI 0x320 B at 0x03023F30; state struct at 0x03023F34.
- Module 82 callbacks: tick 0x030824DE (increments state+0x14), service 0x0308249C (running → 0x03081FDA, paused/over → 0x030822BA), paint 0x030824EA, init 0x030824A8, deinit 0x030824D0.
- **Input:** `GetKey()` = 0x03062FA6 returns an event word: type in the top byte (0x40…, 0x20…, 0x41/0x42…), ladder key code in the low bits (0x001 GPIO key, 0x002 Select, 0x004 Right, 0x008 Left, 0x010 Up, 0x020 Down, 0x040 B, 0x080 A, 0x100 Start). Exact type meanings (press / repeat / release / long) still to confirm.
- **Messages:** bitset at 0x03023280; post = 0x03067ED4(id), test-and-clear = 0x03067EF0(id). Paint checks message ids such as 0x18C / 0x186 to decide what to redraw.
- **Drawing:** current colour (RGB565) at 0x03022DEC; fill rect 0x03064688(x0, y0, x1, y1) with that colour; text 0x03063E38(x, y, str16). The fill goes pixel by pixel (0x03064DC4), so a 60 fps game will want its own framebuffer writes plus the (still untraced) flush path.
- **Space while music plays:** module 33 (music) runs from 0x0308BF84 and decoders from 0x0308FFBC, so a replacement game module at 0x030815C4 has ~43 KB of code before it collides with the music engine.

## Device experiments log

- **H0 / H0a (2026-11-07), build 11.** Hook in the code.bin 0x57B8C gap, BL at 0x03083978 redirected. Both hang USB mass storage (see Memory). First H0 copy-update was silently consumed without flashing (battery was flat; device would not power on until charged). Second attempt flashed both slots.
- **Sector patching in loader mode works.** The flash copy of a slot is the IMG without its CRC trailer (slot offset 0x1C00000 holds unrelated data), so a change confined to one sector can be written directly with `rkwrite.py wl <slot LBA + sector> <512-byte file> --allow-any` (fw1 LBA 0, fw2 LBA 0xF000). Used to switch H0 → H0a and then restore the stock BL sector (0x40C) in both slots.
- **After a stalled read, the BootROM can drop off USB or fail the descriptor request.** Power off fully (hold 10 s) and replug; send `td` before the first read.
- **H1 (2026-11-07), build 12: PASSED.** Same INQUIRY-swap hook, linked at 0x0309F800 and loaded through module slot 2 (`build_hook.py h1`). Normal copy-update, booted normally; internal disk enumerates as `SCHALAOS ZEAL HOOK` rev `0.1`, SD stays `HIFI MP3 SD`. First custom code running on the AP30. Also shows USB DMA reads fine from 0x0309Fxxx.
- **D1 (2026-11-07), build 13: PASSED.** INQUIRY name = `<clock hex> <ch1 hex> <ch0 hex>`, rev `D1`. Read live without admin and without replugging with `tools/inquiry.py D [--loop N --changes]` (SCSI INQUIRY pass-through on `\\.\D:`). Results: clock 200 MHz, battery ch0 ≈ 0x372 (≈ 4.3 V on USB), buttons above. The ADC sampler keeps running in USB mode. B on the USB screen exits to the main menu (drops USB). The prompt appeared in Chinese after this update (settings likely reset by updates; to check).
- Device now: D1, stamp `26 20 07 11 13`.

## Game Boy probe (build 41, 2026-11-13)

- **Free RAM outside the library build:** modules overlapping 0x0308BF84..0x0309F7CC are m33 (music engine,
  0x0308BF84+0x37A0), m34 / m36 (0x0308F724), m40..m57 (0x0308FFBC, at most 0x490) and m39 (the library
  builder, 0x03081924..0x0309F7CC). No literal in the image points into 0x03090450..0x0309F7CC (the few hits are
  instruction encodings), so that ~62 KB is only used while the library builds. The probe uses
  0x03090800..0x0309F7C0 and the overlay window after its own code (to 0x0308BF84); the music engine stays.
- **Unused file space for a large module:** stock games 87..99 (tasks 20..32) are contiguous in code.bin
  0x95578..0xA3EC0 (58 KB) and unreachable since build 21's menu; m100 (donor) starts right after.
- **Stock games (traced 2026-11-14, build 55):** names in text.bin, English = language block 2 at 0x48EC + 2 x
  0x14896; fixed 0x112-byte UTF-16 records, text id n at block + 0x13C0 + (n - 86) x 0x112. Id 272 "Game", then 273..301
  one per task 14..42 in order: Retro Block Puzzle, Snake, Box Pusher, Brick Breaker, Block Shooter, Tank Battle,
  Gomoku, Minesweeper, Maze, Sudoku, Make 24, Number Merge, Number Slide, Match 3, Pair Link, Reversi, Jigsaw Puzzle,
  Memory Match, Fruit Catch, Car Racing, Gold Catch, Sky Shooter, Bubble Pop, Chinese Checkers, Frog Crossing,
  Block Puzzle+, Space Battle, Chinese Chess, Mole Hunt (task 43 also -> m109). Order confirmed by m81 =
  Block_Game.c and by size (the two largest intact modules, m104 9.6 KB and m108 11.1 KB, are Chinese Checkers and
  Chinese Chess). Untouched in amuletOS (byte-identical to stock): tasks 14, 16, 17, 18, 34..42. Reused: 15 Blockz,
  19 Playlists, 20..32 the Games screen span, 33 the extension donor. Every game quits with TaskSwitch(10, &7) (the
  stock game list, Settings page 7); build 55 patches the untouched ones to TaskSwitch(20) (`games_back`). The stock
  list itself (Settings > Game) lists all 29, including the reused ones; build 56 (`settings_game`) makes the
  Game item open task 20 instead.
- **Settings menu (module 32, traced 2026-11-14, build 56):** menu nodes are text ids; the key handler's enter step
  (0x0308247C) takes the selected child id from the current level (+5 selection, +8 node, ids at node +0x10) and calls
  0x03081C8E(id), which pushes a level for a submenu (Game = 0x110) or runs the leaf action 0x030836FC(id): a switch
  on id - 0x7f over 32-bit offsets from 0x03083770. Game leaves 0x111..0x12d launch: 0x111 -> 15, 0x112 -> 14,
  0x113..0x116 -> 16..19, 0x117 -> 22, 0x118 -> 21, 0x119 -> 20, 0x11a..0x120 -> 23..29, 0x121 -> 31, 0x122 -> 32,
  0x123..0x127 -> 34..38, 0x128 -> 30, 0x129..0x12b -> 39..41, 0x12c -> 43, 0x12d -> 42 (no item launches 33).
  This does not match the in-order name list above (e.g. 0x111 Retro Block Puzzle -> task 15, 0x112 Snake -> 14,
  0x128 Chinese Checkers -> 30); not yet checked which is right.
- **Owner's /f/roms/gb:** Tetris (World) (Rev 1), Kirby's Dream Land 2, Final Fantasy Adventure (USA) and My
  Friendly Little Island Deluxe are colourised hacks with header 0x143 = 0xC0 (Game Boy Color only); original
  Game Boy games there: Super Mario Land, Catrap, Pipe Dream, QIX, Burger Time Deluxe, Picross 2, Embers of Mana,
  The Frog for Whom the Bell Tolls.
- **No DWT cycle counter** (build 43: CYCCNT stays 0 after DEMCR.TRCENA + DWT_CTRL.CYCCNTENA). Time short spans
  with SysTick VAL (counts down at the core clock from LOAD; (start - end) mod LOAD + 1, under one 10 ms tick).
- **0x03090800.. is not executable** (build 45 Benchmark, 2026-11-13: a 3-instruction loop copied to 0x03090900 and
  called with interrupts off hung the device at that step; build 44 ran the same and came back with the probe's
  state scrambled). Data only: fine for emulator state and the page cache; code stays in the overlay window.
- **Screen push (traced 2026-11-13, build 47):** stock flush 0x0306558A -> panel ops (table 0x0306FD14, from module 4
  = resident panel driver at 0x03080E9C) ops[5] = 0x03080FEC(x0, y0, x1, y1, src): window 0x03080F28, 0x0306DE9C(0, 6),
  DMA channel 0x030614F8, DMA 0x03061524(ch, src, 0x6007002C, w*h/2, settings copied from 0x0306E96C, completion
  0x03080EAD) and a wait loop (0x03056704) until u16 0x03023B44 == 1 (set by the completion). Full-width rows only
  (one contiguous block). Rows >= 190 take a second pass after a ~1 ms busy wait (0x03065B58(1) = clk / 3000 loops).
  Full width x 144 rows took 3.2 ms (~22 us a row).
  Started without the wait (build 47) the DMA finishes during the next frame's emulation: Mario 59.6 fps, no tearing.

## Sound output (traced 2026-11-13, build 48)

Traced from the music engine (module 33: MusicInit 0x0308DDD0, Audio Start 0x0308C8EE, Music Thread Exit 0x0308E798)
and USB audio (module 11: 0x03082F4E). All helpers are resident (module 0).

| Run address | What it is |
|---|---|
| 0x03052BFC / 0x03056C2C / 0x03056C66 | GPIO (port, pin, x): pin mux / direction (1 = out) / level |
| 0x03062858 | watchdog kick (0x76 -> 0x4012000C); stock calls it around audio start |
| 0x03051F8E | DAC (re)start (CS43198 power-up) |
| 0x03056960 | I2S init (1, 2, 1, rate, 0, format, 0): format 0x17 = 24-bit (music), 0x0F = 16-bit (USB audio) |
| 0x0305094E / 0x03050A00 | I2S1 TX start (DMACR \|= 0x110, XFER on) / stop: args (1, 4) |
| 0x030622E4 | codec sample-rate setup (8000 .. 192000) |
| 0x0306242E | SetVolume(level); level = sys+0x12. 0 = codec 0xFF + amp off. Unmutes the amp only while the player thread runs |
| 0x03052B20 | CRU (n, on) at 0x40180000 + 0xC0: stock calls (4, 1) before codec setup |
| 0x03056774 | DMA channel busy (ChEnReg 0x600003A0 bit) |
| 0x0306602C | stock's audio DMA completion: restarts channel 5 on the next buffer |
| 0x030661A4 | stock's audio refill interrupt: decoder -> 0x030660E6 (to 24-bit right-justified) |

- **State:** u8 0x030227DA = DAC powered. MusicInit powers up only when it is 0: GPIO0 pin 12 low, GPIO1 pin 4 high,
  flag = 1, GPIO2 pin 14 high, GPIO2 pin 2 high, 11 ms, watchdog, DAC restart, I2S init 48 kHz 24-bit, TX start,
  100 ms, TX stop, CRU (4, 1). The player's exit powers it down (flag 0, GPIO1 pin 4 low, amp off, 0x03051C8A,
  GPIO2 pin 2 low).
- **Amp:** GPIO2 pin 1, low = on, high = off.
- **Per track (Audio Start):** CRU (4, 1), CodecRate(rate), SetVolume(sys+0x12), wait for channel 5 idle, I2S init
  (rate, 0x17), DmaStart(5, buffer, 0x40030024, words, 0x03005764, 0x0306602D), watchdog, 80 ms, TX start.
- **Data:** one 32-bit word per sample, left then right, **MSB-aligned (s16 << 16)**: build 50 sent s16 << 8 (as
  stock's refill converter 0x030660E6 produces) and it was ~48 dB too quiet. DMA count in words.
  Settings block 0x03005764 is module 0 initialised data (valid from boot).
- DMA channel 5 is the audio channel (stock's allocator 0x030614F8 hands out 0..4).
- **DAC power-up is needed even when the flag says on** (builds 48 / 49): with no music since boot the flag was 1,
  skipping MusicInit's sequence left the I2S taking words ~10x too fast (984 completions in 2 s for 94) and the DAC
  silent; after the full sequence the rate is exact (one 1024-frame buffer every 21333 us).
- **Ring for game sound (build 50):** 0x0308BF84..0x0308FF84 (m33 code + start of m34) while the player is stopped;
  restore with ModuleOverlay(33, 1) and (34, 1) (code only). Now Playing's start also reloads m33 when the player
  thread is not running.
- Now Playing B: press 0x40000040 -> 0x030838B0 (stock: back to the browser / Music list), hold 0x20000040 ->
  0x03083A64 = TaskSwitch(0, {0}) main menu; key 0x40000002 -> TaskSwitch(10, {1}) = Settings (task 10, m32).

