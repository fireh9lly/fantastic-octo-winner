/* amuletOS four-way main menu: tap / double-tap logic (see dpad.h). */
#include "dpad.h"

void dpad_init(dpad_t *d, int sel)
{
    d->sel = (uint8_t)((unsigned)sel < DPAD_N ? sel : DPAD_RIGHT);
    d->armed = 0;
    d->t_ms = 0;
}

int dpad_tap(dpad_t *d, int dir, uint32_t now_ms)
{
    if ((unsigned)dir >= DPAD_N)
        return DPAD_NONE;
    /* unsigned difference: correct across the tick counter wrapping */
    if (d->armed && dir == d->sel && now_ms - d->t_ms <= DPAD_WINDOW_MS) {
        d->armed = 0;
        return DPAD_OPEN;
    }
    d->sel = (uint8_t)dir;
    d->armed = 1;
    d->t_ms = now_ms;
    return DPAD_HIGHLIGHT;
}

void dpad_cancel(dpad_t *d)
{
    d->armed = 0;
}
