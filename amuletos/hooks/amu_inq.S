/*
 * amuletOS name for the internal disk (build 36; replaces the D1 diagnostics hook, which built the reply live and
 * took 0x8C bytes of slot 2). Loaded by stock through module slot 2 (build_hook.py) and called in place of
 * `bl usb_send` at 0x03083978 (module 12): when the PC asks the internal disk (stock block 0x03036790) for its
 * identity, send this reply instead. Windows shows "AMULETOS AP30 USB Device"; tools/inquiry.py reads it.
 * SD card INQUIRY is unchanged. Keep the revision field current with the release.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .equ STOCK_INQ,  0x03036790     @ internal-disk INQUIRY block
    .equ USB_SEND,   0x03081AA5     @ usb_send(ep r0, len r1, src r2) | Thumb

    .section .text.amu, "ax"
    .global amu_send
    .type amu_send, %function
    .thumb_func
amu_send:
    ldr     r3, =STOCK_INQ
    cmp     r2, r3
    bne     1f
    adr     r2, inq
1:  ldr     r3, =USB_SEND
    bx      r3
    .ltorg

    .balign 4
inq:
    .byte   0x00, 0x80, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00   @ disk, removable, len 31
    .ascii  "AMULETOS"                                       @ vendor   (8)  +8
    .ascii  "AP30            "                               @ product (16) +16
    .ascii  "0.3 "                                           @ revision (4) +32
