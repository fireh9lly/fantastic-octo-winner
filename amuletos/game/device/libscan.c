/* Library scan skip (v0.3; split for V1.8.3). This file is the resident part, in module slot 2 with
 * np_helpers.c (tools/build_helpers.py); the fingerprint work is in libscan_ovl.c (module slot 29).
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
 * Saved: in RAM next to the slot-2 code (FP, survives until power-off) and in the system config flash
 * block 0 at offset 0x300 (stock writes 0x800 bytes but only the first 0x2F5 are config; the rest is
 * 0xFF). cfg_write appends it on every config save. lib_force (Folders "Update Library?" Yes) forgets it.
 * docs/HARDWARE.md, Library update trigger. No data or ZI: stack only (slot 2 is reloaded by stock).
 *
 * V1.8.3: the library builder (module 39) now ends at 0x0309FC9C, leaving 648 B of resident code space, so only
 * what must be callable at any time, or must survive the build, stays here. lib_gate loads the overlay
 * (libscan_ovl.c) before the build to compare fingerprints, and loads it again after the build (which overwrote
 * it) to save the new one. */
#include "libscan.h"

/* Resident code space is tight (every byte counted): the config hooks share one body and so one set of constants,
 * the 6-word copy and "no fingerprint" are shared calls, and FP is reached through one pointer (short offsets). */
#ifdef LIBSCAN_HOST
#define FPW ((uint32_t *)FP)
#else
/* FP's address as an absolute symbol rather than a constant: GCC then loads it once and uses short offsets, instead
 * of a shared 0x0309F000 base with 4-byte instructions */
__asm__(".global amu_fp\n.set amu_fp, 0x0309FFC0");
extern uint32_t amu_fp[6];
#define FPW amu_fp
#endif
__attribute__((noinline)) static void fp_copy(uint32_t *d, const uint32_t *s) { for (int i = 0; i < 6; i++) d[i] = s[i]; }
__attribute__((noinline)) static void fp_set(uint32_t *p, uint32_t s) { p[0] = s; p[5] = ~s; }

/* module 5 service, replaces "sys+0x42 = 0; sys+0x64 = 0; Build(); Post(0x18D)" */
void lib_gate(void)
{
    ModuleOverlay(LIB_SLOT, 7);
    if (!LIB_CHECK()) return;                          /* card unchanged since the last build: skip */
    Build();                                           /* ends with SaveConfig(0) */
    Post(0x18D);                                       /* stock: recount internal disk free space */
    ModuleOverlay(LIB_SLOT, 7);                        /* the build overwrote it */
    LIB_DONE();                                        /* fingerprint of the card as built, saved */
}

/* The two block-0 writes:
 * - boot (cfg_boot_write): stock's config loader (module 1) loads slot 2 and then rewrites block 0 from the block it
 *   read, or from defaults when the config was bad (0xFF there), on every boot (0x03082C80..0x03082CBA). Its copy is
 *   the truth after any reset, so RAM takes the fingerprint from it; anything but a valid "SKF1" record becomes
 *   "no fingerprint".
 * - config save (cfg_write, SaveSysConfig's block write after it loads slot 2): append the fingerprint to the 0x800
 *   buffer. RAM always holds a valid state after boot (v0.3 also re-read flash here if it didn't: no room for that
 *   now, and if RAM were ever corrupted the cost is one extra library build, as stock). */
__attribute__((noinline)) static uint32_t fp_io(uint32_t blk, uint8_t *buf, uint32_t len, int boot)
{
    uint32_t *f = (uint32_t *)(buf + FP_OFF), *p = FPW;
    if (boot) {
        fp_copy(p, f);
        if (p[0] != MAG || p[5] != ~MAG) fp_set(p, NONE);
    } else if (p[0] == MAG) fp_copy(f, p);              /* RAM holds MAG only together with ~MAG (fp_set, fp_copy) */
    return BlkWrite(blk, buf, len);
}
uint32_t cfg_write(uint32_t blk, uint8_t *buf, uint32_t len) { return fp_io(blk, buf, len, 0); }
uint32_t cfg_boot_write(uint32_t blk, uint8_t *buf, uint32_t len) { return fp_io(blk, buf, len, 1); }

/* Folders "Update Library?" Yes: replaces "sys+0x42 = 1"; always rebuild */
void lib_force(void)
{
    SYS16(0x42) = 1;
    fp_set(FPW, NONE);
}
