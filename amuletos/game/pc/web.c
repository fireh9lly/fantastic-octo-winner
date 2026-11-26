/* wasm entry points for the browser preview (play.html). Same core and renderer as the device. */
#include "../core.h"
#include "../render.h"

static bg_game_t G;
static bg_rcache_t RC;
static uint16_t FBUF[BG_SCR_W * BG_SCR_H];

__attribute__((export_name("fb"))) uint16_t *web_fb(void) { return FBUF; }

__attribute__((export_name("init"))) void web_init(uint32_t seed, int das2, int arr2, int sdf2)
{
    bg_cfg_t c; bg_default_cfg(&c);
    c.das2 = (uint8_t)das2; c.arr2 = (uint8_t)arr2; c.sdf2 = (uint8_t)sdf2;
    uint32_t best = G.best;
    bg_init(&G, &c, seed);
    G.best = best;
    RC.valid = 0;
}

__attribute__((export_name("step"))) uint32_t web_step(uint32_t in) { return bg_step(&G, (uint8_t)in); }
__attribute__((export_name("render"))) int web_render(void) { return bg_render(&G, FBUF, BG_SCR_W, &RC); }
__attribute__((export_name("state"))) int web_state(void) { return G.state; }
