/* PC preview of the Now Playing hooks (game/device/npui.c): stock's drawing calls emulated on a 296x240
 * RGB565 buffer with the device fonts, over a background prepared by art/np_preview.py.
 *   np_preview BG.raw FONT0 FONT1 OUT.raw "title" "artist" "album" pos_s total_s n total
 * Writes three frames (title scroll at 0 s, 3 s, 6 s) as raw RGB565. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NPUI_HOST
static uint16_t fb[240][296], color_, spacing_ = 0;
static uint8_t *font0, *font1;
static int fontsel = 2;
static uint32_t tick_, play_[2], scroll_[3];
static uint16_t title_[80], fname_[80];
static int wx0, wy0, wx1, wy1, wx, wy;

#define COLOR      color_
#define SPACING    spacing_
#define FONTBASE   0u
#define TICK       tick_
#define PLAY       play_
#define TITLE      title_
#define FNAME      fname_
#define SCROLL     scroll_
static void SetFont(uint32_t n) { fontsel = (int)n; }
static void put(int x, int y, uint16_t c) { if (x >= 0 && x < 296 && y >= 0 && y < 240) fb[y][x] = c; }
static void Fill(int x0, int y0, int x1, int y1) { for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) put(x, y, color_); }
static void Window(int x0, int y0, int x1, int y1) { wx0 = x0; wy0 = y0; wx1 = x1; wy1 = y1; wx = x0; wy = y0; }
static void Pixel(uint32_t c) { put(wx, wy, (uint16_t)c); if (++wx > wx1) { wx = wx0; wy++; } }
static uint32_t CharW(uint32_t ch)
{
    /* stock 0x03063BC6: adv byte > 0x80 -> byte - 0x80, otherwise the font's default (6 / 8, CJK full width) */
    uint8_t b = fontsel == 1 ? font0[ch * 32 + 24] : font1[ch * 33 + 32];
    if (b > 0x80) return b - 0x80;
    return ch >= 0x2E80 ? (fontsel == 1 ? 12 : 16) : (fontsel == 1 ? 6 : 8);
}
static void FontRead(uint32_t off, void *b, uint32_t n) { memcpy(b, font1 + off, n); }
static void glyph(int x, int y, uint32_t ch, int x1)
{
    int rows = fontsel == 1 ? 12 : 16, rec = fontsel == 1 ? 32 : 33;
    const uint8_t *g = (fontsel == 1 ? font0 : font1) + ch * rec;
    for (int r = 0; r < rows; r++) {
        uint32_t v = g[2 * r] << 8 | g[2 * r + 1];
        for (int c = 0; c < 16; c++) if ((v & (0x8000 >> c)) && x + c <= x1) put(x + c, y + r, color_);
    }
}
static void Text(int x, int y, const uint16_t *s) { for (; *s; s++) { glyph(x, y, *s, 295); x += CharW(*s) + spacing_; } }
typedef struct { uint16_t x0, y0, x1, y1; } rect_t_;
#define Draw(r, s, m) draw_((r)->x0, (r)->y0, (r)->x1, s)
static void draw_(int x, int y, int x1, const uint16_t *s) { for (; *s && x <= x1; s++) { glyph(x, y, *s, x1); x += CharW(*s) + spacing_; } }
static int scroll_msg;
static void Post(uint32_t m) { scroll_msg = 1; }
static void Clear(uint32_t m) { scroll_msg = 0; }
#include "../device/npui.c"

static void u16s(uint16_t *d, const char *s) { while (*s) *d++ = (uint8_t)*s++; *d = 0; }
static uint8_t *load(const char *p, long *n)
{
    FILE *f = fopen(p, "rb"); if (!f) { perror(p); exit(1); }
    fseek(f, 0, SEEK_END); long z = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *b = malloc(z); fread(b, 1, z, f); fclose(f); if (n) *n = z; return b;
}

int main(int argc, char **argv)
{
    if (argc < 12) { fprintf(stderr, "usage: see source\n"); return 2; }
    long n; uint8_t *bg = load(argv[1], &n);
    font0 = load(argv[2], 0); font1 = load(argv[3], 0);
    FILE *out = fopen(argv[4], "wb");
    u16s(title_, argv[5]); u16s(fname_, "05 Scars of Time.flac");
    uint16_t artist[80], album[80]; u16s(artist, argv[6]); u16s(album, argv[7]);
    uint32_t pos = atoi(argv[8]), tot = atoi(argv[9]);
    memcpy(fb, bg, sizeof fb);
    play_[0] = tot * 1000; play_[1] = pos * 1000;
    rect_t r = {168, 91, 296, 106};
    if (artist[0]) np_artist(&r, &r, artist, 2); else np_clear_artist();
    np_album(&r, &r, album, 2);
    np_count(atoi(argv[10]), atoi(argv[11]));
    np_progress();
    np_time(pos / 3600, pos / 60 % 60, pos % 60, 0);
    tick_ = 1000;
    np_title_new();
    fwrite(fb, sizeof fb, 1, out);
    for (int k = 1; k <= 2; k++) {
        tick_ = 1000 + 300 * k;
        if (scroll_msg) np_title_step(0);
        fwrite(fb, sizeof fb, 1, out);
    }
    fclose(out);
    printf("scroll %s, width %u\n", scroll_msg ? "on" : "off", scroll_[1]);
    return 0;
}
