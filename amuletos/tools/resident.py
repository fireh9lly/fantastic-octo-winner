"""Safety check for amuletOS's always-loaded RAM (module slot 2 and the tables above it).

Stock loads slot 2 once at boot and never reloads it, so nothing stock loads later may overlap it. On V1.7.8 the
highest stock module (39, the music-library builder) ended at 0x0309F7CC, below slot 2 at 0x0309F800. On V1.8.3 it
ends at 0x0309FC9C, so the V1.7.8 placement would be overwritten during a library rebuild: crash. This check stops
the build instead of producing such an image.
"""
import struct

BASE = 0x03050000


def overlaps(code, start, end, skip=(2,)):
    """stock modules (code, data or ZI) whose run range overlaps [start, end)"""
    n = struct.unpack_from("<I", code, 4)[0]
    hits = []
    for i in range(n):
        if i in skip:
            continue
        cl, ce, cs, dl, de, ds, ze, zs = struct.unpack_from("<8I", code, 8 + 32 * i)
        for kind, a, size in (("code", ce, cs), ("data", de, ds), ("ZI", ze, zs)):
            if size and a < end and start < a + size:
                hits.append(f"module {i} {kind} {a:#x}..{a + size:#x}")
    return hits


def check(code, start, end, what):
    hits = overlaps(code, start, end)
    assert not hits, (f"{what} at {start:#x}..{end:#x} overlaps stock RAM that is loaded later: {'; '.join(hits)}. "
                      "It would be overwritten (see tools/resident.py).")
