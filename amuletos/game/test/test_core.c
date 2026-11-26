/* Unit tests for Blockz core and renderer (PC). Build: game/build.py test */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "../core.h"
#include "../render.h"
#include "../pc/bot.h"

static int fails, checks;
#define CHECK(c) do { checks++; if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

static bg_game_t G;

static void start(uint32_t seed)
{
    bg_cfg_t c; bg_default_cfg(&c);
    bg_init(&G, &c, seed);
    bg_step(&G, 0);                               /* clear the start-up input mask */
    while (G.state == ST_READY) bg_step(&G, 0);
}

static void place(uint8_t type, uint8_t rot, int x, int y)
{
    G.cur.type = type; G.cur.rot = rot; G.cur.x = (int8_t)x; G.cur.y = (int8_t)y;
    G.lock_cnt = 0; G.resets = 0; G.lowest_y = (int8_t)y; G.grav_acc = 0;
    G.das_dir = 0; G.das_cnt = 0;
}

static void test_minos(void)
{
    int8_t m[4][2];
    bg_minos(P_T, 1, m);                          /* T state R: column x=1 rows 0..2 + (2,1) */
    int ok = 0;
    for (int i = 0; i < 4; i++)
        ok += (m[i][0] == 1 && m[i][1] >= 0 && m[i][1] <= 2) || (m[i][0] == 2 && m[i][1] == 1);
    CHECK(ok == 4);
    bg_minos(P_I, 1, m);                          /* I state R: column x=2 */
    for (int i = 0; i < 4; i++) CHECK(m[i][0] == 2);
    bg_minos(P_I, 2, m);                          /* I state 2: row y=2 */
    for (int i = 0; i < 4; i++) CHECK(m[i][1] == 2);
}

static void test_bag(void)
{
    /* lock 70 pieces with hard drops on an empty field: every group of 7 holds all 7 */
    start(7);
    int counts[8] = {0}, seen = 0;
    uint8_t group[7];
    for (int n = 0; n < 70; n++) {
        group[n % 7] = G.cur.type;
        counts[G.cur.type]++;
        if (n % 7 == 6) {
            int mask = 0;
            for (int k = 0; k < 7; k++) mask |= 1 << group[k];
            CHECK(mask == 0xFE);
            seen++;
        }
        for (int y = 0; y < BG_H; y++) for (int x = 0; x < BG_W; x++) G.field[y][x] = 0;
        bg_step(&G, 0);
        for (int k = 0; k < 6; k++) bg_step(&G, 0);
        bg_step(&G, IN_UP); bg_step(&G, 0);
    }
    CHECK(seen == 10);
    for (int t = 1; t <= 7; t++) CHECK(counts[t] == 10);
}

static void test_spawn(void)
{
    start(3);
    CHECK(G.state == ST_PLAY);
    CHECK(G.cur.x == 3 && G.cur.y == 20 && G.cur.rot == 0);   /* spawned at 21, dropped one row */
    uint8_t v[BG_VISIBLE][BG_W]; bg_view(&G, v);
    int top = 0;
    for (int x = 0; x < BG_W; x++) top += (v[0][x] & 0x20) != 0;
    CHECK(top >= 1);                                          /* lower spawn row visible at once */
}

static void test_kicks(void)
{
    start(1);
    /* R->2 at the left wall: test 1 blocked, test 2 (+1,0) */
    place(P_T, 1, -1, 10);
    G.prev_in = 0;
    bg_step(&G, IN_CW);
    CHECK(G.cur.rot == 2 && G.cur.x == 0 && G.cur.y == 10);

    /* floor kick: T state 0 on the floor, 0->R: tests 1,2 go below the floor, test 3 (-1,+1) */
    for (int y = 0; y < BG_H; y++) for (int x = 0; x < BG_W; x++) G.field[y][x] = 0;
    place(P_T, 0, 4, 1);                           /* bottom row of the box at y=0 */
    G.prev_in = 0;
    bg_step(&G, IN_CW);
    CHECK(G.cur.rot == 1 && G.cur.x == 3 && G.cur.y == 2);

    /* I 0->R next to the right wall uses test 2 (-2,0) if test 1 is blocked by a stack */
    for (int y = 0; y < BG_H; y++) for (int x = 0; x < BG_W; x++) G.field[y][x] = 0;
    place(P_I, 0, 6, 10);                          /* cells x 6..9 at y 9 */
    for (int y = 6; y <= 11; y++) G.field[y][8] = P_O;  /* blocks column 8 (state R column) */
    G.field[9][8] = 0;                             /* keep the piece's own row clear */
    for (int x = 6; x <= 9; x++) G.field[9][x] = 0;
    G.prev_in = 0;
    int ok = bg_fits(&G, P_I, 0, 6, 10);
    CHECK(ok);
    bg_step(&G, IN_CW);
    CHECK(G.cur.rot == 1 && G.cur.x == 4);         /* column 4+2 = 6 */

    /* O never kicks or moves */
    place(P_O, 0, 3, 10); G.prev_in = 0;
    bg_step(&G, IN_CW);
    CHECK(G.cur.x == 3 && G.cur.y == 10);
}

static void clear_field(void) { for (int y = 0; y < BG_H; y++) for (int x = 0; x < BG_W; x++) G.field[y][x] = 0; }

static void test_lock_delay(void)
{
    start(2);
    clear_field();
    place(P_T, 0, 3, 1); G.prev_in = 0;
    uint16_t p0 = G.pieces;
    int f = 0;
    while (G.pieces == p0 && f < 100) { bg_step(&G, 0); f++; }
    CHECK(f == 30);                                /* 30 frames on the ground, then lock */

    /* move resets: alternate left/right taps keep it alive for 15 resets, then it locks */
    clear_field();
    place(P_T, 0, 3, 1); G.prev_in = 0;
    p0 = G.pieces; f = 0;
    int moves = 0;
    while (G.pieces == p0 && f < 2000) {
        uint8_t in = 0;
        if (f % 20 == 0) { in = (moves & 1) ? IN_RIGHT : IN_LEFT; moves++; }
        bg_step(&G, in); f++;
    }
    CHECK(moves == 16);                            /* 15 resets used; the 16th move locks at once */
    CHECK(f > 15 * 20 && f < 17 * 20);

    /* falling to a new lowest row restores the resets */
    clear_field();
    for (int x = 0; x < 6; x++) G.field[4][x] = P_O;   /* ledge at y=4 for x<6 */
    place(P_T, 0, 0, 6);                           /* resting on the ledge */
    G.prev_in = 0;
    G.resets = 10;                                 /* 6 taps: the 6th (16th reset) takes it off the ledge */
    p0 = G.pieces;
    for (int k = 0; k < 6; k++) { bg_step(&G, IN_RIGHT); bg_step(&G, 0); }
    CHECK(G.pieces == p0 && G.cur.x == 6);
    for (int k = 0; k < 400 && G.cur.y > 1; k++) bg_step(&G, 0);
    CHECK(G.cur.y == 1 && G.resets == 0 && G.pieces == p0);
    bg_step(&G, 0);
    CHECK(G.pieces == p0);                         /* full lock delay again on the new floor */
}

static void test_hard_drop(void)
{
    start(4);
    uint16_t p0 = G.pieces;
    bg_step(&G, IN_UP);
    CHECK(G.pieces == p0 + 1);
    bg_step(&G, 0);
    bg_step(&G, IN_UP);                            /* within drop protection: ignored */
    CHECK(G.pieces == p0 + 1);
    for (int k = 0; k < 5; k++) bg_step(&G, 0);
    bg_step(&G, IN_UP);
    CHECK(G.pieces == p0 + 2);
    bg_step(&G, IN_UP);                            /* held: no repeat */
    for (int k = 0; k < 10; k++) bg_step(&G, IN_UP);
    CHECK(G.pieces == p0 + 2);
}

static void test_das(void)
{
    start(5);
    clear_field();
    place(P_O, 0, 0, 20); G.prev_in = 0;           /* O cells at x 1,2 */
    int xs[16];
    for (int f = 0; f < 16; f++) { bg_step(&G, IN_RIGHT); xs[f] = G.cur.x; }
    /* tap on frame 1, DAS 9f: next move on frame 10, then ARR 1f */
    CHECK(xs[0] == 1);
    for (int f = 1; f < 9; f++) CHECK(xs[f] == 1);
    CHECK(xs[9] == 2 && xs[10] == 3 && xs[11] == 4);
    CHECK(xs[15] == 7);                            /* wall: O at box x 7 = cells 8,9 */

    /* direction change restarts DAS */
    bg_step(&G, IN_LEFT);
    CHECK(G.cur.x == 6);
    for (int f = 0; f < 8; f++) bg_step(&G, IN_LEFT);
    CHECK(G.cur.x == 6);
    bg_step(&G, IN_LEFT);
    CHECK(G.cur.x == 5);

    /* ARR instant slides to the wall at DAS */
    G.cfg.arr2 = 0;
    bg_step(&G, 0);
    for (int f = 0; f < 9; f++) bg_step(&G, IN_RIGHT);
    CHECK(G.cur.x == 6);
    bg_step(&G, IN_RIGHT);
    CHECK(G.cur.x == 7);
    bg_step(&G, 0);

    /* ARR 0.5f: two cells per frame after DAS */
    G.cfg.arr2 = 1;
    place(P_O, 0, -1, 20); G.prev_in = 0;
    for (int f = 0; f < 10; f++) bg_step(&G, IN_RIGHT);   /* tap, then first repeat at DAS */
    CHECK(G.cur.x == 1);
    bg_step(&G, IN_RIGHT);
    CHECK(G.cur.x == 3);
}

static void test_soft_drop(void)
{
    start(6);
    clear_field();
    place(P_T, 0, 3, 20); G.prev_in = 0;
    bg_step(&G, IN_DOWN);
    CHECK(G.cur.y == 1);                           /* instant: straight to the floor */
    CHECK(G.pieces == 0 || G.state == ST_PLAY);    /* not locked by soft drop itself */
    uint16_t p0 = G.pieces;
    bg_step(&G, 0);
    CHECK(G.pieces == p0);
}

static void test_gravity(void)
{
    start(8);
    clear_field();
    place(P_T, 0, 3, 20); G.prev_in = 0;
    for (int f = 0; f < 59; f++) bg_step(&G, 0);
    CHECK(G.cur.y == 20);
    bg_step(&G, 0);
    CHECK(G.cur.y == 19);                          /* 1 row per 60 frames */
}

static void test_lines(void)
{
    start(9);
    clear_field();
    for (int x = 0; x < BG_W; x++) if (x < 3 || x > 6) { G.field[0][x] = P_J; G.field[1][x] = P_J; }
    G.field[2][0] = P_L;                           /* sits on top, must move down 2 */
    place(P_O, 0, 3, 21); G.prev_in = 0;           /* O at x 4,5: rows 0,1 still have gaps at 3,6 */
    bg_step(&G, IN_UP);
    CHECK(G.lines == 0);
    clear_field();
    for (int x = 0; x < BG_W; x++) if (x != 4 && x != 5) { G.field[0][x] = P_J; G.field[1][x] = P_J; }
    G.field[2][0] = P_L;
    for (int k = 0; k < 6; k++) bg_step(&G, 0);
    place(P_O, 0, 3, 21); G.prev_in = 0;
    bg_step(&G, IN_UP);
    CHECK(G.lines == 2 && G.last_clear == 2);
    CHECK(G.field[0][0] == P_L && G.field[1][0] == 0);
}

static void test_hold(void)
{
    start(10);
    uint8_t first = G.cur.type, nxt = G.queue[0];
    bg_step(&G, IN_HOLD);
    CHECK(G.hold == first && G.cur.type == nxt && G.hold_used);
    bg_step(&G, 0);
    bg_step(&G, IN_HOLD);                          /* once per piece */
    CHECK(G.hold == first && G.cur.type == nxt);
    for (int k = 0; k < 6; k++) bg_step(&G, 0);
    bg_step(&G, IN_UP); bg_step(&G, 0);
    CHECK(!G.hold_used);
    bg_step(&G, IN_HOLD);
    CHECK(G.cur.type == first && G.cur.rot == 0 && G.cur.x == 3);
}

static void test_topout(void)
{
    start(11);
    for (int y = 0; y < 22; y++) for (int x = 0; x < BG_W; x++) G.field[y][x] = (x == 0) ? 0 : P_Z;
    for (int k = 0; k < 6; k++) bg_step(&G, 0);
    bg_step(&G, IN_UP);                            /* next spawn overlaps */
    CHECK(G.state == ST_FAIL);
    bg_step(&G, 0);
    bg_step(&G, IN_CW);                            /* A = retry */
    CHECK(G.state == ST_READY && G.pieces == 0);
}

static void test_pause(void)
{
    start(12);
    uint32_t t = G.time;
    bg_step(&G, IN_START);
    CHECK(G.state == ST_PAUSE);
    for (int k = 0; k < 30; k++) bg_step(&G, 0);
    CHECK(G.time == t);
    bg_step(&G, IN_DOWN); bg_step(&G, 0); bg_step(&G, IN_DOWN); bg_step(&G, 0);
    CHECK(G.pause_sel == 2);
    uint32_t ev = bg_step(&G, IN_CW);
    CHECK(ev & EV_QUIT);
    G.state = ST_PAUSE; G.pause_sel = 0;
    bg_step(&G, 0); bg_step(&G, IN_START);
    CHECK(G.state == ST_PLAY);
}

static int run_bot(uint32_t seed, int think, uint32_t *frames, uint16_t *pieces)
{
    bg_cfg_t c; bg_default_cfg(&c);
    bg_init(&G, &c, seed);
    bot_t b; bot_init(&b, think);
    for (int f = 0; f < 60 * 60 * 10; f++) {
        bg_step(&G, bot_input(&b, &G));
        if (G.state == ST_DONE || G.state == ST_FAIL) break;
    }
    *frames = G.time; *pieces = G.pieces;
    return G.state == ST_DONE;
}

static void test_sprint_bot(void)
{
    int done = 0;
    uint32_t fr; uint16_t pc;
    for (uint32_t seed = 1; seed <= 30; seed++) done += run_bot(seed, 4, &fr, &pc);
    CHECK(done == 30);
    run_bot(1, 4, &fr, &pc);
    printf("  bot sprint seed 1: %u.%02u s, %u pieces, lines %u\n", fr / 60, fr % 60 * 100 / 60, pc, G.lines);
    CHECK(G.lines >= 40 && G.lines <= 43);
}

static void test_determinism(void)
{
    uint32_t f1, f2; uint16_t p1, p2;
    run_bot(99, 3, &f1, &p1);
    uint8_t snap[BG_H][BG_W]; memcpy(snap, G.field, sizeof snap);
    run_bot(99, 3, &f2, &p2);
    CHECK(f1 == f2 && p1 == p2 && !memcmp(snap, G.field, sizeof snap));
}

/* incremental rendering must equal a full redraw on every frame */
static void test_render_incremental(void)
{
    static uint16_t a[BG_SCR_W * BG_SCR_H], b[BG_SCR_W * BG_SCR_H];
    static bg_rcache_t ra, rb;
    bg_cfg_t c; bg_default_cfg(&c);
    bg_init(&G, &c, 21);
    bot_t bt; bot_init(&bt, 4);
    memset(&ra, 0, sizeof ra);
    int bad = 0, frames = 0;
    for (int f = 0; f < 4000 && !bad; f++) {
        uint8_t in = bot_input(&bt, &G);
        if (f == 700 || f == 760) in = IN_START;   /* pause and resume once */
        if (f == 720 || f == 730) in = IN_DOWN;    /* move the pause cursor */
        if (f == 740 || f == 750) in = IN_UP;
        bg_step(&G, in);
        bg_render(&G, a, BG_SCR_W, &ra);
        memset(&rb, 0, sizeof rb);
        bg_render(&G, b, BG_SCR_W, &rb);
        if (memcmp(a, b, sizeof a)) {
            int i = 0; while (a[i] == b[i]) i++;
            bad = 1; printf("  render mismatch at frame %d (state %d) at %d,%d\n", f, G.state, i % BG_SCR_W, i / BG_SCR_W);
        }
        frames++;
        if (G.state == ST_DONE && G.frame > 5) break;
    }
    CHECK(!bad);
    CHECK(frames > 1000);
}

int main(void)
{
    test_minos();
    test_bag();
    test_spawn();
    test_kicks();
    test_lock_delay();
    test_hard_drop();
    test_das();
    test_soft_drop();
    test_gravity();
    test_lines();
    test_hold();
    test_topout();
    test_pause();
    test_sprint_bot();
    test_determinism();
    test_render_incremental();
    printf("%d checks, %d failed\n", checks, fails);
    return fails != 0;
}
