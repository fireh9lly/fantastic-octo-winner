/* Playlist table shared by the Playlists screen (playlists.c, module 86, writes it) and the resident song-change
 * hook (np_helpers.c pl_step, slot 2, reads it). RAM above the slot-2 helpers (tools/build_helpers.py RUN_END):
 * 0x0309FF28 .. 0x0309FFC0, right below libscan.c's fingerprint. 24 entries: slot 2 has no room for more (owner's
 * longest playlist: 20). */
#ifndef PL_TABLE_H
#define PL_TABLE_H
#include <stdint.h>

#define PLT_BASE  0x0309FF28u
#define PLT_MAX   24
#define PLT_MAGIC 0x504C5354u          /* written last, cleared first */

typedef struct {
    uint32_t magic;
    uint16_t n, cur;                   /* entries, current entry (0-based) */
    uint32_t clus[PLT_MAX];            /* folder cluster */
    uint16_t num[PLT_MAX];             /* file number = directory slot + 1 */
} pl_table_t;                          /* 152 bytes */

#define PLT ((volatile pl_table_t *)PLT_BASE)

#endif
