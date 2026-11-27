#!/usr/bin/env python3
"""AP30 Music Boy firmware image tool (RKnano HIFIYFnn.IMG).

Commands:
  info   IMG                 print header, section table and integrity checks
  unpack IMG OUTDIR          split into header + sections + manifest.json
  pack   OUTDIR IMG [--stamp HEX16]
                             rebuild an image from an unpacked dir; sections may
                             change size, offsets/backup header/CRC are recomputed
  verify IMG                 run the same checks the bootloader/updater does

Layout (from HIFIYF18.IMG, V1.7.8):
  0x000  512-byte header: 8-byte stamp, magic 0x76543210 @0x0C, 'Rockchip' @0x10,
         'RKnano SDK 1.0' @0x30, section groups from 0x50, backup header
         offset (u32) @0x1F4, 'RKnanoFW' @0x1F8
  ...    sections, packed back to back from 0x200
  align  backup copy of the header at the next 32 KiB boundary (as both official images)
  pad    zeros up to the next 1 MiB boundary
  last 4 bytes: Rockchip CRC32 (poly 0x04C10DB7, MSB first, init 0) of all
         preceding bytes, little endian
"""
import argparse, json, os, struct, sys

HDR = 0x200
MAGIC_OFF, MAGIC = 0x1F8, b"RKnanoFW"
BACKUP_PTR = 0x1F4
BACKUP_ALIGN = 0x8000           # Hidizs: V1.8.3 sections end 0x1B95B08 -> backup 0x1B98000 (32 KiB); V1.7.8 0x1B90000 either way
TOTAL_ALIGN = 0x100000

# Section groups: (table offset, group name, names of the entries in order).
# Each group is a u32 count followed by count x (u32 offset, u32 size).
# The loader group has 4 slots; only the last one is populated in stock.
GROUPS = [
    (0x50, "loader", ["loader0", "loader1", "loader2", "code"]),
    (0x74, "font", ["font0", "font1"]),
    (0xC8, "charmap", ["charmap"]),
    (0xF4, "text", ["text"]),
    (0x148, "images", ["images"]),
    (0x19C, "reserved", ["reserved"]),
]

def _table():
    t = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C10DB7) if c & 0x80000000 else (c << 1)
            c &= 0xFFFFFFFF
        t.append(c)
    return t
_T = _table()

def rkcrc(data, crc=0):
    t = _T
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ t[(crc >> 24) ^ b]
    return crc

def u32(b, o): return struct.unpack_from("<I", b, o)[0]

def read_sections(hdr):
    out = []
    for toff, group, names in GROUPS:
        count = u32(hdr, toff)
        for i in range(count):
            off, size = struct.unpack_from("<II", hdr, toff + 4 + 8 * i)
            name = names[i] if i < len(names) else f"{group}{i}"
            out.append({"name": name, "group": group, "slot": i,
                        "table": toff + 4 + 8 * i, "offset": off, "size": size})
    return out

def checks(d):
    hdr = d[:HDR]
    res = []
    res.append(("magic RKnanoFW (fw1 Sign)", hdr[MAGIC_OFF:MAGIC_OFF + 8] == MAGIC))
    bk = u32(hdr, BACKUP_PTR)
    res.append((f"backup header @0x{bk:X} matches (fw1 compare)", d[bk:bk + HDR] == hdr))
    want = u32(d, len(d) - 4)
    got = rkcrc(d[:-4])
    res.append((f"CRC32 0x{got:08X} == stored 0x{want:08X}", got == want))
    secs = read_sections(hdr)
    end = max((s["offset"] + s["size"] for s in secs if s["size"]), default=HDR)
    res.append((f"sections end 0x{end:X} before backup header", end <= bk))
    return res

def cmd_info(a):
    d = open(a.img, "rb").read()
    hdr = d[:HDR]
    print(f"file      {a.img}  {len(d)} bytes (0x{len(d):X})")
    print(f"stamp     {hdr[:8].hex(' ')}")
    print(f"vendor    {hdr[0x10:0x20].rstrip(b'\0').decode()} / {hdr[0x30:0x40].rstrip(b'\0').decode()}")
    print(f"backup    0x{u32(hdr, BACKUP_PTR):X}")
    print("sections:")
    for s in read_sections(hdr):
        print(f"  {s['name']:<9} @0x{s['offset']:08X}  size 0x{s['size']:08X} ({s['size'] / 1048576:6.2f} MB)")
    for name, ok in checks(d):
        print(("  OK   " if ok else "  FAIL ") + name)

def cmd_verify(a):
    d = open(a.img, "rb").read()
    bad = [n for n, ok in checks(d) if not ok]
    print("PASS" if not bad else "FAIL:\n  " + "\n  ".join(bad))
    sys.exit(1 if bad else 0)

def cmd_unpack(a):
    d = open(a.img, "rb").read()
    os.makedirs(a.outdir, exist_ok=True)
    hdr = d[:HDR]
    open(os.path.join(a.outdir, "header.bin"), "wb").write(hdr)
    secs = read_sections(hdr)
    for s in secs:
        if s["size"]:
            s["file"] = s["name"] + ".bin"
            open(os.path.join(a.outdir, s["file"]), "wb").write(d[s["offset"]:s["offset"] + s["size"]])
    man = {"source": os.path.basename(a.img), "size": len(d), "stamp": hdr[:8].hex(),
           "backup": u32(hdr, BACKUP_PTR), "crc": u32(d, len(d) - 4), "sections": secs}
    json.dump(man, open(os.path.join(a.outdir, "manifest.json"), "w"), indent=2)
    print(f"unpacked {sum(1 for s in secs if s['size'])} sections to {a.outdir}")

def align(x, a): return (x + a - 1) // a * a

def cmd_pack(a):
    man = json.load(open(os.path.join(a.dir, "manifest.json")))
    hdr = bytearray(open(os.path.join(a.dir, "header.bin"), "rb").read())
    if a.stamp:
        st = bytes.fromhex(a.stamp)
        if len(st) != 8: sys.exit("--stamp must be 8 bytes (16 hex digits)")
        hdr[:8] = st
    body = bytearray()
    pos = HDR
    for s in man["sections"]:
        if s.get("file"):
            blob = open(os.path.join(a.dir, s["file"]), "rb").read()
            struct.pack_into("<II", hdr, s["table"], pos, len(blob))
            body += blob
            pos += len(blob)
        else:
            # empty slots keep their original pointer (0x200 for loader, 0 for reserved)
            struct.pack_into("<II", hdr, s["table"], s["offset"], 0)
    backup = align(pos, BACKUP_ALIGN)
    struct.pack_into("<I", hdr, BACKUP_PTR, backup)
    total = align(backup + HDR, TOTAL_ALIGN)
    img = bytearray(total + 4)
    img[:HDR] = hdr
    img[HDR:pos] = body
    img[backup:backup + HDR] = hdr
    struct.pack_into("<I", img, total, rkcrc(memoryview(img)[:total]))
    open(a.img, "wb").write(img)
    print(f"packed {a.img}: {len(img)} bytes, backup @0x{backup:X}, CRC 0x{u32(img, total):08X}")

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("info"); s.add_argument("img"); s.set_defaults(f=cmd_info)
    s = sp.add_parser("verify"); s.add_argument("img"); s.set_defaults(f=cmd_verify)
    s = sp.add_parser("unpack"); s.add_argument("img"); s.add_argument("outdir"); s.set_defaults(f=cmd_unpack)
    s = sp.add_parser("pack"); s.add_argument("dir"); s.add_argument("img"); s.add_argument("--stamp"); s.set_defaults(f=cmd_pack)
    a = p.parse_args(); a.f(a)

if __name__ == "__main__":
    main()
