#!/usr/bin/env python3
"""Reconstruct the wall plate and compose a3 from the untouched source."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import compose

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
SOURCE = BUILD / "media-generation-mugshot-base-v2-0-e07db233-f1cb-4f83-8494-15faecb4f112.webp"


def continuous_runs(bits):
    indices = np.flatnonzero(bits)
    if not len(indices):
        return []
    cuts = np.flatnonzero(np.diff(indices) > 1) + 1
    return [(int(p[0]), int(p[-1]) + 1) for p in np.split(indices, cuts)]


def make_plate(attempt=1):
    original = Image.open(SOURCE).convert('RGB')
    a = np.asarray(original).copy()
    white = a.min(axis=2) > 215
    black = a.max(axis=2) < 60
    # In the chart wall, near-black pixels adjacent to near-white pixels are
    # silhouette details; isolated black horizontal runs are the old ticks.
    white_near = np.asarray(Image.fromarray(white.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(17))) > 0
    black_subject = black.copy()
    black_subject[:760, 400:1121] &= white_near[:760, 400:1121]
    subject = white | black_subject
    # Remove only long near-black horizontal ink components below the placard;
    # clear their dilation halo too, while leaving the broad shadow untouched.
    for row in range(1450, 1600):
        for lo, hi in continuous_runs(black[row, 400:1121]):
            if hi - lo >= 22:
                ya, yb = max(0, row - 5), min(1600, row + 6)
                subject[ya:yb, max(0,399+lo):min(1600,401+hi)] = False
    sm = Image.fromarray(subject.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(11))
    subject = np.asarray(sm) > 0

    radius = 22 if attempt < 3 else 24
    blur = np.asarray(original.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32)
    # Mirrored tiling keeps the source patch's texture continuous at tile edges.
    patch = original.crop((1280, 60, 1560, 340))
    hp = np.asarray(patch, dtype=np.float32) - np.asarray(patch.filter(ImageFilter.GaussianBlur(22)), dtype=np.float32)
    mode = 'reflect'
    tiled = np.pad(hp, ((0, 1600), (0, 1600), (0, 0)), mode=mode)[:1600, :1600]
    # Tile period 560; mirror flips alternating tiles to avoid seams.
    tiled = np.tile(hp, (6, 6, 1))[:1600, :1600]
    yy, xx = np.indices((1600, 1600))
    flip_y = ((yy // 280) % 2) == 1
    flip_x = ((xx // 280) % 2) == 1
    # Explicit reflected indexing into the 280px patch.
    iy = np.where(flip_y, 279 - (yy % 280), yy % 280)
    ix = np.where(flip_x, 279 - (xx % 280), xx % 280)
    tiled = hp[iy, ix]

    rng = np.random.default_rng(9147 + attempt)
    strength = 0.35 if attempt < 3 else 0.42
    plate = np.clip(blur + tiled * strength + rng.normal(0, 3.5, (1600,1600,1)), 0, 255).astype(np.uint8)
    plate[subject] = a[subject]

    # Tick ink is painted only into wall pixels. Mask runs, never luminance.
    im = Image.fromarray(plate, 'RGB')
    draw = ImageDraw.Draw(im)
    ink = (22, 22, 22)
    y = 147.0
    k = 0
    while y <= 1580:
        row = int(round(y))
        available = ~subject[row]
        for lo, hi in continuous_runs(available[400:1121]):
            x0, x1 = 400 + lo + 4, 400 + hi - 4
            if x1 > x0:
                draw.rectangle((x0, row - 3, x1 - 1, row + 3), fill=ink)
        y = 147 + (k + 1) * (280 / 6)
        k += 1
    plate = np.asarray(im).copy()
    # Verify the first row's left-of-ghost line forms a solid segment.
    y0 = 147
    dark = (plate[y0, 400:800].max(axis=1) < 50)
    runs = continuous_runs(dark)
    longest = max((b-a for a,b in runs), default=0)
    print(f"Attempt {attempt}: y=147 left-side longest solid run = {longest}px")
    if longest < 120:
        raise RuntimeError("Mask clipping failed solidity check; inspect subject mask logic")

    out = BUILD / 'base_v4.png'
    Image.fromarray(plate).save(out, optimize=True)
    compose.main(base=out, output_tag='a3')
    # Requested upscaled inspection crops from final composite.
    final = Image.open(BUILD / 'meme_a3.png').convert('RGB')
    crops = [('crop_head_a3.png', (150,60,900,560)), ('crop_bottom_a3.png',(150,1330,1450,1600))]
    for name, box in crops:
        crop = final.crop(box)
        crop.resize((crop.width*2,crop.height*2), Image.Resampling.NEAREST).save(BUILD/name, optimize=True)
    print(f"Saved {out}, meme_a3.png, preview480_a3.png and inspection crops")

if __name__ == '__main__':
    make_plate(1)
