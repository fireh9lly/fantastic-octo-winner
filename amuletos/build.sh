#!/usr/bin/env bash
# Build the firmware image on Linux (or macOS / Git Bash) from Hidizs's official AP30 V1.8.3 firmware.
#
#   ./build.sh STOCK_IMG [BUILD_DIR] [STAMP16]
#
#   STOCK_IMG  official firmware V1.8.3 HIFIYF23.IMG (SHA-256 79d186f5...), from the Hidizs download center
#   BUILD_DIR  work folder (default: build/); the image ends up in BUILD_DIR/out/HIFIYF23.IMG
#   STAMP16    firmware stamp, YY YY DD MM BB 00 00 00 in BCD (default 2620271114000000 = 27 Nov 2026, build 14).
#              The player keeps two firmware copies and boots the one whose stamp is "newer", and the BUILD byte
#              counts first (2026-11-27: 26 Nov build 01 lost to 23 Nov build 13). So raise the build number on every
#              image: it must be higher than the installed one's (stock V1.8.3 is build 03; the owner's player has had
#              builds up to 13). BCD, so at most 99.
#
# The steps follow amuletOS v0.3's release build (build/b60.sh plus the art steps in docs/HANDOFF.md, section 2).
# The source was converted from V1.7.8 to V1.8.3 addresses by tools/port_convert.py; commit 21f8ac1 is the last
# that builds amuletOS v0.3 from V1.7.8, byte-identical to its release. Needs Python 3 with numpy and Pillow, and
# the pinned Arm GCC (tools/get_toolchain.sh); capstone only for the port tools. Never commit or share the images
# this writes: they contain Hidizs firmware.
set -euo pipefail

STOCK_IMG=${1:?usage: ./build.sh STOCK_IMG [BUILD_DIR] [STAMP16]}
B=${2:-build}
STAMP=${3:-2620271114000000}
PY=${PYTHON:-python3}
cd "$(dirname "$0")"
mkdir -p "$B"
LOG="$B/build.log"
: > "$LOG"
step() { echo "== $*"; echo "== $*" >> "$LOG"; }

GCC=$("$PY" -c 'import sys; sys.path.insert(0, "tools"); from toolchain import tool; print(tool("gcc"))')
step "toolchain: $GCC ($("$GCC" -dumpversion)); amuletOS v0.3 used 13.3.1"

step "unpack stock image"
rm -rf "$B/stock" "$B/amu" "$B/img_stock" "$B/art_orange" "$B/art_orange_auto" "$B/art_pocket_all" \
       "$B/d1h" "$B/d1h_o" "$B/d1h_e" "$B/d1h_np" "$B/d1h_np_bz" "$B/d1h_np_bz_pl" "$B/d1h_np_bz_pl_gb" "$B/v060"
"$PY" tools/ap30fw.py verify "$STOCK_IMG" >> "$LOG"
SHA_IN=$( (sha256sum "$STOCK_IMG" 2>/dev/null || shasum -a 256 "$STOCK_IMG") | cut -d' ' -f1)
if [ "$SHA_IN" != 79d186f5f2fe60e46a3ff3a54f91221675fdfe2802654f7fab8d046f12aaba55 ]; then
    echo "error: $STOCK_IMG is not the official V1.8.3 HIFIYF23.IMG (SHA-256 79d186f5...)"; exit 1
fi
"$PY" tools/ap30fw.py unpack "$STOCK_IMG" "$B/stock" >> "$LOG"

step "identity hook (USB name MOONLET OS AP30, module slot 2)"
"$PY" tools/build_hook.py amu 2620071136000000 --src "$B/stock" --out "$B/amu" >> "$LOG"

step "art: stock images, orange theme on black (art/orange.py), recolour; stock font"
"$PY" tools/imgres.py export "$B/stock/images.bin" "$B/img_stock" >> "$LOG"
# owner's orange theme on black (2026-11-27; amuletOS's Pocket look and tall font: git history, art/pocket.py)
"$PY" art/orange.py "$B/art_orange" >> "$LOG"
"$PY" art/recolor.py "$B/img_stock" "$B/art_orange" "$B/art_orange_auto" orange >> "$LOG"
mkdir -p "$B/art_pocket_all"
cp "$B"/art_orange_auto/*.png "$B"/art_orange/*.png "$B/art_pocket_all/"

step "code: slot-2 helpers, Now Playing overlay, menu extensions, patches, modules"
"$PY" tools/build_helpers.py "$B/amu" "$B/d1h" game/device/np_helpers.c game/device/np_stub.S game/device/libscan.c >> "$LOG"
# library-scan work, loaded only around a library build (libscan.h: slot 44, run = end of module 5)
"$PY" tools/build_overlay.py "$B/d1h" "$B/d1h" game/device/libscan_ovl.S game/device/libscan_ovl.c --slot 44 --run 0x03081DF4 --max 0x4D0 --at 0x58800 --json libscan.json --entry lib_entry >> "$LOG"
"$PY" tools/build_overlay.py "$B/d1h" "$B/d1h_o" game/device/npui.c --slot 28 --run 0x030843DC --max 0x758 --at 0x5B8D0 --json npui.json >> "$LOG"
"$PY" tools/extend_module.py "$B/d1h_o" "$B/d1h_e" game/device/m21_ext.S game/device/m21_ext.c --module 21 --json e21.json >> "$LOG"
"$PY" tools/extend_module.py "$B/d1h_e" "$B/d1h_e" game/device/m22_ext.S game/device/m22_ext.c --module 22 --json e22.json >> "$LOG"
"$PY" tools/patch_code.py "$B/d1h_e" "$B/d1h_np" np_v4,np_hide_format,menu_games_to_blockz,lib_skip,menu_carousel,music_update,playlists,keep_settings,english,np_back_home,games_back,settings_game,usb_dac_handover,dark_text >> "$LOG"
"$PY" tools/build_module.py "$B/d1h_np" "$B/d1h_np_bz" game/device/blockz.c --at 0x58CD0 >> "$LOG" 2>&1
"$PY" tools/build_module.py "$B/d1h_np_bz" "$B/d1h_np_bz_pl" game/device/playlists.c --module 86 --in-place --desc pl_desc --data-max 0xD00 >> "$LOG" 2>&1
"$PY" tools/build_module.py "$B/d1h_np_bz_pl" "$B/d1h_np_bz_pl_gb" game/device/gbprobe.c --module 87 --span 0x968bc:0xa68c0 --desc gb_desc --opt O2 --data-max 0xD00 >> "$LOG" 2>&1

step "pack: art, stamp $STAMP"
"$PY" tools/build_reskin.py "$B/d1h_np_bz_pl_gb" "$B/art_pocket_all" "$STAMP" --out "$B/v060" >> "$LOG"

step "done"
mkdir -p "$B/out"
cp "$B/v060/HIFIYF18.IMG" "$B/out/HIFIYF23.IMG"      # same name as Hidizs's V1.8.3 file (updater: HIFIYF??.IMG)
( sha256sum "$B/out/HIFIYF23.IMG" 2>/dev/null || shasum -a 256 "$B/out/HIFIYF23.IMG" )
