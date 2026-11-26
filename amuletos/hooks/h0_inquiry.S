/*
 * H0: prove injected code runs from the resident zero gap.
 *
 * Linked at 0x030A7B8C (code.bin 0x57B8C), a 16 KB zero gap that the boot ROM
 * loads into RAM with the rest of the code image and that nothing references.
 *
 * Stock module 12 (USB mass storage) sends the INQUIRY response with
 *     bl usb_send   @ 0x03083978   (usb_send = 0x03081AA4, r0 ep, r1 len, r2 src)
 * The build redirects that bl to h0_send below. If the source is the internal
 * disk's identity block (0x03036790) we substitute our own, then tail-call the
 * original routine, so behaviour is otherwise unchanged.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .text.h0, "ax"
    .global h0_send
    .type h0_send, %function
    .thumb_func
h0_send:
    ldr     r3, =0x03036790         @ stock internal-disk INQUIRY block
    cmp     r2, r3
    bne     1f
    adr     r2, h0_inquiry          @ our block instead
1:  ldr     r3, =0x03081AA5         @ usb_send | Thumb bit
    bx      r3
    .ltorg

    .balign 4
h0_inquiry:
    .byte   0x00, 0x80, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00   @ disk, removable, len 31
    .ascii  "SCHALAOS"                                       @ vendor   (8)
    .ascii  "ZEAL HOOK       "                               @ product (16)
    .ascii  "0.1 "                                           @ revision (4)
