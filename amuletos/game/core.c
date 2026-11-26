/* amuletOS Blockz core. See core.h and docs/BLOCKZ.md.
 * Rules: guideline SRS (kicks from tetris.wiki), 7-bag, hold, ghost, lock delay with
 * move reset, DAS/ARR/soft drop in half-frames, Sprint 40 lines, no line-clear delay. */
#include "core.h"

#define GRAV_1_60 1093u          /* 16.16 cells per frame, just over 1/60 so row 1 falls at frame 60 */
#define ONE       65536u

/* spawn-state minos in box coords (x right, y down); I is a 4x4 box, others 3x3 */
static const int8_t BASE[8][4][2] = {
    {{0,0},{0,0},{0,0},{0,0}},
    {{0,1},{1,1},{2,1},{3,1}},   /* I */
    {{1,0},{2,0},{1,1},{2,1}},   /* O */
    {{1,0},{0,1},{1,1},{2,1}},   /* T */
    {{1,0},{2,0},{0,1},{1,1}},   /* S */
    {{0,0},{1,0},{1,1},{2,1}},   /* Z */
    {{0,0},{0,1},{1,1},{2,1}},   /* J */
    {{2,0},{0,1},{1,1},{2,1}},   /* L */
};

/* kicks (+x right, +y up), indexed by the state rotated from */
static const int8_t KICK_CW[4][5][2] = {             /* JLSTZ */
    {{0,0},{-1,0},{-1, 1},{0,-2},{-1,-2}},           /* 0->R */
    {{0,0},{ 1,0},{ 1,-1},{0, 2},{ 1, 2}},           /* R->2 */
    {{0,0},{ 1,0},{ 1, 1},{0,-2},{ 1,-2}},           /* 2->L */
    {{0,0},{-1,0},{-1,-1},{0, 2},{-1, 2}},           /* L->0 */
};
static const int8_t KICK_CCW[4][5][2] = {
    {{0,0},{ 1,0},{ 1, 1},{0,-2},{ 1,-2}},           /* 0->L */
    {{0,0},{ 1,0},{ 1,-1},{0, 2},{ 1, 2}},           /* R->0 */
    {{0,0},{-1,0},{-1, 1},{0,-2},{-1,-2}},           /* 2->R */
    {{0,0},{-1,0},{-1,-1},{0, 2},{-1, 2}},           /* L->2 */
};
static const int8_t KICK_I_CW[4][5][2] = {
    {{0,0},{-2,0},{ 1,0},{-2,-1},{ 1, 2}},           /* 0->R */
    {{0,0},{-1,0},{ 2,0},{-1, 2},{ 2,-1}},           /* R->2 */
    {{0,0},{ 2,0},{-1,0},{ 2, 1},{-1,-2}},           /* 2->L */
    {{0,0},{ 1,0},{-2,0},{ 1,-2},{-2, 1}},           /* L->0 */
};
static const int8_t KICK_I_CCW[4][5][2] = {
    {{0,0},{-1,0},{ 2,0},{-1, 2},{ 2,-1}},           /* 0->L */
    {{0,0},{ 2,0},{-1,0},{ 2, 1},{-1,-2}},           /* R->0 */
    {{0,0},{ 1,0},{-2,0},{ 1,-2},{-2, 1}},           /* 2->R */
    {{0,0},{-2,0},{ 1,0},{-2,-1},{ 1, 2}},           /* L->2 */
};

void bg_minos(uint8_t type, uint8_t rot, int8_t out[4][2])
{
    int n = (type == P_I || type == P_O) ? 4 : 3;
    for (int i = 0; i < 4; i++) {
        int x = BASE[type][i][0], y = BASE[type][i][1];
        if (type != P_O)
            for (int r = 0; r < (rot & 3); r++) { int t = x; x = n - 1 - y; y = t; }
        out[i][0] = (int8_t)x; out[i][1] = (int8_t)y;
    }
}

int bg_fits(const bg_game_t *g, uint8_t type, uint8_t rot, int x, int y)
{
    int8_t m[4][2];
    bg_minos(type, rot, m);
    for (int i = 0; i < 4; i++) {
        int fx = x + m[i][0], fy = y - m[i][1];
        if (fx < 0 || fx >= BG_W || fy < 0 || fy >= BG_H) return 0;
        if (g->field[fy][fx]) return 0;
    }
    return 1;
}

static int fits_cur(const bg_game_t *g, int dx, int dy)
{
    return bg_fits(g, g->cur.type, g->cur.rot, g->cur.x + dx, g->cur.y + dy);
}

int bg_ghost_y(const bg_game_t *g)
{
    int y = g->cur.y;
    while (bg_fits(g, g->cur.type, g->cur.rot, g->cur.x, y - 1)) y--;
    return y;
}

/* ---- randomiser ---- */
static uint32_t rnd(bg_game_t *g)
{
    uint32_t x = g->rng;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return g->rng = x;
}

static uint8_t bag_draw(bg_game_t *g)
{
    if (!g->bag_left) {
        for (int i = 0; i < 7; i++) g->bag[i] = (uint8_t)(i + 1);
        for (int i = 6; i > 0; i--) {
            int j = (int)(rnd(g) % (uint32_t)(i + 1));
            uint8_t t = g->bag[i]; g->bag[i] = g->bag[j]; g->bag[j] = t;
        }
        g->bag_left = 7;
    }
    return g->bag[7 - g->bag_left--];
}

static uint8_t next_piece(bg_game_t *g)
{
    uint8_t t = g->queue[0];
    for (int i = 0; i < BG_QUEUE - 1; i++) g->queue[i] = g->queue[i + 1];
    g->queue[BG_QUEUE - 1] = bag_draw(g);
    return t;
}

/* ---- piece life ---- */
static int spawn(bg_game_t *g, uint8_t type)
{
    g->cur.type = type; g->cur.rot = 0; g->cur.x = 3; g->cur.y = 21;
    g->lock_cnt = 0; g->resets = 0; g->grav_acc = 0; g->sdf_acc = 0;
    if (!fits_cur(g, 0, 0)) return 0;           /* block out */
    if (fits_cur(g, 0, -1)) g->cur.y--;         /* drop one row at once, as in the guideline */
    g->lowest_y = g->cur.y;
    return 1;
}

static void moved(bg_game_t *g, int was_grounded)
{
    if (was_grounded || !fits_cur(g, 0, -1)) {
        if (g->resets < g->cfg.lock_resets) g->lock_cnt = 0;
        if (g->resets < 255) g->resets++;
    }
}

static int shift(bg_game_t *g, int dx)
{
    if (!fits_cur(g, dx, 0)) return 0;
    int gr = !fits_cur(g, 0, -1);
    g->cur.x += dx;
    moved(g, gr);
    return 1;
}

static int fall(bg_game_t *g)
{
    if (!fits_cur(g, 0, -1)) return 0;
    g->cur.y--;
    if (g->cur.y < g->lowest_y) { g->lowest_y = g->cur.y; g->resets = 0; g->lock_cnt = 0; }
    return 1;
}

static int rotate(bg_game_t *g, int dir)
{
    uint8_t from = g->cur.rot, to = (uint8_t)((from + dir) & 3);
    int gr = !fits_cur(g, 0, -1);
    if (g->cur.type == P_O) { g->cur.rot = to; moved(g, gr); return 1; }
    const int8_t (*k)[2] = g->cur.type == P_I ? (dir > 0 ? KICK_I_CW[from] : KICK_I_CCW[from])
                                              : (dir > 0 ? KICK_CW[from] : KICK_CCW[from]);
    for (int i = 0; i < 5; i++) {
        int nx = g->cur.x + k[i][0], ny = g->cur.y + k[i][1];
        if (bg_fits(g, g->cur.type, to, nx, ny)) {
            g->cur.x = (int8_t)nx; g->cur.y = (int8_t)ny; g->cur.rot = to;
            if (g->cur.y < g->lowest_y) { g->lowest_y = g->cur.y; g->resets = 0; g->lock_cnt = 0; }
            moved(g, gr);
            return 1;
        }
    }
    return 0;
}

static uint32_t lock_piece(bg_game_t *g)
{
    int8_t m[4][2];
    int above = 1;
    bg_minos(g->cur.type, g->cur.rot, m);
    for (int i = 0; i < 4; i++) {
        int fx = g->cur.x + m[i][0], fy = g->cur.y - m[i][1];
        g->field[fy][fx] = g->cur.type;
        if (fy < BG_VISIBLE) above = 0;
    }
    g->pieces++;
    uint32_t ev = EV_LOCK;

    int n = 0, dst = 0;
    for (int y = 0; y < BG_H; y++) {
        int full = 1;
        for (int x = 0; x < BG_W; x++) if (!g->field[y][x]) { full = 0; break; }
        if (full) { n++; continue; }
        if (dst != y) for (int x = 0; x < BG_W; x++) g->field[dst][x] = g->field[y][x];
        dst++;
    }
    for (; dst < BG_H; dst++) for (int x = 0; x < BG_W; x++) g->field[dst][x] = 0;
    g->last_clear = (uint8_t)n;
    if (n) { g->lines += (uint16_t)n; ev |= EV_CLEAR; }

    if (g->lines >= g->cfg.goal_lines) {
        g->state = ST_DONE; g->frame = 0;
        if (!g->best || g->time < g->best) g->best = g->time;
        return ev | EV_DONE;
    }
    if (above || !spawn(g, next_piece(g))) {    /* lock out / block out */
        g->state = ST_FAIL; g->frame = 0;
        return ev | EV_FAIL;
    }
    g->hold_used = 0;
    return ev;
}

/* DAS/ARR. Returns 1 if the piece moved. charge_only: count DAS without moving (READY). */
static int horizontal(bg_game_t *g, uint8_t in, uint8_t pressed, int charge_only)
{
    int dir;
    if ((in & IN_LEFT) && (in & IN_RIGHT))
        dir = (pressed & IN_LEFT) ? -1 : (pressed & IN_RIGHT) ? 1 : g->das_dir;
    else
        dir = (in & IN_LEFT) ? -1 : (in & IN_RIGHT) ? 1 : 0;

    int mv = 0;
    if (dir != g->das_dir) {                     /* new direction: tap, DAS restarts */
        g->das_dir = (int8_t)dir; g->das_cnt = 0; g->arr_acc = 0;
        if (dir && !charge_only) mv |= shift(g, dir);
        return mv;
    }
    if (!dir) return 0;
    if (g->das_cnt < g->cfg.das2) {
        g->das_cnt += 2;
        if (g->das_cnt < g->cfg.das2) return 0;
        g->das_cnt = g->cfg.das2;
        if (charge_only) return 0;
        g->arr_acc = 0;
        if (!g->cfg.arr2) { while (shift(g, dir)) mv = 1; return mv; }
        return shift(g, dir);                    /* first auto-repeat at DAS */
    }
    if (charge_only) return 0;
    if (!g->cfg.arr2) { while (shift(g, dir)) mv = 1; return mv; }
    g->arr_acc += 2;
    while (g->arr_acc >= g->cfg.arr2) { g->arr_acc -= g->cfg.arr2; if (!shift(g, dir)) { g->arr_acc = 0; break; } mv = 1; }
    return mv;
}

static uint32_t play(bg_game_t *g, uint8_t in, uint8_t pressed)
{
    uint32_t ev = 0;
    if (pressed & IN_START) { g->state = ST_PAUSE; g->pause_sel = 0; return 0; }
    g->time++;
    if (g->since_drop < 255) g->since_drop++;

    if ((pressed & IN_HOLD) && !g->hold_used) {
        uint8_t t = g->cur.type, n = g->hold ? g->hold : next_piece(g);
        g->hold = t;
        if (!spawn(g, n)) { g->state = ST_FAIL; g->frame = 0; return EV_HOLD | EV_FAIL; }
        g->hold_used = 1;
        ev |= EV_HOLD;
    }
    if ((pressed & IN_CW) && rotate(g, 1)) ev |= EV_MOVE;
    if ((pressed & IN_CCW) && rotate(g, -1)) ev |= EV_MOVE;
    if (horizontal(g, in, pressed, 0)) ev |= EV_MOVE;

    if ((pressed & IN_UP) && g->since_drop >= g->cfg.drop_prot) {
        g->cur.y = (int8_t)bg_ghost_y(g);
        g->since_drop = 0;
        return ev | lock_piece(g);
    }

    if (in & IN_DOWN) {
        if (!g->cfg.sdf2) { while (fall(g)) ; }
        else {
            g->sdf_acc += 2;
            while (g->sdf_acc >= g->cfg.sdf2) { g->sdf_acc -= g->cfg.sdf2; if (!fall(g)) { g->sdf_acc = 0; break; } }
        }
    } else g->sdf_acc = 0;

    g->grav_acc += GRAV_1_60;
    while (g->grav_acc >= ONE) { g->grav_acc -= ONE; if (!fall(g)) { g->grav_acc = 0; break; } }

    if (!fits_cur(g, 0, -1)) {                   /* grounded: lock delay */
        if (g->resets > g->cfg.lock_resets || ++g->lock_cnt >= g->cfg.lock_frames)
            return ev | lock_piece(g);
    } else g->lock_cnt = 0;
    return ev;
}

uint32_t bg_step(bg_game_t *g, uint8_t in)
{
    uint8_t pressed = (uint8_t)(in & ~g->prev_in);
    g->prev_in = in;
    g->frame++;
    switch (g->state) {
    case ST_READY:
        horizontal(g, in, pressed, 1);
        if (g->frame >= g->cfg.ready_frames) {
            g->state = ST_PLAY; g->frame = 0;
            if (!spawn(g, next_piece(g))) { g->state = ST_FAIL; return EV_FAIL; }
        }
        return 0;
    case ST_PLAY:
        return play(g, in, pressed);
    case ST_PAUSE:
        if (pressed & IN_UP)   g->pause_sel = (uint8_t)((g->pause_sel + 2) % 3);
        if (pressed & IN_DOWN) g->pause_sel = (uint8_t)((g->pause_sel + 1) % 3);
        if (pressed & IN_START) { g->state = ST_PLAY; return 0; }
        if (pressed & IN_CW) {
            if (g->pause_sel == 0) { g->state = ST_PLAY; return 0; }
            if (g->pause_sel == 1) { bg_restart(g, g->seed + 1); return EV_RETRY; }
            return EV_QUIT;
        }
        return 0;
    default:                                     /* ST_DONE, ST_FAIL */
        if (pressed & (IN_CW | IN_START)) { bg_restart(g, g->seed + 1); return EV_RETRY; }
        if (pressed & IN_CCW) return EV_QUIT;
        return 0;
    }
}

void bg_default_cfg(bg_cfg_t *c)
{
    c->das2 = 18; c->arr2 = 2; c->sdf2 = 0;
    c->lock_frames = 30; c->lock_resets = 15; c->drop_prot = 5;
    c->ready_frames = 60; c->goal_lines = 40;
}

void bg_restart(bg_game_t *g, uint32_t seed)
{
    bg_cfg_t c = g->cfg;
    uint32_t best = g->best;
    uint8_t *p = (uint8_t *)g;
    for (unsigned i = 0; i < sizeof *g; i++) p[i] = 0;
    g->cfg = c; g->best = best;
    g->seed = seed;
    g->rng = seed ? seed * 2654435761u : 0x9E3779B9u;
    if (!g->rng) g->rng = 1;
    for (int i = 0; i < BG_QUEUE; i++) g->queue[i] = bag_draw(g);
    g->state = ST_READY;
    g->prev_in = 0xFF;                           /* ignore buttons held while starting */
    g->since_drop = 255;
}

void bg_init(bg_game_t *g, const bg_cfg_t *c, uint32_t seed)
{
    g->cfg = *c; g->best = 0;
    bg_restart(g, seed);
}

void bg_view(const bg_game_t *g, uint8_t out[BG_VISIBLE][BG_W])
{
    for (int r = 0; r < BG_VISIBLE; r++)
        for (int x = 0; x < BG_W; x++)
            out[r][x] = g->field[BG_VISIBLE - 1 - r][x];
    if (g->state != ST_PLAY && g->state != ST_PAUSE) return;
    int8_t m[4][2];
    bg_minos(g->cur.type, g->cur.rot, m);
    int gy = bg_ghost_y(g);
    for (int pass = 0; pass < 2; pass++) {
        int y = pass ? g->cur.y : gy;
        uint8_t v = (uint8_t)((pass ? 0x20 : 0x10) | g->cur.type);
        for (int i = 0; i < 4; i++) {
            int fx = g->cur.x + m[i][0], fy = y - m[i][1];
            if (fy >= 0 && fy < BG_VISIBLE) out[BG_VISIBLE - 1 - fy][fx] = v;
        }
    }
}
