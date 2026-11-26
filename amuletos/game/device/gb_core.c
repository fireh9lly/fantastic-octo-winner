/* Game Boy probe core (build 41), portable: Peanut-GB (game/third_party/peanut_gb, MIT) plus a ROM page cache and
 * the screen palette. The device screen (gbprobe.c) and the host test (game/test/test_gb.c) supply:
 *   void gbx_read_page(gbx_t *x, uint32_t page, uint8_t *dst)   - one page of ROM from the SD card / a file
 *   void gbx_line(const uint16_t *rgb, int line)                 - one finished 160-pixel line, RGB565
 *
 * Memory: the AP30 has no heap and almost no free RAM. The whole gbx_t and the page buffers live at fixed
 * addresses chosen by the caller (device: the library builder's region, docs/HARDWARE.md "Game Boy probe").
 * ROM: games are 32 KB..2 MB and cannot be held in RAM, so ROM is read in pages on demand into however many page
 * buffers fit, replaced by the clock (second chance) rule. 1 KB pages (two sectors): on the owner's 512 KB..1 MB
 * games 52 x 1 KB gave 1.6-6.7 page loads per second of play (worst second 23-67), against 106 / s (worst 718)
 * for 13 x 4 KB in the same memory (game/test/test_gb.c, 2026-11-13).
 * Cartridge RAM (build 54): taken from the same page buffers, 1 KB at a time, only when the game first writes a
 * page (unwritten cartridge RAM reads 0xFF, as a blank save; no saves yet). Build 53 reserved all of it up front:
 * Pokemon's 32 KB left 11 of the AP30's 43 pages for 1 MB of ROM, 175+ page loads a second, stutter (owner). */
#include <stdint.h>

#define ENABLE_LCD   1
#define PEANUT_GB_IS_LITTLE_ENDIAN 1
/* Sound (build 50): GBX_SOUND = output rate. minigb_apu (game/third_party/minigb_apu, MIT) renders one frame's worth
 * of samples from the sound registers (gbx_audio(): AUDIO_SAMPLES stereo int16 = 803 at 48 kHz). */
#ifdef GBX_SOUND
#define ENABLE_SOUND 1
#define MINIGB_APU_AUDIO_FORMAT_S16SYS
#define AUDIO_SAMPLE_RATE GBX_SOUND
#include "../third_party/minigb_apu/minigb_apu.h"
static struct minigb_apu_ctx *gbx_apu;
uint8_t audio_read(const uint16_t addr) { return minigb_apu_audio_read(gbx_apu, addr); }
void audio_write(const uint16_t addr, const uint8_t val) { minigb_apu_audio_write(gbx_apu, addr, val); }
#include "../third_party/minigb_apu/minigb_apu.c"
#else
#define ENABLE_SOUND 0
#endif
#include "../third_party/peanut_gb/peanut_gb.h"

#ifndef PG_SHIFT
#define PG_SHIFT  10
#endif
#define PG_SIZE   (1u << PG_SHIFT)
#define PG_MAP    ((2u << 20) >> PG_SHIFT)   /* 2 MB of ROM */
#ifndef PG_SLOTS
#define PG_SLOTS  96                 /* slot index + 1 must fit map[]'s u8 */
#endif
#define GBX_CRAM_MAX   0x8000u                       /* bigger cartridge RAM: not in the probe */
#define GBX_CRAM_PAGES (GBX_CRAM_MAX >> PG_SHIFT)
#define GBX_ROM_MIN    8                             /* slots always left for ROM */
#define GBX_ERR_RAM    0x40                          /* err: cartridge RAM writes left too few ROM slots */
#define OWN_FREE       0xFFFF
#define OWN_CRAM       0xFFFE

typedef struct gbx_s {
    struct gb_s gb;                  /* first: the Peanut callbacks get this pointer */
    uint8_t  map[PG_MAP];            /* ROM page -> slot + 1; 0 = not loaded */
    uint16_t owner[PG_SLOTS];        /* slot -> ROM page; 0xFFFF = empty */
    uint8_t  used[PG_SLOTS];
    uint8_t *slot[PG_SLOTS];
    uint32_t nslots, hand, npages;
    uint8_t *cpage[GBX_CRAM_PAGES];  /* cartridge RAM, per 1 KB page: a slot once written, else 0 (reads 0xFF) */
    uint32_t cram_len, cram_pages;   /* size (up to 32 KB), pages taken */
    uint32_t misses;                 /* page loads since the last reset of the counter */
    int32_t  err;                    /* last Peanut error + 1; 0 = none */
    uint32_t err_addr;
    uint16_t pal[4];
    uint16_t line[LCD_WIDTH];
#ifdef GBX_SOUND
    struct minigb_apu_ctx apu;
#endif
} gbx_t;

void gbx_read_page(gbx_t *x, uint32_t page, uint8_t *dst);
void gbx_line(const uint16_t *rgb, int line);

static uint32_t gbx_victim(gbx_t *x)                 /* a slot for new use; its ROM page (if any) is dropped */
{
    uint32_t h;
    for (;;) {                                       /* clock: skip (and clear) recently used pages once */
        h = x->hand;
        x->hand = h + 1 == x->nslots ? 0 : h + 1;
        if (x->owner[h] == OWN_CRAM) continue;       /* cartridge RAM stays */
        if (x->owner[h] != OWN_FREE && x->used[h]) { x->used[h] = 0; continue; }
        break;
    }
    if (x->owner[h] != OWN_FREE) x->map[x->owner[h]] = 0;
    return h;
}

static uint32_t gbx_miss(gbx_t *x, uint32_t p)
{
    uint32_t h = gbx_victim(x);
    gbx_read_page(x, p, x->slot[h]);
    x->owner[h] = (uint16_t)p;
    x->map[p] = (uint8_t)(h + 1);
    x->misses++;
    return h + 1;
}

static uint8_t gbx_rom_read(struct gb_s *gb, const uint_fast32_t addr)
{
    gbx_t *x = (gbx_t *)gb;
    uint32_t p = (uint32_t)addr >> PG_SHIFT;
    if (p >= x->npages) return 0xFF;
    uint32_t s = x->map[p];
    if (!s) s = gbx_miss(x, p);
    x->used[s - 1] = 1;
    return x->slot[s - 1][addr & (PG_SIZE - 1)];
}

static uint8_t gbx_cram_read(struct gb_s *gb, const uint_fast32_t addr)
{
    gbx_t *x = (gbx_t *)gb;
    if (addr >= x->cram_len) return 0xFF;
    const uint8_t *pg = x->cpage[addr >> PG_SHIFT];
    return pg ? pg[addr & (PG_SIZE - 1)] : 0xFF;
}

static void gbx_cram_write(struct gb_s *gb, const uint_fast32_t addr, const uint8_t val)
{
    gbx_t *x = (gbx_t *)gb;
    if (addr >= x->cram_len) return;
    uint8_t *pg = x->cpage[addr >> PG_SHIFT];
    if (!pg) {
        if (val == 0xFF) return;                     /* already reads 0xFF */
        if (x->nslots - x->cram_pages <= GBX_ROM_MIN) { x->err = GBX_ERR_RAM; return; }
        uint32_t h = gbx_victim(x);
        x->owner[h] = OWN_CRAM;
        pg = x->slot[h];
        for (uint32_t i = 0; i < PG_SIZE; i++) pg[i] = 0xFF;
        x->cpage[addr >> PG_SHIFT] = pg;
        x->cram_pages++;
    }
    pg[addr & (PG_SIZE - 1)] = val;
}

static void gbx_error(struct gb_s *gb, const enum gb_error_e e, const uint16_t addr)
{
    gbx_t *x = (gbx_t *)gb;
    x->err = (int32_t)e + 1;
    x->err_addr = addr;
}

static void gbx_draw_line(struct gb_s *gb, const uint8_t *px, const uint_fast8_t line)
{
    gbx_t *x = (gbx_t *)gb;
    for (int i = 0; i < LCD_WIDTH; i++) x->line[i] = x->pal[px[i] & 3];
    gbx_line(x->line, line);
}

/* Set up for a ROM of rom_len bytes with the given page buffers (each PG_SIZE bytes). Returns 0 or the Peanut
 * init error + 1. Cartridge RAM: set cram_len after this (gbx_save_size, at most GBX_CRAM_MAX); pages come lazily. */
static int gbx_init(gbx_t *x, uint32_t rom_len, uint8_t **pages, uint32_t npg)
{
    uint8_t *p = (uint8_t *)x;
    for (uint32_t i = 0; i < sizeof *x; i++) p[i] = 0;
    x->npages = (rom_len + PG_SIZE - 1) >> PG_SHIFT;
    if (x->npages > PG_MAP) x->npages = PG_MAP;
    if (npg > PG_SLOTS) npg = PG_SLOTS;
    x->nslots = npg;
    for (uint32_t i = 0; i < npg; i++) { x->slot[i] = pages[i]; x->owner[i] = OWN_FREE; }
    /* Pocket-look greys: screen white, two inks, ink (art/pocket.py) */
    x->pal[0] = 0xFFDF; x->pal[1] = 0xAD55; x->pal[2] = 0x52CD; x->pal[3] = 0x2125;
    enum gb_init_error_e r = gb_init(&x->gb, gbx_rom_read, gbx_cram_read, gbx_cram_write, gbx_error, 0);
    if (r != GB_INIT_NO_ERROR) return (int)r + 1;
    gb_init_lcd(&x->gb, gbx_draw_line);
    x->gb.direct.joypad = 0xFF;
#ifdef GBX_SOUND
    gbx_apu = &x->apu;
    minigb_apu_audio_init(&x->apu);
#endif
    return 0;
}

#ifdef GBX_SOUND
/* One frame of sound: AUDIO_SAMPLES_TOTAL int16, left / right interleaved. */
static void gbx_audio(gbx_t *x, int16_t *out) { minigb_apu_audio_callback(&x->apu, out); }
#endif

static uint32_t gbx_save_size(gbx_t *x)
{
    size_t n = 0;
    if (gb_get_save_size_s(&x->gb, &n) != 0) return 0;
    return (uint32_t)n;
}
