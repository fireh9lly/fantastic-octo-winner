@ Main menu (module 21) extension: carousel helpers (tools/extend_module.py, build 37; were in slot 2).
    .syntax unified
    .thumb

@ ---- v0.3 one-level carousel (main menu, module 21; tools/patch_code.py menu_carousel) ----
@ The carousel position is kept here across screens (0x0309FFE4, above slot 2): stock passes its own tile
@ numbers back to the menu, which no longer match the new order.
    .equ MENU_IDX, 0x03023B94
    .equ MENU_RAM, 0x0309FFE4
    .equ MENU_TAG, 0xCA5100

@ init: replaces "ldrb r1, [r4]; strh r1, [r0]" (r0 = &index); keeps r0
    .section .text.menu_idx_init
    .global menu_idx_init
    .thumb_func
menu_idx_init:
    push    {r0, lr}
    ldr     r1, =MENU_RAM
    ldr     r1, [r1]
    lsrs    r2, r1, #8
    ldr     r3, =(MENU_TAG >> 8)
    cmp     r2, r3
    bne     1f
    uxtb    r1, r1
    cmp     r1, #5                  @ five items (build 54)
    blo     2f
1:  movs    r1, #1                  @ fresh boot: Music (owner, build 33)
2:  strh    r1, [r0]
    bl      menu_art                @ grey Now Playing unless the player runs
    bl      tlog_install            @ v0.4 timing log: boot time (build 57, m21_ext.c)
    pop     {r0, pc}
    .ltorg

@ Left / Right: r0 = 4 (back) or 1 (on); five items, wrapping (build 54: + Games)
    .section .text.menu_step
    .global menu_step
    .thumb_func
menu_step:
    ldr     r2, =MENU_IDX
    ldrh    r1, [r2]
    add     r1, r0
    cmp     r1, #5
    it      hs
    subhs   r1, #5
    strh    r1, [r2]
    ldr     r2, =MENU_RAM
    ldr     r3, =MENU_TAG
    orr     r1, r1, r3
    str     r1, [r2]
    bx      lr
    .ltorg

@ main menu key dispatch fallthrough (module 21 0x03081B8A, was "b.w exit"): r1 = event - 0x40000010.
@ Start press (0x40000100, r1 = 0xF0) -> the Settings code at 0x03081BA6 (menu_carousel); anything else -> exit.
    .section .text.menu_key_more
    .global menu_key_more
    .thumb_func
menu_key_more:
    cmp     r1, #0xF0
    ite     eq
    ldreq   r0, =0x03081BA7
    ldrne   r0, =0x03081D75
    bx      r0
    .ltorg

