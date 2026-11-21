#!/usr/bin/env python3
"""Rebuild the wall chart ticks using a geometric ghost/placard protection zone."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

import compose

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
SOURCE = BUILD / "media-generation-mugshot-base-v2-0-e07db233-f1cb-4f83-8494-15faecb4f112.webp"


def runs(bits):
    ix = np.flatnonzero(bits)
    if not len(ix):
        return []
    return [(int(part[0]), int(part[-1]) + 1) for part in np.split(ix, np.flatnonzero(np.diff(ix) > 1) + 1)]


def build_plate():
    original = Image.open(SOURCE).convert("RGB")
    rgb = np.asarray(original)
    white = np.min(rgb, axis=2) > 215
    # Close small gaps in the bright ghost/placard body, then fill enclosed
    # dark outline, facial features, and placard details to form solid shapes.
    bright = ndimage.binary_closing(white, structure=np.ones((9, 9), dtype=bool))
    solid = ndimage.binary_fill_holes(bright)
    # Keep substantial white objects (ghost and placard) and discard isolated
    # light flecks in the wall before expanding the protection zone.
    labels, count = ndimage.label(solid)
    sizes = np.bincount(labels.ravel())
    substantial = sizes >= 1000
    substantial[0] = False
    silhouette = substantial[labels]
    dist = ndimage.distance_transform_edt(~silhouette)
    zone = dist <= 26.0
    core = ndimage.binary_erosion(zone, structure=np.ones((7, 7), dtype=bool))

    blur = np.asarray(original.filter(ImageFilter.GaussianBlur(22)), dtype=np.float32)
    patch = original.crop((1280, 60, 1560, 340))
    patch_a = np.asarray(patch, dtype=np.float32)
    hp = patch_a - np.asarray(patch.filter(ImageFilter.GaussianBlur(22)), dtype=np.float32)
    yy, xx = np.indices(zone.shape)
    iy = np.where((yy // 280) % 2 == 1, 279 - yy % 280, yy % 280)
    ix = np.where((xx // 280) % 2 == 1, 279 - xx % 280, xx % 280)
    texture = hp[iy, ix]
    rng = np.random.default_rng(9147)
    plate = np.clip(blur + texture * 0.35 + rng.normal(0, 3.5, (1600, 1600, 1)), 0, 255)

    # Preserve all original pixels in the eroded zone. Blend only the 2px
    # perimeter so the clean plate joins the original outline without a seam.
    core_d = ndimage.distance_transform_edt(core)
    alpha = np.clip((core_d - 1.0) / 2.0, 0, 1)[..., None]
    composite = plate * (1 - alpha) + rgb.astype(np.float32) * alpha
    composite[core] = rgb[core]
    composite = np.clip(composite, 0, 255).astype(np.uint8)

    im = Image.fromarray(composite, "RGB")
    draw = ImageDraw.Draw(im)
    y = 147.0
    k = 0
    while y <= 1580:
        row = int(round(y))
        available = ~zone[row]
        for lo, hi in runs(available[400:1121]):
            x0, x1 = 400 + lo + 4, 400 + hi - 4
            if x1 > x0:
                draw.rectangle((x0, row - 3, x1 - 1, row + 3), fill=(22, 22, 22))
        y = 147 + (k + 1) * (280 / 6)
        k += 1
    result = np.asarray(im).copy()
    first = runs(result[147, 400:800].max(axis=1) < 50)
    longest = max((b - a for a, b in first), default=0)
    if longest < 120:
        raise RuntimeError(f"First tick row's left segment is only {longest}px")
    out = BUILD / "base_v5.png"
    Image.fromarray(result).save(out, optimize=True)
    print(f"y=147 left segment longest solid run: {longest}px")
    return out


def report_checks(final_path):
    final = np.asarray(Image.open(final_path).convert("RGB"), dtype=np.int16)
    reference = np.asarray(Image.open(BUILD / "meme_a.png").convert("RGB"), dtype=np.int16)
    eye_diff = float(np.abs(final[330:560, 620:1000] - reference[330:560, 620:1000]).mean())
    print(f"Eye crop mean absolute pixel difference: {eye_diff:.4f}")
    if eye_diff >= 3:
        raise RuntimeError("Eye crop differs too much from the original composite")

    # Exclude the newly drawn tick rows, then count connected dark components
    # wider than 6px in the specified wall band.
    band = final[420:701, 180:331]
    dark = np.max(band, axis=2) < 55
    for yy in range(420, 701):
        if any(abs(yy - round(147 + k * (280 / 6))) <= 3 for k in range(40)):
            dark[yy - 420] = False
    labs, n = ndimage.label(dark)
    counts = np.bincount(labs.ravel())
    widths = np.zeros(n + 1, dtype=int)
    for lab in range(1, n + 1):
        xs = np.where(labs == lab)[1]
        widths[lab] = xs.max() - xs.min() + 1 if len(xs) else 0
    clusters = sum(widths[1:] > 6)
    print(f"Dark wall clusters wider than 6px in x=180..330, y=420..700: {clusters}")


def main():
    base = build_plate()
    compose.main(base=base, output_tag="a4")
    final_path = BUILD / "meme_a4.png"
    final = Image.open(final_path).convert("RGB")
    for name, box, scale in (
        ("crop_eyes_a4.png", (620, 330, 1000, 560), 3),
        ("crop_head_a4.png", (150, 60, 900, 560), 2),
    ):
        crop = final.crop(box)
        crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST).save(BUILD / name, optimize=True)
    report_checks(final_path)


if __name__ == "__main__":
    main()
