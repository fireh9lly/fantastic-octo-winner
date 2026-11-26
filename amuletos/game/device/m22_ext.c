/* Music menu (module 22) extension, linked after the module's own code by tools/extend_module.py (build 37).
 * Stack only, no data / rodata.
 *
 * Row icons: stock's row paint (0x03081EB0) never draws the table's icon ids, only the selection bar (image 184)
 * and the row text at x = 15 (0x030644A0). Both of its text calls (0x03081F54 full redraw, 0x03082034 selection
 * change) come here instead: draw the row's icon (art/pocket.py LIST_GLYPHS; +10 = the set on the selection bar),
 * then the text 26 px further right. */
#include <stdint.h>

#define TextBox(x, y, w, h, z, id) ((void (*)(int, int, int, int, int, int))(0x030644A0u | 1))(x, y, w, h, z, id)
#define DrawImage(i, x, y)         ((void (*)(uint32_t, int, int))(0x03064D20u | 1))(i, x, y)
#define SEL_ROW  (*(volatile uint8_t *)0x03023B92u)       /* m22 ZI: selected visible row */
#define TEXT_DY  0x42                                     /* stock: text y = 0x42 + 23 * row; row top = 0x3D + 23 * row */
#define SHIFT    26

extern const uint16_t music_menu[];                       /* m22_ext.S: {icon, text id, action} x 8 */

/* v0.4 timing log (build 57; timing.c / timing.S in slot 2). ModuleOverlay and the audio refill interrupt run
 * (and TaskSwitch, build 59) before stock loads slot 2 at boot, so they are hooked here, in RAM, once the Music menu draws (module 0 stays in
 * RAM until power-off; a site is only patched while it still holds stock's bytes). Here rather than in the main
 * menu: if writing module 0 ever faulted, only this menu would break, and a normal update would still work.
 * H_ names are slot-2 addresses (tools/extend_module.py, from helpers.json). */
#if AMU_TIMING                          /* dev builds only (-DAMU_TIMING=1) */
extern const char H_t_task[], H_t_ovl[], H_t_irq[];

static void hook_bw(uint32_t at, uint32_t to, uint32_t stock)
{
    volatile uint16_t *p = (volatile uint16_t *)at;
    if ((p[0] | (uint32_t)p[1] << 16) != stock) return;
    int32_t off = (int32_t)((to & ~1u) - (at + 4));
    uint32_t s = (uint32_t)off >> 31, i1 = ((uint32_t)off >> 23) & 1, i2 = ((uint32_t)off >> 22) & 1;
    uint32_t j1 = (i1 ^ s ^ 1) & 1, j2 = (i2 ^ s ^ 1) & 1;
    uint16_t h1 = (uint16_t)(0xF000 | s << 10 | (((uint32_t)off >> 12) & 0x3FF));
    uint16_t h2 = (uint16_t)(0x9000 | j1 << 13 | j2 << 11 | (((uint32_t)off >> 1) & 0x7FF));
    __asm volatile ("cpsid i" ::: "memory");
    p[0] = h1;
    p[1] = h2;
    __asm volatile ("dsb\n\tisb\n\tcpsie i" ::: "memory");
}

static void tlog_install(void)
{
    hook_bw(0x030680D4u, (uint32_t)H_t_task, 0x18702E4Bu);     /* TaskSwitch: ldr r3, [pc, #0xb8]; strb r0, [r3] */
    hook_bw(0x030683DEu, (uint32_t)H_t_ovl, 0x4FF0E92Du);      /* ModuleOverlay: push.w {r4-r11, lr} */
    hook_bw(0x030661A4u, (uint32_t)H_t_irq, 0x43F0E92Du);      /* audio refill: push.w {r4-r9, lr} */
}
#endif

void m22_row_text(int x, int y, int w, int h, int z, int id)
{
    uint32_t icon = 0;
#if AMU_TIMING
    tlog_install();
#endif
    for (int i = 0; i < 8; i++)
        if (music_menu[3 * i + 1] == (uint16_t)id) { icon = music_menu[3 * i]; break; }
    int row = (y - TEXT_DY) / 23;
    if (icon) DrawImage(icon + (row == SEL_ROW ? 10 : 0), 8, y - (TEXT_DY - 0x3D) - 1);
    TextBox(x + SHIFT, y, w - SHIFT, h, z, id);
}
