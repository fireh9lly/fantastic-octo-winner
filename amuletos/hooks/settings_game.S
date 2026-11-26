@ Settings (module 32): the "Game" item (text 0x110) opens the Games screen (task 20, game/device/gbprobe.c)
@ instead of the stock game list, which also lists the games whose tasks amuletOS reuses (build 56; see
@ tools/patch_code.py settings_game). Placed at 0x03083C1C, the launch code of the stock games on tasks 21..31,
@ whose menu cases settings_game points at the task-20 case first.
@ Entered from the key handler's "enter item" step (0x0308247C, r4 = current menu level: +5 selection,
@ +8 node with child text ids at +0x10).
    .syntax unified
    .thumb
    .equ ENTER,      0x03081C8E     @ stock: enter item (r0 = text id), returns the key result
    .equ AFTER,      0x0308248C     @ stock: "mov r5, r0" after that call
    .equ EXIT,       0x0308250A     @ stock: key handler epilogue, returns r5
    .equ TASKSWITCH, 0x030680D4     @ (task, arg*)

    .text
    .global settings_enter

    .thumb_func
settings_enter:
    ldrb    r1, [r4, #5]
    ldr     r0, [r4, #8]
    add.w   r0, r0, r1, lsl #1
    ldrh    r0, [r0, #0x10]         @ text id of the selected item
    cmp.w   r0, #0x110              @ "Game"
    beq     1f
    bl      ENTER
    b.w     AFTER
1:  movs    r1, #0
    movs    r0, #20                 @ Games screen
    bl      TASKSWITCH
    movs    r5, #1
    b.w     EXIT
