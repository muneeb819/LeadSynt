#!/usr/bin/env python3
"""Build the LeadSynt branding asset set from the master uploads.

Outputs (frontend/public/branding/ + app icon):
  leadsynt-website-black.png    black master, transparent (white header)
  leadsynt-website-white.png    white master, transparent (dark mode/footer)
  leadsynt-monogram-black.png   512 mark-only, transparent
  leadsynt-monogram-white.png   512 mark-only, transparent
  leadsynt-monogram-white-32.png 32 favicon size
  leadsynt-hover-master.png     hover state (master)
  leadsynt-hover-monogram.png   hover state (monogram)
  leadsynt-loader-static.png    copy of provided (navy #0A1020)
  leadsynt-loader.gif           animated preloader (pulse)
  leadsynt-hero-banner.png      wide banner (from webp upload)
  app/icon.png                  512 white mark (favicon, auto-served by Next)
"""
from PIL import Image
import math
import os
import shutil

UP = "/home/user/uploads"
OUT = "/home/user/LeadSynt/frontend/public/branding"
APP = "/home/user/LeadSynt/frontend/app"
os.makedirs(OUT, exist_ok=True)


def load(name):
    return Image.open(os.path.join(UP, name)).convert("RGBA")


def content_bbox(im, thresh=20):
    a = im.getchannel("A")
    return a.point(lambda x: 255 if x > thresh else 0).getbbox() or (0, 0, *im.size)


def crop_pad(im, bbox, pad_frac=0.06):
    """Crop the source to a square region centered on the content bbox
    (out-of-bounds areas become transparent), with proportional padding."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    m = max(w, h)
    pad = int(m * pad_frac)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = (m / 2) + pad
    sx0, sy0 = int(cx - half), int(cy - half)
    return im.crop((sx0, sy0, sx0 + int(2 * half), sy0 + int(2 * half)))


def mark_to_square(im, mark_bbox, out_size=512, margin_frac=0.07):
    """Crop the mark (keeping aspect ratio) and center it on a square
    transparent canvas — no risk of swallowing the wordmark below."""
    x0, y0, x1, y1 = mark_bbox
    w, h = x1 - x0, y1 - y0
    pad = int(max(w, h) * 0.04)
    crop = im.crop((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
    cw, ch = crop.size
    scale = (out_size * (1 - 2 * margin_frac)) / max(cw, ch)
    crop = crop.resize((max(1, int(cw * scale)), max(1, int(ch * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (out_size, out_size), (0, 0, 0, 0))
    canvas.paste(crop, ((out_size - crop.width) // 2, (out_size - crop.height) // 2), crop)
    return canvas


def find_row_gap(im, bbox):
    """Find the biggest transparent horizontal band inside content.
    Returns (mark_box, text_box) if a clean gap exists, else (bbox, None)."""
    x0, y0, x1, y1 = bbox
    a = im.getchannel("A")
    rows = [0] * (y1 - y0)
    for y in range(y0, y1):
        s = 0
        for x in range(x0, x1, 2):
            s += a.getpixel((x, y))
        rows[y - y0] = s
    # find longest run of near-empty rows
    best = (0, 0, 0)  # start, end, length (relative)
    run_start = None
    for i, s in enumerate(rows):
        if s < 300:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                if i - run_start > best[2]:
                    best = (run_start, i, i - run_start)
                run_start = None
    if run_start is not None and (y1 - y0) - run_start > best[2]:
        best = (run_start, y1 - y0, (y1 - y0) - run_start)
    gap_len = best[2]
    if gap_len > 0.03 * (y1 - y0) and best[0] > 0.15 * (y1 - y0) and best[1] < 0.95 * (y1 - y0):
        # mark = everything ABOVE the gap, text = everything below it
        mark = (x0, y0, x1, y0 + best[0])
        text = (x0, y0 + best[1], x1, y1)
        return mark, text
    return bbox, None


def save(name, im):
    path = os.path.join(OUT, name)
    im.save(path, optimize=True)
    print(f"  {name:34s} {im.size[0]}x{im.size[1]}  {os.path.getsize(path)//1024} KB")


# ---------- 1. website masters (wide, keep native aspect) ----------
print("website masters")
for src, dst in [("MASTER_BLACK.png", "leadsynt-website-black.png"),
                 ("MASTER_WHITE.png", "leadsynt-website-white.png")]:
    im = load(src)
    bb = content_bbox(im)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    pad = int(max(w, h) * 0.04)
    im = im.crop((bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad))
    save(dst, im)

# ---------- 2. hover states ----------
print("hover states")
for src, dst in [("HOVER_MASTER.png", "leadsynt-hover-master.png"),
                 ("HOVER_MONOGRAM.png", "leadsynt-hover-monogram.png")]:
    im = load(src)
    bb = content_bbox(im)
    pad = int(max(bb[2] - bb[0], bb[3] - bb[1]) * 0.05)
    im = im.crop((bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad))
    save(dst, im)

# ---------- 3. monograms (mark-only, 512 square) ----------
print("monograms")
MONO_SOURCES = [("V1_white.png", "leadsynt-monogram-white.png"),
                ("image_20260918_133445_transparent.png", "leadsynt-monogram-black.png")]
for src, dst in MONO_SOURCES:
    im = load(src)
    bb = content_bbox(im)
    mark, text = find_row_gap(im, bb)
    box = mark if text else bb
    print(f"  {src}: content={bb} mark_only={box if text else 'n/a (full content)'}")
    save(dst, mark_to_square(im, box, out_size=512))

m32 = load(MONO_SOURCES[0][0])
mark, _ = find_row_gap(m32, content_bbox(m32))
save("leadsynt-monogram-white-32.png", mark_to_square(m32, mark, out_size=32, margin_frac=0.05))

# app icon (white mark, transparent) — Next auto-serves as favicon
im = load(MONO_SOURCES[0][0])
mark, _ = find_row_gap(im, content_bbox(im))
icon = mark_to_square(im, mark, out_size=512)
icon.save(os.path.join(APP, "icon.png"), optimize=True)
print(f"  app/icon.png                     512x512  favicon")

# ---------- 4. loader static (copy) + animated gif ----------
print("loader")
shutil.copy(os.path.join(UP, "leadsynt_loader_static.png"),
            os.path.join(OUT, "leadsynt-loader-static.png"))
print("  leadsynt-loader-static.png         copied (navy #0A1020)")

base = Image.open(os.path.join(OUT, "leadsynt-loader-static.png")).convert("RGBA")
size = 480
base = base.resize((size, size), Image.LANCZOS)
frames = []
n = 14
for i in range(n):
    t = i / n
    # sine pulse 0.35 -> 1.0
    op = 0.35 + 0.65 * (0.5 - 0.5 * math.cos(2 * math.pi * t))
    f = base.copy()
    a = f.getchannel("A").point(lambda v, op=op: int(v * op))
    f.putalpha(a)
    frames.append(f.convert("P", palette=Image.ADAPTIVE, colors=256))
frames[0].save(
    os.path.join(OUT, "leadsynt-loader.gif"),
    save_all=True, append_images=frames[1:], duration=110, loop=0,
    optimize=True, disposal=2,
)
print(f"  leadsynt-loader.gif              {size}x{size}  {n} frames  "
      f"{os.path.getsize(os.path.join(OUT, 'leadsynt-loader.gif'))//1024} KB")

# ---------- 5. hero banner (bonus) ----------
banner = Image.open(os.path.join(UP, "image_20260918_134631.webp")).convert("RGB")
save("leadsynt-hero-banner.png", banner)

print("\nDone.")
