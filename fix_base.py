#!/usr/bin/env python3
"""Repair the mugshot wall ticks and draw a regular height chart."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageDraw


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
SOURCE = BUILD / "media-generation-mugshot-base-v2-0-e07db233-f1cb-4f83-8494-15faecb4f112.webp"
OUTPUT = BUILD / "base_v3.png"


def runs(mask):
    """Half-open contiguous true runs."""
    ix = np.flatnonzero(mask)
    if not len(ix):
        return []
    cuts = np.flatnonzero(np.diff(ix) > 1) + 1
    return [(int(part[0]), int(part[-1]) + 1) for part in np.split(ix, cuts)]


def repair_wall_ticks(a):
    h, w, _ = a.shape
    gray = np.asarray(Image.fromarray(a).convert("L"))
    # Only these areas are safe to repair. The dark threshold catches tick ink;
    # require a long horizontal run to avoid altering plaster defects.
    # The side strips overlap the placard border below its top edge; stop
    # there so the placard itself is never sampled as a wall tick.
    zones = [(0, 340, 0, 730), (1240, w, 0, 730), (340, 1240, 0, 235), (340, 1240, 1470, h)]
    repaired = 0
    for x0, x1, y0, y1 in zones:
        for y in range(y0, y1):
            dark_runs = [(x, z) for x, z in runs(gray[y, x0:x1] < 82) if z - x >= 18]
            for sx, ex in dark_runs:
                left, right = x0 + sx, x0 + ex
                # Find an offset that maps the entire segment to a clean,
                # similarly lit stretch of wall on this same row.
                best = None
                for delta in (48, -48, 80, -80, 120, -120, 180, -180, 240, -240):
                    tx0, tx1 = left + delta, right + delta
                    if tx0 < 0 or tx1 > w:
                        continue
                    candidate = gray[y, tx0:tx1]
                    if np.mean(candidate < 82) < 0.04 and np.mean((candidate > 90) & (candidate < 210)) > 0.55:
                        # Prefer similar average lightness and nearer donors.
                        score = abs(float(candidate.mean()) - 128) + abs(delta) * 0.08
                        if best is None or score < best[0]:
                            best = (score, tx0)
                if best is None:
                    # A row-local median/noise fallback, with noise measured
                    # in nearby wall pixels, avoids a flat patch.
                    lo, hi = max(0, left - 90), min(w, right + 90)
                    local = a[y, lo:hi]
                    valid = (gray[y, lo:hi] > 90) & (gray[y, lo:hi] < 210)
                    samples = local[valid]
                    if len(samples) < 3:
                        continue
                    med = np.median(samples, axis=0)
                    sigma = np.std(samples.astype(float) - med, axis=0)
                    rng = np.random.default_rng(y * 1601 + left)
                    patch = np.clip(med + rng.normal(0, sigma, (right-left, 3)), 0, 255).astype(np.uint8)
                else:
                    patch = a[y, best[1]:best[1] + (right-left)].copy()
                # Feather only the horizontal seams; retain the donor's grain.
                original = a[y, left:right].astype(float)
                p = patch.astype(float)
                alpha = np.ones(right-left, dtype=float)
                feather = min(4, (right-left)//2)
                if feather:
                    alpha[:feather] = np.linspace(0.2, 1, feather)
                    alpha[-feather:] = np.linspace(1, 0.2, feather)
                a[y, left:right] = np.clip(original * (1-alpha[:, None]) + p * alpha[:, None], 0, 255).astype(np.uint8)
                repaired += 1
    return repaired


def soften_shadow(a):
    """Lift the darkest placard shadow pixels with a feathered mask."""
    im = Image.fromarray(a)
    gray = np.asarray(im.convert("L"))
    h, w = gray.shape
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[780:1391, 1323:1431] = 255
    mask[1370:1451, 260:1321] = 255
    soft = Image.fromarray(mask).filter(ImageFilter.GaussianBlur(14))
    alpha = np.asarray(soft, dtype=float) / 255.0
    # Target a nearby wall-brightness estimate; leave highlights and non-shadow
    # pixels alone, and blend only the darkest part of the shadow band.
    yy, xx = np.mgrid[:h, :w]
    target = np.zeros((h, w), dtype=float)
    right_wall = gray[820:1360, 1435:1515]
    right_med = float(np.median(right_wall)) if right_wall.size else 128
    below_wall = gray[1455:1520, 350:1250]
    below_med = float(np.median(below_wall)) if below_wall.size else 128
    target[:] = right_med
    target[1370:, :] = below_med
    darkness = np.clip((112 - gray.astype(float)) / 75.0, 0, 1)
    strength = alpha * darkness * 0.25
    a[:] = np.clip(a.astype(float) + strength[:, :, None] * (target[:, :, None] - a.astype(float)), 0, 255).astype(np.uint8)


def draw_even_ticks(a):
    gray = np.asarray(Image.fromarray(a).convert("L"))
    # Exclude the placard and all non-wall runs by requiring mid-grey wall
    # pixels. Shrink each detected wall run by six pixels as specified.
    wall = (gray > 90) & (gray < 210)
    ink = np.array([22, 22, 22], dtype=np.uint8)
    k = 0
    while True:
        row = int(round(147 + k * (280 / 6)))  # 6 inches spans 140 px, 2 inches = 46.6667
        if row < 30 or row > 1580:
            if row > 1580:
                break
            k += 1
            continue
        # Lines span x 400..1120, clipped to each contiguous wall run.
        for x0, x1 in runs(wall[row, 380:1141]):
            start, end = max(400, 380 + x0 + 6), min(1120, 380 + x1 - 6)
            if end > start:
                a[max(0, row-3):min(1600, row+4), start:end] = ink
        k += 1


def main():
    a = np.asarray(Image.open(SOURCE).convert("RGB")).copy()
    if a.shape != (1600, 1600, 3):
        raise ValueError(f"Expected 1600x1600 source, got {a.shape[1]}x{a.shape[0]}")
    n = repair_wall_ticks(a)
    # The available shadow area contains both the intentional cast shadow and
    # textured wall. A lift there produced a visible broad band, so keep it intact.
    draw_even_ticks(a)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a).save(OUTPUT, format="PNG", optimize=True)
    print(f"(a) Repaired {n} horizontal tick row segments in the specified wall zones using same-row wall texture patches.")
    print("(b) Drew 2-inch ticks at the specified 46.67 px spacing, clipped to wall-colored runs with 6 px end clearance.")
    print("(c) Skipped: shadow lifting produced a broad visible band on this textured wall, so the shadow was left intact.")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
