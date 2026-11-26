#!/usr/bin/env python3
"""Send a fresh SCSI INQUIRY to a drive letter and print the identity (Windows).

  inquiry.py D [--loop N] [--interval S]

Used with diagnostic hooks (D1) that report values in the INQUIRY name.
Uses IOCTL_SCSI_PASS_THROUGH on \\\\.\\D: (works without admin on removable drives
where Windows allows it).
"""
import ctypes, ctypes.wintypes as wt, sys, time, argparse

IOCTL_SCSI_PASS_THROUGH = 0x4D004
GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
FILE_SHARE_RW = 3
OPEN_EXISTING = 3

class SPT(ctypes.Structure):
    _fields_ = [("Length", ctypes.c_ushort), ("ScsiStatus", ctypes.c_ubyte), ("PathId", ctypes.c_ubyte),
                ("TargetId", ctypes.c_ubyte), ("Lun", ctypes.c_ubyte), ("CdbLength", ctypes.c_ubyte),
                ("SenseInfoLength", ctypes.c_ubyte), ("DataIn", ctypes.c_ubyte),
                ("DataTransferLength", ctypes.c_ulong), ("TimeOutValue", ctypes.c_ulong),
                ("DataBufferOffset", ctypes.c_size_t), ("SenseInfoOffset", ctypes.c_ulong),
                ("Cdb", ctypes.c_ubyte * 16)]

class SPTB(ctypes.Structure):
    _fields_ = [("spt", SPT), ("sense", ctypes.c_ubyte * 32), ("data", ctypes.c_ubyte * 96)]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
k32.DeviceIoControl.argtypes = [wt.HANDLE, wt.DWORD, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, wt.DWORD,
                                ctypes.POINTER(wt.DWORD), ctypes.c_void_p]

def inquiry(letter):
    h = k32.CreateFileW(f"\\\\.\\{letter}:", GENERIC_READ | GENERIC_WRITE, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    if h in (None, wt.HANDLE(-1).value):
        raise OSError(ctypes.get_last_error(), "CreateFile failed")
    try:
        b = SPTB()
        b.spt.Length = ctypes.sizeof(SPT)
        b.spt.CdbLength = 6
        b.spt.SenseInfoLength = 32
        b.spt.DataIn = 1
        b.spt.DataTransferLength = 36
        b.spt.TimeOutValue = 5
        b.spt.SenseInfoOffset = SPTB.sense.offset
        b.spt.DataBufferOffset = SPTB.data.offset
        b.spt.Cdb[0] = 0x12          # INQUIRY
        b.spt.Cdb[4] = 36            # allocation length
        n = wt.DWORD()
        if not k32.DeviceIoControl(h, IOCTL_SCSI_PASS_THROUGH, ctypes.byref(b), ctypes.sizeof(b),
                                   ctypes.byref(b), ctypes.sizeof(b), ctypes.byref(n), None):
            raise OSError(ctypes.get_last_error(), "DeviceIoControl failed")
        return bytes(b.data[:36])
    finally:
        k32.CloseHandle(h)

def main():
    p = argparse.ArgumentParser(); p.add_argument("letter")
    p.add_argument("--loop", type=int, default=1); p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--changes", action="store_true", help="print only when the identity changes, with time")
    a = p.parse_args()
    if a.changes:
        t0, last = time.time(), None
        for i in range(a.loop):
            d = inquiry(a.letter.rstrip(":"))[16:32].decode("ascii", "replace")
            if d != last:
                print(f"{time.time() - t0:6.1f}s  {d}", flush=True); last = d
            time.sleep(a.interval)
        return
    for i in range(a.loop):
        d = inquiry(a.letter.rstrip(":"))
        print(f"{d[8:16].decode('ascii', 'replace')} | {d[16:32].decode('ascii', 'replace')} | {d[32:36].decode('ascii', 'replace')}", flush=True)
        if i + 1 < a.loop: time.sleep(a.interval)

if __name__ == "__main__":
    main()
