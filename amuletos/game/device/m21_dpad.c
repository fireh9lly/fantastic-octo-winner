/* Four-way main menu: device glue for module 21 (amuletOS main menu), to be linked with
 * tools/extend_module.py next to game/device/m21_ext.c. DRAFT: the hook sites in tools/patch_code.py are not
 * wired yet (see ../../README.md, "Still to do"); this file compiles for the Cortex-M3 but has not run on a device.
 *
 * Stock dispatch (docs/HARDWARE.md, module 21 service 0x030819E4): Up/Down press + repeat -> 0x03081CDE, Right ->
 * 0x03081CF0, Left -> 0x03081D1C, A -> tile action 0x0308188E. The v0.3 carousel (patch menu_carousel) turned
 * Right/Left into menu_step and Up/Down into "do nothing". The D-pad patch sends the four PRESS events (0x40000010
 * Up, 0x40000004 Right, 0x40000020 Down, 0x40000008 Left; repeats 0x30... are ignored) to menu_dir below, then:
 *   return 0 -> repaint (the carousel's own repaint path, 0x03081CD6), image = STATES[highlighted direction]
 *   return 1 -> run the tile action for the highlighted item (the A path)
 */
#include <stdint.h>
#include "../dpad.h"

/* stock's 10 ms tick counter (game/device/timing.c) */
#define SYS_TICKS   (*(volatile uint32_t *)0x0302288Cu)
/* carousel index (module 21 RAM) and the persisted position word (m21_ext.S MENU_IDX / MENU_RAM / MENU_TAG) */
#define MENU_IDX    (*(volatile uint16_t *)0x03023B94u)
#define MENU_RAM    (*(volatile uint32_t *)0x0309FFE4u)
#define MENU_TAG    0xCA5100u
/* tap state across calls. TO VERIFY: the word after MENU_RAM is assumed free like MENU_RAM itself (above slot 2) */
#define DPAD_STATE  ((dpad_t *)0x0309FFE8u)
#define DPAD_TAG    (*(volatile uint32_t *)0x0309FFF0u)
#define DPAD_MAGIC  0xD9AD0001u

/* direction -> carousel item (its tile action and image): Up Now Playing, Right Music, Down Games, Left Blockz.
 * Must match art/dpad_menu.py ITEMS. Change both together to remap. One nibble per direction (Up = lowest), kept
 * in an immediate because module 21's extension has no data or rodata section (m21_ext.c). */
#define ITEM_MAP    0x2310u
#define ITEM_OF(dir) ((ITEM_MAP >> (4u * (unsigned)(dir))) & 0xFu)

static dpad_t *state(void)
{
    dpad_t *d = DPAD_STATE;
    if (DPAD_TAG != DPAD_MAGIC) {             /* fresh boot: start on Music, like the carousel */
        dpad_init(d, DPAD_RIGHT);
        DPAD_TAG = DPAD_MAGIC;
    }
    return d;
}

/* r0 = direction (DPAD_UP..DPAD_LEFT). Sets the highlighted item; returns 1 to open it. */
int menu_dir(int dir)
{
    dpad_t *d = state();
    int r = dpad_tap(d, dir, SYS_TICKS * 10u);
    uint32_t item = ITEM_OF(d->sel);
    MENU_IDX = (uint16_t)item;
    MENU_RAM = MENU_TAG | item;
    return r == DPAD_OPEN;
}

/* any other key in the menu (A, B, Start, wheel) cancels a pending double tap */
void menu_other_key(void)
{
    dpad_cancel(state());
}
