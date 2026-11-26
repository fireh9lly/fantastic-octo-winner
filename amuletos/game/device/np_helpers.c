/* Resident helpers linked after the D1 hook in module slot 2 (RAM 0x0309F800+, loaded by stock at boot and never
 * overwritten): Now Playing loader and the playlist song-change hooks (resident: they run from the player
 * thread). No data or ZI: stack only. Screen-only helpers live in their screen's module (tools/extend_module.py:
 * m21_ext.*, m22_ext.*, build 37). The v0.2 Now Playing helpers
 * (np_v2 / np_v3: artist / album wrap, title fallback) were removed in build 33 for room; they are in git
 * history up to e86d06a. */
#include <stdint.h>

/* v0.3 Now Playing: module 27's init ends with "ModuleOverlay(18, 7)" (cover decoder); patched to come here
 * so the layout A drawing code (game/device/npui.c, module slot 28 at 0x030843DC) is loaded first. */
uint32_t np_load(void)
{
    ((uint32_t (*)(uint32_t, uint32_t))(0x030684E4u | 1))(28, 7);
    return ((uint32_t (*)(uint32_t, uint32_t))(0x030684E4u | 1))(18, 7);
}

/* v0.3 M3U playlists: one step of the music source record (0x0305EC0C's entry, via np_stub.S pl_step_hook).
 * Next, Prev and track end all come through here (docs/HARDWARE.md). While the record is still on the playlist's
 * current entry (source 0x63 "files", cluster and number as in the table), move along the table and fill the
 * record the way stock's lookups do; anything else (another playback started since) runs stock's step. */
#include "pl_table.h"
#define REC     0x03022F14u
#define TICK10  (*(volatile uint32_t *)0x0302288Cu)

/* 1 while the music source record is on the playlist table's current entry (source 0x63, cluster and file number
 * as in the table): the hook below and the player-init hooks (np_stub.S pl_init_count / pl_init_seek) act only
 * then, so any other playback (Folders, library) runs stock's code. */
uint32_t pl_active(void)
{
    pl_table_t *t = (pl_table_t *)PLT_BASE;            /* the player thread is the only user while it runs */
    uint16_t *r16 = (uint16_t *)REC;
    uint32_t *r32 = (uint32_t *)REC;
    uint32_t n = t->n, i = t->cur;
    return t->magic == PLT_MAGIC && r16[0xF2 / 2] == 0x63 && i < n && n <= PLT_MAX
        && r32[0x34 / 4] == t->clus[i] && r32[0x38 / 4] == t->num[i];
}

uint32_t pl_step(uint8_t *rec, int32_t dir)
{
    pl_table_t *t = (pl_table_t *)PLT_BASE;
    uint16_t *r16 = (uint16_t *)rec;
    uint32_t *r32 = (uint32_t *)rec;
    if ((uint32_t)rec != REC || !dir || !pl_active()) return 0;
    uint32_t n = t->n, i = t->cur;
    if (r16[0x0C / 2] == 1 && n > 1) i += 1 + TICK10 % (n - 1);     /* shuffle: any other entry */
    else i += dir > 0 ? 1 : n - 1;
    if (i >= n) i -= n;
    t->cur = (uint16_t)i;
    r32[0x34 / 4] = t->clus[i];
    r32[0x38 / 4] = t->num[i];
    r16[0] = (uint16_t)n; r16[1] = r16[3] = (uint16_t)(i + 1);
    r32[0x44 / 4] = r32[0x48 / 4] = r32[0x4C / 4] = 0;
    return 1;
}
