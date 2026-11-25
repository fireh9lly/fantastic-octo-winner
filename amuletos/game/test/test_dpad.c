/* PC test for the D-pad menu tap logic:  cc -I.. test_dpad.c ../dpad.c -o test_dpad && ./test_dpad */
#include <stdio.h>
#include "../dpad.h"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

int main(void)
{
    dpad_t d;

    /* fresh menu starts on Music (Right), nothing armed */
    dpad_init(&d, DPAD_RIGHT);
    CHECK(d.sel == DPAD_RIGHT && !d.armed);
    dpad_init(&d, 9);
    CHECK(d.sel == DPAD_RIGHT);

    /* first tap on the already highlighted item only arms it (no accidental open on entering the menu) */
    dpad_init(&d, DPAD_RIGHT);
    CHECK(dpad_tap(&d, DPAD_RIGHT, 1000) == DPAD_HIGHLIGHT);
    CHECK(dpad_tap(&d, DPAD_RIGHT, 1200) == DPAD_OPEN);

    /* single tap moves the highlight */
    dpad_init(&d, DPAD_RIGHT);
    CHECK(dpad_tap(&d, DPAD_UP, 0) == DPAD_HIGHLIGHT && d.sel == DPAD_UP);

    /* double tap inside the window opens; exactly at the edge still opens */
    dpad_init(&d, DPAD_RIGHT);
    dpad_tap(&d, DPAD_DOWN, 5000);
    CHECK(dpad_tap(&d, DPAD_DOWN, 5000 + DPAD_WINDOW_MS) == DPAD_OPEN);

    /* too slow: second tap just re-arms */
    dpad_init(&d, DPAD_RIGHT);
    dpad_tap(&d, DPAD_LEFT, 5000);
    CHECK(dpad_tap(&d, DPAD_LEFT, 5000 + DPAD_WINDOW_MS + 1) == DPAD_HIGHLIGHT);
    CHECK(dpad_tap(&d, DPAD_LEFT, 5000 + DPAD_WINDOW_MS + 100) == DPAD_OPEN);   /* ...and the next quick one opens */

    /* different direction in between restarts: Up, Left, Up never opens */
    dpad_init(&d, DPAD_RIGHT);
    CHECK(dpad_tap(&d, DPAD_UP, 100) == DPAD_HIGHLIGHT);
    CHECK(dpad_tap(&d, DPAD_LEFT, 150) == DPAD_HIGHLIGHT);
    CHECK(dpad_tap(&d, DPAD_UP, 200) == DPAD_HIGHLIGHT && d.sel == DPAD_UP);

    /* triple tap opens once, third tap re-arms */
    dpad_init(&d, DPAD_RIGHT);
    dpad_tap(&d, DPAD_UP, 0);
    CHECK(dpad_tap(&d, DPAD_UP, 100) == DPAD_OPEN);
    CHECK(dpad_tap(&d, DPAD_UP, 200) == DPAD_HIGHLIGHT);

    /* another key cancels a pending double tap */
    dpad_init(&d, DPAD_RIGHT);
    dpad_tap(&d, DPAD_UP, 0);
    dpad_cancel(&d);
    CHECK(dpad_tap(&d, DPAD_UP, 100) == DPAD_HIGHLIGHT);

    /* tick counter wrap */
    dpad_init(&d, DPAD_RIGHT);
    dpad_tap(&d, DPAD_UP, 0xFFFFFF00u);
    CHECK(dpad_tap(&d, DPAD_UP, 0x00000010u) == DPAD_OPEN);

    /* bad direction ignored */
    CHECK(dpad_tap(&d, 7, 0) == DPAD_NONE);

    printf(fails ? "%d failure(s)\n" : "dpad: all tests passed\n", fails);
    return fails != 0;
}
