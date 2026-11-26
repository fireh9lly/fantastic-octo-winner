/* amuletOS Blockz renderer: draws a bg_game_t into an RGB565 framebuffer
 * (296x240), redrawing only what changed since the last call. Freestanding C. */
#ifndef BG_RENDER_H
#define BG_RENDER_H
#include "core.h"

#define BG_SCR_W 296
#define BG_SCR_H 240

typedef struct {
    int     valid;                       /* 0 = full redraw on next call */
    uint8_t view[BG_VISIBLE][BG_W];
    uint8_t hold, hold_dim, next, overlay, sel;
    int16_t vol;                         /* volume shown on the pause panel last time */
    char    txt[8][10];
    int     x0, y0, x1, y1;              /* dirty rect of the last call (x1/y1 exclusive), x0 >= x1 if none */
} bg_rcache_t;

/* volume shown on the pause panel (device: 0..100), or -1 for none (PC preview) */
extern int bg_pause_volume;

/* stride in pixels. Returns 1 if anything was drawn. */
int bg_render(const bg_game_t *g, uint16_t *fb, int stride, bg_rcache_t *rc);

#endif
