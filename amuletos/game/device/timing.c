/* v0.4 timing log (builds 57..59), resident in slot 2: where the time between choosing a track and hearing it goes.
 * There is no phone video, so the device timestamps its own play path (owner, Notion "amuletOS: Build Plan to 1.0").
 * Hooks: timing.S. Readout: the Games screen's "Timing" row (gbprobe.c). Times are stock's 10 ms tick (0x030248CC,
 * counts from power-on).
 *
 * Log: the 52 B between the library builder's code end (module 39, 0x0309F7CC) and slot 2 (0x0309F800), which no
 * module uses and nothing points into (build 57 had it inside the library builder's code: unsafe).
 * Words: [0] 0x544C << 16 | events logged, [1] boot tick (30 bits) | frozen << 30 | armed << 31, then TL_N entries
 * tick (20 bits) | tag << 20 | arg << 24, a ring. Tags:
 *   1 TaskSwitch (arg screen)   2 ModuleOverlay (arg module)   3 player thread init (MusicInit)
 *   4 Audio Start (file open)   6 first audio refill after 3 / 4 (first sound)   7 track step (Next / Prev / end)
 * Build 59 (owner's first run: 660 ms from the Now Playing load to the first refill, boot 250 s, the start pushed
 * out of the ring): a start (TaskSwitch to Now Playing, screen 3, or a track step) begins a sequence; the first
 * sound freezes the log until the next start, so moving to the Timing screen keeps it whole. Main menu (8) only
 * sets the boot time: the first after power-on (the tick restarts at 0; RAM may survive a restart). */
#include <stdint.h>

#define TL         ((volatile uint32_t *)0x0309F7CCu)
#define TL_N       11u
#define SYS_TICKS  (*(volatile uint32_t *)0x030248CCu)
#define FROZEN     0x40000000u
#define ARMED      0x80000000u
#define BOOT       0x3FFFFFFFu

void tlog_hook(uint32_t a0, uint32_t a1, uint32_t tag)
{
    volatile uint32_t *t = TL;
    uint32_t h = t[0], b, now = SYS_TICKS;
    if (h >> 16 != 0x544Cu) { h = 0x544C0000u; b = 0; } else b = t[1];
    if (tag == 8) {                                           /* boot time: first menu after power-on */
        if (!(b & BOOT) || now < (b & BOOT)) { t[1] = (b & ~BOOT) | (now & BOOT); t[0] = h; }
        return;
    }
    if (tag == 7 || (tag == 1 && (a0 & 0xFFu) == 3)) b &= ~FROZEN;
    else if (b & FROZEN) return;
    if (tag == 6) { if (!(b & ARMED)) return; b = (b & BOOT) | FROZEN; }   /* every refill comes here */
    else if (tag - 3u <= 1u) b |= ARMED;
    t[2 + (h & 0xFFFFu) % TL_N] = (now & 0xFFFFFu) | tag << 20 | (a0 & 0xFFu) << 24;
    t[1] = b;
    t[0] = h + 1;
}
