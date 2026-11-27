/* Library scan skip, the part that is only loaded around a library build: module slot 44, linked at LIB_RUN
 * (libscan.h; tools/build_overlay.py). lib_gate (libscan.c, resident) loads it before the build to decide, and
 * again after the build to save the new fingerprint. Entry table first (libscan_ovl.S). No data or ZI: stack only. */
#include "libscan.h"

static uint32_t rd32(const volatile uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }

/* RAM lost its fingerprint (it shouldn't: cfg_boot_write sets it at boot): take the one saved in flash */
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

/* before the build: 0 = card unchanged since the last build, skip it; 1 = build (fingerprint forgotten first, in
 * RAM and in flash, in case the build is cut off) */
uint32_t lib_check(void)
{
    SYS16(0x42) = 0;
    SYS8(0x64) = 0;
    fp_ensure();
    uint32_t now[4];
    if (FP[0] == MAG && fp_compute(now) && now[0] == FP[1] && now[1] == FP[2] && now[2] == FP[3]
        && now[3] == FP[4] && db_has_records())
        return 0;
    fp_state(NONE);
    SaveConfig(0);
    return 1;
}

/* after the build: the card's fingerprint as it is now, saved with the config */
void lib_done(void)
{
    uint32_t now[4];
    if (fp_compute(now)) {
        for (int i = 0; i < 4; i++) FP[i + 1] = now[i];
        fp_state(MAG);
        SaveConfig(0);
    }
}
