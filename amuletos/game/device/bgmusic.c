/* Blockz background music (v0.21), included by blockz.c.
 * Owner's behaviour: if music is already playing when Blockz opens, leave it alone. Otherwise play a random
 * track from /_blockgame/ on the SD card and keep picking random tracks from that folder until Blockz exits,
 * then stop. No card / folder / file: start silently at once.
 *
 * Uses stock's file system and player the way the folder browser and Now Playing do (docs/HARDWARE.md,
 * "Starting music"). First attempt from static analysis: every step reports a status so a wrong guess shows
 * up as a plain label on screen (MUSIC panel) and as numbers on the INFO page, never as a silent failure. */

#define SYSC   0x030248d4u      /* system config */
#define PREC   0x03024F54u      /* music source record */
#define PHAND  0x030252FCu      /* player thread handle */
#define PDESC  0x03038230u      /* player thread descriptor (module 33) */
#ifndef BGWALK_HOST
#define FILTER ((const void *)0x0300570Bu)   /* "MP1MP2MP3WMA..." audio extension list */
#endif
#define FTYPE  6u               /* entry type the library scanner uses */

#define ThreadRunning(h, d)  STOCK_FN(0x03057F58, uint32_t, uint32_t, uint32_t)(h, d)
#define ThreadDelete(hp)     STOCK_FN(0x03057F14, void, uint32_t)(hp)
#define ThreadCreate(hp, d, a) STOCK_FN(0x03057E72, void, uint32_t, uint32_t, void *)(hp, d, a)
#define ModuleLoad(n)        STOCK_FN(0x03068800, uint32_t, uint32_t, uint32_t)(n, 7)
#define DiskSwitch(d)        STOCK_FN(0x03058802, void, uint32_t)(d)
#define FindFirst(f, it, e, t) STOCK_FN(0x0305BED2, uint32_t, void *, void *, const void *, uint32_t)(f, it, e, t)
#define FindNext(f, it, e, t)  STOCK_FN(0x0305BEA6, uint32_t, void *, void *, const void *, uint32_t)(f, it, e, t)
#define FatName(c, i, t, o)  STOCK_FN(0x0305C640, uint32_t, uint32_t, uint32_t, uint32_t, uint16_t *)(c, i, t, o)
#define FatFiles(c, e, t)    STOCK_FN(0x0305C0D2, uint32_t, uint32_t, const void *, uint32_t)(c, e, t)
#define FatDirs(c, t)        STOCK_FN(0x0305A990, uint32_t, uint32_t, uint32_t)(c, t)
#define RecPrepare()         STOCK_FN(0x030555e0, void, void)()
#define AudioClose()         STOCK_FN(0x0308EAE6, void, uint32_t)(1)
#define AudioControl(c, a)   STOCK_FN(0x0308C454, uint32_t, uint32_t, uint32_t)(c, a)

enum { BGM_OFF, BGM_KEPT, BGM_NOCARD, BGM_NOFOLDER, BGM_NOFILE, BGM_PLAY, BGM_ERRFIND, BGM_ERRSTART, BGM_SCAN };

typedef struct {                 /* the browser's iterator (BrowserUI listing, sp+0 .. sp+0x47) */
    uint32_t clus, index, count;
    uint8_t  pad[0x10];
    uint8_t  ex[0x2C];           /* exFAT directory info, 0x2A bytes used */
} fs_iter_t;

static struct {
    uint8_t  status, mine;       /* mine: we started the player and own it until exit */
    uint8_t  fstype;
    uint32_t root, clus, files, cur, rnd;
    uint8_t  restarts;
    uint16_t nums[PLT_MAX];      /* file numbers (directory slot + 1) of the folder's tracks */
} M;

static uint32_t m_rd32(uint32_t a) { volatile uint8_t *p = (volatile uint8_t *)a; return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }

static int name_is_blockgame(const uint16_t *s)
{
    static const char want[] = "_blockgame";
    for (int i = 0; i < 10; i++) {
        uint16_t c = s[i];
        if (c >= 'A' && c <= 'Z') c += 32;
        if (c != (uint8_t)want[i]) return 0;
    }
    return s[10] == 0;
}

static uint32_t m_random(uint32_t n)
{
    M.rnd = M.rnd * 1664525u + 1013904223u;
    return n ? (M.rnd >> 8) % n : 0;
}

/* exFAT directory walk (build 34). Builds 25-33 used stock's folder iterator, whose directory info is the
 * root's, not the found folder's: the folder was found by name, then its file count and the library-database
 * search both came back empty (EMPTY). We read the card ourselves instead, with the raw sector read the scan skip
 * uses (libscan.c, proven on the owner's card): root directory -> "_blockgame" entry set -> its first cluster ->
 * count the files whose extension is in stock's audio filter. A few sectors per service call (MUSIC panel SCAN).
 * Owner's card: /_blockgame/ = cluster 0x000A0C32 (Windows LCN 0xA0C30), one file. */
#ifndef BGWALK_HOST             /* game/test/test_bgwalk.c supplies these */
#define ReadSec(l, b) STOCK_FN(0x03057FA4, uint32_t, uint32_t, void *)(l, b)
#define VOLI      0x0307EBE0u   /* +0 FS type (3 = exFAT), +2 sectors/cluster shift, +4 bytes/sector shift;
                                   +0x0C volume info: +0x0D root cluster, +0x1F heap LBA, +0x23 partition LBA */
#endif
#define WALK_STEP 4             /* sectors per service call */
#define WALK_MAX  4096          /* sectors per directory before giving up */
#define WALK_INTO (-1)          /* walk_entry: found /_blockgame/, now walking it */

static struct {
    uint32_t lba, sec_in_clus, clus, nofat, sec_left, reads, dsec, set_slot;
    uint32_t heap, part, fat, shift;
    uint8_t  phase;              /* 0 root, 1 /_blockgame/ */
    uint8_t  in_set, sec_rem, is_dir, dot, elen;
    uint16_t nlen, name[10];
    uint8_t  ext[4];
    uint32_t first, flags, len;
    uint32_t buf[132];           /* one sector; also find_folder's name buffer (0x104 chars) on FAT cards */
} W;

static int ext_audio(void)
{
    if (W.elen < 3) return 0;
    const volatile uint8_t *f = (const volatile uint8_t *)FILTER;   /* "MP1MP2MP3WMA...": 3-letter groups */
    for (int i = 0; i < 60 && f[i] && f[i + 1] && f[i + 2]; i += 3)
        if (f[i] == W.ext[0] && f[i + 1] == W.ext[1] && f[i + 2] == W.ext[2]) return 1;
    return 0;
}

static void walk_dir(uint32_t clus, uint32_t nofat, uint32_t bytes)
{
    W.clus = clus; W.nofat = nofat;
    W.lba = W.heap + ((clus - 2) << W.shift); W.sec_in_clus = 0; W.dsec = 0;
    W.sec_left = nofat ? (bytes + 511) >> 9 : WALK_MAX;
    if (W.sec_left > WALK_MAX) W.sec_left = WALK_MAX;
    W.in_set = 0;
}

static int walk_done(void) { return W.phase ? (M.files ? BGM_PLAY : BGM_NOFILE) : BGM_NOFOLDER; }

static int walk_begin(void)
{
    const volatile uint8_t *v = (const volatile uint8_t *)VOLI;
    W.shift = v[2] | v[3] << 8;
    if ((v[4] | v[5] << 8) != 9 || W.shift > 16) return BGM_ERRFIND;
    M.root = m_rd32(VOLI + 0x0C + 0x0D);
    W.heap = m_rd32(VOLI + 0x0C + 0x1F);
    W.part = m_rd32(VOLI + 0x0C + 0x23);
    if (M.root < 2) return BGM_ERRFIND;
    uint8_t *s = (uint8_t *)W.buf;
    ReadSec(W.part, W.buf);
    if (s[3] != 'E' || s[4] != 'X' || s[5] != 'F') return BGM_ERRFIND;
    W.fat = W.part + (s[0x50] | s[0x51] << 8 | s[0x52] << 16 | (uint32_t)s[0x53] << 24);
    W.phase = 0; W.reads = 0;
    walk_dir(M.root, 0, 0);
    return BGM_SCAN;
}

/* one 32-byte directory entry: BGM_SCAN to go on, WALK_INTO, or the final status */
static int walk_entry(const uint8_t *e, uint32_t slot)
{
    uint8_t t = e[0];
    if (t == 0) return walk_done();                        /* end of directory */
    if (t == 0x85) {                                       /* file / folder entry set */
        W.in_set = 1; W.sec_rem = e[1]; W.is_dir = (e[4] & 0x10) != 0; W.set_slot = slot;
        W.nlen = 0; W.dot = 0; W.elen = 0;
        return BGM_SCAN;
    }
    if (!W.in_set) return BGM_SCAN;
    if (!(t & 0x80)) { W.in_set = 0; return BGM_SCAN; }    /* deleted entry inside a set */
    if (t == 0xC0) {                                       /* stream extension */
        W.flags = e[1];
        W.first = e[20] | e[21] << 8 | e[22] << 16 | (uint32_t)e[23] << 24;
        W.len = e[24] | e[25] << 8 | e[26] << 16 | (uint32_t)e[27] << 24;
    } else if (t == 0xC1) {                                /* 15 name characters */
        for (int i = 0; i < 15; i++) {
            uint16_t c = e[2 + 2 * i] | e[3 + 2 * i] << 8;
            if (!c) break;
            if (c >= 'a' && c <= 'z') c -= 32;
            if (W.nlen < 10) W.name[W.nlen] = c;
            W.nlen++;
            if (c == '.') { W.dot = 1; W.elen = 0; }
            else if (W.dot && W.elen < 4) W.ext[W.elen++] = (uint8_t)c;
        }
    }
    if (W.sec_rem && --W.sec_rem) return BGM_SCAN;
    W.in_set = 0;                                          /* entry set complete */
    if (W.phase == 0) {
        static const char want[10] = "_BLOCKGAME";
        if (!W.is_dir || W.nlen != 10) return BGM_SCAN;
        for (int i = 0; i < 10; i++) if (W.name[i] != (uint8_t)want[i]) return BGM_SCAN;
        if (W.first < 2) return BGM_NOFILE;
        M.clus = W.first;
        W.phase = 1;
        walk_dir(W.first, W.flags & 2, W.len);             /* flags bit 1: contiguous, no FAT chain */
        return WALK_INTO;
    }
    if (!W.is_dir && ext_audio()) {                        /* file number = directory slot + 1 (HARDWARE.md) */
        if (M.files < PLT_MAX) M.nums[M.files] = (uint16_t)(W.set_slot + 1);
        M.files++;
    }
    return BGM_SCAN;
}

static uint32_t fat_next(uint32_t c)
{
    ReadSec(W.fat + (c >> 7), W.buf);
    return W.buf[c & 127];
}

/* a few sectors per call; BGM_SCAN while running, else the final status */
static int walk_step(void)
{
    for (int k = 0; k < WALK_STEP; k++) {
        if (!W.sec_left) return walk_done();
        W.sec_left--;
        ReadSec(W.lba, W.buf);
        W.reads++;
        const uint8_t *s = (const uint8_t *)W.buf;
        int r = BGM_SCAN;
        for (int e = 0; e < 512 && r == BGM_SCAN; e += 32) r = walk_entry(s + e, W.dsec * 16 + e / 32);
        if (r == WALK_INTO) continue;                      /* walk_dir set the folder's first sector */
        if (r != BGM_SCAN) return r;
        W.lba++; W.dsec++;
        if (++W.sec_in_clus >= (1u << W.shift)) {          /* next cluster */
            W.sec_in_clus = 0;
            uint32_t n = W.nofat ? W.clus + 1 : fat_next(W.clus);
            if (n < 2 || n >= 0x0FFFFFF7u) return walk_done();
            W.clus = n;
            W.lba = W.heap + ((n - 2) << W.shift);
        }
    }
    return BGM_SCAN;
}

/* FAT cards: stock's iterator (untested on the device; the owner's card is exFAT) */
static int find_folder(void)
{
    static fs_iter_t it;
    static uint8_t fdt[0x40];
    uint16_t *name = (uint16_t *)W.buf;        /* 0x104 chars, shares the walk's sector buffer */
    M.root = m_rd32(0x0307EBEC + 0x0D);
    for (unsigned i = 0; i < sizeof it; i++) ((uint8_t *)&it)[i] = 0;
    it.clus = M.root;
    it.count = FatFiles(M.root, FILTER, FTYPE) + FatDirs(M.root, FTYPE);
    if (FindFirst(fdt, &it, FILTER, FTYPE) != 0) return BGM_ERRFIND;
    for (int n = 0; n < 4000; n++) {
        if (fdt[0x0B] & 0x10) {                            /* a folder: compare its long name */
            name[0] = 0;
            FatName(it.clus, it.index - 1, FTYPE, name);
            name[0x100] = 0;
            if (name_is_blockgame(name)) {
                M.clus = (uint32_t)(fdt[0x14] | fdt[0x15] << 8) << 16 | fdt[0x1A] | fdt[0x1B] << 8;
                M.files = FatFiles(M.clus, FILTER, FTYPE);
                for (uint32_t i = 0; i < M.files && i < PLT_MAX; i++) M.nums[i] = (uint16_t)(i + 1);   /* untested */
                return M.files ? BGM_PLAY : BGM_NOFILE;
            }
        }
        if (FindNext(fdt, &it, FILTER, FTYPE) != 0) break;
    }
    return BGM_NOFOLDER;
}

/* Start the player on the folder's tracks in a shuffled order (build 35). The tracks go in the playlist table
 * (pl_table.h), so the player itself moves to the next one at track end (np_helpers.c pl_step); the record and
 * the start copy Now Playing's init (m27 0x03081A94), including the engine byte 0x0304A458 = 1 that builds 25-34
 * left out (the player ran but played nothing). */
static void bgm_play(void)
{
    volatile pl_table_t *t = PLT;
    uint32_t n = M.files < PLT_MAX ? M.files : PLT_MAX;
    uint16_t order[PLT_MAX];
    for (uint32_t i = 0; i < n; i++) order[i] = M.nums[i];
    for (uint32_t i = n; i > 1; i--) {                     /* shuffle */
        uint32_t j = m_random(i), k = order[i - 1];
        order[i - 1] = order[j]; order[j] = (uint16_t)k;
    }
    t->magic = 0;
    for (uint32_t i = 0; i < n; i++) { t->clus[i] = M.clus; t->num[i] = order[i]; }
    t->n = (uint16_t)n; t->cur = 0;
    t->magic = PLT_MAGIC;

    RecPrepare();                                          /* the browser's play-request prep */
    *(volatile uint16_t *)0x03024BEC = 0x63;
    *(volatile uint16_t *)(PREC + 0xF2) = 0x63;            /* source as when playing from Folders */
    *(volatile uint32_t *)(PREC + 0x10) = 0x030056E0u;
    *(volatile uint32_t *)(PREC + 0x34) = M.clus;
    *(volatile uint32_t *)(PREC + 0x38) = order[0];
    *(volatile uint16_t *)(PREC + 0) = (uint16_t)n;
    *(volatile uint16_t *)(PREC + 2) = 1;
    *(volatile uint16_t *)(PREC + 6) = 1;
    *(volatile uint32_t *)(PREC + 0x44) = 0;
    *(volatile uint32_t *)(PREC + 0x48) = 0;
    *(volatile uint32_t *)(PREC + 0x4C) = 0;
    *(volatile uint8_t *)(SYSC + 0x64) = 0;                /* no resume point */
    static uint16_t arg[14];
    arg[0] = 1; arg[1] = 0x46;
    *(volatile uint16_t *)0x0302487Cu = arg[1];           /* as Now Playing's init */
    ThreadDelete(PHAND);
    ModuleLoad(33);
    ThreadCreate(PHAND, PDESC, arg);
    *(volatile uint8_t *)0x0304A458u = 1;                  /* 0x0308D488(1) in Now Playing's init */
    M.cur = order[0];
    if (ThreadRunning(m_rd32(PHAND), PDESC) != 1) { M.status = BGM_ERRSTART; return; }
    M.status = BGM_PLAY;
    M.mine = 1;
}

/* on Blockz open */
static void bgm_start(uint32_t seed)
{
    for (unsigned i = 0; i < sizeof M; i++) ((uint8_t *)&M)[i] = 0;
    M.rnd = seed | 1;
    if (ThreadRunning(m_rd32(PHAND), PDESC) == 1) { M.status = BGM_KEPT; return; }
    if (!*(volatile uint8_t *)(SYSC + 0x1F)) { M.status = BGM_NOCARD; return; }
    if (*(volatile uint8_t *)(SYSC + 0x0E) != 4) {   /* SD card is disk 4 */
        *(volatile uint8_t *)(SYSC + 0x0E) = 4;
        DiskSwitch(4);
    }
    M.fstype = *(volatile uint8_t *)VOLI;
    M.status = (uint8_t)(M.fstype == 3 ? walk_begin() : find_folder());
    if (M.status == BGM_PLAY) bgm_play();
}

/* every service call while Blockz runs */
static void bgm_poll(void)
{
    if (M.status == BGM_SCAN) {                    /* card walk, a few sectors per call */
        int r = walk_step();
        if (r != BGM_SCAN) { M.status = (uint8_t)r; if (r == BGM_PLAY) bgm_play(); }
        return;
    }
    if (!M.mine || ThreadRunning(m_rd32(PHAND), PDESC) == 1) return;
    /* the player stopped: after the last track in normal play mode, or on an error; reshuffle and go again */
    M.mine = 0;
    if (++M.restarts > 20) { M.status = BGM_ERRSTART; return; }
    bgm_play();
}

/* on Blockz exit: stop what we started */
static void bgm_stop(void)
{
    if (M.mine) { ThreadDelete(PHAND); PLT->magic = 0; }
    M.mine = 0;
}

static const char *bgm_label(void)
{
    switch (M.status) {
    case BGM_KEPT:     return "ON";
    case BGM_NOCARD:   return "NO SD";
    case BGM_NOFOLDER: return "NO DIR";
    case BGM_NOFILE:   return "EMPTY";
    case BGM_PLAY:     return "PLAY";
    case BGM_ERRFIND:  return "ERR 1";
    case BGM_ERRSTART: return "ERR 2";
    case BGM_SCAN:     return "SCAN";
    default:           return "OFF";
    }
}
