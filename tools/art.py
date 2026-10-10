#!/usr/bin/env python3
"""Lusaka Brief — story illustration plates.

Draws a 1536x1024 editorial illustration for a story: a flat geometric motif
in the section's colours plus a short label. Everything is generated locally
with Pillow, so an edition never depends on an outside image service.

    python3 tools/art.py out.webp --section Courts --motif scales \
        --label "The Solwezi file" --seed solwezi-ruling
"""
import argparse
import hashlib
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
W, H = 1536, 1024
SS = 2  # supersample factor for smooth edges

# bg, tone (slightly lighter), deep (slightly darker), accent, ink (label)
PALETTES = {
    "Politics":  ("#173f2f", "#225743", "#0f2d21", "#c9a227", "#f6f3ec"),
    "Economy":   ("#8a3f15", "#a8521f", "#6d2f0e", "#f0c660", "#f6f3ec"),
    "Courts":    ("#3b3160", "#4f4380", "#2a2247", "#c9a227", "#f6f3ec"),
    "Health":    ("#1f4566", "#2c5c85", "#16334d", "#e8b04a", "#f6f3ec"),
    "Sport":     ("#6e2424", "#8a3030", "#521919", "#f0c660", "#f6f3ec"),
    "Culture":   ("#6b5119", "#866724", "#4f3b10", "#f3ddb0", "#f6f3ec"),
    "Explained": ("#efeade", "#e2dccb", "#d6cfba", "#b4551f", "#173f2f"),
}
DEFAULT_MOTIF = {
    "Politics": "assembly", "Economy": "bars", "Courts": "scales",
    "Health": "pulse", "Sport": "pitch", "Culture": "sun", "Explained": "book",
}
MOTIFS = ["assembly", "ballot", "scales", "columns", "bars", "coins", "ingots",
          "power", "drop", "pulse", "pitch", "sun", "globe", "book", "road"]


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _rng(seed):
    return random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16))


def _s(v):
    return int(round(v * SS))


class Plate:
    def __init__(self, section, seed):
        self.bg, self.tone, self.deep, self.accent, self.ink = PALETTES.get(
            section, PALETTES["Politics"])
        self.r = _rng(seed)
        self.im = Image.new("RGB", (W * SS, H * SS), self.bg)
        self.d = ImageDraw.Draw(self.im)

    # -- primitives (coordinates in final pixels) --
    def circle(self, cx, cy, rad, fill=None, outline=None, width=0):
        self.d.ellipse([_s(cx - rad), _s(cy - rad), _s(cx + rad), _s(cy + rad)],
                       fill=fill, outline=outline, width=_s(width))

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=0, radius=0):
        self.d.rounded_rectangle([_s(x0), _s(y0), _s(x1), _s(y1)], radius=_s(radius),
                                 fill=fill, outline=outline, width=_s(width))

    def poly(self, pts, fill=None):
        self.d.polygon([(_s(x), _s(y)) for x, y in pts], fill=fill)

    def line(self, pts, fill, width):
        self.d.line([(_s(x), _s(y)) for x, y in pts], fill=fill, width=_s(width),
                    joint="curve")
        for x, y in (pts[0], pts[-1]):
            self.circle(x, y, width / 2, fill=fill)

    def arc(self, cx, cy, rad, a0, a1, fill, width):
        self.d.arc([_s(cx - rad), _s(cy - rad), _s(cx + rad), _s(cy + rad)],
                   a0, a1, fill=fill, width=_s(width))

    # -- motifs: each fills the right-hand ~60% of the plate --
    def assembly(self):
        cx, cy = 1060 + self.r.randint(-20, 20), 700
        for row in range(5):
            rad = 150 + row * 74
            n = 6 + row * 3
            for i in range(n):
                a = math.pi + (i + 0.5) * math.pi / n
                x, y = cx + rad * math.cos(a), cy + rad * math.sin(a)
                col = self.accent if (row == 0 and i == n // 2) else (
                    self.tone if (i + row) % 3 else self.deep)
                self.circle(x, y, 24 + row * 1.5, fill=col)
        self.rect(cx - 96, cy - 40, cx + 96, cy + 26, fill=self.accent, radius=10)
        self.rect(cx - 470, cy + 70, cx + 470, cy + 84, fill=self.ink)
        self.rect(cx - 210, cy + 84, cx + 210, cy + 330, fill=self.deep)

    def ballot(self):
        x, y = 820 + self.r.randint(-20, 30), 470
        self.poly([(x + 190, y - 330), (x + 470, y - 280), (x + 420, y - 10),
                   (x + 150, y - 60)], fill=self.ink)
        self.line([(x + 240, y - 235), (x + 400, y - 205)], self.tone, 16)
        self.line([(x + 228, y - 175), (x + 388, y - 145)], self.tone, 16)
        self.line([(x + 250, y - 130), (x + 290, y - 95), (x + 370, y - 190)],
                  self.accent, 20)
        self.rect(x, y, x + 600, y + 620, fill=self.tone, radius=18)
        self.rect(x, y, x + 600, y + 110, fill=self.deep, radius=18)
        self.rect(x + 130, y + 42, x + 470, y + 68, fill=self.bg, radius=13)
        self.circle(x + 300, y + 350, 92, outline=self.accent, width=16)

    def scales(self):
        cx = 1090 + self.r.randint(-20, 20)
        tilt = self.r.choice([-38, -22, 22, 38])
        top = 250
        self.rect(cx - 14, top, cx + 14, 800, fill=self.accent)
        self.poly([(cx - 190, 860), (cx + 190, 860), (cx + 120, 800), (cx - 120, 800)],
                  fill=self.accent)
        self.circle(cx, top, 34, fill=self.accent)
        lx, ly, rx, ry = cx - 290, top + 40 + tilt, cx + 290, top + 40 - tilt
        self.line([(lx, ly), (cx, top + 40), (rx, ry)], self.accent, 18)
        for px, py in ((lx, ly), (rx, ry)):
            self.line([(px, py), (px - 120, py + 250)], self.tone, 7)
            self.line([(px, py), (px + 120, py + 250)], self.tone, 7)
            self.d.pieslice([_s(px - 150), _s(py + 130), _s(px + 150), _s(py + 370)],
                            0, 180, fill=self.ink)

    def columns(self):
        x0 = 800 + self.r.randint(-15, 15)
        self.poly([(x0 - 40, 380), (x0 + 660, 380), (x0 + 310, 190)], fill=self.tone)
        self.circle(x0 + 310, 300, 34, fill=self.accent)
        self.rect(x0 - 40, 380, x0 + 660, 430, fill=self.deep)
        for i in range(5):
            cx = x0 + 30 + i * 140
            self.rect(cx, 430, cx + 70, 840, fill=self.ink if i != 2 else self.accent)
            self.rect(cx - 14, 430, cx + 84, 458, fill=self.tone)
            self.rect(cx - 14, 812, cx + 84, 840, fill=self.tone)
        self.rect(x0 - 70, 840, x0 + 690, 890, fill=self.deep)
        self.rect(x0 - 110, 890, x0 + 730, 940, fill=self.tone)

    def bars(self):
        x0, base = 700 + self.r.randint(-20, 20), 860
        hs = sorted(self.r.sample(range(160, 600, 40), 6))
        if self.r.random() < 0.35:
            hs = hs[::-1]
        pts = []
        for i, h in enumerate(hs):
            x = x0 + i * 122
            self.rect(x, base - h, x + 84, base, fill=self.tone if i % 2 else self.deep,
                      radius=6)
            pts.append((x + 42, base - h - 70))
        self.line(pts, self.accent, 14)
        for p in pts:
            self.circle(p[0], p[1], 17, fill=self.ink)
        self.rect(x0 - 40, base, x0 + 760, base + 12, fill=self.ink)

    def coins(self):
        x0 = 760 + self.r.randint(-20, 20)
        for col, n in enumerate([3, 6, 4, 8]):
            cx = x0 + col * 185
            for k in range(n):
                y = 860 - k * 62
                fill = self.accent if (k == n - 1) else (self.tone if k % 2 else self.deep)
                self.d.ellipse([_s(cx - 82), _s(y - 30), _s(cx + 82), _s(y + 30)],
                               fill=fill, outline=self.bg, width=_s(5))
        self.line([(x0 - 60, 430), (x0 + 130, 360), (x0 + 330, 400), (x0 + 600, 210)],
                  self.ink, 12)
        self.poly([(x0 + 620, 180), (x0 + 560, 190), (x0 + 610, 248)], fill=self.ink)

    def ingots(self):
        x0, base = 760 + self.r.randint(-15, 15), 870
        rows = [4, 3, 2, 1]
        for r_i, n in enumerate(rows):
            y = base - r_i * 128
            off = r_i * 92
            for i in range(n):
                x = x0 + off + i * 184
                fill = self.accent if (r_i == 3) else (self.tone if (i + r_i) % 2 else "#b4551f")
                self.poly([(x + 22, y - 112), (x + 150, y - 112), (x + 172, y), (x, y)],
                          fill=fill)
                self.poly([(x + 34, y - 100), (x + 138, y - 100), (x + 144, y - 72),
                           (x + 28, y - 72)], fill=self.deep)
        self.rect(x0 - 40, base, x0 + 800, base + 12, fill=self.ink)

    def power(self):
        for k, x in enumerate([880, 1180, 1410]):
            sc = 1.0 - k * 0.22
            top, base = 860 - 620 * sc, 860
            w = 110 * sc
            col = self.ink if k == 0 else self.tone
            self.line([(x - w, base), (x - w * 0.25, top)], col, 10 * sc)
            self.line([(x + w, base), (x + w * 0.25, top)], col, 10 * sc)
            for t in (0.2, 0.42, 0.66):
                y = base - (base - top) * t
                ww = w * (1 - 0.75 * t)
                self.line([(x - ww, y), (x + ww, y)], col, 8 * sc)
            for t in (0.78, 0.92):
                y = base - (base - top) * t
                self.line([(x - w * 1.25, y), (x + w * 1.25, y)], col, 9 * sc)
        self.line([(700, 330), (880, 372), (1180, 470), (1410, 545), (1536, 560)],
                  self.deep, 6)
        bx, by = 1010, 130
        self.poly([(bx + 70, by), (bx - 30, by + 190), (bx + 40, by + 190),
                   (bx - 20, by + 360), (bx + 130, by + 130), (bx + 55, by + 130),
                   (bx + 120, by)], fill=self.accent)

    def drop(self):
        cx, cy = 1100 + self.r.randint(-20, 20), 600
        rad = 230
        self.circle(cx, cy, rad, fill=self.accent)
        self.poly([(cx - rad * 0.86, cy - rad * 0.5), (cx + rad * 0.86, cy - rad * 0.5),
                   (cx, cy - rad * 2.0)], fill=self.accent)
        self.d.pieslice([_s(cx - 150), _s(cy - 150), _s(cx + 150), _s(cy + 150)],
                        20, 110, fill=self.ink)
        self.circle(cx, cy, 104, fill=self.accent)
        for i in range(5):
            self.arc(cx, 900, 290 + i * 52, 180, 360, self.tone if i % 2 else self.deep, 12)

    def pulse(self):
        cx, cy = 1040 + self.r.randint(-30, 30), 470
        self.circle(cx, cy, 300, fill=self.tone)
        self.rect(cx - 62, cy - 190, cx + 62, cy + 190, fill=self.ink, radius=16)
        self.rect(cx - 190, cy - 62, cx + 190, cy + 62, fill=self.ink, radius=16)
        y = 840
        pts = [(600, y), (800, y), (850, y - 60), (900, y + 40), (960, y - 190),
               (1030, y + 110), (1080, y - 30), (1120, y), (1536, y)]
        self.line(pts, self.accent, 14)

    def pitch(self):
        x0, y0, x1, y1 = 740, 150, 1700, 900
        self.rect(x0, y0, x1, y1, fill=self.tone)
        for i in range(0, 8, 2):
            self.rect(x0 + i * 120, y0, x0 + (i + 1) * 120, y1, fill=self.deep)
        ln = self.ink
        self.rect(x0, y0, x1, y1, outline=ln, width=9)
        mx = x0 + 480
        self.line([(mx, y0), (mx, y1)], ln, 9)
        self.circle(mx, (y0 + y1) / 2, 130, outline=ln, width=9)
        self.circle(mx, (y0 + y1) / 2, 14, fill=ln)
        self.rect(x0, 330, x0 + 190, 720, outline=ln, width=9)
        self.rect(x0, 430, x0 + 80, 620, outline=ln, width=9)
        bx, by = mx + 210 + self.r.randint(-40, 40), 330 + self.r.randint(0, 300)
        self.circle(bx, by, 46, fill=self.accent)
        self.circle(bx, by, 46, outline=self.bg, width=6)

    def sun(self):
        cx, cy = 1060 + self.r.randint(-30, 30), 520
        n = 24
        for i in range(n):
            a0 = 2 * math.pi * i / n
            a1 = a0 + math.pi / n
            col = self.tone if i % 2 else self.deep
            self.poly([(cx, cy), (cx + 900 * math.cos(a0), cy + 900 * math.sin(a0)),
                       (cx + 900 * math.cos(a1), cy + 900 * math.sin(a1))], fill=col)
        self.circle(cx, cy, 250, fill=self.bg)
        self.circle(cx, cy, 205, fill=self.accent)
        for k, rad in enumerate((150, 96, 44)):
            self.circle(cx, cy, rad, fill=(self.bg, self.ink, self.bg)[k])
        for i in range(16):
            a = 2 * math.pi * i / 16
            self.circle(cx + 178 * math.cos(a), cy + 178 * math.sin(a), 11, fill=self.bg)

    def globe(self):
        cx, cy, rad = 1050 + self.r.randint(-30, 30), 520, 330
        self.circle(cx, cy, rad, fill=self.tone)
        for f in (0.35, 0.72):
            self.d.ellipse([_s(cx - rad * f), _s(cy - rad), _s(cx + rad * f), _s(cy + rad)],
                           outline=self.ink, width=_s(7))
        self.line([(cx, cy - rad), (cx, cy + rad)], self.ink, 7)
        for dy in (-0.55, 0, 0.55):
            hw = rad * math.sqrt(1 - dy * dy)
            self.line([(cx - hw, cy + rad * dy), (cx + hw, cy + rad * dy)], self.ink, 7)
        self.circle(cx, cy, rad, outline=self.ink, width=9)
        px, py = cx + 60, cy + 40
        self.circle(px, py - 70, 50, fill=self.accent)
        self.poly([(px - 44, py - 48), (px + 44, py - 48), (px, py + 40)], fill=self.accent)
        self.circle(px, py - 70, 19, fill=self.tone)

    def book(self):
        cx, cy = 1050 + self.r.randint(-30, 30), 560
        left = [(cx, cy - 210), (cx - 380, cy - 270), (cx - 380, cy + 210), (cx, cy + 270)]
        right = [(cx, cy - 210), (cx + 380, cy - 270), (cx + 380, cy + 210), (cx, cy + 270)]
        self.poly([(x - 14 if x < cx else x + 14, y + 34) for x, y in left + right[::-1]],
                  fill=self.accent)
        self.poly(left, fill=PALETTES["Politics"][0])
        self.poly(right, fill="#225743")
        for i in range(5):
            y = cy - 150 + i * 78
            self.line([(cx - 320, y - 42), (cx - 60, y - 2)], self.bg, 10)
            self.line([(cx + 60, y - 2), (cx + 320 - (90 if i == 4 else 0), y - 42 + (14 if i == 4 else 0))],
                      self.bg, 10)
        self.line([(cx, cy - 210), (cx, cy + 270)], self.accent, 8)

    def road(self):
        vx, vy = 1080 + self.r.randint(-40, 40), 300
        self.poly([(0, 0), (W, 0), (W, vy), (0, vy)], fill=self.deep)
        self.circle(vx + 190, vy - 20, 120, fill=self.accent)
        self.poly([(0, vy), (W, vy), (W, vy + 16), (0, vy + 16)], fill=self.tone)
        self.poly([(vx - 14, vy), (vx + 14, vy), (1500, H), (560, H)], fill=self.tone)
        for i in range(7):
            t0, t1 = (i / 7) ** 1.8, ((i + 0.55) / 7) ** 1.8
            y0, y1 = vy + (H - vy) * t0, vy + (H - vy) * t1
            c0 = vx + (1030 - vx) * t0
            c1 = vx + (1030 - vx) * t1
            w0, w1 = 3 + 16 * t0, 3 + 16 * t1
            self.poly([(c0 - w0, y0), (c0 + w0, y0), (c1 + w1, y1), (c1 - w1, y1)],
                      fill=self.ink)

    # -- finishing --
    def render(self, motif, label, section):
        getattr(self, motif)()
        im = self.im.resize((W, H), Image.LANCZOS)
        # left-hand veil so the label always sits on calm ground
        veil = Image.new("RGB", (W, H), self.bg)
        ramp = Image.new("L", (256, 1))
        ramp.putdata([255 if x < 80 else max(0, int(255 * (132 - x) / 52)) for x in range(256)])
        mask = ramp.resize((W, H), Image.BILINEAR)
        im = Image.composite(veil, im, mask)
        # paper grain
        noise = Image.effect_noise((W, H), 9).convert("RGB")
        im = ImageChops.soft_light(im, noise)
        d = ImageDraw.Draw(im)
        # frame
        d.rectangle([28, 28, W - 29, H - 29], outline=self.accent, width=2)
        # wordmark + section
        small = _font("inter-latin-700-normal.woff", 25)
        tag = f"LUSAKA BRIEF  ·  {section.upper()}"
        d.text((84, 88), tag, font=small, fill=self.accent, spacing=4,
               features=["-kern"] if False else None)
        d.rectangle([84, 132, 84 + 96, 136], fill=self.accent)
        # label, wrapped to the left column
        size = 104
        while size > 54:
            f = _font("fraunces-latin-800-normal.woff", size)
            lines = _wrap(d, label, f, 600)
            if len(lines) <= 4 and all(d.textlength(l, font=f) <= 600 for l in lines):
                break
            size -= 6
        lh = int(size * 1.06)
        y = H - 96 - lh * len(lines)
        for l in lines:
            d.text((80, y), l, font=f, fill=self.ink)
            y += lh
        ital = _font("fraunces-latin-400-italic.woff", 27)
        d.text((84, H - 82), "Illustration", font=ital, fill=self.accent)
        return im


def _wrap(d, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make(path, section, label, motif=None, seed=None):
    """Render a plate to `path` (WebP, quality 82). Returns the motif used."""
    motif = motif or DEFAULT_MOTIF.get(section, "assembly")
    if motif not in MOTIFS:
        raise ValueError(f"unknown motif {motif!r}; choose from {', '.join(MOTIFS)}")
    im = Plate(section, seed or label).render(motif, label, section)
    im.save(path, "WEBP", quality=82, method=6)
    return motif


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--section", default="Politics", choices=list(PALETTES))
    ap.add_argument("--motif", choices=MOTIFS)
    ap.add_argument("--label", required=True)
    ap.add_argument("--seed")
    a = ap.parse_args()
    print(make(a.out, a.section, a.label, a.motif, a.seed))
