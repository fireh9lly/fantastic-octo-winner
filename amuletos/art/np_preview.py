"""PC preview of the v0.3 Now Playing (layout A): the real hook code (game/device/npui.c) run on the PC.

  python art/np_preview.py [FONT_DIR] [OUT_DIR]

Background = art/screens.py now_playing() + stock's status icons and the default cover at their stock
positions (v0.1 art); game/pc/np_preview.c then runs npui.c's draws on it with the device fonts.
Writes OUT_DIR/np_preview.png (three samples, each at title scroll 0 s / 3 s / 6 s).
"""
import subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "art"))
import pocket  # noqa: E402

ART = ROOT / "build/art_pocket_all"
ZIG = [sys.executable, "-m", "ziglang", "cc"]
SAMPLES = [
    ("Scars of Time", "Yasunori Mitsuda", "Chrono Cross Original Soundtrack", 102, 245, 3, 22),
    ("Radical Dreamers - Le Tresor Interdit", "Yasunori Mitsuda, Noriko Mitose", "Chrono Cross Disc 2", 1834, 3901, 118, 1204),
    ("", "", "Untagged", 5, 61, 1, 1),
]


def background():
    im = pocket.now_playing().image(1).convert("RGB")
    for n, xy in ((34, (105, 10)), (31, (143, 6)), (45, (183, 7)), (287, (209, 11)), (277, (17, 46))):
        im.paste(Image.open(ART / f"{n:03d}.png").convert("RGB"), xy)
    a = np.array(im).astype(np.uint16)
    return ((a[..., 0] >> 3) << 11 | (a[..., 1] >> 2) << 5 | (a[..., 2] >> 3)).astype("<u2")


CORNER_TOP, CORNER_BOTTOM = 24, 48   # bezel radii estimated from the owner's photo of build 33 (bottom much rounder)


def to_image(raw):
    v = np.frombuffer(raw, "<u2").reshape(240, 296).astype(np.uint32)
    rgb = np.stack([(v >> 11) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3], -1).astype(np.uint8)
    yy, xx = np.mgrid[0:240, 0:296].astype(float) + 0.5
    for r, cy in ((CORNER_TOP, CORNER_TOP), (CORNER_BOTTOM, 240 - CORNER_BOTTOM)):
        for cx in (r, 296 - r):
            zone = (np.abs(xx - cx) > 0) & ((xx < cx) if cx == r else (xx > cx)) & ((yy < cy) if cy == r else (yy > cy))
            rgb[zone & (((xx - cx) ** 2 + (yy - cy) ** 2) > r * r)] = 0
    return Image.fromarray(rgb)


def main():
    fdir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/v029"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build/np_preview"
    out.mkdir(parents=True, exist_ok=True)
    exe = out / "np_preview.exe"
    subprocess.run(ZIG + ["-O1", "-w", "-o", str(exe), str(ROOT / "game/pc/np_preview.c")], check=True)
    (out / "bg.raw").write_bytes(background().tobytes())
    rows = []
    for title, artist, album, pos, tot, n, total in SAMPLES:
        subprocess.run([str(exe), str(out / "bg.raw"), str(fdir / "font0.bin"), str(fdir / "font1.bin"),
                        str(out / "f.raw"), title, artist, album, str(pos), str(tot), str(n), str(total)], check=True)
        raw = (out / "f.raw").read_bytes()
        fs = 296 * 240 * 2
        rows.append([to_image(raw[i * fs:(i + 1) * fs]) for i in range(3)])
    sheet = Image.new("RGB", (3 * (592 + 16) + 8, len(rows) * (480 + 40) + 8), (27, 33, 64))
    d = ImageDraw.Draw(sheet)
    for r, frames in enumerate(rows):
        for c, im in enumerate(frames):
            x, y = 8 + c * 608, 8 + r * 520 + 28
            sheet.paste(im.resize((592, 480), Image.NEAREST), (x, y))
            d.text((x, y - 22), f"sample {r + 1}, title scroll at {3 * c} s", fill=(232, 236, 248))
    sheet.save(out / "np_preview.png")
    rows[0][0].resize((592, 480), Image.NEAREST).save(out / "np_layout_a.png")
    print("wrote", out / "np_preview.png")


if __name__ == "__main__":
    main()
