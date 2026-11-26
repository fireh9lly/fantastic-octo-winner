@ Stock Now Playing (module 27): show the title tag on the scrolling line, falling back to the
@ file name when a song has no title. Placed in module 27's own dead code (the album/genre
@ lines, skipped by np_hide_album_genre) at 0x03082F00; see tools/patch_code.py np_title_tag.
@ Title: tag record 0x0304a610 + 0x60 (filled by the tag reader at play start, 127 UTF-16 max).
@ File name: 0x0304a4e0 (library record +0x400, 64 UTF-16 max).
    .syntax unified
    .thumb
    .equ TITLE, 0x0304A670
    .equ FNAME, 0x0304a4e0
    .equ TEXTW, 0x0306402E          @ text width (r0 = str16)
    .equ DRAW,  0x03064252          @ text in rect (r0, r1 = rect*, r2 = str16, r3 = mode)

    .text
    .global np_fill_strlen, np_fill_draw

    .thumb_func
fill:                               @ title empty -> copy the file name in; clobbers r0-r3
    ldr     r0, =TITLE
    ldrh    r1, [r0]
    cbnz    r1, 2f
    ldr     r1, =FNAME
    movs    r3, #63
1:  ldrh    r2, [r1], #2
    strh    r2, [r0], #2
    cbz     r2, 2f
    subs    r3, #1
    bne     1b
    movs    r2, #0
    strh    r2, [r0]
2:  bx      lr

    .thumb_func
np_fill_strlen:                     @ replaces "ldr r0, =FNAME; bl TEXTW" (mode 0, before the draw)
    push    {r4, lr}
    bl      fill
    pop     {r4, lr}
    ldr     r0, =TITLE
    b.w     TEXTW

    .thumb_func
np_fill_draw:                       @ replaces the mode-1 draw of the long file name
    push    {r4, lr}
    bl      fill
    pop     {r4, lr}
    add     r1, sp, #8              @ caller's rect on its stack (sp unchanged after the pop)
    strh.w  r4, [r8]                @ caller's colour store, as in the original sequence
    movs    r3, #2
    ldr     r2, =TITLE
    mov     r0, r1
    b.w     DRAW

    .ltorg
