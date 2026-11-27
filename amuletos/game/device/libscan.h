/* Library scan skip: shared by the resident part (libscan.c, module slot 2) and the overlay that does the work
 * (libscan_ovl.c, module slot 29, loaded only around a library build). See libscan.c for the design. */
#ifndef LIBSCAN_H
#define LIBSCAN_H
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
#define ModuleOverlay(n, f) ((uint32_t (*)(uint32_t, uint32_t))(0x03068800u | 1))(n, f)

/* The overlay: module slot 29 (empty in stock, which never loads it), run address = the end of module 5's code,
 * where stock loads module 39 (the build) and module 7 (after it). Module 5 only uses that RAM during and after
 * the build, so the overlay can sit there just before the build and just after it. Entry table at its start
 * (libscan_ovl.S): LIB_RUN = lib_check, LIB_RUN + 4 = lib_done. */
#define LIB_SLOT  29
#define LIB_RUN   0x03081DF4u
#define LIB_CHECK() ((uint32_t (*)(void))((LIB_RUN) | 1))()
#define LIB_DONE()  ((void (*)(void))((LIB_RUN + 4) | 1))()
#endif

static inline int fp_valid(void) { uint32_t s = FP[0]; return (s == MAG || s == NONE) && FP[5] == ~s; }
static inline void fp_state(uint32_t s) { FP[0] = s; FP[5] = ~s; }

#endif
