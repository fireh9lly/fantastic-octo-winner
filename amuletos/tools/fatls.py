#!/usr/bin/env python3
"""List a FAT16/32 volume inside a raw image. Read-only.

  fatls.py IMAGE OFFSET            list the tree
  fatls.py IMAGE OFFSET PATH OUT   extract one file to OUT
"""
import struct, sys

img, base = sys.argv[1], int(sys.argv[2], 0)
f = open(img, "rb")

def rd(off, n):
    f.seek(base + off); return f.read(n)

bs = rd(0, 512)
bps, spc, res, nfat = struct.unpack_from("<HBHB", bs, 11)
rootents = struct.unpack_from("<H", bs, 17)[0]
spf16 = struct.unpack_from("<H", bs, 22)[0]
spf = spf16 or struct.unpack_from("<I", bs, 36)[0]
is32 = spf16 == 0
root_clus = struct.unpack_from("<I", bs, 44)[0] if is32 else 0
fat_off = res * bps
rootdir_off = (res + nfat * spf) * bps
data_off = rootdir_off + (0 if is32 else (rootents * 32 + bps - 1) // bps * bps)
csz = spc * bps
fat = rd(fat_off, spf * bps)

def nextc(c):
    return struct.unpack_from("<I", fat, c * 4)[0] & 0x0FFFFFFF if is32 else struct.unpack_from("<H", fat, c * 2)[0]

def chain(c):
    end = 0x0FFFFFF8 if is32 else 0xFFF8
    seen = 0
    while 2 <= c < end and seen < 1 << 20:
        yield c; c = nextc(c); seen += 1

def clus_off(c):
    return data_off + (c - 2) * csz

def read_dir(c):
    raw = b"".join(rd(clus_off(x), csz) for x in chain(c)) if c else rd(rootdir_off, rootents * 32)
    out, lfn = [], ""
    for i in range(0, len(raw), 32):
        e = raw[i:i + 32]
        if e[0] == 0: break
        if e[0] == 0xE5: lfn = ""; continue
        attr = e[11]
        if attr == 0x0F:
            part = e[1:11] + e[14:26] + e[28:32]
            lfn = part.decode("utf-16-le", "replace").split("\x00")[0] + lfn
            continue
        name = (e[0:8].rstrip().decode("ascii", "replace") + ("." + e[8:11].rstrip().decode("ascii", "replace") if e[8:11].strip() else ""))
        disp = lfn or name; lfn = ""
        if disp in (".", ".."): continue
        first = (struct.unpack_from("<H", e, 20)[0] << 16) | struct.unpack_from("<H", e, 26)[0]
        size = struct.unpack_from("<I", e, 28)[0]
        out.append((disp, attr, first, size))
    return out

def walk(c, prefix="", depth=0):
    for name, attr, first, size in read_dir(c):
        if attr & 0x10:
            print(f"{'  ' * depth}{name}/")
            if depth < 6: walk(first, prefix + name + "/", depth + 1)
        else:
            print(f"{'  ' * depth}{name}  ({size} B)")

def read_file(c, size):
    data = b"".join(rd(clus_off(x), csz) for x in chain(c))
    return data[:size]

def find(c, parts):
    for name, attr, first, size in read_dir(c):
        if name.lower() == parts[0].lower():
            if len(parts) == 1 and not attr & 0x10: return read_file(first, size)
            if attr & 0x10: return find(first, parts[1:])
    return None

print(f"FAT{'32' if is32 else '16'}  bps={bps} spc={spc} clustersize={csz} root={'clus ' + str(root_clus) if is32 else 'fixed'}")
if len(sys.argv) >= 5:
    data = find(root_clus, sys.argv[3].strip("/").split("/"))
    if data is None: sys.exit("not found")
    open(sys.argv[4], "wb").write(data); print(f"wrote {len(data)} B to {sys.argv[4]}")
else:
    walk(root_clus)
