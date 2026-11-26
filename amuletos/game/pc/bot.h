#ifndef BG_BOT_H
#define BG_BOT_H
#include "../core.h"

typedef struct {
    int think, wait, planned;
    uint16_t pieces_seen;
    uint8_t type_seen, rot, last;
    int8_t x;
} bot_t;

void bot_init(bot_t *b, int think);       /* think = idle frames before acting on each piece */
uint8_t bot_input(bot_t *b, const bg_game_t *g);

#endif
