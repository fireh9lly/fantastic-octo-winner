@ Slot-2 assembly helpers (playlist song-change hooks), linked with np_helpers.c and libscan.c. The main menu and
@ Music menu helpers moved to their modules in build 37 (m21_ext.S, m22_ext.S; tools/extend_module.py).
    .syntax unified
    .thumb

@ ---- v0.3 M3U playlists (build 35; tools/patch_code.py playlists) ----
@ 0x0305E930 entry (one step of the music source record, r0 = record, r1 = direction), was
@ "push.w {r3-r11, lr}": pl_step (np_helpers.c) handles playlist songs (return 0 = success, like stock's step).
    .section .text.pl_step_hook
    .global pl_step_hook
    .thumb_func
pl_step_hook:
    push    {r0-r3, r12, lr}
#if AMU_TIMING                      /* dev builds only (-DAMU_TIMING=1): timing log, track step (timing.c) */
    movs    r2, #7
    bl      tlog_hook
    ldmia   sp, {r0, r1}
#endif
    bl      pl_step
    cmp     r0, #0
    pop     {r0-r3, r12, lr}
    bne     1f
    push.w  {r3, r4, r5, r6, r7, r8, r9, r10, r11, lr}
    ldr     r12, =0x0305E935        @ stock's step after its push
    bx      r12
1:  movs    r0, #0
    bx      lr
    .ltorg

@ Player thread init (module 33, r7 = music source record). For source 0x63 stock counts the current Folders folder
@ (0x0308DD48 -> record total) and seeks to the requested index (0x0305E85C -> record cluster / file number), which
@ for a playlist (or Blockz) uses a stale browser state: hang or wrong file (build 35). While pl_active, skip both.
@ 0x0308DF12, was "ldrh.w r0, [r7, #0xf2]; cmp r0, #0x63; beq 0x0308DF26":
    .equ PL_COUNT_SKIP,  0x0308DF40
    .equ PL_COUNT_STOCK, 0x0308DF26
    .equ PL_CMP6,        0x0308DF1A
    .equ PL_SEEK_SKIP,   0x0308E014
    .equ PL_SEEK_STOCK,  0x0308DFFA
    .equ PL_LIBRARY,     0x0308DFC4
    .section .text.pl_init_count
    .global pl_init_count
    .thumb_func
pl_init_count:
    bl      pl_active
    cbnz    r0, 1f
    ldrh.w  r0, [r7, #0xf2]
    cmp     r0, #0x63
    beq.w   PL_COUNT_STOCK          @ stock: count
    b.w     PL_CMP6                 @ stock: "cmp r0, #6" with r0 = source
1:  b.w     PL_COUNT_SKIP           @ playlist: past the folder count

@ 0x0308DFB8, was "ldrh.w r0, [r7, #0xf2]; cmp r0, #0x63; it ne; cmpne r0, #6; beq 0x0308DFFA":
    .section .text.pl_init_seek
    .global pl_init_seek
    .thumb_func
pl_init_seek:
    bl      pl_active
    cbnz    r0, 1f
    ldrh.w  r0, [r7, #0xf2]
    cmp     r0, #0x63
    it      ne
    cmpne   r0, #6
    beq.w   PL_SEEK_STOCK           @ stock: seek
    b.w     PL_LIBRARY              @ stock: library sources
1:  b.w     PL_SEEK_SKIP            @ playlist: past the seek
