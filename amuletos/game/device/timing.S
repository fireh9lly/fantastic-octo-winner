@ v0.4 timing log (build 57): hook stubs in slot 2. Each one logs (tag, r0, r1) through timing.c tlog_hook,
@ replays the 4 bytes its hook replaced and returns to the site + 4.
@ Module 0 sites (TaskSwitch, ModuleOverlay, the audio refill interrupt) are patched at run time by m21_ext.c
@ tlog_install when the main menu opens: at boot those functions run before stock loads slot 2. Module 33 sites
@ (player thread init, Audio Start) are patched in the image by tools/patch_code.py timing.
    .syntax unified
    .thumb

    .macro STUB name, tag
    .section .text.\name
    .global \name
    .thumb_func
\name:
    push    {r0-r3, r12, lr}
    movs    r2, #\tag
    bl      tlog_hook
    pop     {r0-r3, r12, lr}
    .endm

    STUB t_task, 1                      @ TaskSwitch(id, arg) 0x030683F0 (build 59: the key press that opens Now Playing)
    ldr     r3, =0x03005800             @ replayed: "ldr r3, [pc, #0xb8]; strb r0, [r3]"
    strb    r0, [r3]
    ldr     r12, =0x030683F5
    bx      r12
    .ltorg

    STUB t_ovl, 2                       @ ModuleOverlay(module, type) 0x030686FA
    push.w  {r4-r11, lr}                @ replayed
    ldr     r12, =0x030686FF
    bx      r12
    .ltorg

    STUB t_irq, 6                       @ audio refill interrupt 0x03066480 (logged once after each start)
    push.w  {r4-r9, lr}                 @ replayed
    ldr     r12, =0x03066485
    bx      r12
    .ltorg

    STUB t_music, 3                     @ player thread init (MusicInit) m33 0x0308F070
    push.w  {r4-r9, lr}                 @ replayed
    ldr     r12, =0x0308DDD5
    bx      r12
    .ltorg

    STUB t_astart, 4                    @ Audio Start (file open) m33 0x0308D872
    push.w  {r4-r11, lr}                @ replayed
    ldr     r12, =0x0308C8F3
    bx      r12
    .ltorg
