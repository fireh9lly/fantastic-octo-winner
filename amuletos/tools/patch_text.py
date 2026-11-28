#!/usr/bin/env python3
"""Relabel stock menu text in an unpacked image's text.bin, in place.

  patch_text.py DIR

text.bin holds every language; the firmware forces English (patch_code.py english), so only the English block is
changed. English = language block 2 at 0x48EC + 2 x 0x14896; text id n is a fixed 0x112-byte UTF-16 record at
block + 0x13C0 + (n - 86) x 0x112 (docs/HARDWARE.md, "Stock games"). Each change checks the stock string first and
keeps the record's length, so nothing after it moves.
"""
import os, sys

BLOCK = 0x48EC + 2 * 0x14896
REC = 0x112

# text id -> (stock English, new)
RELABEL = {
    0xF6: ("Language", "Key Test"),    # Settings root row: opens the key test (hooks/settings_game.S, 2026-11-28)
}

def record(n):
    return BLOCK + 0x13C0 + (n - 86) * REC

def read(d, n):
    o = record(n)
    return d[o:o + REC].decode("utf-16-le").split("\x00")[0]

def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = os.path.join(sys.argv[1], "text.bin")
    d = bytearray(open(path, "rb").read())
    for n, (old, new) in RELABEL.items():
        got = read(d, n)
        assert got == old, f"text {n:#x} is {got!r}, expected {old!r}"
        enc = new.encode("utf-16-le") + b"\0\0"
        assert len(enc) <= REC, f"text {n:#x}: {new!r} is too long"
        o, span = record(n), max(len(enc), (len(old) + 1) * 2)    # clear what is left of a longer old string
        d[o:o + span] = enc.ljust(span, b"\0")
        assert read(d, n) == new
        print(f"text {n:#x}: {old!r} -> {new!r}")
    open(path, "wb").write(d)

if __name__ == "__main__":
    main()
