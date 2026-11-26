/* Stock V1.7.8 firmware entry points used by amuletOS modules (core A, module 0).
 * Addresses are run addresses (Thumb bit added where called). See docs/HARDWARE.md. */
#ifndef STOCK_H
#define STOCK_H
#include <stdint.h>

#define STOCK_FN(addr, ret, ...) ((ret (*)(__VA_ARGS__))((addr) | 1u))

/* input: event word = type << 24 | key code (0x002 Select, 0x004 Right, 0x008 Left,
 * 0x010 Up, 0x020 Down, 0x040 B, 0x080 A, 0x100 Start, 0x001 GPIO key) */
#define GetKey()            STOCK_FN(0x03063282, uint32_t, void)()
/* message bitset at 0x030252c0 */
#define SendMsg(id)         STOCK_FN(0x030681F0, void, uint32_t)(id)
#define GetMsg(id)          STOCK_FN(0x0306820C, uint32_t, uint32_t)(id)
/* window/task switch used by stock games on quit: (0xA, &(uint16_t)7) then service returns -1 */
#define TaskSwitch(id, arg) STOCK_FN(0x030683F0, void, uint32_t, void *)(id, arg)
/* drawing: current colour (RGB565) is shared by fill and text */
#define COLOR               (*(volatile uint16_t *)0x03024E2C)
#define FillRect(x0, y0, x1, y1) STOCK_FN(0x03064964, void, int, int, int, int)(x0, y0, x1, y1)
#define DrawText(x, y, s16) STOCK_FN(0x03064114, void, int, int, const uint16_t *)(x, y, s16)
/* stock game window enter/leave helpers (called by module 82's init/deinit) */
#define GameEnterA()        STOCK_FN(0x030667AE, void, void)()
#define GameEnterB()        STOCK_FN(0x03053822, void, void)()
#define GameLeaveA()        STOCK_FN(0x03066766, void, void)()
#define GameLeaveB()        STOCK_FN(0x03065EA0, void, void)()

#define RGB565(r, g, b) ((uint16_t)((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3)))

/* window descriptor: must be the first thing in the module's data (run 0x03025B88) */
typedef struct {
    uint32_t zero0, zero1;
    int32_t (*tick)(void);
    int32_t (*service)(void);
    void (*paint)(void);
    void (*init)(void);
    void (*deinit)(void);
} win_desc_t;

#endif
