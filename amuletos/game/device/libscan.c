/* Library scan skip (v0.3). Resident in module slot 2 with np_helpers.c (tools/build_helpers.py).
 *
 * Stock rebuilds the music library (~1 minute on the owner's card) whenever sys+0x42 ("library needs
 * update") is set: card seen at boot, card inserted, USB session with writes, card missing while the
 * library is from the card, ... All of those end in module 5 (MDBBuildWin), whose service clears the flag
 * and runs the build. lib_gate replaces that clear + build: it builds only when the card's fingerprint
 * differs from the one saved after the last build.
 *
 * Fingerprint (exFAT SD card only; anything else always builds, as stock): volume serial, cluster count,
 * a hash of the root directory's first cluster (top-level folders with their modified times, access
 * times left out) and a hash of the whole allocation bitmap (any file added, removed or rewritten).
 *
 * Saved: in RAM above the slot-2 code (FP, survives until power-off) and in the system config flash
 * block 0 at offset 0x300 (stock writes 0x800 bytes but only the first 0x2F5 are config; the rest is
 * 0xFF). cfg_write appends it on every config save. lib_force (Folders "Update Library?" Yes) forgets it.
 * docs/HARDWARE.md, Library update trigger. No data or ZI: stack only (slot 2 is reloaded by stock). */
#include <stdint.h>

#define FP_OFF    0x300                                /* in flash block 0 */
#define MAG       0x31464B53u                          /* "SKF1": FP holds the fingerprint of the last build */
#define NONE      0x454E4F4Eu                          /* "NONE": no valid fingerprint (build next time) */

#ifndef LIBSCAN_HOST                                   /* game/test/test_libscan.c supplies these on the PC */
#define SYS8(o)   (*(volatile uint8_t *)(0x030248d4u + (o)))
#define SYS16(o)  (*(volatile uint16_t *)(0x030248d4u + (o)))
#define VOL       ((volatile uint8_t *)0x0307EBE0u)   /* +0 FS type (3 = exFAT), +2 u16 sectors/cluster shift,
                                                           +4 u16 bytes/sector shift; +0x0C.. volume info */
#define VI        (VOL + 0x0C)                         /* +0x0D root clus, +0x1B clusters, +0x1F heap, +0x23 part */
#define FP        ((volatile uint32_t *)0x0309FFC0u)  /* [0] state, [1..4] fingerprint, [5] ~state */

#define ReadSec(l, b)     ((uint32_t (*)(uint32_t, void *))(0x03057FA4u | 1))(l, b)
#define BlkRead(n, b, l)  ((void (*)(uint32_t, void *, uint32_t))(0x0306D926u | 1))(n, b, l)
#define BlkWrite          ((uint32_t (*)(uint32_t, void *, uint32_t))(0x0306D998u | 1))
#define SaveConfig(f)     ((void (*)(uint32_t))(0x0306D9FCu | 1))(f)
#define Build()           ((void (*)(void))(0x03081af8u | 1))()      /* module 5: the stock library build */
#define Post(m)           ((void (*)(uint32_t))(0x030681F0u | 1))(m)
#define FlashRead(o, n, b) ((uint32_t (*)(uint32_t, uint32_t, uint32_t, void *))(0x030684b0u | 1))(0x30001, o, n, b)
#endif

static uint32_t rd32(const volatile uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }

static int fp_valid(void) { uint32_t s = FP[0]; return (s == MAG || s == NONE) && FP[5] == ~s; }
static void fp_state(uint32_t s) { FP[0] = s; FP[5] = ~s; }

/* first use after power-on: take the fingerprint saved in flash */
static void fp_ensure(void)
{
    if (fp_valid()) return;
    uint32_t b[0x400 / 4];
    BlkRead(0, b, sizeof b);
    const uint32_t *f = b + FP_OFF / 4;
    if (f[0] == MAG && f[5] == ~MAG) { for (int i = 1; i < 5; i++) FP[i] = f[i]; fp_state(MAG); }
    else fp_state(NONE);
}

static uint32_t fnv(uint32_t h, const uint8_t *p, int n, int skip_atime)
{
    for (int i = 0; i < n; i++) {
        /* exFAT File entry (0x85): skip set checksum 2..3, access time 0x10..0x13 and its UTC offset 0x18 */
        if (skip_atime && p[i & ~31] == 0x85) {
            int k = i & 31;
            if (k == 2 || k == 3 || (k >= 0x10 && k <= 0x13) || k == 0x18) continue;
        }
        h = (h ^ p[i]) * 16777619u;
    }
    return h;
}

/* fingerprint of the mounted volume; 0 when it is not an exFAT SD card */
static int fp_compute(uint32_t out[4])
{
    if (VOL[0] != 3 || SYS8(0x0E) != 4) return 0;
    uint32_t sh = VOL[2] | VOL[3] << 8, bs = VOL[4] | VOL[5] << 8;
    if (bs != 9 || sh > 16) return 0;
    uint32_t root = rd32(VI + 0x0D), ncl = rd32(VI + 0x1B), heap = rd32(VI + 0x1F), part = rd32(VI + 0x23);
    if (root < 2 || ncl < 2) return 0;

    uint32_t b[128];
    uint8_t *s = (uint8_t *)b;
    ReadSec(part, b);
    if (s[3] != 'E' || s[4] != 'X' || s[5] != 'F' || s[6] != 'A' || s[7] != 'T') return 0;
    out[0] = rd32(s + 0x64);                            /* volume serial */
    out[1] = ncl;

    uint32_t h = 2166136261u, bmc = 0, bml = 0, nsec = 1u << sh, lba = heap + ((root - 2) << sh);
    if (nsec > 64) nsec = 64;
    for (uint32_t i = 0; i < nsec; i++) {
        ReadSec(lba + i, b);
        int end = 0;
        for (int e = 0; e < 512; e += 32) {
            if (s[e] == 0) { end = 1; break; }
            if (s[e] == 0x81 && !bmc) { bmc = rd32(s + e + 0x14); bml = rd32(s + e + 0x18); }
            h = fnv(h, s + e, 32, 1);
        }
        if (end) break;
    }
    out[2] = h;
    if (bmc < 2 || !bml) return 0;

    uint32_t n = (bml + 511) >> 9;
    if (n > 16384) return 0;                            /* > 8 MB bitmap: not a card we expect */
    lba = heap + ((bmc - 2) << sh);
    h = 2166136261u;
    for (uint32_t i = 0; i < n; i++) { ReadSec(lba + i, b); h = fnv(h, s, 512, 0); }
    out[3] = h;
    return 1;
}

static int db_has_records(void)
{
    uint32_t rec[2];
    FlashRead(rd32(&SYS8(0x79)) << 9, 8, rec);
    return rec[0] != 0xFFFFFFFFu;
}

/* module 5 service, replaces "sys+0x42 = 0; sys+0x64 = 0; Build(); Post(0x18D)" */
void lib_gate(void)
{
    SYS16(0x42) = 0;
    SYS8(0x64) = 0;
    fp_ensure();
    uint32_t now[4];
    if (FP[0] == MAG && fp_compute(now) && now[0] == FP[1] && now[1] == FP[2] && now[2] == FP[3]
        && now[3] == FP[4] && db_has_records())
        return;                                         /* card unchanged since the last build: skip */
    fp_state(NONE);
    SaveConfig(0);                                      /* forget it in flash too, in case the build is cut off */
    Build();                                            /* ends with SaveConfig(0) */
    Post(0x18D);                                        /* stock: recount internal disk free space */
    if (fp_compute(now)) {
        for (int i = 0; i < 4; i++) FP[i + 1] = now[i];
        fp_state(MAG);
        SaveConfig(0);
    }
}

/* SaveSysConfig's block write (after it loads slot 2): append the fingerprint to the 0x800 buffer */
uint32_t cfg_write(uint32_t blk, uint8_t *buf, uint32_t len)
{
    fp_ensure();
    if (FP[0] == MAG) {
        uint32_t *f = (uint32_t *)(buf + FP_OFF);
        for (int i = 0; i < 6; i++) f[i] = FP[i];
    }
    return BlkWrite(blk, buf, len);
}

/* boot: stock's config loader (module 1) rewrites block 0 from the block it read, or from defaults when the
 * config was bad (0xFF there). Its copy is the truth after any reset, so RAM takes the fingerprint from it. */
uint32_t cfg_boot_write(uint32_t blk, uint8_t *buf, uint32_t len)
{
    const uint32_t *f = (const uint32_t *)(buf + FP_OFF);
    if (f[0] == MAG && f[5] == ~MAG) { for (int i = 1; i < 5; i++) FP[i] = f[i]; fp_state(MAG); }
    else fp_state(NONE);
    return BlkWrite(blk, buf, len);
}

/* Folders "Update Library?" Yes: replaces "sys+0x42 = 1"; always rebuild */
void lib_force(void)
{
    SYS16(0x42) = 1;
    fp_state(NONE);
}
