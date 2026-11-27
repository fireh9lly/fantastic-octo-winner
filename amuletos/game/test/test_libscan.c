/* Host test for the library scan skip (game/device/libscan.c, resident, and libscan_ovl.c, the overlay it loads
 * around a build): a simulated exFAT SD card, flash block 0 and the stock calls they use (sector read, config save,
 * library build). On the PC the overlay is simply linked in. Run by `game/build.py test`. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define LIBSCAN_HOST
static uint8_t  sys_[0x400], vol_[0x40], disk[2048][512], blk0[0x800];
static uint32_t fp_[6];
static int builds, saves, db_empty, flash_fp_during_build = -1;

#define SYS8(o)   (sys_[o])
#define SYS16(o)  (*(uint16_t *)&sys_[o])
#define VOL       vol_
#define VI        (vol_ + 0x0C)
#define FP        fp_
static uint32_t ReadSec(uint32_t lba, void *b) { memcpy(b, disk[lba], 512); return 0; }
static void BlkRead(uint32_t n, void *b, uint32_t l) { memcpy(b, blk0, l); }
static uint32_t BlkWrite(uint32_t n, void *b, uint32_t l) { memcpy(blk0, b, l); return 0; }
static void SaveConfig(uint32_t f);
static void Build(void);
static void Post(uint32_t m) { (void)m; }
static uint32_t FlashRead(uint32_t o, uint32_t n, void *b) { memset(b, db_empty ? 0xFF : 0x11, n); return 0; }
static int overlay_loads;
#define ModuleOverlay(n, f) (overlay_loads++, 0)
uint32_t lib_check(void);
void lib_done(void);
#define LIB_SLOT    29
#define LIB_CHECK() lib_check()
#define LIB_DONE()  lib_done()
#include "../device/libscan.c"
#include "../device/libscan_ovl.c"

#define PART 64
#define HEAP (PART + 128)          /* absolute sector of cluster 2 */
#define SH 3                       /* 8 sectors per cluster */
#define ROOT 5
static uint8_t *clus(uint32_t c) { return disk[HEAP + ((c - 2) << SH)]; }

/* stock SaveSysConfig: 0xFF buffer, config copy, block write through the patched call */
static void SaveConfig(uint32_t f) { uint8_t b[0x800]; memset(b, 0xFF, sizeof b); memcpy(b, sys_, 0x2F5); cfg_write(0, b, 0x800); saves++; }
static void Build(void)
{
    const uint32_t *f = (const uint32_t *)(blk0 + FP_OFF);
    flash_fp_during_build = f[0] == MAG;
    builds++;
    SaveConfig(0);
}

static void card(uint32_t serial)
{
    memset(disk, 0, sizeof disk);
    uint8_t *bs = disk[PART];
    memcpy(bs + 3, "EXFAT   ", 8);
    memcpy(bs + 0x64, &serial, 4);
    uint8_t *r = clus(ROOT);
    r[0] = 0x83;                                           /* label */
    r[32] = 0x81; r[32 + 0x14] = 2; r[32 + 0x18] = 50;     /* bitmap: cluster 2, 50 bytes */
    r[64] = 0x82;                                          /* upcase */
    r[96] = 0x85; r[96 + 0x0C] = 0x21; r[96 + 0x10] = 0x31; /* folder: modified 0x0C, accessed 0x10 */
    r[128] = 0xC0; r[160] = 0xC1; r[162] = 'A';
    memset(clus(2), 0x3F, 50);
    vol_[0] = 3; vol_[2] = SH; vol_[4] = 9;
    uint32_t v[] = {ROOT, 400, HEAP, PART};
    int off[] = {0x0D, 0x1B, 0x1F, 0x23};
    for (int i = 0; i < 4; i++) memcpy(VI + off[i], &v[i], 4);
    sys_[0x0E] = 4;
}

static void boot(void)                       /* power cycle: RAM garbage, stock's boot rewrite of block 0 */
{
    for (int i = 0; i < 6; i++) fp_[i] = 0xA5A5A5A5u * (i + 3);
    uint8_t b[0x800]; memcpy(b, blk0, sizeof b);
    cfg_boot_write(0, b, 0x800);
}

static int fails;
static void gate_expect(const char *what, int build)
{
    int before = builds;
    SYS16(0x42) = 1;
    lib_gate();
    int did = builds - before;
    if (did != build || SYS16(0x42) != 0) { printf("FAIL %s: build %d, expected %d\n", what, did, build); fails++; }
    else printf("ok   %s: %s\n", what, build ? "build" : "skip");
}

int main(void)
{
    memset(blk0, 0xFF, sizeof blk0);
    card(0xC0FFEE01);
    boot();
    gate_expect("first boot, nothing saved", 1);
    if (flash_fp_during_build != 0) { printf("FAIL old fingerprint still in flash during the build\n"); fails++; }
    boot();
    gate_expect("reboot, card unchanged", 0);
    gate_expect("again, same session", 0);
    clus(ROOT)[96 + 0x10] = 0x99; clus(ROOT)[96 + 0x02] ^= 0x5A;
    gate_expect("PC only read a folder (access time, checksum)", 0);
    clus(ROOT)[96 + 0x0C] = 0x22;
    gate_expect("folder modified time changed", 1);
    gate_expect("after that build", 0);
    clus(2)[7] ^= 0x40;
    gate_expect("bitmap changed (file added or rewritten)", 1);
    clus(ROOT)[192] = 0x85; clus(ROOT)[224] = 0xC0;
    gate_expect("new top-level folder", 1);
    boot();
    gate_expect("reboot after those", 0);
    lib_force(); SYS16(0x42) = 0;
    gate_expect("Folders > Update Library? Yes", 1);
    gate_expect("after forced build", 0);
    db_empty = 1;
    gate_expect("library database empty", 1);
    db_empty = 0;

    /* RAM lost the fingerprint between boots (can't happen: every boot sets it; V1.8.3 has no room for v0.3's flash
     * re-read in the config save): that save drops it, so the next gate builds once, as stock would */
    for (int i = 0; i < 6; i++) fp_[i] = 0x5A5A5A5Au * (i + 1);
    SaveConfig(1);
    boot();
    gate_expect("save with RAM corrupted, then reboot (one extra build)", 1);
    gate_expect("after that build", 0);

    /* stock reset its config to defaults (0xFF after the config): stale RAM must not skip */
    memset(blk0 + 0x2F5, 0xFF, 0x800 - 0x2F5);
    { uint8_t b[0x800]; memcpy(b, blk0, sizeof b); cfg_boot_write(0, b, 0x800); }
    gate_expect("config reset to defaults (warm reset, RAM kept)", 1);

    card(0xC0FFEE02);
    gate_expect("different card", 1);
    gate_expect("that card again", 0);
    sys_[0x0E] = 2;
    gate_expect("internal disk", 1);
    gate_expect("internal disk again (no fingerprint: always)", 1);
    card(0xC0FFEE02); vol_[0] = 2;
    gate_expect("FAT32 card (always builds, as stock)", 1);

    /* the overlay is loaded before every gate, and again after a build (the build overwrites it) */
    card(0xC0FFEE03);
    gate_expect("exFAT card again", 1);
    { int l0 = overlay_loads, b0 = builds; gate_expect("overlay loads: skip", 0);
      if (overlay_loads - l0 != 1) { printf("FAIL skip loaded the overlay %d times\n", overlay_loads - l0); fails++; }
      lib_force(); SYS16(0x42) = 0; l0 = overlay_loads; gate_expect("overlay loads: build", 1);
      if (overlay_loads - l0 != 2 || builds - b0 != 1) { printf("FAIL build loaded the overlay %d times\n", overlay_loads - l0); fails++; } }

    printf("%s: %d failure(s), %d builds, %d saves\n", fails ? "FAILED" : "libscan ok", fails, builds, saves);
    return fails != 0;
}
