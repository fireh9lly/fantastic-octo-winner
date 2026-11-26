/* amuletOS Blockz renderer. Layout (native px, screen 296x240):
 *   well 110x220 at (93,10), 11 px cells, framed
 *   left panels  x 10..85 : HOLD, TIME, LINES
 *   right panels x 210..285: NEXT, PIECES, PPS, BEST
 * Colours from art/zeal.py (theme "zeal"); background = sky blue diamonds as in the menus. */
#include "render.h"

#define RGB(h) ((uint16_t)(((((h) >> 16) & 0xFF) >> 3) << 11 | ((((h) >> 8) & 0xFF) >> 2) << 5 | (((h) & 0xFF) >> 3)))

#define C_BG1    0xacd2f4
#define C_BG2    0x8fbaec
#define C_PANEL  0xfffdf6
#define C_BORDER 0x283c88
#define C_TEXT   0x121a40
#define C_ACCENT 0xd9a02a
#define C_DIM    0x6a7cb0
#define C_WELL   0x121838
#define C_LAVINK 0x7d5bc9

/* guideline colours tuned toward the palette */
static const uint32_t PIECE[8] = {
    0, 0x4cc8e4 /* I */, 0xf0c440 /* O */, 0x9a6ad8 /* T */, 0x5cc06a /* S */,
    0xe0546a /* Z */, 0x4a6ad8 /* J */, 0xec9038 /* L */,
};

#define WELL_X 93
#define WELL_Y 10
#define CELL   11
#define LX     10
#define RX     210
#define PW     76

static uint16_t *FB; static int STRIDE; static bg_rcache_t *RC;
int bg_pause_volume = -1;

static uint32_t mixc(uint32_t a, uint32_t b, int k /* /16 */)
{
    uint32_t r = 0;
    for (int s = 0; s <= 16; s += 8) {
        int x = (int)((a >> s) & 0xFF), y = (int)((b >> s) & 0xFF);
        r |= (uint32_t)(x + (y - x) * k / 16) << s;
    }
    return r;
}

static void dirty(int x, int y, int w, int h)
{
    if (RC->x0 >= RC->x1) { RC->x0 = x; RC->y0 = y; RC->x1 = x + w; RC->y1 = y + h; return; }
    if (x < RC->x0) RC->x0 = x;
    if (y < RC->y0) RC->y0 = y;
    if (x + w > RC->x1) RC->x1 = x + w;
    if (y + h > RC->y1) RC->y1 = y + h;
}

#ifdef BG_FILL_EXTERN
/* device: every pixel goes through the platform's rectangle fill (stock FillRect) */
void bg_fill_rect(int x, int y, int w, int h, uint16_t rgb565);
#endif

static void fill(int x, int y, int w, int h, uint32_t c)
{
    uint16_t v = RGB(c);
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > BG_SCR_W) w = BG_SCR_W - x;
    if (y + h > BG_SCR_H) h = BG_SCR_H - y;
    if (w <= 0 || h <= 0) return;
#ifdef BG_FILL_EXTERN
    bg_fill_rect(x, y, w, h, v);
#else
    for (int j = 0; j < h; j++) {
        uint16_t *p = FB + (y + j) * STRIDE + x;
        for (int i = 0; i < w; i++) p[i] = v;
    }
#endif
    dirty(x, y, w, h);
}

/* ---- font: original 5x7 glyphs from art/zeal.py, bit 4 = left column ---- */
static const char GCH[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .:-";
static const uint8_t GLY[][7] = {
    {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},{30,17,17,17,17,17,30},
    {31,16,16,30,16,16,31},{31,16,16,30,16,16,16},{14,17,16,23,17,17,15},{17,17,17,31,17,17,17},
    {14,4,4,4,4,4,14},{7,2,2,2,2,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
    {17,27,21,21,17,17,17},{17,17,25,21,19,17,17},{14,17,17,17,17,17,14},{30,17,17,30,16,16,16},
    {14,17,17,17,21,18,13},{30,17,17,30,20,18,17},{15,16,16,14,1,1,30},{31,4,4,4,4,4,4},
    {17,17,17,17,17,17,14},{17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
    {17,17,10,4,4,4,4},{31,1,2,4,8,16,31},
    {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},{31,2,4,2,1,17,14},
    {2,6,10,18,31,2,2},{31,16,30,1,1,17,14},{6,8,16,30,17,17,14},{31,1,2,4,8,8,8},
    {14,17,17,14,17,17,14},{14,17,17,15,1,2,12},
    {0,0,0,0,0,0,0},{0,0,0,0,0,12,12},{0,12,12,0,12,12,0},{0,0,0,14,0,0,0},
};

static int narrow(char c) { return c == '.' || c == ':'; }

static int text_w(const char *s)
{
    int w = 0;
    for (; *s; s++) w += narrow(*s) ? 6 : 12;
    return w ? w - 2 : 0;
}

/* scale 2, matching the 2x art grid */
static void text(int x, int y, const char *s, uint32_t c)
{
    for (; *s; s++) {
        int gi = 0;
        while (GCH[gi] && GCH[gi] != *s) gi++;
        if (!GCH[gi]) gi = 36;
        int ox = narrow(*s) ? x - 2 : x;
        for (int r = 0; r < 7; r++)
            for (int col = 0; col < 5; col++)
                if (GLY[gi][r] & (16 >> col)) fill(ox + col * 2, y + r * 2, 2, 2, c);
        x += narrow(*s) ? 6 : 12;
    }
}

static void text_c(int x, int w, int y, const char *s, uint32_t c) { text(x + (w - text_w(s)) / 2, y, s, c); }

/* ---- shapes ---- */
static int diamond_on(int x, int y)
{
    int ax = x >> 1, ay = y >> 1, tx = ax & 7, ty = ay & 7;
    int m2 = (tx * 2 - 7 < 0 ? 7 - tx * 2 : tx * 2 - 7) + (ty * 2 - 7 < 0 ? 7 - ty * 2 : ty * 2 - 7); /* 2*manhattan */
    return m2 <= 3 || (m2 >= 6 && m2 <= 7 && (((ax >> 3) + (ay >> 3)) & 1));
}

/* sky blue with the menu diamonds, as horizontal runs (2 px tall: the art grid is 2x) */
static void background(void)
{
    for (int y = 0; y < BG_SCR_H; y += 2) {
        int x0 = 0, on0 = diamond_on(0, y);
        for (int x = 2; x <= BG_SCR_W; x += 2) {
            int on = x < BG_SCR_W ? diamond_on(x, y) : !on0;
            if (on != on0) { fill(x0, y, x - x0, 2, on0 ? C_BG2 : C_BG1); x0 = x; on0 = on; }
        }
    }
}

/* framed panel with cut corners: 2 px edge */
static void panel(int x, int y, int w, int h, uint32_t edge, uint32_t fillc)
{
    fill(x + 2, y, w - 4, h, edge);
    fill(x, y + 2, w, h - 4, edge);
    fill(x + 1, y + 1, w - 2, h - 2, edge);
    fill(x + 2, y + 2, w - 4, h - 4, fillc);
}

static void well_frame(void)
{
    int x = WELL_X - 3, y = WELL_Y - 3, w = BG_W * CELL + 6, h = BG_VISIBLE * CELL + 6;
    fill(x + 1, y, w - 2, h, C_BORDER);
    fill(x, y + 1, w, h - 2, C_BORDER);
    fill(x + 2, y + 2, w - 4, h - 4, C_ACCENT);
}

static void block(int px, int py, uint8_t t)
{
    uint32_t b = PIECE[t], hi = mixc(b, 0xffffff, 8), lo = mixc(b, 0x000000, 6);
    fill(px, py, CELL, CELL, b);
    fill(px, py, CELL, 1, hi);
    fill(px, py, 1, CELL, hi);
    fill(px, py + CELL - 1, CELL, 1, lo);
    fill(px + CELL - 1, py, 1, CELL, lo);
    fill(px + 2, py + 2, 2, 1, hi);
    fill(px + 2, py + 3, 1, 1, hi);
}

static void empty_cell(int px, int py)
{
    fill(px, py, CELL, CELL, C_WELL);
    fill(px + 5, py + 5, 1, 1, mixc(C_WELL, C_DIM, 5));
}

static void ghost(int px, int py, uint8_t t)
{
    uint32_t c = PIECE[t];
    empty_cell(px, py);
    fill(px + 1, py + 1, CELL - 2, 1, c);
    fill(px + 1, py + CELL - 2, CELL - 2, 1, c);
    fill(px + 1, py + 1, 1, CELL - 2, c);
    fill(px + CELL - 2, py + 1, 1, CELL - 2, c);
}

static void cell(int r, int x, uint8_t v)
{
    int px = WELL_X + x * CELL, py = WELL_Y + r * CELL;
    if (!v) empty_cell(px, py);
    else if (v & 0x10) ghost(px, py, v & 7);
    else block(px, py, v & 7);
}

/* a piece centred in a box (HOLD / NEXT); dim = greyed (hold used) */
static void mini(int x, int y, int w, int h, uint8_t t, int dim, uint32_t bg)
{
    fill(x, y, w, h, bg);
    if (!t) return;
    int8_t m[4][2];
    bg_minos(t, 0, m);
    int minx = 9, maxx = -9, miny = 9, maxy = -9;
    for (int i = 0; i < 4; i++) {
        if (m[i][0] < minx) minx = m[i][0];
        if (m[i][0] > maxx) maxx = m[i][0];
        if (m[i][1] < miny) miny = m[i][1];
        if (m[i][1] > maxy) maxy = m[i][1];
    }
    int pw = (maxx - minx + 1) * CELL, ph = (maxy - miny + 1) * CELL;
    int ox = x + (w - pw) / 2, oy = y + (h - ph) / 2;
    for (int i = 0; i < 4; i++) {
        int px = ox + (m[i][0] - minx) * CELL, py = oy + (m[i][1] - miny) * CELL;
        if (dim) {
            uint32_t c = mixc(C_DIM, C_PANEL, 6);
            fill(px, py, CELL, CELL, c);
            fill(px, py + CELL - 1, CELL, 1, mixc(c, 0, 3));
            fill(px + CELL - 1, py, 1, CELL, mixc(c, 0, 3));
        } else block(px, py, t);
    }
}

/* ---- text helpers (no libc) ---- */
static char *put_u(char *p, uint32_t v, int digits)
{
    char tmp[10]; int n = 0;
    do { tmp[n++] = (char)('0' + v % 10); v /= 10; } while (v || n < digits);
    while (n) *p++ = tmp[--n];
    *p = 0;
    return p;
}

static void scpy(char *d, const char *s) { while ((*d++ = *s++) != 0) { } }

static void fmt_time(char *s, uint32_t frames, int none)
{
    if (none) { scpy(s, "-:--.--"); return; }
    uint32_t cs = frames * 100u / 60u;
    if (cs > 59999) cs = 59999;                  /* 9:59.99 */
    char *p = put_u(s, cs / 6000, 1);
    *p++ = ':'; p = put_u(p, cs / 100 % 60, 2);
    *p++ = '.'; put_u(p, cs % 100, 2);
}

static int streq(const char *a, const char *b) { while (*a && *a == *b) { a++; b++; } return *a == *b; }

/* value line of a panel: redraw only if the string changed */
static void value(int slot, int x, int y, const char *s, int full)
{
    if (!full && streq(RC->txt[slot], s)) return;
    scpy(RC->txt[slot], s);
    fill(x + 2, y, PW - 4, 14, C_PANEL);         /* whole inner width: m:ss.cc is 70 px */
    text_c(x, PW, y, s, C_TEXT);
}

/* ---- overlays inside the well ---- */
enum { OV_NONE, OV_READY, OV_GO, OV_PAUSE, OV_DONE, OV_FAIL };

static void overlay(const bg_game_t *g, int ov)
{
    int x = WELL_X + 4, w = BG_W * CELL - 8;
    char s[12];
    switch (ov) {
    case OV_READY: case OV_GO:
        panel(x, 96, w, 30, C_BORDER, C_PANEL);
        text_c(x, w, 104, ov == OV_READY ? "READY" : "GO", C_TEXT);
        break;
    case OV_PAUSE: {
        static const char *items[3] = { "RESUME", "RETRY", "QUIT" };
        int vh = bg_pause_volume >= 0 ? 18 : 0;
        panel(x, 66, w, 92 + vh, C_BORDER, C_PANEL);
        text_c(x, w, 74, "PAUSE", C_DIM);
        if (vh) {                                /* wheel adjusts it while paused */
            char *p = s; *p++ = 'V'; *p++ = 'O'; *p++ = 'L'; *p++ = ' ';
            put_u(p, (uint32_t)bg_pause_volume, 1);
            text_c(x, w, 152, s, C_DIM);
        }
        for (int i = 0; i < 3; i++) {
            int ty = 98 + i * 18;
            text(x + 22, ty, items[i], C_TEXT);
            if (i == g->pause_sel) {             /* arrow cursor */
                static const uint8_t AR[7] = {16, 24, 28, 30, 28, 24, 16};
                for (int r = 0; r < 7; r++)
                    for (int col = 0; col < 5; col++)
                        if (AR[r] & (16 >> col)) fill(x + 8 + col * 2, ty + r * 2, 2, 2, C_LAVINK);
            }
        }
        break;
    }
    case OV_DONE:
        panel(x, 44, w, 136, C_BORDER, C_PANEL);
        text_c(x, w, 52, "FINISH", C_DIM);
        fmt_time(s, g->time, 0);
        text_c(x, w, 70, s, C_TEXT);
        text_c(x, w, 94, "BEST", C_DIM);
        fmt_time(s, g->best, !g->best);
        text_c(x, w, 112, s, C_TEXT);
        fill(x + 8, 133, w - 16, 1, C_DIM);
        text_c(x, w, 140, "A RETRY", C_TEXT);
        text_c(x, w, 158, "B QUIT", C_TEXT);
        break;
    case OV_FAIL:
        panel(x, 62, w, 100, C_BORDER, C_PANEL);
        text_c(x, w, 70, "GAME", C_DIM);
        text_c(x, w, 88, "OVER", C_DIM);
        fill(x + 8, 111, w - 16, 1, C_DIM);
        text_c(x, w, 118, "A RETRY", C_TEXT);
        text_c(x, w, 136, "B QUIT", C_TEXT);
        break;
    }
}

int bg_render(const bg_game_t *g, uint16_t *fb, int stride, bg_rcache_t *rc)
{
    FB = fb; STRIDE = stride; RC = rc;
    rc->x0 = rc->x1 = 0; rc->y0 = rc->y1 = 0;
    int full = !rc->valid;

    if (full) {
        background();
        well_frame();
        panel(LX, 14, PW, 60, C_BORDER, C_PANEL);  text_c(LX, PW, 20, "HOLD", C_DIM);
        panel(LX, 80, PW, 40, C_BORDER, C_PANEL);  text_c(LX, PW, 84, "TIME", C_DIM);
        panel(LX, 126, PW, 40, C_BORDER, C_PANEL); text_c(LX, PW, 130, "LINES", C_DIM);
        panel(RX, 14, PW, 60, C_BORDER, C_PANEL);  text_c(RX, PW, 20, "NEXT", C_DIM);
        panel(RX, 80, PW, 40, C_BORDER, C_PANEL);  text_c(RX, PW, 84, "PIECES", C_DIM);
        panel(RX, 126, PW, 40, C_BORDER, C_PANEL); text_c(RX, PW, 130, "PPS", C_DIM);
        panel(RX, 172, PW, 40, C_BORDER, C_PANEL); text_c(RX, PW, 176, "BEST", C_DIM);
        rc->hold = rc->next = 0xFF;
        rc->overlay = 0xFF;
        rc->valid = 1;
    }

    /* overlay state */
    int ov = OV_NONE;
    if (g->state == ST_READY) ov = g->frame < g->cfg.ready_frames / 2 ? OV_READY : OV_GO;
    else if (g->state == ST_PAUSE) ov = OV_PAUSE;
    else if (g->state == ST_DONE) ov = OV_DONE;
    else if (g->state == ST_FAIL) ov = OV_FAIL;
    else if (g->state == ST_PLAY && g->time < 30 && !g->pieces) ov = OV_GO;   /* GO stays 0.5 s into play */

    int ov_changed = ov != rc->overlay ||
                     (ov == OV_PAUSE && (g->pause_sel != rc->sel || rc->vol != bg_pause_volume));
    if (ov_changed)                              /* cells under the old overlay redraw */
        for (int r = 0; r < BG_VISIBLE; r++) for (int x = 0; x < BG_W; x++) rc->view[r][x] = 0xFF;

    /* well cells */
    uint8_t v[BG_VISIBLE][BG_W];
    int changed = 0;
    bg_view(g, v);
    for (int r = 0; r < BG_VISIBLE; r++)
        for (int x = 0; x < BG_W; x++) {
            uint8_t c = v[r][x];
            if (c & 0x20) c &= 7;                /* active piece draws as a block */
            if (rc->view[r][x] != c) { rc->view[r][x] = c; cell(r, x, c); changed = 1; }
        }
    if (ov != OV_NONE && (changed || ov_changed)) overlay(g, ov);
    rc->overlay = (uint8_t)ov; rc->sel = g->pause_sel; rc->vol = (int16_t)bg_pause_volume;

    /* HOLD / NEXT */
    uint8_t nx = (g->state == ST_DONE) ? 0 : g->queue[0];
    if (g->hold != rc->hold || g->hold_used != rc->hold_dim) {
        rc->hold = g->hold; rc->hold_dim = g->hold_used;
        mini(LX + 4, 36, PW - 8, 34, g->hold, g->hold_used, C_PANEL);
    }
    if (nx != rc->next) { rc->next = nx; mini(RX + 4, 36, PW - 8, 34, nx, 0, C_PANEL); }

    /* values */
    char s[12];
    fmt_time(s, g->time, 0);                                value(0, LX, 102, s, full);
    put_u(s, g->lines >= g->cfg.goal_lines ? 0 : (uint32_t)(g->cfg.goal_lines - g->lines), 1);
                                                            value(1, LX, 148, s, full);
    put_u(s, g->pieces, 1);                                 value(2, RX, 102, s, full);
    {
        uint32_t pps = g->time ? (uint32_t)g->pieces * 6000u / g->time : 0;   /* x100 */
        char *p = put_u(s, pps / 100, 1); *p++ = '.'; put_u(p, pps % 100, 2);
    }                                                       value(3, RX, 148, s, full);
    fmt_time(s, g->best, !g->best);                         value(4, RX, 194, s, full);

    return rc->x1 > rc->x0;
}
