#!/usr/bin/env python3
"""Read-only rockusb client for the AP30 in loader mode (USB 2207:262D).

This tool can only READ. It implements four rockusb opcodes and nothing else:
  0x00 TEST_UNIT_READY, 0x1A READ_FLASH_INFO, 0x1B READ_CHIP_INFO, 0x14 READ_LBA.
There is no write, erase, reset or loader-download code in this file.

Follows ReChord's findings for this BootROM (Echo Mini, same 2207:262D):
  - the BootROM speaks rockusb directly, so no 'db' loader download
  - at most 32 sectors per transfer (larger wedges USB)
  - finite 5 s timeouts (upstream rkdeveloptool waits forever)

Usage:
  rkread.py ld                     list matching devices
  rkread.py td                     test unit ready
  rkread.py rfi                    flash info (size in sectors)
  rkread.py rci                    chip info
  rkread.py rl START COUNT OUT     read COUNT sectors from LBA START into OUT
  rkread.py dump OUT               read the whole flash (size from rfi)
"""
import os, random, struct, sys, time
import usb.core, usb.util, usb.backend.libusb1
import libusb_package

VID, PID = 0x2207, 0x262D
SECTOR = 512
CHUNK = 32
TIMEOUT_MS = 5000

TEST_UNIT_READY, READ_LBA, READ_FLASH_INFO, READ_CHIP_INFO = 0x00, 0x14, 0x1A, 0x1B
ALLOWED = {TEST_UNIT_READY, READ_LBA, READ_FLASH_INFO, READ_CHIP_INFO}

def backend():
    return usb.backend.libusb1.get_backend(find_library=lambda _: libusb_package.get_library_path())

class Dev:
    def __init__(self):
        self.d = usb.core.find(idVendor=VID, idProduct=PID, backend=backend())
        if self.d is None:
            sys.exit("no 2207:262D device found. Is the AP30 in loader mode with the WinUSB driver installed?")
        try:
            self.d.set_configuration()
        except usb.core.USBError:
            pass  # already configured
        intf = self.d.get_active_configuration()[(0, 0)]
        self.ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        self.ep_in = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
        usb.util.claim_interface(self.d, intf.bInterfaceNumber)

    def cmd(self, op, data_len, lba=0, count=0):
        assert op in ALLOWED, "read-only tool: opcode not allowed"
        tag = random.getrandbits(32)
        cb = bytearray(16)
        cb[0] = op
        cb_len = 0x06
        if op == READ_LBA:
            struct.pack_into(">I", cb, 2, lba)
            struct.pack_into(">H", cb, 7, count)
            cb_len = 0x0A
        cbw = struct.pack("<IIIBBB", 0x43425355, tag, data_len, 0x80, 0, cb_len) + bytes(cb)
        self.ep_out.write(cbw, TIMEOUT_MS)
        data = b""
        while len(data) < data_len:
            data += bytes(self.ep_in.read(data_len - len(data), TIMEOUT_MS))
        csw = bytes(self.ep_in.read(13, TIMEOUT_MS))
        sig, rtag, residue, status = struct.unpack("<IIIB", csw[:13])
        if sig != 0x53425355 or rtag != tag:
            raise IOError(f"bad CSW {csw.hex()}")
        if status != 0:
            raise IOError(f"command 0x{op:02X} failed, status {status}")
        return data

    def flash_info(self):
        b = self.cmd(READ_FLASH_INFO, 11)
        size, block, page, ecc, access, manuf, cs = struct.unpack("<IHBBBBB", b)
        return {"sectors": size, "bytes": size * SECTOR, "block": block, "page": page,
                "ecc": ecc, "manuf": manuf, "cs": cs, "raw": b.hex()}

def read_range(dev, start, count, out):
    t0, done = time.time(), 0
    with open(out, "wb") as f:
        lba = start
        while done < count:
            n = min(CHUNK, count - done)
            f.write(dev.cmd(READ_LBA, n * SECTOR, lba, n))
            lba += n; done += n
            if done % 4096 == 0 or done == count:
                mb = done * SECTOR / 1048576
                rate = mb / max(time.time() - t0, 1e-6)
                print(f"\r  {done}/{count} sectors  {mb:7.1f} MB  {rate:5.2f} MB/s", end="", flush=True)
    print()

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    c = a[0]
    if c == "ld":
        for d in usb.core.find(find_all=True, idVendor=VID, backend=backend()):
            print(f"Vid=0x{d.idVendor:04x} Pid=0x{d.idProduct:04x} bcdUSB=0x{d.bcdUSB:04x} bcdDevice=0x{d.bcdDevice:04x} bus={d.bus} addr={d.address}")
        return
    dev = Dev()
    if c == "td":
        dev.cmd(TEST_UNIT_READY, 0); print("Test Device OK")
    elif c == "rfi":
        print(dev.flash_info())
    elif c == "rci":
        print(dev.cmd(READ_CHIP_INFO, 16).hex(" "))
    elif c == "rl":
        read_range(dev, int(a[1], 0), int(a[2], 0), a[3])
    elif c == "dump":
        info = dev.flash_info()
        print(f"flash: {info['sectors']} sectors = {info['bytes'] / 1048576:.1f} MB")
        read_range(dev, 0, info["sectors"], a[1])
    else:
        sys.exit(__doc__)

if __name__ == "__main__":
    main()
