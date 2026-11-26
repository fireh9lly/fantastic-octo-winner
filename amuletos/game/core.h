/* amuletOS Blockz core: portable, freestanding C (no libc), deterministic.
 * Driven by one input bitmask per frame (60 fps). Used by the device module,
 * the unit tests and the PC preview. Spec: docs/BLOCKZ.md. */
#ifndef BG_CORE_H
#define BG_CORE_H
#include <stdint.h>

#define BG_W        10
#define BG_H        40      /* stored rows; y = 0 is the bottom row */
#define BG_VISIBLE  20
#define BG_QUEUE    7       /* next pieces kept (1 shown) */

enum { P_NONE = 0, P_I, P_O, P_T, P_S, P_Z, P_J, P_L };   /* cell values 1..7 */

/* input bits: held state this frame. Edges are found by the core. */
enum {
    IN_LEFT  = 1 << 0,
    IN_RIGHT = 1 << 1,
    IN_DOWN  = 1 << 2,   /* soft drop */
    IN_UP    = 1 << 3,   /* hard drop */
    IN_CW    = 1 << 4,   /* A */
    IN_CCW   = 1 << 5,   /* B */
    IN_HOLD  = 1 << 6,   /* wheel up: set for one frame per step */
    IN_START = 1 << 7,   /* pause */
};

enum { ST_READY, ST_PLAY, ST_PAUSE, ST_DONE, ST_FAIL };

/* events returned by bg_step (bitmask) */
enum {
    EV_LOCK   = 1 << 0,
    EV_CLEAR  = 1 << 1,
    EV_DONE   = 1 << 2,
    EV_FAIL   = 1 << 3,
    EV_QUIT   = 1 << 4,  /* pause menu Quit or B on the result screen */
    EV_RETRY  = 1 << 5,
    EV_HOLD   = 1 << 6,
    EV_MOVE   = 1 << 7,  /* piece moved or rotated */
};

/* handling, in half-frames so ARR 0.5f fits; 0 = instant */
typedef struct {
    uint8_t das2;        /* DAS: 18 = 9f (Fast) */
    uint8_t arr2;        /* ARR: 2 = 1f (Fast) */
    uint8_t sdf2;        /* soft drop interval: 0 = Instant */
    uint8_t lock_frames; /* 30 */
    uint8_t lock_resets; /* 15 */
    uint8_t drop_prot;   /* frames after a hard drop in which Up is ignored */
    uint8_t ready_frames;/* READY + GO countdown length */
    uint8_t goal_lines;  /* 40 */
} bg_cfg_t;

typedef struct {
    int8_t  x, y;        /* box top-left, field coords (y up) */
    uint8_t type, rot;
} bg_piece_t;

typedef struct {
    bg_cfg_t cfg;
    uint8_t  field[BG_H][BG_W];
    bg_piece_t cur;
    uint8_t  hold, hold_used;
    uint8_t  queue[BG_QUEUE];
    uint8_t  bag[7], bag_left;
    uint32_t rng;

    uint8_t  state, pause_sel;
    uint8_t  prev_in;
    int8_t   das_dir;    /* -1, 0, +1 */
    uint16_t das_cnt;    /* half-frames held */
    uint16_t arr_acc;
    uint16_t sdf_acc;
    uint32_t grav_acc;   /* 16.16 cells */
    uint8_t  lock_cnt, resets;
    int8_t   lowest_y;   /* lowest box y reached by this piece */
    uint8_t  since_drop;

    uint32_t frame;      /* frames since the state began (READY counts down with it) */
    uint32_t time;       /* play frames (timer) */
    uint16_t lines, pieces;
    uint32_t best;       /* best time in frames, 0 = none (kept across retries) */
    uint8_t  last_clear; /* lines cleared by the last lock */
    uint32_t seed;
} bg_game_t;

void bg_default_cfg(bg_cfg_t *c);
void bg_init(bg_game_t *g, const bg_cfg_t *c, uint32_t seed);
void bg_restart(bg_game_t *g, uint32_t seed);
uint32_t bg_step(bg_game_t *g, uint8_t in);

/* helpers for renderers and tests */
void bg_minos(uint8_t type, uint8_t rot, int8_t out[4][2]);  /* box coords, x right, y down */
int  bg_ghost_y(const bg_game_t *g);
int  bg_fits(const bg_game_t *g, uint8_t type, uint8_t rot, int x, int y);
/* visible 20x10 view, row 0 = top: 0 empty, 1..7 block, 0x10|type ghost, 0x20|type active */
void bg_view(const bg_game_t *g, uint8_t out[BG_VISIBLE][BG_W]);

#endif
