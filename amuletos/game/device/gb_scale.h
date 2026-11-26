/* Full-screen Game Boy picture with a DMG look (build 53, owner's choice from PC mockups; build 54: stretched to
 * the full width, owner): 160 x 144 scaled to 296 x 240 (5/3 vertically, 296/160 horizontally, nearest
 * neighbour; 53 kept the shape at 266 x 240, centred), in a soft
 * DMG olive palette with a faint pixel grid. Game Boy pixels come out 1 or 2 screen pixels wide and tall; on the
 * 2-wide (2-tall) ones the second column (row) is drawn 35% toward the lightest shade, which reads as the gaps
 * between LCD pixels. Shared by the device (gbprobe.c) and the PC test (game/test/test_gb.c). */
#ifndef GB_SCALE_H
#define GB_SCALE_H
#include <stdint.h>

#define GBS_W 296                         /* build 53: 266 */
#define GBS_H 240
#define GBS_X 0                           /* build 53: 15 */
#define GBS_NONE 0xFFFFu

typedef struct {
    uint16_t d0[160];                     /* framebuffer column of each Game Boy pixel's first screen column */
    uint16_t d1[160];                     /* its second (grid) column, or GBS_NONE when it is 1 wide */
} gbs_t;

/* RGB565: shades 0..3 (lightest first), then the same 35% toward shade 0 for the grid.
 * DMG soft: c4cfa1, 8b956d, 4d533c, 1f1f1f (art mockup, build 53). */
static const uint16_t GBS_LUT[8] = { 0xC674, 0x8CAD, 0x4A87, 0x18E3, 0xC674, 0x9D4F, 0x73EB, 0x5AE9 };

/* mirror: column = 295 - x (the panel's rotation flag); swap: pixels swapped in pairs (index ^ 1) */
static void gbs_init(gbs_t *t, int mirror, int swap)
{
    for (int g = 0; g < 160; g++) t->d0[g] = t->d1[g] = GBS_NONE;
    for (int i = 0; i < GBS_W; i++) {
        int g = i * 160 / GBS_W;
        int col = GBS_X + i;
        if (mirror) col = 295 - col;
        if (swap) col ^= 1;
        if (t->d0[g] == GBS_NONE) t->d0[g] = (uint16_t)col; else t->d1[g] = (uint16_t)col;   /* never 3 wide */
    }
}

/* Screen rows of Game Boy line L: y0 .. y0 + n - 1 (n = 2, 2, 1, repeating); the second of two is a grid row. */
static int gbs_rows(int line, int *y0)
{
    int a = (5 * line + 2) / 3, b = (5 * line + 7) / 3;
    *y0 = a;
    return b - a;
}

/* One Game Boy line of shades (0..3) into its screen row, and into the grid row below when it is 2 tall (r2). */
static void gbs_line(const gbs_t *t, const uint16_t *shade, uint16_t *r1, uint16_t *r2)
{
    const uint16_t *d0 = t->d0, *d1 = t->d1;
    if (r2) {
        for (int g = 0; g < 160; g++) {
            uint32_t s = shade[g]; uint16_t c = GBS_LUT[s], e = GBS_LUT[4 | s];
            uint32_t a = d0[g], b = d1[g];
            r1[a] = c; r2[a] = e;
            if (b != GBS_NONE) { r1[b] = e; r2[b] = e; }
        }
    } else {
        for (int g = 0; g < 160; g++) {
            uint32_t s = shade[g];
            uint32_t a = d0[g], b = d1[g];
            r1[a] = GBS_LUT[s];
            if (b != GBS_NONE) r1[b] = GBS_LUT[4 | s];
        }
    }
}
#endif
