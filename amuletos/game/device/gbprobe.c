/* Game Boy probe (build 41; 42: direct framebuffer drawing, no sprite sorting; 47: background push): task 20
 * (module 87's slot; the code sits in the file space of stock games 87..99,
 * tools/build_module.py --span). Opened by the Music menu's temporary "Games" row (m22_ext.S).
 *
 * Lists /_gb/*.gb on the SD card, runs the chosen one with Peanut-GB (gb_core.c) at 1x in the middle of the
 * screen, and shows what we need to know before committing to Game Boy support (owner, 2026-11-13):
 *   top:    game title, frames per second reached (target 59.7)
 *   line 2: milliseconds per frame spent emulating, drawing (stock Window + Pixel) and pushing (stock flush)
 *   bottom: page cache (pages, loads per second, ms spent loading), cartridge RAM size
 *   line 4: raw button ADC, GPIO key level, the held Game Boy buttons, the last GetKey event
 * Build 55 (owner): the Games screen is one list with two headed sections, "Emu" (the ROMs in /_gb) and
 * "Built-in" (the stock games whose modules are untouched; their exits come back here, patch_code.py games_back).
 * The test rows (Sound test, core B memory, Benchmark; builds 43..54) are gone (owner).
 * Build 57 (v0.4 speed work): a last row "Timing" shows the play-start log (timing.c). Dev builds only
 * (-DAMU_TIMING=1); release builds leave it out (v0.3 release, owner: no test items in views).
 * Build 50: game sound (minigb_apu), paced by the sound output. Hold Select for 1.5 s to quit. No saves.
 * Build 53 (owner): no stats; the picture fills the screen height (266 x 240) in a DMG look (gb_scale.h).
 *
 * Memory (docs/HARDWARE.md "Game Boy probe"): the emulator state, the list and part of the page cache use
 * 0x03090cd0..0x0309FC90, which only the library builder (module 39) ever loads into; more cache pages use the
 * overlay window after this module's code, up to the music engine (0x0308C454). Music can keep playing. */
#include <stdint.h>
#include "../stock.h"
#define EX_NAME 26
#include "exfat.c"
#define PEANUT_GB_HIGH_LCD_ACCURACY 0   /* build 42: no per-line sprite sort (speed) */
#define GBX_SOUND 48000                 /* build 50 */
#include "gb_core.c"
#include "gb_scale.h"

void *memcpy(void *d, const void *s, size_t n) { uint8_t *a = d; const uint8_t *b = s; while (n--) *a++ = *b++; return d; }
void *memset(void *d, int v, size_t n) { uint8_t *a = d; while (n--) *a++ = (uint8_t)v; return d; }
void abort(void) { for (;;) {} }

#define SYSC       0x03022894u
#define S8(o)      (*(volatile uint8_t *)(SYSC + (o)))
#define DiskSwitch(n)       STOCK_FN(0x03058802, void, uint32_t)(n)
#define SetFont(n)          STOCK_FN(0x0306467E, uint32_t, uint32_t)(n)
#define CharW(c)            STOCK_FN(0x03063EA2, uint32_t, uint32_t)(c)
#define FontRead(o, b, n)   STOCK_FN(0x03065638, void, uint32_t, void *, uint32_t)(o, b, n)
#define Window(a, b, c, d)  STOCK_FN(0x03065184, void, int, int, int, int)(a, b, c, d)
#define Pixel(c)            STOCK_FN(0x030650A0, void, uint32_t)(c)
#define Flush()             STOCK_FN(0x03065866, void, void)()
#define ThreadRunning(h, d) STOCK_FN(0x03057F58, uint32_t, uint32_t, uint32_t)(h, d)
#define FONTBASE   (*(volatile uint32_t *)0x03022868u)
#define SPACING    (*(volatile int16_t *)0x03022E04u)
#define SYS_TICKS  (*(volatile uint32_t *)0x0302288Cu)
#define ST_LOAD    (*(volatile uint32_t *)0xE000E014u)
#define ST_VAL     (*(volatile uint32_t *)0xE000E018u)
#define ADC_CH1    (*(volatile uint16_t *)(0x03005A8Cu + 2))
#define GPIO2      (*(volatile uint32_t *)0x50030000u)

#define U_BASE     0x03090800u
#define U_END      0x0309F7C0u
#define WIN_END    0x0308BF84u
extern char _text_end[];             /* module.ld: end of this module's code */

#define MSG_DRAW   0x186
#define EV_PRESS   0x40u
#define K_UP       0x010
#define K_DOWN     0x020
#define K_B        0x040
#define K_A        0x080
#define K_LEFT     0x008

#define C_INK    RGB565(0x23, 0x25, 0x2e)
#define C_DIM    RGB565(0x7d, 0x82, 0x91)
#define C_WHITE  RGB565(0xff, 0xff, 0xff)
#define C_HEAD   RGB565(0xf2, 0xf3, 0xf6)
#define C_TRACK  RGB565(0xdf, 0xe1, 0xe8)
#define C_SCREEN RGB565(0xfb, 0xfb, 0xf8)
#define C_TINT   RGB565(0xe9, 0xe3, 0xfb)
#define C_GRAPE  RGB565(0x73, 0x53, 0xe0)

#define FRAME_US 16743u              /* 70224 cycles at 4.194304 MHz */
#define ROWS     7
#define NLIST    24

enum { ST_LIST, ST_RUN, ST_ERR, ST_QUIT, ST_TIMING };   /* build 55: no card / folder / games are list messages (S.emsg) */

typedef struct {
    uint32_t first, len;
    uint8_t  nofat, cgb, nlen;
    uint16_t name[EX_NAME];
} rom_t;

typedef struct {                     /* everything big, at U_BASE */
    gbx_t   g;
    rom_t   list[NLIST];
    uint32_t clus[512];              /* clusters of a fragmented ROM (2 MB in 4 KB clusters at most) */
    uint8_t sec[512];
    int16_t snd[AUDIO_SAMPLES_TOTAL];  /* one frame of sound before conversion (build 50) */
    gbs_t scale;                       /* full-height picture tables (build 53) */
    uint32_t keep;                     /* build 55: KEEP_TAG | top << 8 | sel, the row to come back to */
} big_t;
#define B ((big_t *)U_BASE)

static struct {
    uint8_t state, dirty, nlist, adc_state, adc_cand, gpio_idle, last_hdr, bstep;
    int sel, top;
    uint32_t adc_since, sel_since, next, stat_t0;
    uint32_t frames, emu_us, draw_us, push_us, load_us, loads0, late, line_us, wait_us, snd_us, stat_us, under0;
    uint8_t dma_busy, push_ph;        /* build 53: push phase 1 = rows 0..189 going, 2 = rows 190..239 going */
    uint32_t push_done_t;
    uint32_t skips;
    uint32_t last_ev, err;
    const rom_t *rom;
    const char *emsg;                 /* build 55: shown in the Emu section instead of ROMs (no card / folder / games) */
    int ttop;                         /* build 57: first event line shown on the Timing screen */
} S;

/* ---- text (stock 16 px font, drawn as runs; as playlists.c) ---- */
static void fill(int x0, int y0, int x1, int y1, uint16_t c) { COLOR = c; FillRect(x0, y0, x1, y1); }

static int text(int x, int y, const uint16_t *s, uint16_t col, int x_max)
{
    SetFont(2);
    uint32_t base = FONTBASE;
    COLOR = col;
    for (; *s; s++) {
        int w = (int)CharW(*s) + SPACING;
        if (x + w > x_max) break;
        if (*s != ' ') {
            uint8_t g[32];
            FontRead(base + *s * 33u, g, 32);
            for (int r = 0; r < 16; r++) {
                uint32_t v = (uint32_t)g[2 * r] << 8 | g[2 * r + 1];
                for (int c = 0; c < 16; ) {
                    if (!(v & (0x8000u >> c))) { c++; continue; }
                    int c0 = c;
                    while (c < 16 && (v & (0x8000u >> c))) c++;
                    FillRect(x + c0, y + r, x + c - 1, y + r);
                }
            }
        }
        x += w;
    }
    return x;
}

/* tiny formatter: %s (char *), %d, %x (8 digits), %1 (value / 10 with one decimal: 597 -> 59.7) */
static void fmt(uint16_t *o, const char *f, const uint32_t *a)
{
    int k = 0;
    for (; *f && k < 60; f++) {
        if (*f != '%') { o[k++] = (uint8_t)*f; continue; }
        char t = *++f; uint32_t v = *a++;
        char tmp[12]; int n = 0;
        if (t == 's') { for (const char *s = (const char *)v; *s && k < 60; s++) o[k++] = (uint8_t)*s; continue; }
        if (t == 'x') { for (int i = 7; i >= 0; i--) { uint32_t d = (v >> (4 * i)) & 15; o[k++] = d < 10 ? '0' + d : 'A' + d - 10; } continue; }
        uint32_t w = t == '1' ? v / 10 : v;
        do { tmp[n++] = (char)('0' + w % 10); w /= 10; } while (w);
        while (n) o[k++] = tmp[--n];
        if (t == '1') { o[k++] = '.'; o[k++] = (uint16_t)('0' + v % 10); }
    }
    o[k] = 0;
}

static void say(int x, int y, uint16_t col, const char *f, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4)
{
    uint32_t a[5] = { a0, a1, a2, a3, a4 };
    uint16_t b[64];
    fmt(b, f, a);
    text(x, y, b, col, 294);
}

static uint32_t now_us(void)
{
    uint32_t t1, v, load;
    do { t1 = SYS_TICKS; v = ST_VAL; load = ST_LOAD; } while (t1 != SYS_TICKS);
    if (v > load) v = load;
    uint32_t per_us = (load + 1u) / 10000u;
    return t1 * 10000u + (per_us ? (load - v) / per_us : 0);
}

/* ---- ROM pages from the SD card ---- */
static uint32_t sec_of(const rom_t *r, uint32_t off)          /* absolute LBA of the sector holding byte off */
{
    uint32_t cb = 9 + X.shift, ci = off >> cb;
    uint32_t c = r->nofat ? r->first + ci : B->clus[ci];
    return ex_lba(c) + ((off >> 9) & ((1u << X.shift) - 1));
}

void gbx_read_page(gbx_t *x, uint32_t page, uint8_t *dst)
{
    uint32_t t0 = now_us(), off = page << PG_SHIFT;
    for (uint32_t k = 0; k < PG_SIZE; k += 512)
        if (off + k < S.rom->len) ReadSec(sec_of(S.rom, off + k), dst + k);
        else for (int i = 0; i < 512; i++) dst[k + i] = 0xFF;
    S.load_us += now_us() - t0;
}

/* Draw straight into stock's RAM framebuffer (build 42; build 41 went through stock's Window + Pixel: 15 ms a
 * frame). Layout, from Pixel 0x030650A0 / flush 0x03065866 (docs/HARDWARE.md "Display"): rows 0..189 at
 * 0x030066c8 + page * 0x1B760, rows 190..239 at 0x03070220 + page * 0x73A0, 592 bytes a row; the panel is mounted
 * mirrored (column = 295 - x while the rotation flag is set) and pixels are swapped in pairs (index ^ 1). After a
 * frame, Window() over the Game Boy area marks the rows dirty for the flush, as Pixel would. */
#define FBS        0x03022E48u
#define FB_PAGE    (*(volatile uint16_t *)(FBS + 0x00))
#define FB_DIRTY   (*(volatile uint32_t *)(FBS + 0x0C))
#define FB_ROT     (*(volatile uint32_t *)(FBS + 0x14))

static void push_service(void);
static uint16_t *fb_any(int y)                           /* any row: 0..189 in the page, 190..239 in the second area */
{
    return y < 190 ? (uint16_t *)(0x03006688u + FB_PAGE * 0x1B760u + (uint32_t)y * 592u)
                   : (uint16_t *)(0x0306FD50u + FB_PAGE * 0x73A0u + (uint32_t)(y - 190) * 592u);
}

/* Build 53: the core hands over shades 0..3 (B->g.pal = 0..3); each Game Boy line becomes 1 or 2 screen rows,
 * 266 wide, DMG colours and grid (gb_scale.h). Then the second half of the last push may be due (push_service). */
void gbx_line(const uint16_t *sh, int line)
{
    uint32_t t0 = now_us();
    int y0, n = gbs_rows(line, &y0);
    gbs_line(&B->scale, sh, fb_any(y0), n == 2 ? fb_any(y0 + 1) : 0);
    S.line_us += now_us() - t0;
    push_service();
}

/* Background push (build 47). The panel driver's push (module 4, ops[5] = 0x030814BC, called by stock's flush)
 * sets the LCD window, sends command 6, starts a DMA from the framebuffer to the LCD FIFO 0x6007002C and then
 * loops until the DMA's completion handler (0x0308137C) sets *(u16 *)0x03025B84 = 1: build 46 measured 3.2 ms
 * of waiting per frame. We do the same steps and return at once; the next push (or any stock flush) first waits
 * for the flag. The DMA reads rows top to bottom at ~22 us a row, ahead of the next frame's line writes (~86 us
 * a line), so it never shows a half-new frame. Full-width rows: the transfer is one contiguous block. */
#define LCD_DONE   (*(volatile uint16_t *)0x03023B44u)
#define LcdWindow(a, b, c, d)  STOCK_FN(0x030813F8, void, int, int, int, int)(a, b, c, d)
#define VopCmd(a, b)           STOCK_FN(0x0306E334, void, uint32_t, uint32_t)(a, b)
#define DmaGet()               STOCK_FN(0x030617D4, uint32_t, void)()
#define DmaStart(ch, src, dst, n, cfg, cb)     STOCK_FN(0x03061800, void, uint32_t, uint32_t, uint32_t, uint32_t, void *, uint32_t)(ch, src, dst, n, cfg, cb)

/* Build 53: the whole screen, in two parts as stock's flush does: rows 0..189 (page), then ~1 ms after that DMA has
 * finished, rows 190..239 (second area) with their own window. The second part is started from the line callback
 * (push_service, every ~90 us of emulation) so nothing waits; the next frame reaches row 190 only ~11 ms in. */
static uint32_t push_cfg[4];

static void push_part(int y0, int y1, uint32_t src)
{
    LCD_DONE = 0;
    LcdWindow(0, y0, 0x127, y1);
    VopCmd(0, 6);
    uint32_t ch = DmaGet() & 0xFF;
    DmaStart(ch, src, 0x6007002Cu, 0x128u * (uint32_t)(y1 - y0 + 1) / 2u, push_cfg, 0x03080EADu);
}

static void push_service(void)
{
    if (S.push_ph != 1 || LCD_DONE != 1) return;
    uint32_t t = now_us();
    if (!S.push_done_t) { S.push_done_t = t | 1; return; }
    if (t - S.push_done_t < 1000) return;
    push_part(190, 239, (uint32_t)fb_any(190));
    S.push_ph = 2;
}

static void push_wait(void)
{
    if (!S.dma_busy) return;
    uint32_t t0 = now_us();
    while (S.push_ph == 1) { push_service(); if (now_us() - t0 > 50000) break; }   /* never hang: 50 ms cap */
    while (LCD_DONE != 1) { if (now_us() - t0 > 50000) break; }
    S.wait_us += now_us() - t0;
    S.dma_busy = 0;
    S.push_ph = 0;
}

static void push_async(void)
{
    push_wait();
    const volatile uint32_t *c = (const volatile uint32_t *)0x0306E96Cu;   /* the driver's DMA settings */
    for (int i = 0; i < 4; i++) push_cfg[i] = c[i];
    push_part(0, 189, (uint32_t)fb_any(0));
    S.push_ph = 1;
    S.push_done_t = 0;
    S.dma_busy = 1;
}

/* ---- sound (build 48; 50: ring buffer, game sound) ---- docs/HARDWARE.md "Sound output"
 * Traced from the music engine (module 33: MusicInit 0x0308F070, Audio Start 0x0308D872) and USB audio (module 11
 * 0x0308341E). Output = DMA channel 5 (reserved for audio; the allocator hands out 0..4) from RAM to the I2S1 FIFO
 * 0x40030024 with stock's settings block 0x03005784 (module 0 initialised data), one 32-bit word per sample, left
 * then right, MSB-aligned: s16 << 16 (build 51; 50 sent s16 << 8, as stock's refill converter 0x030663C2 does, and
 * the owner heard almost nothing: 48 dB down. Stock's first-buffer converter 0x0306634A gives s16 << 16).
 * The music player is stopped first (it owns the same channel).
 * Build 50: a ring of NCH chunks of CHF frames in the music engine's code window (0x0308C454.., m33 + the start of
 * m34; idle once the player is stopped; reloaded from flash on close). Each chunk's DMA completion starts the next
 * chunk at once, then clears the finished one (a late chunk plays silence, not old sound). Games: the emulator runs
 * a frame whenever fewer than SND_MARGIN frames are queued past the playing chunk, so the sound clock paces the game
 * (48000 / 803 = 59.78 frames a second); each frame first renders its 803 samples (minigb_apu, from the sound
 * registers the last frame left) so they are queued before the 13 ms of emulation. */
#define DAC_ON      (*(volatile uint8_t *)0x030227DAu)   /* stock: DAC powered (MusicInit / USB audio / music exit) */
#define PHAND       0x030232BCu                          /* player thread handle, descriptor (bgmusic.c) */
#define PDESC       0x030361A4u
#define ThreadDelete(hp)      STOCK_FN(0x03057F14, void, uint32_t)(hp)
#define DelayMs(n)            STOCK_FN(0x03065E34, void, uint32_t)(n)
#define IoMux(p, n, f)        STOCK_FN(0x03052BFC, void, uint32_t, uint32_t, uint32_t)(p, n, f)
#define GpioDir(p, n, d)      STOCK_FN(0x03056F08, void, uint32_t, uint32_t, uint32_t)(p, n, d)
#define GpioSet(p, n, v)      STOCK_FN(0x03056F42, void, uint32_t, uint32_t, uint32_t)(p, n, v)
#define WdtKick()             STOCK_FN(0x03062b34, uint32_t, void)()          /* 0x76 -> 0x4012000C */
#define DacRestart()          STOCK_FN(0x03051F8E, void, void)()              /* CS43198 power-up */
#define ClkGate(n, on)        STOCK_FN(0x03052B20, void, uint32_t, uint32_t)(n, on)
#define I2sInit(a, b, c, rate, d, fmt, e) STOCK_FN(0x03056c3c, void, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t)(a, b, c, rate, d, fmt, e)
#define I2sTxStart(i, m)      STOCK_FN(0x0305094E, uint32_t, uint32_t, uint32_t)(i, m)
#define I2sTxStop(i, m)       STOCK_FN(0x03050A00, void, uint32_t, uint32_t)(i, m)
#define CodecRate(r)          STOCK_FN(0x030625C0, void, uint32_t)(r)
#define SetVolume(v)          STOCK_FN(0x0306270A, void, uint32_t)(v)
#define DmaBusy(ch)           STOCK_FN(0x03056a50, uint32_t, uint32_t)(ch)
#define ModuleOverlay(n, t)   STOCK_FN(0x030686FA, uint32_t, uint32_t, uint32_t)(n, t)
#define I2S_TXDR    0x40030024u
#define AUDIO_DMA   0x03005764u
#define SND_RATE    48000u
#define CHF         256u                                  /* frames per DMA chunk: 5.3 ms */
#define NCH         8u
#define RINGF       (CHF * NCH)                           /* 2048 frames, 16 KB */
#define SND_MARGIN  960u                                  /* 20 ms queued before a frame is emulated (build 52;
                                                              51: 768). Ring limit: SND_MARGIN + 803 <= 7 chunks */
#define SKIP_BELOW  (SND_MARGIN - CHF)                    /* fewer queued at a frame start: behind, skip drawing */
#define SND_RING    ((int32_t *)0x0308BF84u)              /* .. 0x03090454, below the decoders (0x03091370) */

static void redraw(void);
static volatile uint32_t snd_n, snd_p, snd_irqs, snd_under, snd_t_first, snd_t_last;
static volatile uint8_t snd_stop;
static struct { uint8_t on, music, dac, busy, tone; uint32_t t0, phase, side; } SN;

static int32_t *chunk(uint32_t k) { return SND_RING + (k % NCH) * CHF * 2u; }

/* Tone test: 375 Hz triangle at -24 dB, 1 s left only, then 1 s right only. */
static void tone_fill(int32_t *b)
{
    for (uint32_t i = 0; i < CHF; i++) {
        uint32_t p = SN.phase; SN.phase = p + (uint32_t)(375ull * 4294967296ull / SND_RATE);
        int32_t t = (int32_t)(p >> 16);                   /* 0..65535 */
        int32_t v = t < 32768 ? t - 16384 : 49152 - t;    /* -16384..16384 */
        v = v / 8;                                        /* +-2048 of 32767: -24 dB */
        b[2 * i]     = SN.side == 0 ? v << 16 : 0;
        b[2 * i + 1] = SN.side == 1 ? v << 16 : 0;
    }
}

static void snd_done(void)                               /* DMA completion (interrupt): chunk snd_n finished */
{
    uint32_t k = snd_n, nx = k + 1;
    snd_irqs++;
    { uint32_t t = now_us(); if (!snd_t_first) snd_t_first = t; snd_t_last = t; }
    if (snd_stop) { snd_stop = 2; return; }
    DmaStart(5, (uint32_t)chunk(nx), I2S_TXDR, CHF * 2u, (void *)AUDIO_DMA, (uint32_t)snd_done);
    if (SN.tone) tone_fill(chunk(k));                     /* plays again after the other NCH - 1 chunks */
    else {
        if (snd_p < (nx + 1) * CHF) snd_under++;          /* the chunk just started was not fully rendered */
        int32_t *c = chunk(k); for (uint32_t i = 0; i < CHF * 2u; i++) c[i] = 0;
    }
    snd_n = nx;                                           /* after the clear: the producer may now write there */
}

static void snd_open(int tone)
{
    SN.music = ThreadRunning(*(volatile uint32_t *)PHAND, PDESC) == 1;
    if (SN.music) ThreadDelete(PHAND);                    /* its exit powers the DAC down and mutes */
    for (int i = 0; i < 200 && DmaBusy(5); i++) DelayMs(1);
    SN.busy = (uint8_t)DmaBusy(5);
    SN.dac = DAC_ON;
    {   /* MusicInit's power-up, always (build 50): on 48 the flag said on (no music since boot), we skipped this and
         * the I2S ran ~10x fast with no sound; on 49 (music stopped first, flag 0) it ran at the right rate */
        IoMux(0, 12, 0); GpioDir(0, 12, 1); GpioSet(0, 12, 0);
        IoMux(1, 4, 0);  GpioDir(1, 4, 1);  GpioSet(1, 4, 1);
        DAC_ON = 1;
        IoMux(2, 14, 0); GpioDir(2, 14, 1); GpioSet(2, 14, 1);
        IoMux(2, 2, 0);  GpioDir(2, 2, 1);  GpioSet(2, 2, 1);
        DelayMs(11);
        WdtKick();
        DacRestart();
        I2sInit(1, 2, 1, 48000, 0, 0x17, 0);
        I2sTxStart(1, 4);
        DelayMs(100);
        I2sTxStop(1, 4);
        ClkGate(4, 1);
    }
    ClkGate(4, 1);                                        /* Audio Start's sequence */
    CodecRate(SND_RATE);
    SetVolume(S8(0x12));
    I2sInit(1, 2, 1, SND_RATE, 0, 0x17, 0);
    SN.tone = (uint8_t)tone; SN.phase = 0; SN.side = 0;
    snd_n = 0; snd_stop = 0; snd_irqs = snd_under = 0; snd_t_first = snd_t_last = 0;
    if (tone) for (uint32_t k = 0; k < NCH; k++) tone_fill(chunk(k));
    else { for (uint32_t i = 0; i < RINGF * 2u; i++) SND_RING[i] = 0; snd_p = 2u * CHF; }
    DmaStart(5, (uint32_t)chunk(0), I2S_TXDR, CHF * 2u, (void *)AUDIO_DMA, (uint32_t)snd_done);
    WdtKick();
    DelayMs(80);
    I2sTxStart(1, 4);
    WdtKick();
    IoMux(2, 1, 0); GpioDir(2, 1, 1); GpioSet(2, 1, 0);  /* amp on (stock's SetVolume does this only while the
                                                              player thread runs) */
    SN.on = 1;
    SN.t0 = now_us();
}

static void snd_close(void)
{
    if (!SN.on) return;
    snd_stop = 1;
    uint32_t t0 = now_us();
    while (snd_stop != 2 && now_us() - t0 < 100000) {}    /* the playing chunk finishes (5.3 ms) */
    IoMux(2, 1, 0); GpioDir(2, 1, 1); GpioSet(2, 1, 1);  /* amp off, as stock at volume 0 / music exit */
    I2sTxStop(1, 4);
    ModuleOverlay(33, 1);                                 /* the ring overwrote the music engine's code */
    ModuleOverlay(34, 1);
    SN.on = 0;
}

/* games: room for one more frame of sound? (no more than SND_MARGIN frames queued past the playing chunk) */
static int snd_ready(void) { return snd_p <= (snd_n + 1u) * CHF + SND_MARGIN; }

static void snd_produce(int16_t *tmp)
{
    uint32_t n = snd_n;
    if (snd_p < (n + 1u) * CHF) snd_p = (n + 1u) * CHF;  /* fell behind: start at the next chunk */
    gbx_audio(&B->g, tmp);
    uint32_t p = snd_p;
    for (uint32_t i = 0; i < AUDIO_SAMPLES; i++) {
        int32_t *w = SND_RING + ((p + i) & (RINGF - 1u)) * 2u;
        w[0] = (int32_t)tmp[2 * i] << 16;
        w[1] = (int32_t)tmp[2 * i + 1] << 16;
    }
    snd_p = p + AUDIO_SAMPLES;
}

/* ---- list (build 55): "Emu" heading, the ROMs (or a message), "Built-in" heading, the stock games ---- */
/* Stock games that are still in the firmware (docs/HARDWARE.md "Stock games"): task and English name (text.bin id
 * 273 + task - 14). Tasks 15 and 19..33 hold Blockz, Playlists, this module and the extension donor now. */
static const struct { uint8_t task; char name[19]; } STOCK[] = {
    { 14, "Retro Block Puzzle" }, { 16, "Box Pusher" }, { 17, "Brick Breaker" }, { 18, "Block Shooter" },
    { 34, "Gold Catch" }, { 35, "Sky Shooter" }, { 36, "Bubble Pop" }, { 37, "Chinese Checkers" },
    { 38, "Frog Crossing" }, { 39, "Block Puzzle+" }, { 40, "Space Battle" }, { 41, "Chinese Chess" },
    { 42, "Mole Hunt" } };
#define NSTOCK   ((int)(sizeof STOCK / sizeof STOCK[0]))
#define KEEP_TAG 0x4B500000u
enum { R_HEAD_EMU, R_ROM, R_MSG, R_HEAD_BUILTIN, R_STOCK, R_TIMING };

static int emu_rows(void) { return S.emsg ? 1 : S.nlist; }
#ifndef AMU_TIMING
#define AMU_TIMING 0
#endif
static int row_count(void) { return emu_rows() + 2 + NSTOCK + (AMU_TIMING ? 1 : 0); }   /* + "Timing" (dev) */
static int row_kind(int i, int *idx)
{
    int e = emu_rows();
    if (i == 0) return R_HEAD_EMU;
    if (i <= e) { *idx = i - 1; return S.emsg ? R_MSG : R_ROM; }
    if (i == e + 1) return R_HEAD_BUILTIN;
    *idx = i - e - 2;
    return *idx < NSTOCK ? R_STOCK : R_TIMING;
}
static int selectable(int i)
{
    int k, n = row_count();
    if (i < 0 || i >= n) return 0;
    k = row_kind(i, &n);
    return k == R_ROM || k == R_STOCK || k == R_TIMING;
}
static void show_sel(void)                                /* scroll so the selection (and its heading) shows */
{
    if (S.sel < S.top) S.top = S.sel;
    if (S.top == S.sel && S.sel > 0 && !selectable(S.sel - 1)) S.top = S.sel - 1;
    if (S.sel >= S.top + ROWS) S.top = S.sel - ROWS + 1;
}
static void move_sel(int d)
{
    int n = row_count(), s = S.sel;
    for (int k = 0; k < n; k++) {
        s += d;
        if (s < 0) s = n - 1;
        if (s >= n) s = 0;
        if (selectable(s)) break;
    }
    S.sel = s;
    show_sel();
}

static int list_cb(const exent_t *e, int match, void *ctx)
{
    if (e->is_dir || S.nlist >= NLIST) return 0;
    if (!(e->elen == 2 && e->ext[0] == 'G' && e->ext[1] == 'B') &&
        !(e->elen == 3 && e->ext[0] == 'G' && e->ext[1] == 'B' && e->ext[2] == 'C')) return 0;
    if (e->nlen && e->name[0] == '.') return 0;                 /* macOS ._ files */
    rom_t *r = &B->list[S.nlist++];
    r->first = e->first; r->len = e->len; r->nofat = (e->flags & 2) != 0;
    r->nlen = (uint8_t)(e->cap < EX_NAME ? e->cap : EX_NAME);
    for (int i = 0; i < r->nlen; i++) r->name[i] = e->name[i];
    return 0;
}

static void build_list(void)
{
    static const uint16_t gbdir[] = { '_', 'G', 'B' };
    exdir_t root, dir;
    ex_root(&root);
    if (!ex_find(&root, gbdir, 3, 1, &dir, 0)) { S.emsg = "No _gb folder"; return; }
    ex_walk(&dir, 0, 0, list_cb, 0);
    if (!S.nlist) { S.emsg = "No games"; return; }
    for (int i = 0; i < S.nlist; i++) {                           /* header byte 0x143: 0xC0 = Game Boy Color only */
        rom_t *r = &B->list[i];
        r->cgb = 0;
        if (r->len > 0x150) { ReadSec(ex_lba(r->first), B->sec); r->cgb = B->sec[0x143]; }
    }
}

static void redraw(void) { S.dirty = 1; SendMsg(MSG_DRAW); }

static void init(void)
{
    uint8_t *p = (uint8_t *)&S;
    for (unsigned i = 0; i < sizeof S; i++) p[i] = 0;
    if (!S8(0x1F)) S.emsg = "No SD card";
    else {
        if (S8(0x0E) != 4) { S8(0x0E) = 4; DiskSwitch(4); }
        if (ex_init()) S.emsg = "No SD card";
        else build_list();
    }
    S.sel = -1; move_sel(1);                                      /* first game */
    if ((B->keep & 0xFFFF0000u) == KEEP_TAG) {                    /* back from a game: the same row */
        int s = (int)(B->keep & 0xFF), t = (int)((B->keep >> 8) & 0xFF);
        if (selectable(s) && t <= s && s < t + ROWS) { S.sel = s; S.top = t; }
    }
    GameEnterA();
    GameEnterB();
    redraw();
}

static void deinit(void) { GameLeaveA(); GameLeaveB(); }

static int32_t tick(void) { return 0; }

static void push_wait(void);
static void snd_close(void);
static void quit(void)
{
    uint16_t tile = 1;
    push_wait();
    snd_close();
    GameLeaveB();
    TaskSwitch(0, &tile);
    S.state = ST_QUIT;
}

/* A stock game (build 55): leave as quit() does, then its task. The stock list passed its own argument; the games
 * we checked do not read it, so it is zero. Their exits come back to task 20 (patch_code.py games_back). */
static void launch(uint32_t task)
{
    static uint16_t arg[14];
    B->keep = KEEP_TAG | (uint32_t)S.top << 8 | (uint32_t)S.sel;
    push_wait();
    snd_close();
    GameLeaveB();
    TaskSwitch(task, arg);
    S.state = ST_QUIT;
}

/* ---- buttons: ADC ladder held state (debounced as Blockz) + the GPIO key ---- */
static const uint16_t ADC_EDGE[8] = { 59, 180, 303, 425, 576, 722, 815, 950 };   /* midpoints, docs/HARDWARE.md */
static const uint8_t  ADC_PAD[8]  = { JOYPAD_RIGHT, JOYPAD_UP, JOYPAD_LEFT, JOYPAD_DOWN,
                                      JOYPAD_SELECT, JOYPAD_START, JOYPAD_B, JOYPAD_A };
static uint8_t adc_decode(uint16_t a) { for (int i = 0; i < 8; i++) if (a < ADC_EDGE[i]) return (uint8_t)i; return 8; }

static void poll_adc(uint32_t now)
{
    uint8_t k = adc_decode(ADC_CH1);
    if (k != S.adc_cand) { S.adc_cand = k; S.adc_since = now; return; }
    if (k == S.adc_state) return;
    uint32_t need = k == 8 ? 16000 : S.adc_state == 8 ? (k == 3 ? 40000 : 24000) : k > S.adc_state ? 80000 : 24000;
    if (now - S.adc_since >= need) S.adc_state = k;
}

static uint8_t gpio_key(void) { return (uint8_t)((GPIO2 >> 5) & 1); }

/* ---- running ---- */
static void frame_box(void)
{
    fill(0, 0, 295, 239, C_SCREEN);                               /* build 53: side bars; the picture covers the rest */
}

static void start(const rom_t *r)
{
    S.rom = r;
    if (r->cgb == 0xC0) { S.err = 100; S.state = ST_ERR; redraw(); return; }
    if (r->len > (2u << 20)) { S.err = 101; S.state = ST_ERR; redraw(); return; }
    if (!r->nofat) {                                              /* fragmented: follow the FAT once */
        uint32_t c = r->first, n = (r->len + (512u << X.shift) - 1) >> (9 + X.shift);
        if (n > 512) { S.err = 104; S.state = ST_ERR; redraw(); return; }
        for (uint32_t i = 0; i < n; i++) { B->clus[i] = c; c = ex_next(c, 0); }
    }
    /* page buffers: the window after our code first, then the region after big_t */
    static uint8_t *pages[PG_SLOTS];
    uint32_t n = 0, a = ((uint32_t)_text_end + 3) & ~3u;
    for (; a + PG_SIZE <= WIN_END && n < PG_SLOTS; a += PG_SIZE) pages[n++] = (uint8_t *)a;
    a = (U_BASE + sizeof(big_t) + 3) & ~3u;
    for (; a + PG_SIZE <= U_END && n < PG_SLOTS; a += PG_SIZE) pages[n++] = (uint8_t *)a;
    int e = gbx_init(&B->g, r->len, pages, n);
    if (e) { S.err = (uint32_t)e; S.state = ST_ERR; redraw(); return; }
    for (int i = 0; i < 4; i++) B->g.pal[i] = (uint16_t)i;       /* build 53: shades out, gb_scale.h colours them */
    gbs_init(&B->scale, FB_ROT != 0, 1);
    uint32_t cram = gbx_save_size(&B->g);                         /* build 54: pages taken on first write */
    B->g.cram_len = cram > GBX_CRAM_MAX ? 0 : cram;
    S.gpio_idle = gpio_key();
    S.adc_state = S.adc_cand = 8;
    S.state = ST_RUN;
    frame_box();
    snd_open(0);                                                  /* build 50: game sound (stops the music) */
    S.next = S.stat_t0 = now_us();
    S.frames = S.emu_us = S.draw_us = S.push_us = S.load_us = S.late = S.snd_us = S.stat_us = 0;
    S.loads0 = B->g.misses; S.under0 = snd_under;
}

static void run(void)
{
    uint32_t now = now_us();
    poll_adc(now);
    uint8_t pad = 0xFF;
    if (S.adc_state < 8) pad &= (uint8_t)~ADC_PAD[S.adc_state];
    if (gpio_key() != S.gpio_idle) pad &= (uint8_t)~JOYPAD_A;   /* the one key that combines with the ladder */
    B->g.gb.direct.joypad = pad;
    if (S.adc_state == 4) { if (!S.sel_since) S.sel_since = now | 1; else if (now - S.sel_since > 1500000) { quit(); return; } }
    else S.sel_since = 0;
    int skip = 0;
    if (SN.on) {                                                  /* build 50: paced by the sound clock */
        if (!snd_ready()) return;
        /* Build 52: owner on 51: crackles when Mario moves (scrolling costs more than the 16.7 ms a frame has).
         * Behind by a chunk or more: emulate this frame without drawing it (Peanut skips its line rendering;
         * about half a frame's time on the PC), so the sound catches up and the picture drops a frame instead. */
        int32_t q = (int32_t)(snd_p - (snd_n + 1u) * CHF);
        skip = q < (int32_t)SKIP_BELOW;
        uint32_t a0 = now_us();
        snd_produce(B->snd);
        S.snd_us += now_us() - a0;
    } else if ((int32_t)(now - S.next) < 0) return;
    S.line_us = 0;
    B->g.gb.direct.frame_skip = skip != 0;                        /* Peanut: no lines while frame_skip && !count */
    B->g.gb.display.frame_skip_count = 0;
    if (skip) S.skips++;
    uint32_t t0 = now_us();
    gb_run_frame(&B->g.gb);
    uint32_t t1 = now_us();
    if (!skip) push_async();
    uint32_t t2 = now_us();
    S.emu_us += (t1 - t0) - S.line_us;
    S.draw_us += S.line_us;
    S.push_us += t2 - t1;
    S.frames++;
    if (B->g.err) { snd_close(); S.err = 200 + (uint32_t)B->g.err; S.state = ST_ERR; redraw(); return; }
    S.next += FRAME_US;
    if ((int32_t)(t2 - S.next) > (int32_t)(3 * FRAME_US)) { S.next = t2; S.late++; }
}

/* Build 51: the wheel changes the volume in games (owner on 50: it did nothing). Stock's SetVolume writes the codec;
 * it switches the amp off at 0 and on again only while the player runs, so the amp is ours. */
static void wheel(int d)
{
    int v = S8(0x12) + d;
    if (v < 0) v = 0;
    if (v > 100) v = 100;
    S8(0x12) = (uint8_t)v;
    SetVolume((uint32_t)v);
    if (SN.on && v) { IoMux(2, 1, 0); GpioDir(2, 1, 1); GpioSet(2, 1, 0); }
}

static int32_t service(void)
{
    if (S.state == ST_QUIT) return -1;
    if (S.state == ST_RUN) {
        for (int n = 0; n < 8; n++) {
            uint32_t ev = GetKey(); if (!ev) break; S.last_ev = ev;
            uint32_t k = ev & 0x7FF, t = ev >> 24;
            if ((t == 0x40 || t == 0x30) && (k == 0x400 || k == 0x200)) wheel(k == 0x400 ? 1 : -1);
        }
        run();
        return S.state == ST_QUIT ? -1 : 0;
    }
    for (int n = 0; n < 8; n++) {
        uint32_t ev = GetKey();
        if (!ev) break;
        uint32_t type = ev >> 24, k = ev & 0x1FF;
        if (type != EV_PRESS && type != 0x30) continue;
        if (S.state == ST_TIMING) {                               /* build 57: Up / Down scroll, anything else back */
            if (k == K_UP || k == K_DOWN) { S.ttop += k == K_DOWN ? 1 : -1; if (S.ttop < 0) S.ttop = 0; }
            else if (type == EV_PRESS) S.state = ST_LIST;
            redraw();
            continue;
        }
        if (k == K_B || (k == K_LEFT && type == EV_PRESS)) { quit(); return -1; }
        if (S.state == ST_ERR) { if (type == EV_PRESS) { S.state = ST_LIST; redraw(); } continue; }
        if (S.state != ST_LIST) continue;
        if (k == K_UP || k == K_DOWN) {
            move_sel(k == K_DOWN ? 1 : -1);
            redraw();
        } else if (k == K_A && type == EV_PRESS && selectable(S.sel)) {
            int idx = 0, kind = row_kind(S.sel, &idx);
            if (kind == R_STOCK) { launch(STOCK[idx].task); return -1; }
            if (kind == R_TIMING) { S.state = ST_TIMING; S.ttop = 0; redraw(); continue; }
            B->keep = KEEP_TAG | (uint32_t)S.top << 8 | (uint32_t)S.sel;
            start(&B->list[idx]);
            if (S.state == ST_RUN) return 0;
        }
    }
    return 0;
}

/* ---- Timing screen (build 57): the latest start in the timing log (timing.c), times from that start ---- */
#define TL       ((volatile uint32_t *)0x0309F7CCu)   /* build 58 layout (timing.c) */
#define TL_N     11u
static void timing_paint(void)
{
    volatile uint32_t *t = TL;
    uint32_t cnt = t[0] & 0xFFFF, boot = t[1] & 0x3FFFFFFF;
    if (t[0] >> 16 != 0x544C || !cnt) { say(12, 64, C_INK, "No log yet", 0, 0, 0, 0, 0); return; }
    uint32_t n = cnt < TL_N ? cnt : TL_N, first = cnt - n;    /* events first .. cnt - 1 are in the ring */
    #define EV_T(k)   (t[2 + (k) % TL_N] & 0xFFFFF)
    #define EV_TAG(k) ((t[2 + (k) % TL_N] >> 20) & 0xF)
    #define EV_ARG(k) (t[2 + (k) % TL_N] >> 24)
    uint32_t s = first, k;                    /* latest start: a track step or the switch to Now Playing (screen 3) */
    for (k = cnt; k-- > first; ) if (EV_TAG(k) == 7 || (EV_TAG(k) == 1 && EV_ARG(k) == 3)) { s = k; break; }
    uint32_t t0 = EV_T(s), snd = 0;                           /* times: stock's 10 ms tick */
    for (k = s; k < cnt; k++) if (EV_TAG(k) == 6) { snd = ((EV_T(k) - t0) & 0xFFFFF) * 10u + 1; break; }
    int y = 64;
    if (boot) say(12, y, C_INK, "Boot to menu %1 s", boot / 10u, 0, 0, 0, 0);
    y += 22;
    if (snd) say(12, y, C_INK, "Start to sound %d ms", snd - 1, 0, 0, 0, 0);
    else say(12, y, C_DIM, "No sound after the last start", 0, 0, 0, 0, 0);
    y += 22;
    if (S.ttop > (int)(cnt - s) - 1) S.ttop = (int)(cnt - s) - 1;
    for (k = s + (uint32_t)S.ttop; k < cnt && y < 200; k++, y += 22) {
        uint32_t ms = ((EV_T(k) - t0) & 0xFFFFF) * 10u, a = EV_ARG(k);
        switch (EV_TAG(k)) {
        case 1: say(12, y, C_INK, "%d  Screen %d", ms, a, 0, 0, 0); break;
        case 2: say(12, y, C_INK, "%d  Load %d", ms, a & 0xFF, 0, 0, 0); break;
        case 3: say(12, y, C_INK, "%d  Music init", ms, 0, 0, 0, 0); break;
        case 4: say(12, y, C_INK, "%d  Audio start", ms, 0, 0, 0, 0); break;
        case 6: say(12, y, C_INK, "%d  First sound", ms, 0, 0, 0, 0); break;
        case 7: say(12, y, C_INK, "%d  Track step", ms, 0, 0, 0, 0); break;
        default: say(12, y, C_DIM, "%d  ?", ms, 0, 0, 0, 0); break;
        }
    }
    say(12, 200, C_DIM, "ms from the start, 10 ms steps", 0, 0, 0, 0, 0);
}

static void paint(void)
{
    if (!GetMsg(MSG_DRAW) && !S.dirty) return;
    S.dirty = 0;
    if (S.state == ST_RUN || S.state == ST_QUIT) return;
    uint16_t old = COLOR;
    fill(0, 0, 295, 32, C_WHITE);
    fill(0, 33, 295, 34, C_INK);
    fill(0, 35, 295, 58, C_HEAD);
    fill(0, 59, 295, 60, C_INK);
    fill(0, 221, 295, 222, C_INK);
    fill(0, 223, 295, 239, C_SCREEN);
    say(12, 39, C_INK, S.state == ST_TIMING ? "Timing" : "Games", 0, 0, 0, 0, 0);
    for (int r = 0; r < ROWS; r++) fill(0, 61 + r * 23, 295, 61 + r * 23 + 22, C_WHITE);
    if (S.state == ST_TIMING) { timing_paint(); COLOR = old; return; }
    if (S.state == ST_ERR) {
        if (S.err == 100) say(12, 64, C_INK, "Game Boy Color only", 0, 0, 0, 0, 0);
        else if (S.err == 101) say(12, 64, C_INK, "Over 2 MB", 0, 0, 0, 0, 0);
        else say(12, 64, C_INK, "Error %d", S.err, 0, 0, 0, 0);
        COLOR = old; return;
    }
    int count = row_count();
    for (int r = 0; r < ROWS; r++) {
        int i = S.top + r, y = 61 + r * 23, idx = 0, kind = i < count ? row_kind(i, &idx) : -1;
        int head = kind == R_HEAD_EMU || kind == R_HEAD_BUILTIN, on = i == S.sel && !head && kind >= 0;
        fill(0, y, 295, y + 21, head ? C_HEAD : on ? C_TINT : C_WHITE);
        if (on) fill(0, y, 3, y + 21, C_GRAPE);
        fill(0, y + 22, 295, y + 22, r == ROWS - 1 ? C_WHITE : C_TRACK);
        if (kind == R_HEAD_EMU) say(12, y + 3, C_DIM, "Emu", 0, 0, 0, 0, 0);
        else if (kind == R_HEAD_BUILTIN) say(12, y + 3, C_DIM, "Built-in", 0, 0, 0, 0, 0);
        else if (kind == R_MSG) say(12, y + 3, C_DIM, S.emsg, 0, 0, 0, 0, 0);
        else if (kind == R_STOCK) say(12, y + 3, C_INK, STOCK[idx].name, 0, 0, 0, 0, 0);
        else if (kind == R_TIMING) say(12, y + 3, C_INK, "Timing", 0, 0, 0, 0, 0);
        else if (kind == R_ROM) {
            const rom_t *rm = &B->list[idx];
            uint16_t t[EX_NAME + 1];
            for (int c = 0; c < rm->nlen; c++) t[c] = rm->name[c];
            t[rm->nlen] = 0;
            text(12, y + 3, t, rm->cgb == 0xC0 ? C_DIM : C_INK, 290);
        }
    }
    COLOR = old;
}

__attribute__((section(".desc"), used))
const win_desc_t gb_desc = { 0, 0, tick, service, paint, init, deinit };
