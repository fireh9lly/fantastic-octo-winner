/* Main menu (module 21) extension, linked after the module's own code by tools/extend_module.py (build 37; was in
 * slot 2). Stack only, no data / rodata. */
#include <stdint.h>

/* v0.3 main menu (module 21): the Now Playing card is greyed out and inert while the player thread is not
 * running (fresh boot: stock's Now Playing would open on an empty record and show an error). Same running test
 * as stock's Music menu "Now playing" item. Module 21's tile table {1, i, i, 0, image, text} x6 sits in RAM at
 * 0x03025BA4 and paint reads the image from it, so we set the image ids (art/pocket.py STATES / GREY_STATES).
 * Build 54: five cards, Now Playing 16 (greyed 8), Music 14, Blockz 18, Games 20, Library 22 (greyed 24: its right
 * side icon is Now Playing). */
#define PLAYER_ON() (((uint32_t (*)(uint32_t, uint32_t))(0x03057F58u | 1))(*(volatile uint32_t *)0x030252FCu, \
                                                                          0x03038230u) == 1)
#define MENU_IMG(k) (*(volatile uint16_t *)(0x03025BA4u + 8u * (k) + 4u))

void menu_art(void)
{
    uint32_t on = PLAYER_ON();
    MENU_IMG(0) = on ? 16 : 8;
    MENU_IMG(1) = 14;
    MENU_IMG(2) = 18;
    MENU_IMG(3) = 20;
    MENU_IMG(4) = on ? 22 : 24;
}

/* v0.4 timing log (build 57; timing.c in slot 2): the first main menu after power-on = boot time (tag 8). The hooks
 * themselves are installed from the Music menu (m22_ext.c tlog_install), away from the boot path. H_ names are
 * slot-2 addresses (tools/extend_module.py, from helpers.json). */
extern const char H_tlog_hook[];

void tlog_install(void)                 /* dev builds only (-DAMU_TIMING=1); empty in a release */
{
#if AMU_TIMING
    ((void (*)(uint32_t, uint32_t, uint32_t))((uint32_t)H_tlog_hook | 1))(0, 0, 8);
#endif
}

/* Games tile action (build 54, patch_code.py menu_carousel): the Game Boy list, task 20 (game/device/gbprobe.c) */
void menu_games(void)
{
    ((void (*)(uint32_t, void *))(0x030683F0u | 1))(20, 0);
}

/* Now Playing tile action (patch_code.py menu_carousel): open it while the player runs, else refresh the art
 * (the player may have stopped while the menu was up) and stay. */
void menu_np(void)
{
    if (PLAYER_ON()) {
        ((void (*)(uint32_t, void *))(0x030683F0u | 1))(3, 0);
        return;
    }
    menu_art();
    ((void (*)(uint32_t))(0x030681F0u | 1))(0x2D);   /* repaint the card */
}

