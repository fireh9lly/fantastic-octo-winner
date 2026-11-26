"""Build Blockz on the PC with zig's clang (pip install ziglang).

  python game/build.py test      unit tests
  python game/build.py preview   bot replay -> build/game_preview/*.png + replay.gif
  python game/build.py web       playable page -> build/game_preview/play.html (wasm)
  python game/build.py device    cross-compile check with arm-none-eabi-gcc (size report)
"""
import base64, os, struct, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "build" / "game_preview"
CORE = [ROOT / "core.c", ROOT / "render.c"]
ZIG = [sys.executable, "-m", "ziglang", "cc"]
sys.path.insert(0, str(ROOT.parent / "tools"))
from toolchain import tool            # noqa: E402  (tools/toolchain.py: ARM_TOOLCHAIN_BIN or PATH)
# 32-bit PC target for the exFAT tests (the device is 32-bit): Windows as before, Linux/macOS via musl
PC32 = "x86-windows-gnu" if os.name == "nt" else "x86-linux-musl"

def run(cmd, **kw):
    print(" ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)

def exe(name, srcs):
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / (name + ".exe")
    run(ZIG + ["-O2", "-std=c99", "-Wall", "-Wextra", "-Wno-unused-parameter", "-o", out] + srcs)
    return out

def test():
    t = exe("test_core", CORE + [ROOT / "pc" / "bot.c", ROOT / "test" / "test_core.c"])
    run([t])
    OUT.mkdir(parents=True, exist_ok=True)
    lad = OUT / "test_ladder.exe"     # device shell's button debounce, compiled for the PC
    run(ZIG + ["-O1", "-w", "-I", ROOT, "-o", lad, ROOT / "test" / "test_ladder.c"])
    run([lad])
    lib = OUT / "test_libscan.exe"    # library scan skip (device/libscan.c) on a simulated exFAT card
    run(ZIG + ["-O1", "-w", "-I", ROOT, "-o", lib, ROOT / "test" / "test_libscan.c"])
    run([lib])
    bw = OUT / "test_bgwalk.exe"      # Blockz music folder walk (device/bgmusic.c) on a simulated exFAT card, 32-bit
    run(ZIG + ["-target", PC32, "-O1", "-w", "-I", ROOT, "-o", bw, ROOT / "test" / "test_bgwalk.c"])
    run([bw])
    tp = OUT / "test_playlists.exe"   # playlist resolver (device/exfat.c + pl_core.c) on a simulated card, 32-bit
    run(ZIG + ["-target", PC32, "-O1", "-w", "-I", ROOT, "-o", tp, ROOT / "test" / "test_playlists.c"])
    run([tp])

def preview():
    from PIL import Image
    p = exe("preview", CORE + [ROOT / "pc" / "bot.c", ROOT / "pc" / "preview.c"])
    raw = OUT / "frames.raw"
    run([p, raw, "1"])
    data = raw.read_bytes()
    fsz = 296 * 240 * 2
    hdr = 4
    n = (len(data)) // (fsz + hdr)
    frames = []
    for i in range(n):
        off = i * (fsz + hdr)
        tag = struct.unpack_from("<I", data, off)[0]
        px = data[off + hdr: off + hdr + fsz]
        im = rgb565_to_image(px)
        frames.append((tag, im))
    names = {1: "ready", 2: "go", 3: "early", 4: "mid", 5: "late", 6: "pause", 7: "finish"}
    for tag, im in frames:
        if tag in names:
            im.resize((592, 480), Image.NEAREST).save(OUT / f"{names[tag]}.png")
    anim = [im for tag, im in frames if tag in (0, 3)]
    if anim:
        anim[0].save(OUT / "replay.gif", save_all=True, append_images=anim[1:], duration=33, loop=0)
    # contact sheet of the stills
    stills = [im for tag, im in frames if tag in names]
    sheet = Image.new("RGB", (296 * 4 + 30, 240 * 2 + 10), (40, 40, 40))
    for i, im in enumerate(stills[:8]):
        sheet.paste(im, (6 + (i % 4) * 302, 4 + (i // 4) * 246))
    sheet.save(OUT / "sheet.png")
    raw.unlink()
    print("wrote", OUT)

def rgb565_to_image(px):
    import numpy as np
    from PIL import Image
    a = np.frombuffer(px, dtype="<u2").reshape(240, 296).astype(np.uint32)
    r = ((a >> 11) & 31) * 255 // 31
    g = ((a >> 5) & 63) * 255 // 63
    b = (a & 31) * 255 // 31
    return Image.fromarray(np.dstack([r, g, b]).astype(np.uint8))

def web():
    OUT.mkdir(parents=True, exist_ok=True)
    wasm = OUT / "game.wasm"
    run(ZIG + ["--target=wasm32-freestanding", "-O2", "-std=c99", "-nostdlib", "-Wl,--no-entry",
               "-Wl,--export-dynamic", "-o", wasm] + CORE + [ROOT / "pc" / "web.c"])
    page = (ROOT / "pc" / "play.html").read_text(encoding="utf-8")
    page = page.replace("__WASM_B64__", base64.b64encode(wasm.read_bytes()).decode())
    (OUT / "play.html").write_text(page, encoding="utf-8")
    print("wrote", OUT / "play.html")

def device():
    OUT.mkdir(parents=True, exist_ok=True)
    gcc = tool("gcc")
    for src in CORE:
        o = OUT / (src.stem + ".o")
        run([gcc, "-mcpu=cortex-m3", "-mthumb", "-Os", "-ffreestanding", "-fno-tree-loop-distribute-patterns",
             "-Wall", "-c", src, "-o", o])
        run([tool("size"), o])
        nm = subprocess.run([tool("nm"), "-u", str(o)], capture_output=True, text=True).stdout
        if nm.strip():
            print("  undefined:", nm.split())

if __name__ == "__main__":
    {"test": test, "preview": preview, "web": web, "device": device}[sys.argv[1] if len(sys.argv) > 1 else "test"]()
