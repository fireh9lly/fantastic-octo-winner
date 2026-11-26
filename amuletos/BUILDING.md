# Building on Linux

Tested on Linux x86_64. macOS or Git Bash on Windows should work too.

## One-time setup

```sh
pip install numpy pillow capstone ziglang   # art pipeline, disassembly tools, PC tests
tools/get_toolchain.sh                      # pinned Arm GCC 13.3.1 (xPack), checksum-verified, ~240 MB download
```

The build tools find the compiler in this order: `ARM_TOOLCHAIN_BIN`, then the pinned one from
`tools/get_toolchain.sh`, then `arm-none-eabi-*` on `PATH` (see `tools/toolchain.py`). Other GCC versions build
working firmware but order a few instructions differently, so their output won't match the reference hashes.

## Firmware

You need the official firmware from the
[Hidizs download center](https://www.hidizs.net/pages/download-center). **Never commit or share it, or any image
built from it.**

```sh
./build.sh path/to/HIFIYF18.IMG [build-dir]
```

This writes `build-dir/v060/HIFIYF18.IMG` (default `build/`, which git ignores). The log is in `build-dir/build.log`.

### Reference check: amuletOS v0.3 baseline

With the official **V1.7.8** `HIFIYF18.IMG` (SHA-256 `c7601873…`) and the pinned compiler, the output is
byte-identical to the amuletOS v0.3 release (SHA-256 `3cfeeac7…`). `build.sh` checks this and prints
`reference check: OK`. This was verified on 2026-11-26.

With Debian/Ubuntu's `gcc-arm-none-eabi` 13.2.1, only 22 bytes differ, in two places: slot-2 helpers and the Game
Boy module. Both are instruction-order differences with the same behaviour.

## PC tests

```sh
python3 game/build.py test     # Blockz logic, button debounce, library-scan skip, music-folder walk, playlists
```
