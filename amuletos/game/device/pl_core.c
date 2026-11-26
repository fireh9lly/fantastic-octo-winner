/* M3U playlists: list /_Playlists/ and resolve a playlist's entries to (folder cluster, file number), the
 * address the player uses (file number = directory slot + 1). Needs exfat.c. Used by playlists.c on the
 * device and by game/test/test_playlists.c / game/pc/pl_card.c on the PC.
 *
 * Owner's playlists (2026-11-11): extended M3U8 written by the media sync, UTF-8, LF, entries relative to the
 * playlist folder ("../Artist/Album/01 - Song.mp3"). Also handled: CRLF, a UTF-8 BOM, "\" separators, "./",
 * absolute paths from the card root ("/Artist/..." or "X:\Artist\..."), comment lines (#...). */

#ifndef PL_MAX
#define PL_MAX    32            /* entries kept per playlist (device: PLT_MAX = 24; owner's longest: 20) */
#endif
#define PL_LIST   24            /* playlists listed */
#define PL_LINE   300           /* longest entry line in bytes (owner's: 133) */
#define PL_DEPTH  12            /* path components */

typedef struct { uint32_t first, len; uint8_t nofat; uint16_t nlen; uint16_t name[EX_NAME]; } pl_file_t;

typedef struct {
    pl_file_t files[PL_LIST];
    int count;
    exdir_t dir;                /* /_Playlists/ */
} pl_list_t;

typedef struct { uint32_t clus[PL_MAX]; uint16_t num[PL_MAX]; int n, missing, total; } pl_res_t;

static const uint16_t PL_DIRNAME[10] = { '_', 'P', 'L', 'A', 'Y', 'L', 'I', 'S', 'T', 'S' };

static int pl_list_cb(const exent_t *e, int match, void *ctx)
{
    pl_list_t *L = (pl_list_t *)ctx;
    if (e->is_dir || L->count >= PL_LIST) return 0;
    int m3u = (e->elen == 3 || (e->elen == 4 && e->ext[3] == '8')) && e->ext[0] == 'M' && e->ext[1] == '3' && e->ext[2] == 'U';
    if (!m3u) return 0;
    pl_file_t *f = &L->files[L->count++];
    f->first = e->first; f->len = e->len; f->nofat = (e->flags & 2) != 0;
    int n = e->nlen - (e->elen + 1);                     /* name without the extension */
    if (n > e->cap) n = e->cap;
    if (n < 0) n = 0;
    for (int i = 0; i < n; i++) f->name[i] = e->name[i];
    f->nlen = (uint16_t)n;
    return 0;
}

/* 0 = ok (count may be 0), -1 = no /_Playlists/ folder */
static int pl_list(pl_list_t *L)
{
    exdir_t root;
    L->count = 0;
    ex_root(&root);
    if (!ex_find(&root, PL_DIRNAME, 10, 1, &L->dir, 0)) return -1;
    ex_walk(&L->dir, 0, 0, pl_list_cb, L);
    return 0;
}

/* resolve one entry line (UTF-8, no line ending) relative to the playlist folder: 1 = found */
static int pl_resolve(const pl_list_t *L, const uint8_t *s, int n, uint32_t *clus, uint16_t *num)
{
    static uint16_t want[128];
    int cs[PL_DEPTH], cl[PL_DEPTH], depth = 0, base = 1;  /* base: still relative to /_Playlists/ */
    int i = 0;
    if (n >= 2 && s[1] == ':') { i = 2; }                  /* drive letter */
    if (i < n && (s[i] == '/' || s[i] == '\\')) base = 0;
    while (i < n) {
        while (i < n && (s[i] == '/' || s[i] == '\\')) i++;
        int j = i;
        while (j < n && s[j] != '/' && s[j] != '\\') j++;
        if (j > i) {
            if (j - i == 1 && s[i] == '.') {}
            else if (j - i == 2 && s[i] == '.' && s[i + 1] == '.') {
                if (depth) depth--; else if (base) base = 0; else return 0;
            } else {
                if (depth >= PL_DEPTH) return 0;
                cs[depth] = i; cl[depth] = j - i; depth++;
            }
        }
        i = j;
    }
    if (!depth) return 0;
    exdir_t d;
    if (base) d = L->dir; else ex_root(&d);
    for (int k = 0; k < depth; k++) {
        int w = ex_utf8(s + cs[k], cl[k], want, 128);
        if (w <= 0) return 0;
        uint32_t slot;
        exdir_t next;
        if (k < depth - 1) {
            if (!ex_find(&d, want, w, 1, &next, 0)) return 0;
            d = next;
        } else {
            if (!ex_find(&d, want, w, 0, 0, &slot)) return 0;
            *clus = d.clus;
            *num = (uint16_t)(slot + 1);
        }
    }
    return 1;
}

/* read playlist f and resolve its entries into R (at most PL_MAX; missing ones are skipped and counted) */
static void pl_load(const pl_list_t *L, const pl_file_t *f, pl_res_t *R)
{
    static uint8_t line[PL_LINE];
    int ln = 0, over = 0, first = 1;
    uint32_t c = f->first, sec = 0, left = f->len;
    R->n = R->missing = R->total = 0;
    if (c < 2) return;
    while (left) {
        ReadSec(ex_lba(c) + sec, X.buf);
        X.reads++;
        uint32_t take = left < 512 ? left : 512;
        for (uint32_t o = 0; o < take; o++) {
            uint8_t b = ((const uint8_t *)X.buf)[o];
            int end = b == '\n' || (o + 1 == take && take == left);
            if (b != '\n' && b != '\r') {
                if (ln < PL_LINE) line[ln++] = b; else over = 1;
            }
            if (!end) continue;
            int st = 0;
            if (first && ln >= 3 && line[0] == 0xEF && line[1] == 0xBB && line[2] == 0xBF) st = 3;
            first = 0;
            while (st < ln && (line[st] == ' ' || line[st] == '\t')) st++;
            int en = ln;
            while (en > st && (line[en - 1] == ' ' || line[en - 1] == '\t')) en--;
            if (en > st && line[st] != '#') {
                R->total++;
                uint32_t cl; uint16_t nm;
                if (!over && R->n < PL_MAX && pl_resolve(L, line + st, en - st, &cl, &nm)) {
                    R->clus[R->n] = cl; R->num[R->n] = nm; R->n++;
                } else if (R->n < PL_MAX) R->missing++;
                ReadSec(ex_lba(c) + sec, X.buf);           /* the lookups used the buffer */
                X.reads++;
            }
            ln = 0; over = 0;
        }
        left -= take;
        if (!left) break;
        if (++sec >= (1u << X.shift)) {
            sec = 0;
            c = ex_next(c, f->nofat);
            if (c < 2 || c >= 0x0FFFFFF7u) break;
        }
    }
}
