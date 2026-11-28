/* MoonletOS key test (Settings > Key Test, 2026-11-28): a screen of the Games module (gbprobe.c includes this file),
 * opened by hooks/settings_game.S with TaskSwitch(20, "KEYT"). It answers what the wheel-modifier plan needs to know
 * (PLAN.md, "Hold a button to change what the wheel does"):
 *   - which event types GetKey sends: 0x40 press and 0x30 repeat are known, 0x20 was seen for a held B; is there a
 *     release?
 *   - does stock deliver wheel turns while a face button is held, or keep them waiting in its step counters?
 *   - is the wheel click the GPIO2 pin 5 key?
 * Lines, top to bottom: the held face button with the raw ladder reading (ADC channel 1), the click key's level,
 * wheel events (and how many came while a face button was held), the stock wheel step counters still waiting, then
 * the last four GetKey events, newest first, each with the milliseconds since the one before.
 * Leave: hold B (event 0x20000040), or press B three times within 1.5 s. Back to the Settings list. */

#define WHEEL_DN    (*(volatile uint8_t *)0x03024724u)  /* stock wheel steps waiting: event 0x200 (one way) */
#define WHEEL_UP    (*(volatile uint8_t *)0x03024725u)  /* event 0x400 (the other way) */
#define K_NLOG      4
#define K_Y(i)      (62 + (i) * 19)

static struct {
    uint32_t ev[K_NLOG], dt[K_NLOG];                  /* newest first */
    uint32_t last_us, b_us, wheel, wheel_held, n;
    uint16_t adc;
    uint8_t held, click, dn, up, bcount, live, log;
} K;

static void keys_init(void)
{
    uint8_t *p = (uint8_t *)&K;
    for (unsigned i = 0; i < sizeof K; i++) p[i] = 0;
    S.state = ST_KEYS;
    S.gpio_idle = gpio_key();
    K.held = 8; K.last_us = now_us();
}

static void keys_leave(void)
{
    static uint16_t arg[14] = { 4 };                  /* Settings list, as the main menu's Start opens it */
    push_wait();
    snd_close();
    GameLeaveB();
    TaskSwitch(10, arg);
    S.state = ST_QUIT;
}

static int32_t keys_service(void)
{
    uint32_t now = now_us();
    for (int n = 0; n < 8; n++) {
        uint32_t ev = GetKey();
        if (!ev) break;
        for (int i = K_NLOG - 1; i > 0; i--) { K.ev[i] = K.ev[i - 1]; K.dt[i] = K.dt[i - 1]; }
        K.ev[0] = ev; K.dt[0] = K.n++ ? (now - K.last_us) / 1000u : 0; K.last_us = now;
        K.log = 1;
        uint32_t type = ev >> 24, k = ev & 0xFFFFFFu;
        if (k & 0x600) { K.wheel++; if (adc_decode(ADC_CH1) < 8) K.wheel_held++; K.live = 1; }
        if (ev == 0x20000040u) { keys_leave(); return -1; }          /* hold B */
        if (type == EV_PRESS && k == K_B) {
            if (K.bcount && now - K.b_us < 1500000u) K.bcount++; else { K.bcount = 1; K.b_us = now; }
            if (K.bcount >= 3) { keys_leave(); return -1; }
        }
    }
    uint16_t a = ADC_CH1;
    uint8_t h = adc_decode(a), c = gpio_key() != S.gpio_idle, dn = WHEEL_DN, up = WHEEL_UP;
    int da = (int)a - (int)K.adc;
    if (h != K.held || c != K.click || dn != K.dn || up != K.up || da > 6 || da < -6) {
        K.held = h; K.click = c; K.dn = dn; K.up = up; K.adc = a; K.live = 1;
    }
    return 0;
}

static char *put(char *o, const char *s) { while (*s) *o++ = *s++; *o = 0; return o; }

static char *put_hex(char *o, uint32_t v, int digits)
{
    for (int i = digits - 1; i >= 0; i--) { uint32_t d = (v >> (4 * i)) & 15; *o++ = (char)(d < 10 ? '0' + d : 'A' + d - 10); }
    *o = 0;
    return o;
}

static const char *const KEY_NAME[11] = { "Click", "Select", "Right", "Left", "Up", "Down", "B", "A", "Start",
                                          "Wheel-", "Wheel+" };
static const char *const HELD_NAME[9] = { "Right", "Up", "Left", "Down", "Select", "Start", "B", "A", "nothing" };

static void keys_line(int i, uint16_t col, const char *s)
{
    fill(0, K_Y(i) - 1, 295, K_Y(i) + 17, C_WHITE);
    say(12, K_Y(i), col, "%s", (uint32_t)s, 0, 0, 0, 0);
}

static void keys_event_line(int i, int slot)
{
    char b[64], *o = b;
    uint32_t ev = K.ev[slot], type = ev >> 24, k = ev & 0xFFFFFFu;
    fill(0, K_Y(i) - 1, 295, K_Y(i) + 17, C_WHITE);
    if (slot >= (int)K.n) return;
    say(12, K_Y(i), C_DIM, "%d", K.dt[slot] > 9999u ? 9999u : K.dt[slot], 0, 0, 0, 0);
    o = put_hex(o, ev, 8);
    o = put(o, type == 0x40 ? " press " : type == 0x30 ? " repeat " : type == 0x20 ? " hold " : " type ");
    if (type != 0x40 && type != 0x30 && type != 0x20) { o = put_hex(o, type, 2); o = put(o, " "); }
    int first = 1;
    for (int bit = 0; bit < 11; bit++)
        if (k & (1u << bit)) { if (!first) o = put(o, "+"); o = put(o, KEY_NAME[bit]); first = 0; }
    if (k >> 11) { o = put(o, first ? "?" : "+?"); }
    say(56, K_Y(i), C_INK, "%s", (uint32_t)b, 0, 0, 0, 0);
}

static void keys_paint(void)
{
    int full = GetMsg(MSG_DRAW) || S.dirty;
    if (!full && !K.live && !K.log) return;
    uint16_t old = COLOR;
    char b[64], *o;
    if (full) {
        S.dirty = 0;
        fill(0, 0, 295, 32, C_BAND);
        fill(0, 33, 295, 34, C_RULE);
        fill(0, 35, 295, 58, C_HEAD);
        fill(0, 59, 295, 60, C_RULE);
        fill(0, 61, 295, 220, C_WHITE);
        fill(0, 221, 295, 222, C_RULE);
        fill(0, 223, 295, 239, C_RULE);
        say(12, 39, C_INK, "Key Test", 0, 0, 0, 0, 0);
        say(150, 39, C_DIM, "hold B: back", 0, 0, 0, 0, 0);
        K.live = K.log = 1;
    }
    if (K.live) {
        K.live = 0;
        o = put(b, "Held: "); o = put(o, HELD_NAME[K.held]); o = put(o, "   ADC ");
        fill(0, K_Y(0) - 1, 295, K_Y(0) + 17, C_WHITE);
        say(12, K_Y(0), C_INK, "%s%d", (uint32_t)b, K.adc, 0, 0, 0);
        keys_line(1, C_INK, K.click ? "Click key: pressed" : "Click key: up");
        fill(0, K_Y(2) - 1, 295, K_Y(2) + 17, C_WHITE);
        say(12, K_Y(2), C_INK, "Wheel events %d, %d while held", K.wheel, K.wheel_held, 0, 0, 0);
        fill(0, K_Y(3) - 1, 295, K_Y(3) + 17, C_WHITE);
        say(12, K_Y(3), K.dn || K.up ? C_GRAPE : C_DIM, "Wheel waiting: -%d +%d", K.dn, K.up, 0, 0, 0);
    }
    if (K.log) {
        K.log = 0;
        for (int i = 0; i < K_NLOG; i++) keys_event_line(4 + i, i);
    }
    COLOR = old;
}
