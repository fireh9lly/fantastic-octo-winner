/*
 * D1: diagnostics through the internal disk's INQUIRY name.
 *
 * Loaded by stock through module slot 2 (see build_hook.py) and called in place
 * of `bl usb_send` at 0x03083978 (module 12). When the PC asks the internal
 * disk (stock block 0x03036790) for its identity, we answer with:
 *
 *   vendor   "SCHALAOS"
 *   product  "CCCCCCCC BBB AAA"   CCCCCCCC = system clock in Hz (hex), from
 *                                  *(0x030065C0 + 0x18), read by DelayMs/DelayUs
 *                                  BBB = ADC ch1 (8 face buttons), AAA = ADC ch0
 *                                  (battery), 10-bit, hex, from the sampler's
 *                                  table at 0x03005A8C (u16 per channel)
 *   revision "D1  "
 *
 * Read-only: no hardware register is touched. SD card INQUIRY is unchanged.
 * Windows shows it as "SCHALAOS CCCCCCCC BBB AAA USB Device".
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .equ STOCK_INQ,  0x03036790     @ internal-disk INQUIRY block
    .equ USB_SEND,   0x03081AA5     @ usb_send(ep r0, len r1, src r2) | Thumb
    .equ CLK_VAR,    0x030065C0     @ +0x18 = system clock (Hz)
    .equ ADC_TAB,    0x03005A8C     @ u16[ch]

    .section .text.d1, "ax"
    .global d1_send
    .type d1_send, %function
    .thumb_func
d1_send:
    ldr     r3, =STOCK_INQ
    cmp     r2, r3
    bne     pass
    push    {r0, r1, r4, r5, lr}
    adr     r4, inq

    ldr     r0, =CLK_VAR
    ldr     r0, [r0, #0x18]
    add     r1, r4, #16             @ product field
    movs    r2, #8
    bl      hex

    ldr     r5, =ADC_TAB
    ldrh    r0, [r5, #2]            @ ch1 buttons
    add     r1, r4, #25
    movs    r2, #3
    bl      hex

    ldrh    r0, [r5, #0]            @ ch0 battery
    add     r1, r4, #29
    movs    r2, #3
    bl      hex

    mov     r2, r4
    pop     {r0, r1, r4, r5, lr}
pass:
    ldr     r3, =USB_SEND
    bx      r3

/* hex(value r0, dst r1, digits r2): write r2 upper-case hex digits, MSB first */
    .thumb_func
hex:
    adds    r1, r1, r2
1:  and     r3, r0, #15
    cmp     r3, #10
    ite     lo
    addlo   r3, r3, #48             @ '0'
    addhs   r3, r3, #55             @ 'A' - 10
    strb    r3, [r1, #-1]!
    lsrs    r0, r0, #4
    subs    r2, r2, #1
    bne     1b
    bx      lr
    .ltorg

    .balign 4
inq:
    .byte   0x00, 0x80, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00   @ disk, removable, len 31
    .ascii  "SCHALAOS"                                       @ vendor   (8)  +8
    .ascii  "00000000 000 000"                               @ product (16) +16
    .ascii  "D1  "                                           @ revision (4) +32
