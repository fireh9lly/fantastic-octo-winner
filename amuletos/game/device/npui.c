/* amuletOS Now Playing, layout A (v0.3): drawing hooks for stock's Now Playing (module 27).
 *
 * Stock keeps all behaviour (keys, track changes, cover decode into the framebuffer at (17, 46), its
 * redraw messages); these functions replace what it draws in the right panel, the bottom band and the
 * status bar. Code-only overlay in module slot 28, run address 0x030843DC, at most 0x758 B (free while Now
 * Playing runs: module 27 ends there, module 18 starts at 0x03084b34; modules 9 and 12 there are USB only), loaded by np_load (slot 2) at the end of
 * module 27's init. No data or ZI: stack only; the title scroll state lives at SCROLL (RAM above slot 2).
 * Layout (owner, option A): art/np_options.py; Pocket frames: art/pocket.py now_playing(); patches: tools/patch_code.py np_v4. */
#include <stdint.h>

typedef struct { uint16_t x0, y0, x1, y1; } rect_t;

#define RGB(h) ((uint16_t)((((h) >> 19) & 0x1F) << 11 | (((h) >> 10) & 0x3F) << 5 | (((h) >> 3) & 0x1F)))
/* colours: theme.h (art/orange.py now_playing() draws the frames these sit in) */
#include "theme.h"
#define C_PANEL  RGB(TH_PANEL)     /* frame fill */
#define C_BAND   RGB(TH_BAND)      /* status band (track counter) */
#define C_TEXT   RGB(TH_TEXT)
#define C_ACCENT RGB(TH_ACCENT)    /* artist, bar fill */
#define C_TRACK  RGB(TH_TRACK)

/* layout (screen pixels): right frame fill x 148..281 / y 44..163, bottom frame fill x 23..272 / y 174..227;
 * frames have 8 px rounded corners (art/pocket.py R_NP), so fills stay 6 px clear of the frame corners */
#define RX0 154            /* right panel text */
#define RX1 278
#define ARTIST_Y 50
#define ALBUM_Y  96
#define LINE_GAP 20
#define TX0 29             /* title band, double size: TX1 - TX0 + 1 must be even */
#define TX1 266
#define TY0 176
#define TH  32
#define BAR_X0 79          /* progress bar; room each side for "-1:05:01" */
#define BAR_X1 216
#define BAR_Y  215         /* 4 px track; playhead 4 x 12 from BAR_Y - 4 */
#define TIME_Y 211
#define COUNT_X 22         /* status bar track counter, clear of the rounded corner */
#define COUNT_Y 9
#define TSPACE 5           /* space in the big title (single-size px; the font's 8 doubles too wide) */
#define GAP_S 24           /* scroll loop gap (single-size px) */
#define MAXC 64

#ifndef NPUI_HOST          /* game/pc/np_preview.c supplies these on the PC */
#define COLOR      (*(volatile uint16_t *)0x03024E2Cu)
#define SPACING    (*(volatile int16_t *)0x03024E44u)      /* 0x03024E2C + 0x18: letter spacing stock adds */
#define FONTBASE   (*(volatile uint32_t *)0x030248a8u)
#define TICK       (*(volatile uint32_t *)0x030248CCu)     /* 10 ms */
#define PLAY       (*(volatile uint32_t **)0x0304A460u)    /* [0] total ms, [1] position ms */
#define TITLE      ((const uint16_t *)0x0304A670u)          /* tag record +0x60 */
#define FNAME      ((const uint16_t *)0x0304a4e0u)          /* file name */
#define SCROLL     ((volatile uint32_t *)0x0309FFD8u)      /* [0] start tick, [1] width (single px), [2] magic */
#define SetFont(n)     ((void (*)(uint32_t))(0x0306467Eu | 1))(n)
#define Fill(a, b, c, d) ((void (*)(int, int, int, int))(0x03064964u | 1))(a, b, c, d)
#define Window(a, b, c, d) ((void (*)(int, int, int, int))(0x03065184u | 1))(a, b, c, d)
#define Pixel(c)       ((void (*)(uint32_t))(0x030650A0u | 1))(c)
#define Text(x, y, s)  ((void (*)(int, int, const uint16_t *))(0x03064114u | 1))(x, y, s)
#define Draw(r, s, m)  ((void (*)(rect_t *, rect_t *, const uint16_t *, uint32_t))(0x03064252u | 1))(r, r, s, m)
#define CharW(ch)      ((uint32_t (*)(uint32_t))(0x03063EA2u | 1))(ch)
#define FontRead(o, b, n) ((void (*)(uint32_t, void *, uint32_t))(0x03065638u | 1))(o, b, n)
#define Post(m)        ((void (*)(uint32_t))(0x030681F0u | 1))(m)
#define Clear(m)       ((void (*)(uint32_t))(0x03068232u | 1))(m)
#endif
#define MSG_SCROLL 0x44

static void fill(int x0, int y0, int x1, int y1, uint16_t c) { COLOR = c; Fill(x0, y0, x1, y1); }

static int textw(const uint16_t *s)
{
    int w = 0;
    for (; *s; s++) w += (int)CharW(*s) + SPACING;
    return w;
}

/* ---------- right panel: artist (2 lines) / album (3 lines), wrapped at spaces ---------- */
static void wrapn(int y, const uint16_t *s, uint16_t col, uint32_t mode, int lines)
{
    fill(RX0, y, RX1, y + lines * LINE_GAP - 3, C_PANEL);
    rect_t r = { RX0, y, RX1, y + 17 };
    const int w = RX1 - RX0;
    uint16_t buf[MAXC + 2];
    COLOR = col;
    SetFont(2);
    for (int ln = 0; ln < lines && *s; ln++, r.y0 += LINE_GAP, r.y1 += LINE_GAP) {
        int n = 0, cut = 0, next = 0;
        while (n < MAXC && s[n]) n++;
        for (int i = 0; i < n; i++) buf[i] = s[i];
        buf[n] = 0;
        if (ln == lines - 1 || textw(buf) <= w) { Draw(&r, buf, mode); return; }   /* last line clips */
        for (int i = 1; i < n; i++) {                     /* last space whose prefix fits */
            if (s[i] != ' ') continue;
            buf[i] = 0;
            if (textw(buf) > w) break;
            cut = i; next = i + 1; buf[i] = ' ';
        }
        if (!cut)                                         /* no space fits: split inside the word */
            for (cut = 1; cut < n; cut++) { buf[cut] = 0; if (textw(buf) > w) break; buf[cut] = s[cut]; }
        if (!next) next = --cut > 0 ? cut : (cut = 1);
        buf[cut] = 0;
        Draw(&r, buf, mode);
        s += next;
    }
}

/* replace stock's info-box draws (line 1 artist, line 3 album); stock's rect is ignored */
void np_artist(rect_t *r, rect_t *r2, const uint16_t *s, uint32_t mode) { wrapn(ARTIST_Y, s, C_ACCENT, mode, 2); }
void np_album(rect_t *r, rect_t *r2, const uint16_t *s, uint32_t mode)  { wrapn(ALBUM_Y, s, C_TEXT, mode, 3); }
void np_clear_artist(void) { fill(RX0, ARTIST_Y, RX1, ARTIST_Y + 2 * LINE_GAP - 3, C_PANEL); }
/* replaces stock's three 128 px line clears (image 69 at x 168, y 91/112/133): they ran past the panel's right
 * border (white bars on the frame, owner build 33); clear just the panel's text area, so an empty album still
 * erases the previous one */
void np_clear_info(void) { fill(RX0, ARTIST_Y, RX1, ALBUM_Y + 3 * LINE_GAP - 3, C_PANEL); }

/* ---------- small numbers: track counter, times ---------- */
static uint16_t *put_num(uint16_t *p, uint32_t v, int min_digits)
{
    uint16_t t[10]; int n = 0;
    do { t[n++] = '0' + v % 10; v /= 10; } while (v || n < min_digits);
    while (n) *p++ = t[--n];
    return p;
}

static uint16_t *put_time(uint16_t *p, uint32_t s)
{
    if (s >= 3600) { p = put_num(p, s / 3600, 1); *p++ = ':'; p = put_num(p, s / 60 % 60, 2); }
    else p = put_num(p, s / 60, 1);
    *p++ = ':';
    return put_num(p, s % 60, 2);
}

/* replaces stock's "0003/0022" at (40, 10) */
void np_count(uint32_t n, uint32_t total)
{
    uint16_t s[24], *p = put_num(s, n, 1);
    *p++ = '/'; p = put_num(p, total, 1); *p = 0;
    fill(COUNT_X, COUNT_Y, 102, COUNT_Y + 16, C_BAND);
    SetFont(2);
    COLOR = C_TEXT;
    Text(COUNT_X, COUNT_Y, s);
}

/* replaces stock's time draw (h, m, s, kind 0 = position, 1 = length): position left, remaining right */
void np_time(uint32_t h, uint32_t m, uint32_t s, uint32_t kind)
{
    uint32_t *P = PLAY;
    uint32_t tot = P ? P[0] / 1000 : 0;
    uint32_t pos = kind == 0 ? h * 3600 + m * 60 + s : (P ? P[1] / 1000 : 0);
    if (pos > tot) pos = tot;
    uint16_t a[12], b[12], *p;
    p = put_time(a, pos); *p = 0;
    b[0] = '-'; p = put_time(b + 1, tot - pos); *p = 0;
    SetFont(1);
    fill(TX0, TIME_Y, BAR_X0 - 4, TIME_Y + 13, C_PANEL);
    fill(BAR_X1 + 4, TIME_Y, TX1, TIME_Y + 13, C_PANEL);
    COLOR = C_TEXT;
    Text(TX0 + 2, TIME_Y, a);
    Text(TX1 - textw(b), TIME_Y, b);
    SetFont(2);
}

/* replaces stock's progress bar (images 0x62/0x63 columns, playhead 0x124/0x125) */
void np_progress(void)
{
    uint32_t *P = PLAY;
    uint32_t tot = P ? P[0] : 0, pos = P ? P[1] : 0;
    int w = BAR_X1 - BAR_X0;
    if (pos > tot) pos = tot;
    int px = tot >= 16 ? (int)((pos >> 4) * (uint32_t)w / (tot >> 4)) : 0;   /* 32-bit: tracks up to ~5 h */
    fill(BAR_X0 - 2, BAR_Y - 4, BAR_X1 + 2, BAR_Y + 7, C_PANEL);    /* old playhead */
    fill(BAR_X0, BAR_Y, BAR_X1, BAR_Y + 3, C_TRACK);
    if (px > 0) fill(BAR_X0, BAR_Y, BAR_X0 + px - 1, BAR_Y + 3, C_ACCENT);
    fill(BAR_X0 + px - 2, BAR_Y - 4, BAR_X0 + px + 1, BAR_Y + 7, C_TEXT);
}

/* ---------- title: double size, scrolling when wider than the band ---------- */
static int title_text(uint16_t *t)
{
    const uint16_t *s = TITLE[0] ? TITLE : FNAME;
    int n = 0, dot = -1;
    while (n < MAXC && s[n]) { t[n] = s[n]; if (s[n] == '.') dot = n; n++; }
    if (s == FNAME && dot > 0) n = dot;                  /* file name without its extension (owner) */
    t[n] = 0;
    return n;
}

/* draw the band with the text scrolled by off (single-size px) */
static void title_draw(const uint16_t *t, int n, uint32_t off, uint32_t loop)
{
    enum { BW = (TX1 - TX0 + 1) / 2 };                   /* band width in single-size px */
    uint16_t rows[16][(BW + 15) / 16 + 1];
    for (int r = 0; r < 16; r++) for (unsigned k = 0; k < sizeof rows[0] / 2; k++) rows[r][k] = 0;
    SetFont(2);
    uint32_t base = FONTBASE;
    for (int copy = 0; copy < (loop ? 2 : 1); copy++) {
        int x = (int)(copy * loop) - (int)off;
        for (int i = 0; i < n && x < BW; i++) {
            int w = t[i] == ' ' ? TSPACE : (int)CharW(t[i]) + SPACING;
            if (x + w > 0 && t[i] != ' ') {
                uint8_t g[32];
                FontRead(base + t[i] * 33u, g, 32);
                for (int r = 0; r < 16; r++) {
                    uint32_t v = (uint32_t)g[2 * r] << 8 | g[2 * r + 1];
                    for (int c = 0; c < 16 && v; c++, v = (v << 1) & 0xFFFF) {
                        int X = x + c;
                        if ((v & 0x8000) && X >= 0 && X < BW) rows[r][X >> 4] |= 0x8000 >> (X & 15);
                    }
                }
            }
            x += w;
        }
    }
    Window(TX0, TY0, TX0 + 2 * BW - 1, TY0 + TH - 1);
    for (int y = 0; y < TH; y++) {
        const uint16_t *row = rows[y >> 1];
        for (int X = 0; X < 2 * BW; X++)
            Pixel(row[X >> 5] & (0x8000 >> ((X >> 1) & 15)) ? C_TEXT : C_PANEL);
    }
}

/* new track (stock's title line, both modes): draw, and start scrolling if it does not fit */
void np_title_new(void)
{
    uint16_t t[MAXC + 1];
    int n = title_text(t);
    SetFont(2);
    int w = 0;
    for (int i = 0; i < n; i++) w += t[i] == ' ' ? TSPACE : (int)CharW(t[i]) + SPACING;
    SCROLL[0] = TICK; SCROLL[1] = (uint32_t)w; SCROLL[2] = 0x5C011;
    if (2 * w > TX1 - TX0 + 1) Post(MSG_SCROLL); else Clear(MSG_SCROLL);
    title_draw(t, n, 0, 0);
}

/* every paint while MSG_SCROLL is set (replaces stock's scroller step): 25 px/s after a 1.5 s pause */
void np_title_step(const uint16_t *unused)
{
    if (SCROLL[2] != 0x5C011) return;
    uint32_t loop = SCROLL[1] + GAP_S, dt = TICK - SCROLL[0];
    uint32_t off = dt < 150 ? 0 : ((dt - 150) / 4) % loop;
    uint16_t t[MAXC + 1];
    int n = title_text(t);
    title_draw(t, n, off, loop);
}
