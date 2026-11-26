/* Minimal synchronous exFAT reader for amuletOS modules (playlists.c; Blockz has its own incremental walk in
 * bgmusic.c). Reads 512-byte sectors through the stock raw read (0x03057FA4) using the volume info stock keeps
 * at 0x0307EBE0, as libscan.c does. Host tests (game/test/test_playlists.c, game/pc/pl_card.c) supply ReadSec
 * and the volume themselves (EXFAT_HOST).
 *
 * A file is addressed the way the player does it (docs/HARDWARE.md): folder cluster + "file number" =
 * the directory slot (32-byte entry index) of the file's 0x85 entry, plus 1. */
#include <stdint.h>

#ifndef EXFAT_HOST
#define ReadSec(l, b) STOCK_FN(0x03057FA4, uint32_t, uint32_t, void *)(l, b)
#define EX_VOL        ((const volatile uint8_t *)0x0307E710u)
#endif

#define EX_MAXSEC 8192          /* sectors per directory before giving up (4 MB) */
#ifndef EX_NAME
#define EX_NAME   24            /* name characters captured for listings */
#endif

typedef struct { uint32_t clus, len; uint8_t nofat; } exdir_t;

typedef struct {                /* one entry set, as seen while walking */
    uint32_t first, len, slot;
    uint8_t  flags, is_dir;
    uint16_t nlen, cap;          /* total name length, characters captured */
    uint16_t name[EX_NAME];
    uint8_t  ext[4], elen;       /* upper-cased characters after the last dot (up to 4) */
} exent_t;

static struct {
    uint32_t heap, part, fat, shift, root, reads;
    uint32_t buf[128];
} X;

static uint32_t ex_rd32(const volatile uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }

#ifndef EXFAT_HOST
/* current disk's volume (the SD card once disk 4 is selected); 0 = ok */
static int ex_init(void)
{
    const volatile uint8_t *v = EX_VOL;
    X.shift = v[2] | v[3] << 8;
    if (v[0] != 3 || (v[4] | v[5] << 8) != 9 || X.shift > 16) return -1;
    X.root = ex_rd32(v + 0x0C + 0x0D);
    X.heap = ex_rd32(v + 0x0C + 0x1F);
    X.part = ex_rd32(v + 0x0C + 0x23);
    if (X.root < 2) return -1;
    const uint8_t *s = (const uint8_t *)X.buf;
    ReadSec(X.part, X.buf);
    if (s[3] != 'E' || s[4] != 'X' || s[5] != 'F') return -1;
    X.fat = X.part + ex_rd32(s + 0x50);
    return 0;
}
#endif

static void ex_root(exdir_t *d) { d->clus = X.root; d->len = 0; d->nofat = 0; }

static uint32_t ex_lba(uint32_t clus) { return X.heap + ((clus - 2) << X.shift); }

static uint32_t ex_next(uint32_t c, int nofat)
{
    if (nofat) return c + 1;
    ReadSec(X.fat + (c >> 7), X.buf);
    X.reads++;
    return X.buf[c & 127];
}

/* Walk a directory, calling cb for each live, complete entry set (stop when cb returns non-zero; that value is
 * returned). want/wlen: optional name to match (upper-cased UTF-16); *match tells cb whether it matched. */
typedef int (*ex_cb)(const exent_t *e, int match, void *ctx);

static int ex_walk(const exdir_t *d, const uint16_t *want, int wlen, ex_cb cb, void *ctx)
{
    static exent_t e;
    int in_set = 0, rem = 0, bad = 0, dot = 0;
    uint32_t c = d->clus, sec = 0, left = d->nofat ? (d->len + 511) >> 9 : EX_MAXSEC, slot = 0;
    if (left > EX_MAXSEC) left = EX_MAXSEC;
    while (left--) {
        ReadSec(ex_lba(c) + sec, X.buf);
        X.reads++;
        const uint8_t *s = (const uint8_t *)X.buf;
        for (int o = 0; o < 512; o += 32, slot++) {
            const uint8_t *p = s + o;
            uint8_t t = p[0];
            if (t == 0) return 0;                                  /* end of directory */
            if (t == 0x85) {
                in_set = 1; rem = p[1]; bad = 0; dot = 0;
                e.slot = slot; e.is_dir = (p[4] & 0x10) != 0; e.nlen = 0; e.cap = 0; e.elen = 0;
                continue;
            }
            if (!in_set) continue;
            if (!(t & 0x80)) { in_set = 0; continue; }             /* deleted entry inside a set */
            if (t == 0xC0) {
                e.flags = p[1];
                e.first = ex_rd32(p + 20);
                e.len = ex_rd32(p + 24);
            } else if (t == 0xC1) {
                for (int i = 0; i < 15; i++) {
                    uint16_t ch = p[2 + 2 * i] | p[3 + 2 * i] << 8;
                    if (!ch) break;
                    if (e.cap < EX_NAME) e.name[e.cap++] = ch;
                    uint16_t u = ch >= 'a' && ch <= 'z' ? ch - 32 : ch;
                    if (want && (e.nlen >= wlen || want[e.nlen] != u)) bad = 1;
                    e.nlen++;
                    if (u == '.') { dot = 1; e.elen = 0; }
                    else if (dot && e.elen < 4) e.ext[e.elen++] = (uint8_t)u;
                }
            }
            if (rem && --rem) continue;
            in_set = 0;                                            /* set complete */
            if (!dot) e.elen = 0;
            int r = cb(&e, want && !bad && e.nlen == wlen, ctx);
            if (r) return r;
        }
        if (++sec >= (1u << X.shift)) {
            sec = 0;
            c = ex_next(c, d->nofat);
            if (c < 2 || c >= 0x0FFFFFF7u) return 0;
        }
    }
    return 0;
}

/* find one name (upper-cased UTF-16) in d; is_dir: 1 folder, 0 file. Fills *out (folder) and *slot; 1 = found */
typedef struct { int is_dir; exdir_t *out; uint32_t *slot; } ex_find_ctx;

static int ex_find_cb(const exent_t *e, int match, void *ctx)
{
    ex_find_ctx *f = (ex_find_ctx *)ctx;
    if (!match || e->is_dir != f->is_dir) return 0;
    if (f->out) { f->out->clus = e->first; f->out->len = e->len; f->out->nofat = (e->flags & 2) != 0; }
    if (f->slot) *f->slot = e->slot;
    return 1;
}

static int ex_find(const exdir_t *d, const uint16_t *want, int wlen, int is_dir, exdir_t *out, uint32_t *slot)
{
    ex_find_ctx f = { is_dir, out, slot };
    return ex_walk(d, want, wlen, ex_find_cb, &f) == 1;
}

/* UTF-8 bytes -> upper-cased (ASCII only) UTF-16; returns the length, -1 if it does not fit */
static int ex_utf8(const uint8_t *s, int n, uint16_t *out, int max)
{
    int k = 0;
    for (int i = 0; i < n; ) {
        uint32_t c = s[i++];
        if (c >= 0xC0 && c < 0xE0 && i < n) c = (c & 0x1F) << 6 | (s[i++] & 0x3F);
        else if (c >= 0xE0 && c < 0xF0 && i + 1 < n) { c = (c & 0x0F) << 12 | (s[i] & 0x3F) << 6 | (s[i + 1] & 0x3F); i += 2; }
        else if (c >= 0xF0 && i + 2 < n) {                      /* outside the BMP: surrogate pair */
            c = (c & 0x07) << 18 | (s[i] & 0x3F) << 12 | (s[i + 1] & 0x3F) << 6 | (s[i + 2] & 0x3F); i += 3;
            if (k + 2 > max) return -1;
            c -= 0x10000; out[k++] = (uint16_t)(0xD800 + (c >> 10)); out[k++] = (uint16_t)(0xDC00 + (c & 0x3FF));
            continue;
        }
        if (k >= max) return -1;
        if (c >= 'a' && c <= 'z') c -= 32;
        out[k++] = (uint16_t)c;
    }
    return k;
}
