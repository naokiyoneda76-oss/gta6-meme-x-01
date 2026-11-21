#!/usr/bin/env python3
"""Compose the GTA VI mugshot placard at native resolution."""

from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
BASE = BUILD / "base_v3.png"
STATIC_OSWALD = ROOT / "fonts" / "Oswald-Bold-Static.ttf"
OSWALD = ROOT / "fonts" / "Oswald-Bold.ttf"
MONO = "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"
SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
INK = (17, 17, 17)


def make_static_font():
    """Pin the variable Oswald face to bold and save a reusable static TTF."""
    source = TTFont(OSWALD)
    variable_axes = {axis.axisTag: 700 for axis in source["fvar"].axes}
    static = instantiateVariableFont(source, variable_axes, inplace=False, overlap=False)
    static.flavor = None
    static.save(STATIC_OSWALD)


def tracked_width(font, text, tracking):
    if not text:
        return 0.0
    return sum(font.getlength(ch) for ch in text) + tracking * (len(text) - 1)


def fit_size(font_path, text, max_width, tracking=0, target=None):
    """Binary search the largest integer size that fits max_width."""
    lo, hi = 1, (max(1, int(target)) if target is not None else 512)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if tracked_width(ImageFont.truetype(font_path, mid), text, tracking) <= max_width:
            lo = mid
        else:
            hi = mid
    return max(1, lo)


def text_height(font, text):
    box = font.getbbox(text)
    return box[3] - box[1]


def draw_centered(draw, font, text, center_x, top, tracking=0):
    box = font.getbbox(text)
    y = int(round(top - box[1]))
    if tracking == 0:
        w = draw.textlength(text, font=font)
        draw.text((center_x - w / 2, y), text, font=font, fill=INK)
        return (center_x - w / 2, top, center_x + w / 2, top + box[3] - box[1])
    width = tracked_width(font, text, tracking)
    x = center_x - width / 2
    left = x
    for ch in text:
        draw.text((x, y), ch, font=font, fill=INK)
        x += font.getlength(ch) + tracking
    return (left, top, left + width, top + box[3] - box[1])


def main(base=BASE, output_tag="a2"):
    make_static_font()
    image = Image.open(base).convert("RGB")
    if image.size != (1600, 1600):
        raise ValueError(f"Expected 1600x1600 base, got {image.size}")

    draw = ImageDraw.Draw(image)
    # Placard inner box is inset 26 px from the measured outer rectangle.
    left, right = 247 + 26, 1323 - 26
    top, bottom = 762 + 26, 1370 - 26
    center_x = 785
    inner_width = right - left
    max_line = inner_width * 0.94
    narrow_line = inner_width * 0.62

    line1 = "LEONIDA PD"
    headline = "GRAND THEFT AUTO"
    subline = "— REAL LIFE —"
    excuse = 'EXCUSE: "13 YEARS OF PRACTICE"'
    field = "ID NO. 0013 | DATE 11.19.2026 | CASE: GTA VI"

    sizes = {
        "LEONIDA PD": fit_size(STATIC_OSWALD, line1, narrow_line, tracking=6, target=92),
        "GRAND THEFT AUTO": fit_size(STATIC_OSWALD, headline, max_line),
        "— REAL LIFE —": None,
        'EXCUSE: "13 YEARS OF PRACTICE"': fit_size(STATIC_OSWALD, excuse, max_line),
        field: fit_size(MONO, field, max_line, target=54),
    }
    sizes[subline] = max(1, round(sizes[headline] * 0.78))

    # Seven elements: five text rows and two rules. If needed, shrink all
    # type sizes uniformly before laying out the available generous gaps.
    specs = [
        ("text", line1, STATIC_OSWALD, 6),
        ("rule", None, None, 0),
        ("text", headline, STATIC_OSWALD, 0),
        ("text", subline, STATIC_OSWALD, 0),
        ("text", excuse, STATIC_OSWALD, 0),
        ("rule", None, None, 0),
        ("text", field, MONO, 0),
    ]
    avail_top, avail_bottom = 875, 1330
    heights = []
    fonts = []
    for kind, text, path, tracking in specs:
        if kind == "rule":
            heights.append(3)
            fonts.append(None)
        else:
            font = ImageFont.truetype(path, sizes[text])
            fonts.append(font)
            heights.append(text_height(font, text))
    gap = 18
    total = sum(heights) + gap * (len(specs) - 1)
    if total > avail_bottom - avail_top:
        factor = (avail_bottom - avail_top - gap * (len(specs) - 1)) / sum(heights)
        for name in list(sizes):
            sizes[name] = max(1, int(sizes[name] * factor))
        fonts = []
        heights = []
        for kind, text, path, tracking in specs:
            if kind == "rule":
                heights.append(3)
                fonts.append(None)
            else:
                font = ImageFont.truetype(path, sizes[text])
                fonts.append(font)
                heights.append(text_height(font, text))
        total = sum(heights) + gap * (len(specs) - 1)
    if total < avail_bottom - avail_top:
        gap = (avail_bottom - avail_top - sum(heights)) / (len(specs) - 1)

    y = float(avail_top)
    boxes = []
    for i, (kind, text, _path, tracking) in enumerate(specs):
        h = heights[i]
        if kind == "rule":
            rule_width = round(inner_width * 0.70)
            x0 = center_x - rule_width // 2
            draw.rectangle((x0, round(y), x0 + rule_width, round(y) + 2), fill=INK)
            boxes.append((x0, round(y), x0 + rule_width, round(y) + 3))
        else:
            boxes.append(draw_centered(draw, fonts[i], text, center_x, y, tracking))
        y += h + gap

    block_bbox = (
        round(min(box[0] for box in boxes)),
        round(min(box[1] for box in boxes)),
        round(max(box[2] for box in boxes)),
        round(max(box[3] for box in boxes)),
    )

    # Fixed chart label rows, independent of the base-image tick pixels.
    chart_font = ImageFont.truetype(SANS, 44)
    for label, cy in (("5'6\"", 147), ("5'0\"", 287)):
        box = draw.textbbox((0, 0), label, font=chart_font)
        draw.text((392 - (box[2] - box[0]), cy - (box[3] - box[1]) / 2 - box[1]),
                  label, font=chart_font, fill=INK)

    BUILD.mkdir(parents=True, exist_ok=True)
    output = BUILD / f"meme_{output_tag}.png"
    preview = BUILD / f"preview480_{output_tag}.png"
    image.save(output, format="PNG", optimize=True)
    image.resize((480, 480), Image.Resampling.LANCZOS).save(preview, format="PNG", optimize=True)

    print("Final font sizes:")
    for name, size in sizes.items():
        print(f"  {name}: {size}px")
    print(f"Placard text block bbox: {block_bbox}")
    print("Chart tick labels: 5'6\" centered at y=147; 5'0\" centered at y=287; 44px Liberation Sans Bold")
    print(f"Wrote {output}")
    print(f"Wrote {preview}")


if __name__ == "__main__":
    main()
