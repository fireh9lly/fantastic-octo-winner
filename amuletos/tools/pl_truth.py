#!/usr/bin/env python3
"""Independent check for the playlist resolver (game/device/pl_core.c): read the card's exFAT raw (read-only)
and print, for each /_Playlists/*.m3u*, every entry's (folder cluster, directory slot + 1), in the same format as
game/pc/pl_card.c, so the two outputs can be diffed.

  python -I tools/pl_truth.py E
"""
import ctypes, os, struct, sys
from ctypes import wintypes as wt

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
k32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
k32.SetFilePointerEx.argtypes = [wt.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wt.DWORD]

letter = sys.argv[1] if len(sys.argv) > 1 else "E"
h = k32.CreateFileW(f"\\\\.\\{letter}:", 0x80000000, 3, None, 3, 0, None)
if h in (None, wt.HANDLE(-1).value):
    sys.exit(f"open failed: {ctypes.get_last_error()}")

def read(off, n):
    a = off // 512 * 512
    m = (off + n - a + 511) // 512 * 512
    k32.SetFilePointerEx(h, a, None, 0)
    buf = ctypes.create_string_buffer(m)
    got = wt.DWORD()
    if not k32.ReadFile(h, buf, m, ctypes.byref(got), None):
        sys.exit(f"read failed: {ctypes.get_last_error()}")
    return buf.raw[off - a:off - a + n]

bs = read(0, 512)
assert bs[3:8] == b"EXFAT"
fat_off, heap, root = (struct.unpack_from("<I", bs, o)[0] for o in (0x50, 0x58, 0x60))
spc = 1 << bs[0x6D]; cs = 512 * spc

def clus(c): return read((heap + (c - 2) * spc) * 512, cs)
def fat(c): return struct.unpack("<I", read(fat_off * 512 + 4 * c, 4))[0]

def data(c, nofat, length, limit=None):
    out = b""
    if nofat:
        n = (length + cs - 1) // cs
        return b"".join(clus(c + i) for i in range(n))[:length]
    while 2 <= c < 0x0FFFFFF7:
        out += clus(c); c = fat(c)
        if limit and len(out) >= limit: break
    return out if length == 0 else out[:length]

cache = {}
def listdir(d):
    if d in cache: return cache[d]
    c, nofat, length = d
    raw = data(c, nofat, length)
    out = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t == 0: break
        if t == 0x85:
            sec = raw[i + 1]
            se = raw[i + 32:i + 64]
            first, ln = struct.unpack_from("<I", se, 20)[0], struct.unpack_from("<Q", se, 24)[0]
            name = b"".join(raw[i + 32 * k + 2:i + 32 * k + 32] for k in range(2, sec + 1)).decode("utf-16le", "replace").split("\x00")[0]
            attr = struct.unpack_from("<H", raw, i + 4)[0]
            out.append((name, bool(attr & 0x10), (first, se[1] & 2, ln), i // 32))
            i += 32 * (sec + 1); continue
        i += 32
    cache[d] = out
    return out

def find(d, name, is_dir):
    for n, isd, sub, slot in listdir(d):
        if isd == is_dir and n.upper() == name.upper():   # pl_core upper-cases ASCII only; fine for this card
            return sub, slot
    return None

rootd = (root, 0, 0)
pl = find(rootd, "_Playlists", True)
if not pl: sys.exit("no /_Playlists/")
pld = pl[0]
files = [(n, sub) for n, isd, sub, slot in listdir(pld) if not isd and os.path.splitext(n)[1].upper() in (".M3U", ".M3U8")]
print(f"playlists {len(files)} (dir cluster {pld[0]:08x})")
for name, sub in files[:24]:
    text = data(*sub).decode("utf-8-sig", "replace")
    good, total = [], 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        total += 1
        parts = ["_Playlists"] + [p for p in line.replace("\\", "/").split("/") if p and p != "."]
        stack = []
        for p in parts:
            if p == "..":
                if stack: stack.pop()
            else: stack.append(p)
        d, ok = rootd, True
        for p in stack[:-1]:
            r = find(d, p, True)
            if not r: ok = False; break
            d = r[0]
        r = find(d, stack[-1], False) if ok else None
        if r and len(good) < 32: good.append((d[0], r[1] + 1))
    print(f"PL {os.path.splitext(name)[0]}\t{len(good)} of {total} (missing {min(total, 32) - len(good)})")
    for c, n in good: print(f"  {c:08x} {n}")
