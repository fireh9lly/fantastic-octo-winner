/* Blockz on the AP30 (T2): the portable core + renderer in stock's module-82 window.
 * Unity build: core.c and render.c are included here with BG_FILL_EXTERN so every pixel goes
 * through stock's FillRect (the RAM-framebuffer flush path is still untraced).
 *
 * Timing: stock runs SysTick at 10 ms and counts ticks at 0x0302288C; SysTick VAL gives the
 * position inside the tick, so time = ticks * 10 ms + (LOAD - VAL) / (LOAD + 1) * 10 ms,
 * independent of the CPU clock. The core steps at a fixed 60 fps from that clock.
 * Input: Left/Right/Down held state from the button ADC (ch1, measured midpoints), debounced: a reading
 * counts only after it has been stable for 16 ms, because pressing or releasing one button sweeps the
 * ladder voltage through the others (Right -> idle passes Up, Left, Down); A, B, Up,
 * Start as press events from GetKey (type 0x40); Select quits; wheel steps = hold (T2: any
 * direction; the wheel still changes volume). docs/BLOCKZ.md, docs/HARDWARE.md. */
#include <stdint.h>
#include "../stock.h"
#define BG_FILL_EXTERN
#include "../core.c"
#include "../render.c"
#include "pl_table.h"
#include "bgmusic.c"

#define MSG_CLEAR  0x18C
#define MSG_DRAW   0x186

#define SYS_TICKS  (*(volatile uint32_t *)0x0302288C)
#define ST_LOAD    (*(volatile uint32_t *)0xE000E014)
#define ST_VAL     (*(volatile uint32_t *)0xE000E018)
#define ADC_CH1    (*(volatile uint16_t *)(0x03005A8C + 2))
#define WHEEL_A    (*(volatile uint8_t *)0x030226E4)
#define WHEEL_B    (*(volatile uint8_t *)0x030226E5)

#define EV_PRESS   0x40u
#define K_SELECT   0x002
#define K_LEFT     0x008
#define K_UP       0x010
#define K_B        0x040
#define K_A        0x080
#define K_START    0x100
#define K_WHEEL_A  0x200            /* GetKey turns wheel steps into events (0x03062A78): counter 0x030226E4 */
#define K_WHEEL_B  0x400            /* counter 0x030226E5; which one is "up" is still to be confirmed */
#define VOLUME     (*(volatile uint8_t *)(0x03022894 + 0x12))   /* 0..100; applied by player command 0xF8 */

static bg_game_t G;
static bg_rcache_t CACHE;
static struct {
    uint32_t last_us, acc3;      /* acc3: microseconds x3 (a frame is 50000) */
    uint8_t pulses;              /* press events waiting for the next frame */
    uint8_t wa, wb;              /* wheel counters last seen */
    uint8_t dirty, quit;
    uint8_t adc_state, adc_cand; /* debounced ladder state and the candidate being timed */
    uint32_t adc_since;
    uint8_t info, info_drawn;    /* read-only INFO page (pause, then Left) */
    uint8_t bgm_pending, painted, bgm_shown;
    uint32_t vol_until;          /* MUSIC panel shows the volume until this time */
    char music_txt[10];          /* what the MUSIC panel value shows now */
    uint32_t seed;
    uint32_t t0_us, a0_ms;       /* clock check (INFO TM): start time by SysTick and by the music position */
} S;

/* Ladder debounce. Releasing a button sweeps the voltage UP the ladder (Right 0 -> Up 119 -> Left 241 ->
 * Down 364 -> others -> idle 1023) and pressing sweeps it DOWN from idle; the rubber pads can make either
 * sweep slow. So a change towards a higher-value button while one is held is almost always a release in
 * progress (owner: jumps right after a hard drop = Up being released through Left/Down). */
#define DB_IDLE_US     16000     /* any button -> idle */
#define DB_PRESS_US    24000     /* idle -> button, or to a lower-value button (a second press wins) */
#define DB_DOWN_US     40000     /* idle -> Down: a false Down drops the piece to the floor */
#define DB_UPLADDER_US 80000     /* held button -> higher-value button: treat as release unless it stays */

/* libc pieces the compiler may emit for struct copies */
void *memcpy(void *d, const void *s, unsigned n) { uint8_t *a = d; const uint8_t *b = s; while (n--) *a++ = *b++; return d; }
void *memset(void *d, int v, unsigned n) { uint8_t *a = d; while (n--) *a++ = (uint8_t)v; return d; }

void bg_fill_rect(int x, int y, int w, int h, uint16_t c)
{
    COLOR = c;
    FillRect(x, y, x + w - 1, y + h - 1);
}

/* music position in ms (stock play state P[1], real time while a track plays), 0 if none */
static uint32_t play_ms(void)
{
    /* 0x030483D0 is in the music engine's (module 33) RAM: only valid while the player runs (build 31 crashed
     * on open after a boot with nothing played: it followed whatever was there) */
    if (STOCK_FN(0x03057C7C, uint32_t, uint32_t, uint32_t)(*(volatile uint32_t *)0x030232BCu, 0x030361A4) != 1) return 0;
    uint32_t p = *(volatile uint32_t *)0x030483D0u;
    if (p < 0x03000000u || p >= 0x030A0000u - 8 || (p & 3)) return 0;
    return ((volatile uint32_t *)p)[1];
}

static uint32_t now_us(void)
{
    uint32_t t1, v, load;
    do { t1 = SYS_TICKS; v = ST_VAL; load = ST_LOAD; } while (t1 != SYS_TICKS);
    if (v > load) v = load;
    uint32_t per_us = (load + 1u) / 10000u;        /* SysTick counts per microsecond (~200) */
    return t1 * 10000u + (per_us ? (load - v) / per_us : 0);
}

static uint8_t decode_adc(uint16_t a)
{
    /* measured: Right 0, Up ~119, Left ~241, Down 364, idle 1023. Up is a distinct state (0x80 marker)
     * so a sweep through it counts as a change; it maps to no held input (hard drop comes from GetKey). */
    if (a < 60)  return IN_RIGHT;
    if (a < 180) return 0x80;
    if (a < 302) return IN_LEFT;
    if (a < 426) return IN_DOWN;
    if (a < 950) return 0x40;       /* Select / Start / B / A: no held input */
    return 0;
}

static int ladder_rank(uint8_t k)          /* position on the ladder, low voltage first; idle last */
{
    switch (k) {
    case IN_RIGHT: return 0;
    case 0x80:     return 1;   /* Up */
    case IN_LEFT:  return 2;
    case IN_DOWN:  return 3;
    case 0x40:     return 4;   /* Select, Start, B, A */
    default:       return 5;   /* idle */
    }
}

static void poll_adc_raw(uint32_t now, uint16_t raw)
{
    uint8_t k = decode_adc(raw);
    if (k != S.adc_cand) { S.adc_cand = k; S.adc_since = now; return; }
    if (k == S.adc_state) return;
    int from = ladder_rank(S.adc_state), to = ladder_rank(k);
    uint32_t need;
    if (to == 5)          need = DB_IDLE_US;
    else if (from == 5)   need = (k == IN_DOWN) ? DB_DOWN_US : DB_PRESS_US;
    else if (to > from)   need = DB_UPLADDER_US;
    else                  need = DB_PRESS_US;
    if (now - S.adc_since >= need) S.adc_state = k;
}

static void poll_adc(uint32_t now) { poll_adc_raw(now, ADC_CH1); }

static uint8_t held_from_adc(void)
{
    return S.adc_state & (IN_LEFT | IN_RIGHT | IN_DOWN);
}

static void quit(void)
{
    uint16_t tile = 1;               /* main menu focus: BLOCKZ tile */
    bgm_stop();
    GameLeaveB();
    TaskSwitch(0, &tile);
    COLOR = 0;
    S.quit = 1;
}

static void init(void)
{
    uint8_t *p = (uint8_t *)&S;
    for (unsigned i = 0; i < sizeof S; i++) p[i] = 0;
    CACHE.valid = 0;
    bg_cfg_t c;
    bg_default_cfg(&c);
    S.seed = SYS_TICKS ^ ST_VAL;
    if (G.cfg.goal_lines != 40) G.best = 0;      /* first launch: ZI is zeroed by the loader */
    uint32_t best = G.best;
    bg_init(&G, &c, S.seed);
    G.best = best;
    S.last_us = S.t0_us = now_us();
    S.a0_ms = play_ms();
    S.wa = WHEEL_A; S.wb = WHEEL_B;
    S.bgm_pending = 1;               /* music check after the first frame is on screen */
    S.bgm_shown = 0xFF;
    SendMsg(MSG_CLEAR);
    GameEnterA();
    GameEnterB();
}

static void deinit(void)
{
    bgm_stop();
    GameLeaveA();
    GameLeaveB();
}

static int32_t tick(void)
{
    return 0;
}

static int32_t service(void)
{
    if (S.quit) return -1;

    /* press events */
    for (int n = 0; n < 8; n++) {
        uint32_t ev = GetKey();
        if (!ev) break;
        if ((ev >> 24) != EV_PRESS) continue;
        if (S.info) {                                /* INFO page: any of these closes it */
            uint32_t k = ev & 0x1FF;
            if (k == K_LEFT || k == K_B || k == K_START || k == K_A) { S.info = 0; CACHE.valid = 0; S.dirty = 1; }
            continue;
        }
        if ((ev & 0x1FF) == K_LEFT && G.state == ST_PAUSE) { S.info = 1; S.info_drawn = 0; S.dirty = 1; continue; }
        switch (ev & 0x1FF) {
        case K_SELECT: S.pulses |= IN_HOLD; break;  /* owner: Select = hold; exit via Start > QUIT */
        case K_A:      S.pulses |= IN_CW; break;
        case K_B:      S.pulses |= IN_CCW; break;
        case K_UP:     S.pulses |= IN_UP; break;
        case K_START:  S.pulses |= IN_START; break;
        case K_WHEEL_A:                              /* wheel = volume, as everywhere else on the device */
        case K_WHEEL_B: {
            int v = VOLUME + ((ev & 0x1FF) == K_WHEEL_A ? 1 : -1);   /* direction to confirm on device */
            if (v < 0) v = 0;
            if (v > 100) v = 100;
            VOLUME = (uint8_t)v;
            if (ThreadRunning(m_rd32(PHAND), PDESC) == 1) AudioControl(0xF8, 0);
            S.vol_until = now_us() + 1500000u;       /* show VOL nn in the MUSIC panel for 1.5 s */
            S.dirty = 1;
            break;
        }
        }
    }

    if (S.bgm_pending && S.painted) {
        S.bgm_pending = 0;
        bgm_start(S.seed ^ now_us());
        S.dirty = 1;
    }
    bgm_poll();

    /* fixed 60 fps steps from the SysTick clock */
    uint32_t t = now_us(), dt = t - S.last_us;
    poll_adc(t);
    if (S.info) { S.last_us = t; S.acc3 = 0; S.pulses = 0; if (S.dirty) SendMsg(MSG_DRAW); return 0; }
    if ((int32_t)dt < 0) dt = 0;
    S.last_us = t;
    if (dt > 100000) dt = 100000;                  /* after a stall: at most 6 frames of catch-up */
    S.acc3 += dt * 3;
    while (S.acc3 >= 50000) {
        S.acc3 -= 50000;
        uint8_t in = held_from_adc() | S.pulses;
        S.pulses = 0;
        uint32_t ev = bg_step(&G, in);
        S.dirty = 1;
        if (ev & EV_QUIT) { quit(); return -1; }
    }
    if (S.vol_until && (int32_t)(S.vol_until - t) > -100000) S.dirty = 1;   /* let VOL nn time out */
    if (S.dirty) SendMsg(MSG_DRAW);
    return 0;
}

/* ---- INFO page: stock play state, for wiring v0.21 (read-only) ---- */
static int ihex(char *p, uint32_t v, int digits)
{
    for (int i = digits - 1; i >= 0; i--, v >>= 4) p[i] = "0123456789ABCDEF"[v & 15];
    return digits;
}
static uint32_t rd8(uint32_t a)  { return *(volatile uint8_t *)a; }
static uint32_t rd16(uint32_t a) { return rd8(a) | rd8(a + 1) << 8; }
static uint32_t rd32(uint32_t a) { return rd16(a) | rd16(a + 2) << 16; }

static void info_line(int row, const char *label, const uint32_t *v, const uint8_t *digits, int n)
{
    char b[32]; int k = 0;
    while (*label) b[k++] = *label++;
    for (int i = 0; i < n; i++) { b[k++] = ' '; k += ihex(b + k, v[i], digits[i]); }
    b[k] = 0;
    text(14, 10 + row * 16, b, C_TEXT);
}

#define SYSC 0x03022894u   /* system config */
#define PREC 0x03022F14u   /* music source record */

static void info_page(void)
{
    fill(0, 0, BG_SCR_W, BG_SCR_H, C_PANEL);
    uint32_t running = STOCK_FN(0x03057C7C, uint32_t, uint32_t, uint32_t)(rd32(0x030232BC), 0x030361A4);
    static const uint8_t d4[3] = {4, 4, 4}, d8[2] = {8, 8}, dfs[3] = {2, 8, 2}, ddk[3] = {2, 2, 1};
    uint32_t v[3];
    text(14, 10, "INFO  B BACK", C_DIM);
    v[0] = rd16(SYSC + 0x89);  v[1] = rd16(PREC + 0xF2); info_line(1, "SRC", v, d4, 2);
    v[0] = rd16(SYSC + 0x18B); v[1] = rd16(PREC + 0xF4); info_line(2, "DEP", v, d4, 2);
    v[0] = rd16(SYSC + 0x5E);  v[1] = rd16(PREC + 6);    info_line(3, "IDX", v, d4, 2);
    v[0] = rd32(PREC + 0x34);  v[1] = rd32(PREC + 0x38); info_line(4, "CL", v, d8, 2);
    v[0] = rd8(0x0307E710); v[1] = rd32(0x0307F250); v[2] = rd8(0x0307EFC8); info_line(5, "FS", v, dfs, 3);
    for (int i = 0; i < 3; i++) v[i] = rd16(SYSC + 0x18D + 2 * i); info_line(7, "SX", v, d4, 3);
    v[0] = rd32(SYSC + 0x79);  v[1] = rd32(SYSC + 0x7D); info_line(8, "XX", v, d8, 2);
    /* clock check (owner: timer runs ~1.5x fast): ms since Blockz opened by SysTick vs by the music position */
    v[0] = (now_us() - S.t0_us) / 1000u; v[1] = play_ms() - S.a0_ms;
    v[2] = v[0] ? v[1] * 1000u / v[0] : 0;               /* 1000 = SysTick right */
    { static const uint8_t dtm[3] = {6, 6, 4}; info_line(9, "TM", v, dtm, 3); }
    v[0] = ST_LOAD; v[1] = rd32(0x030065C0u + 0x18); v[2] = *(volatile uint32_t *)0xE000E010u;
    { static const uint8_t dck[3] = {6, 8, 2}; info_line(6, "CK", v, dck, 3); }
    v[0] = rd8(SYSC + 0x0E); v[1] = rd8(SYSC + 0x1F); v[2] = running; info_line(10, "DK", v, ddk, 3);
    char b[24]; int k = 0;                      /* first letters of the current path */
    b[k++] = 'P'; b[k++] = ' ';
    for (int i = 0; i < 18; i++) {
        uint32_t c = rd16(0x03022BBA + 2 * i);
        if (!c) break;
        if (c >= 'a' && c <= 'z') c -= 32;
        b[k++] = (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ? (char)c : '-';
    }
    b[k] = 0;
    text(14, 10 + 11 * 16, b, C_TEXT);
    static const uint8_t dbg1[3] = {2, 8, 8}, dbg2[3] = {8, 4, 4};
    v[0] = M.fstype; v[1] = M.root; v[2] = M.clus;  info_line(12, "BG", v, dbg1, 3);   /* FS, root, folder cluster */
    v[0] = W.reads;  v[1] = M.files; v[2] = PLT->cur; info_line(13, "BX", v, dbg2, 3);  /* sectors read, files, table entry */
}

static void paint(void)
{
    uint16_t old_color = COLOR;
    bg_pause_volume = VOLUME;
    if (GetMsg(MSG_CLEAR)) CACHE.valid = 0;
    if (S.info) {
        GetMsg(MSG_DRAW);
        if (!S.info_drawn) { RC = &CACHE; info_page(); S.info_drawn = 1; }
        S.dirty = 0;
        COLOR = old_color;
        return;
    }
    if (GetMsg(MSG_DRAW) || !CACHE.valid) {
        int full = !CACHE.valid;
        bg_render(&G, 0, 0, &CACHE);
        if (full) {                                  /* MUSIC panel, bottom left (free space) */
            panel(LX, 172, PW, 40, C_BORDER, C_PANEL);
            text_c(LX, PW, 176, "MUSIC", C_DIM);
            S.music_txt[0] = 1;                      /* force a redraw of the value */
        }
        char mt[10];
        if ((int32_t)(S.vol_until - now_us()) > 0) {
            mt[0] = 'V'; mt[1] = 'O'; mt[2] = 'L'; mt[3] = ' ';
            put_u(mt + 4, VOLUME, 1);
        } else scpy(mt, M.status == BGM_OFF && S.bgm_pending ? "..." : bgm_label());
        if (!streq(mt, S.music_txt)) {
            scpy(S.music_txt, mt);
            fill(LX + 2, 194, PW - 4, 14, C_PANEL);
            text_c(LX, PW, 194, mt, C_TEXT);
        }
        S.painted = 1;
        S.dirty = 0;
    }
    COLOR = old_color;
}

/* window descriptor: must be the first bytes of the data section (0x03023B48) */
__attribute__((section(".desc"), used))
const win_desc_t blockz_desc = { 0, 0, tick, service, paint, init, deinit };
