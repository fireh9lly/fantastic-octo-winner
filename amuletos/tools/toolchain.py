"""Where the Arm GNU toolchain lives, for every build tool (Linux, macOS or Windows).

Looked up in this order:
  1. ARM_TOOLCHAIN_BIN (the toolchain's bin folder)
  2. the pinned toolchain fetched by tools/get_toolchain.sh (~/.cache/ap30-toolchain/...)
  3. arm-none-eabi-* on PATH

The pinned compiler (GCC 13.3.1, as amuletOS v0.3 used) reproduces the reference images byte for byte; others
produce working firmware with a few instructions in a different order.
"""
import os, shutil, sys

PINNED = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
                      "ap30-toolchain", "xpack-arm-none-eabi-gcc-13.3.1-1.1", "bin")
BIN = os.environ.get("ARM_TOOLCHAIN_BIN") or (PINNED if os.path.isdir(PINNED) else None)


def tool(name):
    """full path of arm-none-eabi-<name> (gcc, as, ld, objcopy, nm, size...)"""
    exe = f"arm-none-eabi-{name}" + (".exe" if os.name == "nt" else "")
    if BIN:
        return os.path.join(BIN, exe)
    path = shutil.which(exe)
    if not path:
        sys.exit(f"{exe} not found: run tools/get_toolchain.sh, install the Arm GNU Toolchain, "
                 "or set ARM_TOOLCHAIN_BIN to its bin folder")
    return path
