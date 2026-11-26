/* amuletOS Playlists screen (v0.3, build 35): module 86 (task 19, stock game slot nobody reaches), opened by the
 * Music menu's "Playlists" row (np_stub.S pl_menu_exit). Lists /_Playlists/*.m3u* on the SD card; A plays the
 * chosen playlist from track 1 in Now Playing; B goes back to the Music menu.
 *
 * Playing: resolve the entries (pl_core.c) into the slot-2 table (pl_table.h), point the music source record at
 * entry 1 the way the folder browser does (source 0x63 "files": folder cluster + file number), then
 * TaskSwitch(3) so Now Playing's own init starts the player. Next / Prev / track end then go through
 * np_helpers.c pl_step. docs/HARDWARE.md, "Now Playing keys". Plain labels only (owner). */
#include <stdint.h>
#include "../stock.h"
#include "pl_table.h"

#define PL_MAX PLT_MAX
#include "exfat.c"
#include "pl_core.c"

#define SYSC       0x03022894u
#define REC        0x03022F14u
#define PHAND      0x030232BCu
#define PDESC      0x030361A4u
#define ThreadRunning(h, d) STOCK_FN(0x03057C7C, uint32_t, uint32_t, uint32_t)(h, d)
#define ThreadStop(hp, d)   STOCK_FN(0x03057BD4, void, uint32_t, uint32_t)(hp, d)
#define DiskSwitch(n)       STOCK_FN(0x03058526, void, uint32_t)(n)
#define RecPrepare()        STOCK_FN(0x03055304, void, void)()
#define SetFont(n)          STOCK_FN(0x030643A2, uint32_t, uint32_t)(n)
#define CharW(c)            STOCK_FN(0x03063BC6, uint32_t, uint32_t)(c)
#define FontRead(o, b, n)   STOCK_FN(0x0306535C, void, uint32_t, void *, uint32_t)(o, b, n)
#define FONTBASE            (*(volatile uint32_t *)0x03022868u)
#define SPACING             (*(volatile int16_t *)0x03022E04u)
#define S8(o)   (*(volatile uint8_t *)(SYSC + (o)))
#define R16(o)  (*(volatile uint16_t *)(REC + (o)))
#define R32(o)  (*(volatile uint32_t *)(REC + (o)))

#define MSG_DRAW  0x186
#define EV_PRESS  0x40u
#define EV_REPEAT 0x30u
#define K_RIGHT 0x004
#define K_LEFT  0x008
#define K_UP    0x010
#define K_DOWN  0x020
#define K_B     0x040
#define K_A     0x080

/* Pocket list look (art/pocket.py list_bg / selection_bar), drawn with FillRect only: build 35 drew stock images
 * and text, which showed black with white text in this game-task window (Blockz also draws only with fills). */
#define C_INK    RGB565(0x23, 0x25, 0x2e)
#define C_DIM    RGB565(0x7d, 0x82, 0x91)
#define C_WHITE  RGB565(0xff, 0xff, 0xff)
#define C_HEAD   RGB565(0xf2, 0xf3, 0xf6)
#define C_TRACK  RGB565(0xdf, 0xe1, 0xe8)
#define C_SCREEN RGB565(0xfb, 0xfb, 0xf8)
#define C_TINT   RGB565(0xe9, 0xe3, 0xfb)
#define C_GRAPE  RGB565(0x73, 0x53, 0xe0)
#define ROW_Y   61
#define ROW_H   23
#define ROWS    7

enum { ST_LIST, ST_NOCARD, ST_NODIR, ST_EMPTY, ST_LOAD, ST_NOTRACKS, ST_QUIT };

static struct {
    uint8_t state, dirty;
    int sel, top;
} S;
static pl_list_t L;

static void a16(uint16_t *d, const char *s) { while ((*d++ = (uint8_t)*s++)) {} }

static void fill(int x0, int y0, int x1, int y1, uint16_t c) { COLOR = c; FillRect(x0, y0, x1, y1); }

/* the device's 16 px font (SetFont(2)) read straight from its bitmaps, drawn as horizontal runs; stops at x_max */
static void text(int x, int y, const uint16_t *s, uint16_t col, int x_max)
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
}

/* playlist row icon (art/pocket.py LIST_GLYPHS 236): 8 x 8 at 2x */
static void icon(int x, int y)
{
    static const uint8_t rows[8] = { 0xDF, 0xDF, 0x00, 0xDF, 0xDF, 0x00, 0xDC, 0xDC };
    COLOR = C_GRAPE;
    for (int r = 0; r < 8; r++)
        for (int c = 0; c < 8; c++)
            if (rows[r] & (0x80 >> c)) FillRect(x + 2 * c, y + 2 * r, x + 2 * c + 1, y + 2 * r + 1);
}

static void redraw(void) { S.dirty = 1; SendMsg(MSG_DRAW); }

static void init(void)
{
    uint8_t *p = (uint8_t *)&S;
    for (unsigned i = 0; i < sizeof S; i++) p[i] = 0;
    L.count = 0;
    if (!S8(0x1F)) S.state = ST_NOCARD;                     /* no SD card */
    else {
        if (S8(0x0E) != 4) { S8(0x0E) = 4; DiskSwitch(4); } /* SD card is disk 4 */
        if (ex_init()) S.state = ST_NOCARD;
        else if (pl_list(&L)) S.state = ST_NODIR;
        else if (!L.count) S.state = ST_EMPTY;
    }
    redraw();
}

static void deinit(void) {}

static int32_t tick(void) { return 0; }

static void quit(void)
{
    TaskSwitch(1, 0);                                      /* Music menu */
    S.state = ST_QUIT;
}

/* resolve the chosen playlist into the slot-2 table and start it in Now Playing */
static void play(void)
{
    static pl_res_t R;
    volatile pl_table_t *t = PLT;
    t->magic = 0;
    pl_load(&L, &L.files[S.sel], &R);
    if (!R.n) { S.state = ST_NOTRACKS; redraw(); return; }
    for (int i = 0; i < R.n; i++) { t->clus[i] = R.clus[i]; t->num[i] = R.num[i]; }
    t->n = (uint16_t)R.n; t->cur = 0;
    t->magic = PLT_MAGIC;

    if (ThreadRunning(*(volatile uint32_t *)PHAND, PDESC) == 1) ThreadStop(PHAND, PDESC);
    RecPrepare();                                          /* the browser's play-request prep */
    *(volatile uint16_t *)0x03022BAC = 0x63;               /* list type, as the browser sets it */
    R16(0xF2) = 0x63;
    R32(0x10) = 0x030056C0u;                               /* browser folder state */
    R32(0x34) = t->clus[0];
    R32(0x38) = t->num[0];
    R16(0) = (uint16_t)R.n; R16(2) = 1; R16(6) = 1;
    R32(0x44) = 0; R32(0x48) = 0; R32(0x4C) = 0;
    S8(0x64) = 0;                                          /* no resume point: a reboot does not restart it */
    static uint16_t arg[14];
    arg[0] = 1; arg[1] = 0x46; arg[2] = 0x504C;            /* as Folders: {index, 0x46}; 0x504C: ours */
    TaskSwitch(3, arg);
    S.state = ST_QUIT;
}

static int32_t service(void)
{
    if (S.state == ST_QUIT) return -1;
    if (S.state == ST_LOAD) { play(); return S.state == ST_QUIT ? -1 : 0; }
    for (int n = 0; n < 8; n++) {
        uint32_t ev = GetKey();
        if (!ev) break;
        uint32_t type = ev >> 24, k = ev & 0x1FF;
        if (type != EV_PRESS && type != EV_REPEAT) continue;
        if (k == K_B || (k == K_LEFT && type == EV_PRESS)) { quit(); return -1; }
        if (S.state == ST_NOTRACKS && type == EV_PRESS) { S.state = ST_LIST; redraw(); }
        if (S.state != ST_LIST) continue;
        if (k == K_UP || k == K_DOWN) {
            int s = S.sel + (k == K_DOWN ? 1 : -1);
            if (s < 0) s = L.count - 1;
            if (s >= L.count) s = 0;
            S.sel = s;
            if (S.sel < S.top) S.top = S.sel;
            if (S.sel >= S.top + ROWS) S.top = S.sel - ROWS + 1;
            redraw();
        } else if ((k == K_A || k == K_RIGHT) && type == EV_PRESS && L.count) {
            S.state = ST_LOAD;                             /* paint "Loading", then resolve next service call */
            redraw();
        }
    }
    return 0;
}

static void paint(void)
{
    if (!GetMsg(MSG_DRAW) && !S.dirty) return;
    S.dirty = 0;
    uint16_t old = COLOR;
    static uint16_t b[40];
    fill(0, 0, 295, 32, C_WHITE);                          /* status band */
    fill(0, 33, 295, 34, C_INK);
    fill(0, 35, 295, 58, C_HEAD);                          /* header */
    fill(0, 59, 295, 60, C_INK);
    fill(0, 221, 295, 222, C_INK);
    fill(0, 223, 295, 239, C_SCREEN);
    a16(b, "Playlists");
    text(12, 39, b, C_INK, 200);
    const char *msg = 0;
    switch (S.state) {
    case ST_NOCARD:   msg = "No SD card"; break;
    case ST_NODIR:    msg = "No _Playlists folder"; break;
    case ST_EMPTY:    msg = "No playlists"; break;
    }
    if (S.state == ST_LOAD)     { a16(b, "Loading"); text(220, 39, b, C_DIM, 292); }
    if (S.state == ST_NOTRACKS) { a16(b, "No tracks"); text(206, 39, b, C_DIM, 292); }
    for (int r = 0; r < ROWS; r++) {
        int i = S.top + r, y = ROW_Y + r * ROW_H, on = !msg && i == S.sel && i < L.count;
        fill(0, y, 295, y + 21, on ? C_TINT : C_WHITE);
        if (on) fill(0, y, 3, y + 21, C_GRAPE);
        fill(0, y + 22, 295, y + 22, r == ROWS - 1 ? C_WHITE : C_TRACK);
        if (msg) { if (r == 0) { a16(b, msg); text(40, y + 3, b, C_DIM, 292); } continue; }
        if (i >= L.count) continue;
        icon(12, y + 3);
        const pl_file_t *f = &L.files[i];
        int n = f->nlen < 39 ? f->nlen : 39;
        for (int c = 0; c < n; c++) b[c] = f->name[c];
        b[n] = 0;
        text(40, y + 3, b, C_INK, 290);
    }
    COLOR = old;
}

/* window descriptor: must be the first bytes of the data section (0x03023B48) */
__attribute__((section(".desc"), used))
const win_desc_t pl_desc = { 0, 0, tick, service, paint, init, deinit };
