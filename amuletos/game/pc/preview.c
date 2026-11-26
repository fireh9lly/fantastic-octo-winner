/* PC preview: the bot plays one Sprint; selected frames are written as tagged raw RGB565
 * (u32 tag + 296x240x2 bytes) for build.py to turn into PNGs and a GIF.
 * Tags: 0 animation, 1 READY, 2 GO, 3 early (also animation), 4 mid, 5 late, 6 pause, 7 finish. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../core.h"
#include "../render.h"
#include "bot.h"

static uint16_t fb[BG_SCR_W * BG_SCR_H];
static FILE *out;

static void emit(uint32_t tag)
{
    fwrite(&tag, 4, 1, out);
    fwrite(fb, sizeof fb, 1, out);
}

int main(int argc, char **argv)
{
    if (argc < 2) { fprintf(stderr, "usage: preview OUT.raw [seed]\n"); return 2; }
    out = fopen(argv[1], "wb");
    if (!out) return 1;
    uint32_t seed = argc > 2 ? (uint32_t)atoi(argv[2]) : 1;

    static bg_game_t g; static bg_rcache_t rc;
    bg_cfg_t c; bg_default_cfg(&c);
    bg_init(&g, &c, seed);
    bot_t b; bot_init(&b, 8);
    bg_pause_volume = 42;                        /* show the device's pause-panel volume line */
    int got_mid = 0, got_late = 0, paused = 0, pause_frames = 0;

    for (int f = 0; f < 60 * 60 * 5; f++) {
        uint8_t in = bot_input(&b, &g);
        if (!paused && g.state == ST_PLAY && g.lines >= 12) { in = IN_START; paused = 1; }
        if (g.state == ST_PAUSE) {
            pause_frames++;
            in = pause_frames == 4 ? IN_DOWN : pause_frames == 8 ? 0 : pause_frames == 10 ? IN_UP
               : pause_frames == 40 ? IN_START : 0;
        }
        bg_step(&g, in);
        bg_render(&g, fb, BG_SCR_W, &rc);

        if (g.state == ST_READY && g.frame == 10) emit(1);
        if (g.state == ST_READY && g.frame == 45) emit(2);
        if (g.state == ST_PLAY && g.time == 300) emit(3);
        else if (g.state == ST_PLAY && g.time < 600 && !(g.time & 1)) emit(0);
        if (!got_mid && g.lines >= 20) { got_mid = 1; emit(4); }
        if (!got_late && g.lines >= 34) { got_late = 1; emit(5); }
        if (g.state == ST_PAUSE && pause_frames == 6) emit(6);
        if (g.state == ST_DONE && g.frame == 10) { emit(7); break; }
        if (g.state == ST_FAIL) { fprintf(stderr, "bot topped out\n"); break; }
    }
    fclose(out);
    printf("sprint: %u frames (%.2f s), %u pieces, best %u\n", g.time, g.time / 60.0, g.pieces, g.best);
    return 0;
}
