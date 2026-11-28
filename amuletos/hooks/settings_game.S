@ Settings (module 32): the "Game" item (text 0x110) opens the Games screen (task 20, game/device/gbprobe.c)
@ instead of the stock game list, which also lists the games whose tasks amuletOS reuses (build 56; see
@ tools/patch_code.py settings_game). Placed at 0x030840EC, the launch code of the stock games on tasks 21..31,
@ whose menu cases settings_game points at the task-20 case first.
@ MoonletOS (2026-11-28): the root "Language" item (text 0xF6, relabelled "Key Test" by tools/patch_text.py; the
@ firmware forces English at boot, so the language list did nothing lasting) opens the key test: the same task 20
@ with the argument "KEYT" (game/device/keytest.c). TaskSwitch copies 28 bytes from the tag; the rest is code.
@ Entered from the key handler's "enter item" step (0x0308294C, r4 = current menu level: +5 selection,
@ +8 node with child text ids at +0x10).
    .syntax unified
    .thumb
    .equ ENTER,      0x0308215E     @ stock: enter item (r0 = text id), returns the key result
    .equ AFTER,      0x0308295C     @ stock: "mov r5, r0" after that call
    .equ EXIT,       0x030829DA     @ stock: key handler epilogue, returns r5
    .equ TASKSWITCH, 0x030683F0     @ (task, arg*)

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
    cmp     r0, #0xF6               @ "Language", shown as "Key Test"
    beq     2f
    bl      ENTER
    b.w     AFTER
1:  movs    r1, #0                  @ Games screen: no argument
    b       3f
2:  adr     r1, keytag              @ key test
3:  movs    r0, #20
    bl      TASKSWITCH
    movs    r5, #1
    b.w     EXIT
    .balign 4
keytag:
    .ascii  "KEYT"
