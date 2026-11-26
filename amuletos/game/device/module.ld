/* Overlay window module replacing stock module 82 (docs/HANDOFF.md 6.2).
 * Code runs in the overlay window; keep it below the music module (0x0308BF84).
 * Data + ZI: the overlay data window from 0x03023B48 holds at least 0xD12 bytes (stock module 98); each module's
 * own limit is checked by tools/build_module.py --data-max (Blockz: 0x708, its stock footprint). */
MEMORY
{
    CODE (rx)  : ORIGIN = 0x030815C4, LENGTH = 0x0308BF84 - 0x030815C4
    DATA (rw)  : ORIGIN = 0x03023B48, LENGTH = 0xD12
}

SECTIONS
{
    .text : ALIGN(4)
    {
        *(.text .text.*)
        *(.rodata .rodata.*)
        . = ALIGN(4);
        _text_end = .;
    } > CODE

    .data : ALIGN(4)
    {
        KEEP(*(.desc))
        *(.data .data.*)
        . = ALIGN(4);
    } > DATA

    .bss (NOLOAD) : ALIGN(4)
    {
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
    } > DATA

    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.ARM.attributes) }
}
