"""Now Playing layout options for v0.3 (design preview only, not used by the build).

  python art/np_options.py [FONT_DIR] [OUT_DIR]

Draws candidate layouts at the device's 296x240 with the device fonts (FONT_DIR/font0.bin, font1.bin:
the tall font from a build) and stock's 116x116 cover size, then writes a 2x sheet for review.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "art"))
from zeal import THEMES, rgb, mix   # noqa: E402

W, H = 296, 240
T = THEMES["zeal"]
SAMPLE = dict(title="Scars of Time", artist="Yasunori Mitsuda", album="Chrono Cross Original Soundtrack",
              track="3/22", el=102, total=245, batt="87%")


class Screen:
    def __init__(self, f0, f1):
        self.px = np.zeros((H, W, 3), np.uint8)
        self.f0, self.f1 = f0, f1

    def rect(self, x, y, w, h, c):
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        if x1 > x0 and y1 > y0: self.px[y0:y1, x0:x1] = rgb(c)

    def diamond(self, y0=0, y1=H):
        a, b = rgb(T["bg1"]), rgb(T["bg2"])
        for y in range(y0, y1):
            for x in range(W):
                tx, ty = (x >> 1) & 7, (y >> 1) & 7
                m = abs(tx - 3.5) + abs(ty - 3.5)
                on = m <= 1.5 or (3 <= m <= 3.5 and (((x >> 4) + (y >> 4)) & 1))
                self.px[y, x] = b if on else a

    def panel(self, x, y, w, h):
        b, p, s = T["border"], T["panel"], T["shade"]
        self.rect(x + 2, y, w - 4, h, b); self.rect(x, y + 2, w, h - 4, b)
        self.rect(x + 4, y + 4, w - 8, h - 8, s)
        self.rect(x + 4, y + 4, w - 12, h - 12, p)

    # device font text: big=1 font1 (16 px), big=2 font1 doubled, small font0 (12 px)
    def font(self, size):
        return (self.f0, 32, 12) if size == "s" else (self.f1, 33, 16)

    def width(self, s, size="m"):
        f, rec, rows = self.font(size)
        k = 2 if size == "l" else 1
        return sum((4 if ch == " " else f[ord(ch) * rec + rows * 2] & 0x7F) for ch in s) * k

    def text(self, s, x, y, c, size="m", clip=(0, W)):
        f, rec, rows = self.font(size)
        k = 2 if size == "l" else 1
        c = rgb(c)
        for ch in s:
            if ch == " ": x += 4 * k; continue
            o = ord(ch) * rec
            for r in range(rows):
                v = f[o + 2 * r] << 8 | f[o + 2 * r + 1]
                for col in range(16):
                    if v & (0x8000 >> col):
                        X = x + col * k
                        if clip[0] <= X < clip[1]: self.rect(X, y + r * k, k, k, c)
            x += (f[o + rows * 2] & 0x7F) * k
        return x

    def wrap(self, s, x, y, w, c, size="m", lines=2, gap=18):
        """wrap at spaces over up to `lines` lines; the last line is cut with '..' if it still does not fit"""
        words, out, cur = s.split(" "), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if self.width(t, size) <= w or not cur: cur = t
            else: out.append(cur); cur = wd
        out.append(cur)
        if len(out) > lines:
            last = " ".join(out[lines - 1:])
            while self.width(last + "..", size) > w: last = last[:-1]
            out = out[:lines - 1] + [last.rstrip() + ".."]
        for i, ln in enumerate(out): self.text(ln, x, y + i * gap, c, size)
        return len(out)

    def art(self, x, y):
        im = Image.open(ROOT / "build/art_v01_all/277.png").convert("RGB")
        self.px[y:y + 116, x:x + 116] = np.array(im)[:116, :116]

    def status(self, track, batt):
        self.rect(0, 0, W, 20, T["border"])
        self.text("♪" if self.width("♪") else "", 6, 2, T["lav"])
        self.text(track, 8, 2, T["panel"])
        bx = W - 30
        self.rect(bx, 5, 22, 11, T["panel"]); self.rect(bx + 22, 8, 2, 5, T["panel"])
        self.rect(bx + 2, 7, 18, 7, T["border"]); self.rect(bx + 3, 8, 13, 5, T["panel"])
        self.text(batt, bx - 6 - self.width(batt), 2, T["panel"])

    def progress(self, x, y, w, el, total, size="m"):
        pw = round((w - 4) * el / total)
        self.rect(x, y, w, 10, T["border"]); self.rect(x + 2, y + 2, w - 4, 6, T["shade"])
        self.rect(x + 2, y + 2, pw, 6, T["accent"])
        self.rect(x + pw - 1, y - 4, 6, 18, T["lavInk"]); self.rect(x + pw + 1, y - 2, 2, 14, T["lav"])
        mm = lambda s: f"{s // 60}:{s % 60:02d}"
        self.text(mm(el), x, y + 16, T["text"], size)
        r = "-" + mm(total - el)
        self.text(r, x + w - self.width(r, size), y + 16, T["text"], size)


def option_a(f0, f1, s=SAMPLE):
    """Mockup: art left, artist + album right, big title band, progress."""
    sc = Screen(f0, f1); sc.diamond(); sc.status(s["track"], s["batt"])
    sc.panel(6, 24, 128, 128); sc.art(12, 30)
    sc.panel(136, 24, 154, 128)
    n = sc.wrap(s["artist"], 144, 32, 138, T["accent"], "m", 2)
    sc.wrap(s["album"], 144, 32 + n * 18 + 8, 138, T["text"], "m", 3)
    sc.panel(6, 154, 284, 82)
    sc.text(s["title"], 14, 160, T["text"], "l", clip=(14, 282))
    sc.progress(14, 198, 268, s["el"], s["total"], "s")
    return sc


def option_b(f0, f1, s=SAMPLE):
    """Text first: art left, title (2 lines) + artist + album right; no scrolling; progress full width."""
    sc = Screen(f0, f1); sc.diamond(); sc.status(s["track"], s["batt"])
    sc.panel(6, 24, 128, 128); sc.art(12, 30)
    sc.panel(136, 24, 154, 128)
    n = sc.wrap(s["title"], 144, 32, 138, T["text"], "m", 2)
    sc.rect(144, 32 + n * 18 + 2, 138, 2, T["shade"])
    y = 32 + n * 18 + 8
    n2 = sc.wrap(s["artist"], 144, y, 138, T["accent"], "m", 2)
    sc.wrap(s["album"], 144, y + n2 * 18 + 4, 138, T["dim"], "s", 2, 14)
    sc.panel(6, 156, 284, 80)
    sc.progress(16, 176, 264, s["el"], s["total"], "m")
    return sc


def option_c(f0, f1, s=SAMPLE):
    """Centred: art top centre, big title under it, artist - album line, progress."""
    sc = Screen(f0, f1); sc.diamond(); sc.status(s["track"], s["batt"])
    sc.panel(84, 22, 128, 128); sc.art(90, 28)
    sc.panel(6, 150, 284, 86)
    tw = sc.width(s["title"], "l")
    sc.text(s["title"], max(14, (W - tw) // 2), 154, T["text"], "l", clip=(14, 282))
    line = s["artist"] + " - " + s["album"]
    lw = sc.width(line, "s")
    sc.text(line, max(14, (W - lw) // 2), 188, T["accent"], "s", clip=(14, 280))
    sc.progress(14, 204, 268, s["el"], s["total"], "s")
    return sc


def main():
    fdir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/v027"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build/np_preview"
    out.mkdir(parents=True, exist_ok=True)
    f0, f1 = (fdir / "font0.bin").read_bytes(), (fdir / "font1.bin").read_bytes()
    opts = [("A  Mockup: big title band", option_a), ("B  Title beside the art, no scrolling", option_b),
            ("C  Art centred, big title under it", option_c)]
    shots = [(name, Image.fromarray(fn(f0, f1).px)) for name, fn in opts]
    cw = W * 2 + 24
    sheet = Image.new("RGB", (cw * len(shots), H * 2 + 44), (27, 33, 64))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(shots):
        sheet.paste(im.resize((W * 2, H * 2), Image.NEAREST), (i * cw + 12, 34))
        d.text((i * cw + 12, 10), name, fill=(232, 236, 248))
        im.resize((W * 2, H * 2), Image.NEAREST).save(out / f"np_{name[0].lower()}.png")
    sheet.save(out / "np_options.png")
    print("wrote", out / "np_options.png")


if __name__ == "__main__":
    main()
