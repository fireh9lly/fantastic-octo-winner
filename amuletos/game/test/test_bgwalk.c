/* Host test for Blockz's /_blockgame/ lookup (game/device/bgmusic.c walk_begin / walk_step) on a simulated exFAT
 * card. Built 32-bit (build.py test) because the device code passes addresses around as uint32_t.
 *
 * Card layout: partition at LBA 100 (boot sector "EXFAT", FAT offset 8 -> FAT at 108), heap at LBA 200,
 * 4 sectors per cluster (shift 2). Root = cluster 5 chained to cluster 9 through the FAT. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../stock.h"

#define BGWALK_HOST
static uint8_t disk[1024][512];
static uint8_t vol[0x40];
static const char filter[] = "MP1MP2MP3WMAWAVAPEFLAAACM4AOGGMP43GPDFFDSF";
static int reads;
static uint32_t read_sec(uint32_t lba, void *b) { reads++; memcpy(b, disk[lba], 512); return 0; }
#define ReadSec(l, b) read_sec(l, b)
#define VOLI   ((uint32_t)(uintptr_t)vol)
#define FILTER ((const void *)filter)

#include "../device/pl_table.h"
#include "../device/bgmusic.c"

enum { PART = 100, FATS = 108, HEAP = 200, SHIFT = 2 };
static uint32_t lba_of(uint32_t clus) { return HEAP + ((clus - 2) << SHIFT); }

/* directory writer: entries are laid out across a list of sectors */
static uint32_t dsec[16]; static int dn, dpos;
static uint8_t *slot(void) { uint8_t *e = disk[dsec[dpos / 16]] + 32 * (dpos % 16); dpos++; return e; }
static void dir_start(const uint32_t *secs, int n) { memcpy(dsec, secs, n * sizeof *secs); dn = n; dpos = 0; }
static void put_set(const char *name, int dir, uint32_t first, uint32_t len, int nofat, uint8_t type)
{
    int nl = (int)strlen(name), nn = (nl + 14) / 15;
    uint8_t *e = slot();
    e[0] = type; e[1] = (uint8_t)(1 + nn); e[4] = dir ? 0x10 : 0x20;
    e = slot();
    e[0] = type == 0x85 ? 0xC0 : 0x40; e[1] = (uint8_t)(1 | (nofat ? 2 : 0)); e[3] = (uint8_t)nl;
    memcpy(e + 20, &first, 4); memcpy(e + 24, &len, 4);
    for (int k = 0; k < nn; k++) {
        e = slot(); e[0] = type == 0x85 ? 0xC1 : 0x41;
        for (int i = 0; i < 15 && k * 15 + i < nl; i++) e[2 + 2 * i] = (uint8_t)name[k * 15 + i];
    }
}
static void put_other(uint8_t type) { uint8_t *e = slot(); e[0] = type; }

static void fat_set(uint32_t c, uint32_t next) { memcpy(disk[FATS + (c >> 7)] + 4 * (c & 127), &next, 4); }

static void card(int with_folder, int folder_files)
{
    memset(disk, 0, sizeof disk); memset(vol, 0, sizeof vol);
    vol[0] = 3; vol[2] = SHIFT; vol[4] = 9;
    uint32_t root = 5, heap = HEAP, part = PART, fo = FATS - PART;
    memcpy(vol + 0x0C + 0x0D, &root, 4); memcpy(vol + 0x0C + 0x1F, &heap, 4); memcpy(vol + 0x0C + 0x23, &part, 4);
    memcpy(disk[PART] + 3, "EXFAT   ", 8); memcpy(disk[PART] + 0x50, &fo, 4);
    fat_set(5, 9); fat_set(9, 0xFFFFFFFFu);

    /* root: cluster 5 (4 sectors) then cluster 9 */
    uint32_t rs[8] = { lba_of(5), lba_of(5) + 1, lba_of(5) + 2, lba_of(5) + 3, lba_of(9), lba_of(9) + 1 };
    dir_start(rs, 6);
    put_other(0x83);                                   /* volume label */
    put_other(0x81);                                   /* bitmap */
    for (int i = 0; i < 12; i++) {                     /* artist folders filling cluster 5 (5 entries each) */
        char n[40]; snprintf(n, sizeof n, "Artist number %02d with a long name", i);
        put_set(n, 1, 100 + i, 512, 0, 0x85);
    }
    put_set("_blockgame", 1, 77, 512, 1, 0x05);        /* deleted folder of the same name */
    put_set("_blockgame", 0, 78, 100, 1, 0x85);        /* a file named like it */
    put_set("_blockgamez", 1, 79, 512, 1, 0x85);       /* longer name */
    while (dpos % 16 != 15) put_other(0xA0);           /* other primary entries: next set starts at a sector's end */
    if (with_folder) put_set("_BlockGame", 1, 40, 3 * 512, 1, 0x85);   /* set straddles a sector boundary */
    put_set("Zappa", 1, 120, 512, 0, 0x85);

    /* /_blockgame/: cluster 40, contiguous, 3 sectors of entries */
    uint32_t fs[3] = { lba_of(40), lba_of(40) + 1, lba_of(40) + 2 };
    dir_start(fs, 3);
    const char *names[] = { "Classic Theme.mp3", "b-side.FLAC", "readme.txt", "noext", "c.ogg" };
    for (int i = 0; i < folder_files && i < 5; i++) put_set(names[i], 0, 300 + i, 1000, 1, 0x85);
    put_set("sub.mp3", 1, 310, 512, 1, 0x85);          /* folder, not a track */
    put_set("gone.mp3", 0, 311, 1000, 1, 0x05);        /* deleted track */
}

static int run_walk(void)
{
    memset(&M, 0, sizeof M); memset(&W, 0, sizeof W); reads = 0;
    M.fstype = 3;
    int r = walk_begin(), steps = 0;
    while (r == BGM_SCAN && steps++ < 10000) r = walk_step();
    return r;
}

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

int main(void)
{
    card(1, 5);
    int r = run_walk();
    CHECK(r == BGM_PLAY, "status %d", r);
    CHECK(M.clus == 40, "folder cluster %u", M.clus);
    CHECK(M.files == 3, "files %u (mp3, FLAC, ogg)", M.files);
    CHECK(W.reads > 4, "reads %u: root continues into the second cluster", W.reads);

    card(1, 3);   /* mp3, FLAC, txt */
    r = run_walk();
    CHECK(r == BGM_PLAY && M.files == 2, "status %d files %u", r, M.files);

    card(1, 0);
    r = run_walk();
    CHECK(r == BGM_NOFILE, "empty folder: status %d", r);

    card(0, 0);
    r = run_walk();
    CHECK(r == BGM_NOFOLDER, "no folder: status %d", r);

    card(1, 1);
    memset(disk[PART] + 3, 0, 8);
    r = run_walk();
    CHECK(r == BGM_ERRFIND, "not exFAT: status %d", r);

    card(1, 5);   /* file numbers are directory slot + 1: mp3 at slot 0, FLAC at 4, ogg at 13 (txt, noext between) */
    run_walk();
    CHECK(M.files == 3 && M.nums[0] == 1 && M.nums[1] == 5 && M.nums[2] == 14,
          "nums %u %u %u (files %u)", M.nums[0], M.nums[1], M.nums[2], M.files);

    printf(fails ? "test_bgwalk: %d FAILED\n" : "test_bgwalk: all passed\n", fails);
    return fails != 0;
}
