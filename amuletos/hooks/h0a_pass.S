/*
 * H0a: pure pass-through from the resident zero gap.
 *
 * Same site as H0 (bl usb_send @ 0x03083e48 -> here), but touches nothing:
 * it only tail-calls the original usb_send. If the disks enumerate with their
 * stock names, code in the gap executes and H0's hang came from the USB
 * transfer reading our INQUIRY block. If it still hangs, the gap does not
 * hold our code at run time.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .text.h0a, "ax"
    .global h0a_send
    .type h0a_send, %function
    .thumb_func
h0a_send:
    ldr     r3, =0x03081F75         @ usb_send | Thumb bit
    bx      r3
    .ltorg
