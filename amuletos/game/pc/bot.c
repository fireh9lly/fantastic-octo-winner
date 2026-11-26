/* Demo/test bot: picks a placement with a simple field heuristic and plays it through
 * the same per-frame inputs a player would use (one face button at a time). PC only. */
#include "bot.h"

static int score_field(uint8_t f[BG_H][BG_W], int lines)
{
    int h[BG_W], agg = 0, holes = 0, bump = 0;
    for (int x = 0; x < BG_W; x++) {
        h[x] = 0;
        for (int y = BG_H - 1; y >= 0; y--) if (f[y][x]) { h[x] = y + 1; break; }
        for (int y = 0; y < h[x]; y++) if (!f[y][x]) holes++;
        agg += h[x];
        if (x) bump += h[x] > h[x - 1] ? h[x] - h[x - 1] : h[x - 1] - h[x];
    }
    return -51 * agg + 76 * lines - 36 * holes * 10 / 4 - 18 * bump;
}

/* best placement for type; returns score, writes rot/x */
static int best_for(const bg_game_t *g, uint8_t type, int *rot, int *bx)
{
    static uint8_t f[BG_H][BG_W];
    int best = -0x7fffffff;
    *rot = 0; *bx = 3;
    for (int r = 0; r < 4; r++)
        for (int x = -2; x < BG_W; x++) {
            int y = 21;
            if (!bg_fits(g, type, (uint8_t)r, x, y)) continue;
            while (bg_fits(g, type, (uint8_t)r, x, y - 1)) y--;
            for (int yy = 0; yy < BG_H; yy++) for (int xx = 0; xx < BG_W; xx++) f[yy][xx] = g->field[yy][xx];
            int8_t m[4][2];
            bg_minos(type, (uint8_t)r, m);
            for (int i = 0; i < 4; i++) f[y - m[i][1]][x + m[i][0]] = type;
            int lines = 0, dst = 0;
            for (int yy = 0; yy < BG_H; yy++) {
                int full = 1;
                for (int xx = 0; xx < BG_W; xx++) if (!f[yy][xx]) { full = 0; break; }
                if (full) { lines++; continue; }
                if (dst != yy) for (int xx = 0; xx < BG_W; xx++) f[dst][xx] = f[yy][xx];
                dst++;
            }
            for (; dst < BG_H; dst++) for (int xx = 0; xx < BG_W; xx++) f[dst][xx] = 0;
            int s = score_field(f, lines);
            if (s > best) { best = s; *rot = r; *bx = x; }
        }
    return best;
}

void bot_init(bot_t *b, int think) { b->think = think; b->pieces_seen = 0xFFFF; b->wait = 0; b->last = 0; b->planned = 0; }

uint8_t bot_input(bot_t *b, const bg_game_t *g)
{
    uint8_t in = 0;
    if (g->state != ST_PLAY) { b->last = 0; return 0; }
    if (g->pieces != b->pieces_seen || g->cur.type != b->type_seen) {   /* new piece */
        b->pieces_seen = g->pieces; b->type_seen = g->cur.type;
        b->wait = b->think; b->planned = 0;
    }
    if (b->wait) { b->wait--; b->last = 0; return 0; }
    if (!b->planned) {
        int r, x, s = best_for(g, g->cur.type, &r, &x);
        if (!g->hold_used) {
            int r2, x2;
            uint8_t alt = g->hold ? g->hold : g->queue[0];
            if (best_for(g, alt, &r2, &x2) > s + 40) { b->last = IN_HOLD; return IN_HOLD; }
        }
        b->rot = (uint8_t)r; b->x = (int8_t)x; b->planned = 1;
    }
    int dr = (b->rot - g->cur.rot) & 3, dx = b->x - g->cur.x;
    if (dr) {
        in = dr == 3 ? IN_CCW : IN_CW;
        if (b->last) in = 0;                     /* release between presses */
    } else if (dx) {
        uint8_t d = dx < 0 ? IN_LEFT : IN_RIGHT;
        int far = dx > 2 || dx < -2;
        in = (far || !(b->last & d)) ? d : 0;    /* hold for DAS when far, tap when near */
    } else {
        in = (b->last & IN_UP) || b->last ? 0 : IN_UP;
    }
    b->last = in;
    return in;
}
