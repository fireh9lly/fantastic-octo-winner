@ Library scan overlay (module slot 29): entry table at its run address, LIB_RUN in libscan.h. Listed first when
@ linking, so it lands at the start; tools/build_overlay.py --entry checks that.
    .syntax unified
    .thumb
    .section .text.0entry, "ax"
    .global lib_entry
lib_entry:
    b.w     lib_check               @ LIB_RUN:     uint32_t lib_check(void)
    b.w     lib_done                @ LIB_RUN + 4: void lib_done(void)
