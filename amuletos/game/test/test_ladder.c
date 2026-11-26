/* Host test for Blockz's ladder debounce (game/device/blockz.c poll_adc_raw), with simulated sweeps. */
#include <stdio.h>
#include <stdint.h>
#define main blockz_unused_main
#include "../device/blockz.c"
#undef main

static int fails;
static uint32_t T;
/* feed `raw` for `ms` milliseconds, sampling every 2 ms; returns the set of held inputs seen */
static uint8_t feed(uint16_t raw, int ms)
{
    uint8_t seen = 0;
    for (int t = 0; t < ms; t += 2) { T += 2000; poll_adc_raw(T, raw); seen |= held_from_adc(); }
    return seen;
}
#define CHECK(c, msg) do { if (!(c)) { fails++; printf("FAIL: %s\n", msg); } } while (0)

int main(void)
{
    feed(1023, 50);
    /* hard drop: press Up quickly, release slowly through Left (30 ms) and Down (30 ms) */
    uint8_t s = feed(500, 4) | feed(364, 4) | feed(241, 4) | feed(119, 100);
    CHECK(!(s & (IN_LEFT | IN_DOWN)), "Up press sweep read as Left/Down");
    s = feed(241, 30) | feed(364, 30) | feed(1023, 40);
    CHECK(!(s & (IN_LEFT | IN_DOWN)), "slow Up release read as Left/Down");
    /* Right press from idle with a slow sweep: Down 10 ms, Left 10 ms, Up 6 ms, then Right */
    s = feed(364, 10) | feed(241, 10) | feed(119, 6);
    CHECK(!(s & (IN_LEFT | IN_DOWN)), "Right press sweep read as Left/Down");
    s = feed(0, 60);
    CHECK(s & IN_RIGHT, "Right not registered");
    /* Right release, slow: Up 20, Left 30, Down 30 ms, idle */
    s = feed(119, 20) | feed(241, 30) | feed(364, 30) | feed(1023, 40);
    CHECK(!(s & (IN_LEFT | IN_DOWN)), "slow Right release read as Left/Down");
    CHECK(!held_from_adc(), "stuck after release");
    /* real Left tap and real Down hold still work */
    s = feed(364, 2) | feed(241, 50); CHECK(s & IN_LEFT, "Left tap missed"); feed(1023, 30);
    s = feed(364, 80); CHECK(s & IN_DOWN, "Down hold missed"); feed(1023, 30);
    /* rolling from Left to Right (lower value wins) is accepted */
    feed(241, 50); s = feed(0, 50); CHECK(s & IN_RIGHT, "Left->Right roll missed");
    printf("ladder debounce: %s\n", fails ? "FAILED" : "all passed");
    return fails != 0;
}
