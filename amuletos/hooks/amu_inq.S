/*
 * MoonletOS name for the internal disk (amuletOS build 36 added this hook as "AMULETOS"; it replaced the D1
 * diagnostics hook, which built the reply live and took 0x8C bytes of slot 2). Loaded by stock through module
 * slot 2 (build_hook.py) and called in place of `bl usb_send` at 0x03083e48 (module 12): when the PC asks the
 * internal disk (stock block 0x030387d0) for its identity, send this reply instead. The vendor field holds 8
 * characters, so the name is split over vendor and product: Windows shows "MOONLET OS AP30 USB Device";
 * tools/inquiry.py reads it. SD card INQUIRY is unchanged. Keep the revision field current with the release.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .equ STOCK_INQ,  0x030387d0     @ internal-disk INQUIRY block
    .equ USB_SEND,   0x03081F75     @ usb_send(ep r0, len r1, src r2) | Thumb

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
    .ascii  "MOONLET "                                       @ vendor   (8)  +8
    .ascii  "OS AP30         "                               @ product (16) +16
    .ascii  "0.3 "                                           @ revision (4) +32
