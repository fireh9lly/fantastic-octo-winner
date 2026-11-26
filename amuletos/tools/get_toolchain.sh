#!/usr/bin/env bash
# Download the pinned Arm GCC (xPack 13.3.1-1.1, Linux x86_64) that reproduces amuletOS v0.3 byte for byte,
# check its SHA-256, and unpack it into the cache folder that tools/toolchain.py looks in.
#
#   tools/get_toolchain.sh            -> ~/.cache/ap30-toolchain/xpack-arm-none-eabi-gcc-13.3.1-1.1/bin
#
# Distro packages (e.g. Debian/Ubuntu gcc-arm-none-eabi 13.2.1) build working firmware too, but order a few
# instructions differently, so their images don't match the reference hashes.
set -euo pipefail
VER=13.3.1-1.1
FILE=xpack-arm-none-eabi-gcc-$VER-linux-x64.tar.gz
URL=https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v$VER/$FILE
SHA=006c89337eced277fdf4c1c3bf3aebe55c85e8d52cba8d412009717fb781b959
DEST=${XDG_CACHE_HOME:-$HOME/.cache}/ap30-toolchain

mkdir -p "$DEST"
cd "$DEST"
if [ ! -x "xpack-arm-none-eabi-gcc-$VER/bin/arm-none-eabi-gcc" ]; then
    curl -fL --retry 3 -o "$FILE" "$URL"
    echo "$SHA  $FILE" | sha256sum -c -
    tar -xzf "$FILE"
    rm "$FILE"
fi
"xpack-arm-none-eabi-gcc-$VER/bin/arm-none-eabi-gcc" --version | head -1
echo "ready: $DEST/xpack-arm-none-eabi-gcc-$VER/bin (used automatically by the build tools)"
