#!/usr/bin/env python3
"""Loader-mode WRITE tool for the AP30 (USB 2207:262D). Kept separate from rkread.py,
which stays read-only.

Commands:
  rkwrite.py wtest
      Recovery proof. Reads 64 sectors at the test LBA (a free, blank area inside
      the user FAT32 volume), refuses unless they are all 0xFF, writes a test
      pattern, reads it back, restores the original bytes, and reads back again.
  rkwrite.py wl START FILE --allow-any
      Write FILE at LBA START with read-back verification. For recovery, e.g.
      writing a known-good firmware image at LBA 0. Refuses without --allow-any.

Guards: by default only LBAs inside TEST_ZONE may be written. Writes go in
32-sector chunks with 5 s timeouts (ReChord's limits for this BootROM). Every
write is read back and compared.
"""
import os, sys, time, hashlib
sys.path.insert(0, os.path.dirname(__file__))
import usb.util
from rkread import Dev, READ_LBA, SECTOR, CHUNK, TIMEOUT_MS
import random, struct

WRITE_LBA = 0x15
TEST_LBA, TEST_N = 786432, 64              # byte 0x18000000, free clusters of the user FAT32
TEST_ZONE = range(TEST_LBA, TEST_LBA + 1024)

class WDev(Dev):
    def write_lba(self, lba, data):
        assert len(data) % SECTOR == 0
        n = len(data) // SECTOR
        assert n <= CHUNK
        tag = random.getrandbits(32)
        cb = bytearray(16); cb[0] = WRITE_LBA
        struct.pack_into(">I", cb, 2, lba); struct.pack_into(">H", cb, 7, n)
        cbw = struct.pack("<IIIBBB", 0x43425355, tag, len(data), 0x00, 0, 0x0A) + bytes(cb)
        self.ep_out.write(cbw, TIMEOUT_MS)
        self.ep_out.write(data, TIMEOUT_MS)
        csw = bytes(self.ep_in.read(13, TIMEOUT_MS))
        sig, rtag, residue, status = struct.unpack("<IIIB", csw[:13])
        if sig != 0x53425355 or rtag != tag: raise IOError(f"bad CSW {csw.hex()}")
        if status != 0: raise IOError(f"write at LBA {lba} failed, status {status}")

    def read(self, lba, n):
        out = b""
        while n:
            k = min(CHUNK, n); out += self.cmd(READ_LBA, k * SECTOR, lba, k); lba += k; n -= k
        return out

    def write_verified(self, lba, data, allow_any=False, progress=False):
        n = len(data) // SECTOR
        if not allow_any and not (lba in TEST_ZONE and lba + n - 1 in TEST_ZONE):
            sys.exit(f"refusing: LBA {lba}..{lba+n-1} is outside the test zone (use --allow-any for recovery)")
        t0 = time.time()
        for i in range(0, n, CHUNK):
            k = min(CHUNK, n - i)
            chunk = data[i * SECTOR:(i + k) * SECTOR]
            self.write_lba(lba + i, chunk)
            if self.read(lba + i, k) != chunk:
                raise IOError(f"read-back mismatch at LBA {lba + i}")
            if progress and (i % 4096 == 0 or i + k == n):
                print(f"\r  {i + k}/{n} sectors written+verified  {(i + k) * SECTOR / 1048576 / max(time.time() - t0, 1e-6):.2f} MB/s", end="", flush=True)
        if progress: print()

def wtest():
    d = WDev()
    orig = d.read(TEST_LBA, TEST_N)
    print(f"test area LBA {TEST_LBA}..{TEST_LBA + TEST_N - 1}: read {len(orig)} bytes, sha256 {hashlib.sha256(orig).hexdigest()[:16]}")
    if orig != b"\xff" * len(orig):
        sys.exit("refusing: test area is not blank (0xFF) on the device, nothing written")
    pattern = b"".join(f"SCHALAOS RECOVERY TEST LBA {TEST_LBA + i:08d} ".encode().ljust(SECTOR, b"\x5a") for i in range(TEST_N))
    d.write_verified(TEST_LBA, pattern)
    print("pattern written and read back OK")
    d.write_verified(TEST_LBA, orig)
    print("original bytes restored and read back OK")
    print("RECOVERY WRITE PATH PROVEN")

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == "wtest":
        wtest()
    elif a[0] == "wl" and len(a) >= 3:
        data = open(a[2], "rb").read()
        if len(data) % SECTOR: data += b"\x00" * (SECTOR - len(data) % SECTOR)
        d = WDev()
        d.write_verified(int(a[1], 0), data, allow_any="--allow-any" in a, progress=True)
        print("write complete and verified")
    else:
        sys.exit(__doc__)

if __name__ == "__main__":
    main()
