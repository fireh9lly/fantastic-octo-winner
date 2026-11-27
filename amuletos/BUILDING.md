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

You need Hidizs's official **V1.8.3** firmware, `HIFIYF23.IMG` (SHA-256 `79d186f5…`), from the
[Hidizs download center](https://www.hidizs.net/pages/download-center). **Never commit or share it, or any image
built from it.**

```sh
./build.sh path/to/HIFIYF23.IMG [build-dir]
```

This writes `build-dir/out/HIFIYF23.IMG`, the same file name as Hidizs's update. The default `build-dir` is
`build/`, which git ignores, and the log is in `build-dir/build.log`.

**Status (2026-11-27): the build runs end to end and passes the image checks; the first test build is ready for
the on-device checklist (`docs/TEST_V183.md`).**

Stamp: the player keeps two firmware copies and boots the one with the "newer" stamp, where the **build number
counts before the date** (seen 2026-11-27: 26 Nov build 01 lost to 23 Nov build 13 and the update seemed to do
nothing). Pass `./build.sh STOCK_IMG BUILD_DIR STAMP16` with a build number above the installed one.

Reproducibility: with the pinned compiler, the code, fonts and text sections come out byte-identical on different
machines. The menu labels are drawn with FreeType (art/orange.py, Inter), so different Pillow / FreeType versions can
change a few anti-aliased pixels in the menu cards (seen 2026-11-27: Pillow 10.2 / FreeType 2.13 vs 13.0 / 2.14,
five images: 014, 018, 020, 022, 024) and so the image hash.
`tools/resident.py` still guards the always-loaded code: it must stay above module 39 (the music-library builder,
which reaches 0x0309FC9C on V1.8.3), in 0x0309FC9C..0x0309FF28.

### History: the amuletOS v0.3 baseline

Commit `21f8ac1` (and earlier) builds amuletOS v0.3 from the official **V1.7.8** `HIFIYF18.IMG` (SHA-256
`c7601873…`). With the pinned compiler its output is byte-identical to the v0.3 release (SHA-256 `3cfeeac7…`),
verified on 2026-11-26. The source was then converted to V1.8.3 by `tools/port_convert.py`, using:
- `docs/port/v183_addresses.tsv`: every address translated, with how;
- `docs/port/v183_patches.json`: every patch's original bytes, identical or relocated.

`docs/HARDWARE.md` and amuletOS's other notes still use V1.7.8 addresses.

## PC tests

```sh
python3 game/build.py test     # Blockz logic, button debounce, library-scan skip, music-folder walk, playlists
```
