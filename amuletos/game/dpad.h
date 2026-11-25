/* amuletOS four-way main menu: one item per D-pad direction.
 * A tap highlights that direction's item; a second tap on the same direction within DPAD_WINDOW_MS opens it.
 * Tapping a different direction moves the highlight and restarts the window. Freestanding C (device and PC). */
#ifndef AMU_DPAD_H
#define AMU_DPAD_H
#include <stdint.h>

enum { DPAD_UP, DPAD_RIGHT, DPAD_DOWN, DPAD_LEFT, DPAD_N };
enum { DPAD_NONE, DPAD_HIGHLIGHT, DPAD_OPEN };

#ifndef DPAD_WINDOW_MS
#define DPAD_WINDOW_MS 350u        /* second tap must land within this many ms of the first */
#endif

typedef struct {
    uint8_t  sel;                  /* highlighted direction */
    uint8_t  armed;                /* 1: the last tap was on sel and may become a double tap */
    uint32_t t_ms;                 /* time of that tap */
} dpad_t;

void dpad_init(dpad_t *d, int sel);

/* A direction press (not a key repeat) at now_ms. Returns DPAD_HIGHLIGHT (sel changed or re-armed) or
 * DPAD_OPEN (open sel). Opening disarms, so a third quick tap starts over. */
int dpad_tap(dpad_t *d, int dir, uint32_t now_ms);

/* Any other key (A, B, wheel...) cancels a pending double tap. */
void dpad_cancel(dpad_t *d);

#endif
