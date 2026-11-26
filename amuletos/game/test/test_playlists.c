/* Host test for the playlist resolver (game/device/exfat.c + pl_core.c) on a simulated exFAT card.
 * Built 32-bit by game/build.py test. Card: heap at LBA 200, FAT at 108, 4 sectors per cluster. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint8_t disk[2048][512];
static uint32_t read_sec(uint32_t lba, void *b) { memcpy(b, disk[lba], 512); return 0; }
#define EXFAT_HOST
#define ReadSec(l, b) read_sec(l, b)
#include "../device/exfat.c"
#include "../device/pl_core.c"

enum { FATS = 108, HEAP = 200, SHIFT = 2 };
static uint32_t lba_of(uint32_t c) { return HEAP + ((c - 2) << SHIFT); }
static void fat_set(uint32_t c, uint32_t n) { memcpy(disk[FATS + (c >> 7)] + 4 * (c & 127), &n, 4); }

/* directory writer over a list of sectors */
static uint32_t dsec[32]; static int dpos;
static uint8_t *slot_p(void) { uint8_t *e = disk[dsec[dpos / 16]] + 32 * (dpos % 16); dpos++; return e; }
static void dir_at(uint32_t clus, int clusters_chain, uint32_t clus2)
{
    for (int i = 0; i < 4; i++) dsec[i] = lba_of(clus) + i;
    for (int i = 0; i < 4; i++) dsec[4 + i] = lba_of(clusters_chain ? clus2 : clus + 1) + i;
    dpos = 0;
}
/* name in UTF-16 given as UTF-8 here (only ASCII and 2-byte sequences used) */
static int put_set(const char *u8, int dir, uint32_t first, uint32_t len, int nofat, int deleted)
{
    uint16_t nm[128]; int nl = 0;
    for (const uint8_t *s = (const uint8_t *)u8; *s; ) {
        if (*s >= 0xC0) { nm[nl++] = (uint16_t)((s[0] & 0x1F) << 6 | (s[1] & 0x3F)); s += 2; }
        else nm[nl++] = *s++;
    }
    int nn = (nl + 14) / 15, slot = dpos;
    uint8_t *e = slot_p();
    e[0] = deleted ? 0x05 : 0x85; e[1] = (uint8_t)(1 + nn); e[4] = dir ? 0x10 : 0x20;
    e = slot_p();
    e[0] = deleted ? 0x40 : 0xC0; e[1] = (uint8_t)(1 | (nofat ? 2 : 0)); e[3] = (uint8_t)nl;
    memcpy(e + 20, &first, 4); memcpy(e + 24, &len, 4);
    for (int k = 0; k < nn; k++) {
        e = slot_p(); e[0] = deleted ? 0x41 : 0xC1;
        for (int i = 0; i < 15 && k * 15 + i < nl; i++) { e[2 + 2 * i] = (uint8_t)nm[k * 15 + i]; e[3 + 2 * i] = (uint8_t)(nm[k * 15 + i] >> 8); }
    }
    return slot;
}
static void put_file(uint32_t clus, const char *text)
{
    size_t n = strlen(text);
    for (size_t i = 0; i < n; i++) disk[lba_of(clus) + i / 512][i % 512] = (uint8_t)text[i];
}

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static char m3u[4096];

int main(void)
{
    memset(disk, 0, sizeof disk);
    X.part = 0; X.fat = FATS; X.heap = HEAP; X.shift = SHIFT; X.root = 5;
    fat_set(5, 0xFFFFFFFFu);
    /* root (cluster 5) */
    dir_at(5, 0, 0);
    put_set("Artist A", 1, 10, 4 * 512, 1, 0);
    put_set("_playlists", 1, 20, 4 * 512, 1, 0);       /* case differs from "_Playlists" */
    put_set("Café Tacvba", 1, 30, 0, 0, 0);           /* FAT-chained folder: clusters 30 -> 33 */
    fat_set(30, 33); fat_set(33, 0xFFFFFFFFu);
    /* /Artist A/ (cluster 10, contiguous): Album 1 */
    dir_at(10, 0, 0);
    put_set("Album 1", 1, 11, 4 * 512, 1, 0);
    /* /Artist A/Album 1/ (cluster 11): deleted leftovers before the real files (slot numbers count them) */
    dir_at(11, 0, 0);
    put_set("02 - Two.sync-conflict.mp3", 0, 0, 1, 1, 1);
    int s1 = put_set("01 - One.mp3", 0, 100, 1000, 1, 0);
    put_set("01 - One.mp3", 0, 0, 1, 1, 1);
    int s2 = put_set("02 - Two.FLAC", 0, 101, 1000, 1, 0);
    /* /Café Tacvba/ (clusters 30 -> 33): fill cluster 30 so the track lands in the second cluster */
    dir_at(30, 1, 33);
    for (int i = 0; i < 19; i++) put_set("filler file name.txt", 0, 200, 10, 1, 0);   /* 3 slots each = 57 */
    while (dpos < 64) put_set("x", 0, 0, 1, 1, 1);
    int s3 = put_set("Señora.mp3", 0, 102, 1000, 1, 0);
    /* Mix.m3u8: BOM, CRLF, comments, relative / absolute / backslash / drive / "./" / missing, crossing a sector */
    char *p = m3u;
    p += sprintf(p, "\xEF\xBB\xBF#EXTM3U\r\n#PLAYLIST:Mix\r\n");
    for (int i = 0; i < 12; i++) p += sprintf(p, "#EXTINF:-1,padding line %02d to push entries across a sector\r\n", i);
    p += sprintf(p, "../Artist A/Album 1/01 - One.mp3\r\n");
    p += sprintf(p, "  ..\\artist a\\ALBUM 1\\02 - two.flac  \r\n");
    p += sprintf(p, "/Café Tacvba/Señora.mp3\r\n");
    p += sprintf(p, "E:\\Artist A\\Album 1\\01 - One.mp3\r\n");
    p += sprintf(p, "../Artist A/./Album 1/missing.mp3\r\n");
    p += sprintf(p, "\r\n# trailing comment\r\n");
    p += sprintf(p, "../Artist A/Album 1/02 - Two.FLAC");      /* no final newline */
    uint32_t mixlen = (uint32_t)(p - m3u);
    CHECK(mixlen > 600, "playlist only %u bytes", mixlen);
    put_file(40, m3u);

    /* /_playlists/ (cluster 20): two playlists, a text file, a subfolder */
    dir_at(20, 0, 0);
    put_set("Mix.m3u8", 0, 40, mixlen, 1, 0);
    put_set("notes.txt", 0, 41, 10, 1, 0);
    put_set("Old.M3U", 0, 42, 0, 1, 0);
    put_set("sub.m3u", 1, 43, 512, 1, 0);


    static pl_list_t L;
    static pl_res_t R;
    CHECK(pl_list(&L) == 0, "no playlist folder");
    CHECK(L.count == 2, "playlists %d", L.count);
    CHECK(L.files[0].nlen == 3 && L.files[0].name[0] == 'M', "first name");
    CHECK(L.files[1].nlen == 3 && L.files[1].name[0] == 'O', "second name");

    pl_load(&L, &L.files[0], &R);
    CHECK(R.total == 6, "entries %d", R.total);
    CHECK(R.n == 5 && R.missing == 1, "resolved %d missing %d", R.n, R.missing);
    uint32_t ec[5] = { 11, 11, 30, 11, 11 };
    uint16_t en[5] = { (uint16_t)(s1 + 1), (uint16_t)(s2 + 1), (uint16_t)(s3 + 1), (uint16_t)(s1 + 1), (uint16_t)(s2 + 1) };
    for (int i = 0; i < 5 && i < R.n; i++)
        CHECK(R.clus[i] == ec[i] && R.num[i] == en[i], "entry %d: %u/%u, want %u/%u", i, R.clus[i], R.num[i], ec[i], en[i]);
    CHECK(s1 == 4 && s3 >= 64, "test layout: s1 %d s3 %d", s1, s3);

    printf(fails ? "test_playlists: %d FAILED\n" : "test_playlists: all passed\n", fails);
    return fails != 0;
}
