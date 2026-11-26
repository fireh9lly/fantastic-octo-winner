/* Run the device playlist code (game/device/exfat.c + pl_core.c) on a real card in the PC's reader, read-only.
 *   pl_card.exe E            -> for each playlist in /_Playlists/: name, entries, then "clus num" per entry
 * Built 32-bit by game/build.py plcard; compare with tools/pl_truth.py (independent Python reader). */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <windows.h>

static HANDLE vol;
static uint32_t read_sec(uint32_t lba, void *b)
{
    LARGE_INTEGER o; o.QuadPart = (LONGLONG)lba * 512;
    DWORD got = 0;
    if (!SetFilePointerEx(vol, o, 0, FILE_BEGIN) || !ReadFile(vol, b, 512, &got, 0) || got != 512) {
        fprintf(stderr, "read %u failed (%lu)\n", lba, GetLastError()); ExitProcess(2);
    }
    return 0;
}
#define EXFAT_HOST
#define ReadSec(l, b) read_sec(l, b)
#include "../device/exfat.c"
#include "../device/pl_core.c"

static void put16(const uint16_t *s, int n)
{
    for (int i = 0; i < n; i++) {                        /* UTF-16 (BMP) -> UTF-8 */
        uint16_t c = s[i];
        if (c < 0x80) putchar(c);
        else if (c < 0x800) { putchar(0xC0 | c >> 6); putchar(0x80 | (c & 0x3F)); }
        else { putchar(0xE0 | c >> 12); putchar(0x80 | ((c >> 6) & 0x3F)); putchar(0x80 | (c & 0x3F)); }
    }
}

int main(int argc, char **argv)
{
    char path[16];
    snprintf(path, sizeof path, "\\\\.\\%c:", argc > 1 ? argv[1][0] : 'E');
    vol = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, 0, 0);
    if (vol == INVALID_HANDLE_VALUE) { fprintf(stderr, "open %s failed (%lu)\n", path, GetLastError()); return 2; }
    uint8_t bs[512];
    read_sec(0, bs);
    if (memcmp(bs + 3, "EXFAT", 5)) { fprintf(stderr, "not exFAT\n"); return 2; }
    X.part = 0;                                          /* volume handle: LBAs are partition-relative */
    X.fat = bs[0x50] | bs[0x51] << 8 | bs[0x52] << 16 | (uint32_t)bs[0x53] << 24;
    X.heap = bs[0x58] | bs[0x59] << 8 | bs[0x5A] << 16 | (uint32_t)bs[0x5B] << 24;
    X.root = bs[0x60] | bs[0x61] << 8 | bs[0x62] << 16 | (uint32_t)bs[0x63] << 24;
    X.shift = bs[0x6D];

    static pl_list_t L;
    static pl_res_t R;
    if (pl_list(&L)) { printf("no /_Playlists/\n"); return 1; }
    printf("playlists %d (dir cluster %08x) reads %u\n", L.count, L.dir.clus, X.reads);
    for (int p = 0; p < L.count; p++) {
        uint32_t r0 = X.reads;
        pl_load(&L, &L.files[p], &R);
        printf("PL ");
        put16(L.files[p].name, L.files[p].nlen);
        printf("\t%d of %d (missing %d) reads %u\n", R.n, R.total, R.missing, X.reads - r0);
        for (int i = 0; i < R.n; i++) printf("  %08x %u\n", R.clus[i], R.num[i]);
    }
    return 0;
}
