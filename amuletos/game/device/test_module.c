/* Blockz device test module (T1): replaces stock module 82 to prove the window contract.
 * Draws a test screen, shows live diagnostics (tick/service counts, system timer, last key
 * events, raw button ADC, wheel counters) and quits to the menu on Select, like stock's game.
 * Mirrors stock module 82's init/deinit/paint conventions (docs/HARDWARE.md, UI window). */
#include <stdint.h>
#include "../stock.h"

#define MSG_CLEAR  0x18C            /* module 82's own ids: full redraw, values redraw */
#define MSG_VALUES 0x186

#define SET_FONT(n)   STOCK_FN(0x030643A2, uint32_t, uint32_t)(n)   /* returns previous */
#define SET_MODE(n)   STOCK_FN(0x030643C6, uint32_t, uint32_t)(n)

#define ADC_CH1   (*(volatile uint16_t *)(0x03005A8C + 2))
#define SYS_TIME  (*(volatile uint32_t *)0x0302288C)
#define WHEEL_A   (*(volatile uint8_t *)0x030226E4)
#define WHEEL_B   (*(volatile uint8_t *)0x030226E5)
#define WHEEL_T   (*(volatile uint32_t *)0x030226E8)

static struct {
    uint32_t ticks, services, paints;
    uint32_t ev[4];                   /* last key events, newest first */
    uint32_t nev;
} S;

static void put_hex(uint16_t *p, uint32_t v, int digits)
{
    for (int i = digits - 1; i >= 0; i--, v >>= 4) p[i] = (uint16_t)("0123456789ABCDEF"[v & 15]);
}

static int put_dec(uint16_t *p, uint32_t v)
{
    char t[10]; int n = 0;
    do { t[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    for (int i = 0; i < n; i++) p[i] = (uint16_t)t[n - 1 - i];
    return n;
}

static int put_str(uint16_t *p, const char *s)
{
    int n = 0;
    while (s[n]) { p[n] = (uint16_t)s[n]; n++; }
    return n;
}

/* one text line: clear its strip, then draw */
static void line(int y, const char *label, uint32_t v, int hex_digits)
{
    uint16_t b[40];
    int n = put_str(b, label);
    if (hex_digits) { put_hex(b + n, v, hex_digits); n += hex_digits; }
    else n += put_dec(b + n, v);
    b[n] = 0;
    COLOR = RGB565(0xff, 0xfd, 0xf6);
    FillRect(20, y, 275, y + 17);
    COLOR = RGB565(0x12, 0x1a, 0x40);
    DrawText(24, y + 1, b);
}

static void init(void)
{
    uint8_t *p = (uint8_t *)&S;
    for (unsigned i = 0; i < sizeof S; i++) p[i] = 0;
    SendMsg(MSG_CLEAR);
    SendMsg(MSG_VALUES);
    GameEnterA();
    GameEnterB();
}

static void deinit(void)
{
    GameLeaveA();
    GameLeaveB();
}

static int32_t tick(void)
{
    S.ticks++;
    if ((S.ticks & 7) == 0) SendMsg(MSG_VALUES);
    return 0;
}

static int32_t service(void)
{
    S.services++;
    uint32_t ev = GetKey();
    if (!ev) return 0;
    S.ev[3] = S.ev[2]; S.ev[2] = S.ev[1]; S.ev[1] = S.ev[0]; S.ev[0] = ev;
    S.nev++;
    SendMsg(MSG_VALUES);
    uint32_t type = ev >> 24, key = ev & 0x1FF;
    if (key == 0x002 && (type == 0x20 || type == 0x40)) {      /* Select: back to the main menu, Games tile */
        uint16_t tile = 1;                                     /* main menu focus: index 1 = Games/Blockz */
        GameLeaveB();
        TaskSwitch(0, &tile);
        COLOR = 0;
        return -1;
    }
    return 0;
}

static void paint(void)
{
    uint16_t old_color = COLOR;
    uint32_t old_font = SET_FONT(2);
    uint32_t old_mode = SET_MODE(1);
    S.paints++;

    if (GetMsg(MSG_CLEAR)) {
        static const uint16_t pal[7] = {                       /* I O T S Z J L, as in the game */
            RGB565(0x4c, 0xc8, 0xe4), RGB565(0xf0, 0xc4, 0x40), RGB565(0x9a, 0x6a, 0xd8),
            RGB565(0x5c, 0xc0, 0x6a), RGB565(0xe0, 0x54, 0x6a), RGB565(0x4a, 0x6a, 0xd8),
            RGB565(0xec, 0x90, 0x38),
        };
        COLOR = RGB565(0xac, 0xd2, 0xf4);                      /* sky */
        FillRect(0, 0, 295, 239);
        COLOR = RGB565(0x28, 0x3c, 0x88);                      /* panel frame */
        FillRect(16, 8, 279, 231);
        COLOR = RGB565(0xff, 0xfd, 0xf6);
        FillRect(18, 10, 277, 229);
        for (int i = 0; i < 7; i++) { COLOR = pal[i]; FillRect(24 + i * 22, 14, 24 + i * 22 + 19, 33); }
        uint16_t t[24];
        t[put_str(t, "BLOCKZ TEST T1")] = 0;
        COLOR = RGB565(0x12, 0x1a, 0x40);
        DrawText(24, 38, t);
        t[put_str(t, "SELECT QUITS")] = 0;
        COLOR = RGB565(0x6a, 0x7c, 0xb0);
        DrawText(24, 208, t);
        SendMsg(MSG_VALUES);
    }
    if (GetMsg(MSG_VALUES)) {
        line(60,  "TICK ", S.ticks, 0);
        line(78,  "SVC  ", S.services, 0);
        line(96,  "TIME ", SYS_TIME, 0);
        line(114, "KEY  ", S.ev[0], 8);
        line(132, "PREV ", S.ev[1], 8);
        line(150, "ADC  ", ADC_CH1, 0);
        line(168, "WHEEL ", (uint32_t)WHEEL_A << 24 | (uint32_t)WHEEL_B << 16 | (WHEEL_T & 0xFFFF), 8);
        line(186, "EVENTS ", S.nev, 0);
    }

    SET_MODE(old_mode);
    COLOR = old_color;
    SET_FONT(old_font);
}

/* window descriptor: must be the first bytes of the data section (0x03023B48) */
__attribute__((section(".desc"), used))
const win_desc_t blockz_desc = { 0, 0, tick, service, paint, init, deinit };
