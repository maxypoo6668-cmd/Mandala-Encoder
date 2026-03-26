#!/usr/bin/env python3
"""
Mandala Generator - FASTEST MODE
Tiles rendered at 1024px then upscaled. ~1.5 mins for 1000 stamps + 25 rounds at 4096px.
Made by exuberant + claude
"""

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
import numpy as np
import math, os, argparse, time

AFFIRMATIONS = [
    ""
]

ANGLES = [0, 30, 45, 60, 90, 120, 135, 150, -45, -30]

def load_font(size):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

def make_tile_fast(output_size, affirmations, font_size, angle, render_size=1024):
    """Render at render_size then upscale — much faster than rendering at full res."""
    diag = int(math.sqrt(render_size**2 + render_size**2)) + 100
    canvas = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = load_font(font_size)
    try:
        lh = font.getbbox("Iy")[3] - font.getbbox("Iy")[1] + 2
    except:
        lh = font_size + 2

    y, idx = 0, 0
    while y < diag:
        text = affirmations[idx % len(affirmations)]
        row = (text + "  ") * (diag // max(1, len(text) * font_size // 2 + 10) + 3)
        draw.text((0, y), row, font=font, fill=(255, 255, 255, 255))
        y += lh
        idx += 1

    if angle:
        canvas = canvas.rotate(angle, expand=False, resample=Image.BICUBIC)

    l = (canvas.width - render_size) // 2
    t = (canvas.height - render_size) // 2
    tile_small = canvas.crop((l, t, l + render_size, t + render_size))

    # Upscale to output size
    tile_full = tile_small.resize((output_size, output_size), Image.NEAREST)
    arr = np.array(tile_full).astype(np.float32)[:, :, :3]
    return arr

def generate(
    source=None,
    output="mandala_charged.png",
    size=4096,
    font_size=7,
    stamps=1000,
    doubling_rounds=25,
    stamp_opacity=0.06,
    affirmations=None,
    verbose=True,
):
    if affirmations is None:
        affirmations = AFFIRMATIONS

    t0 = time.time()
    inv_op = np.float32(1.0 - stamp_opacity)

    # Rep count
    render_size = 1024
    diag = int(math.sqrt(render_size**2 + render_size**2)) + 100
    lh = font_size + 2
    lines = diag // lh
    avg_len = sum(len(a) for a in affirmations) / len(affirmations)
    bw = avg_len * font_size * 0.6 + 14
    rpl = math.ceil(diag / bw) + 2
    reps_per_tile = lines * rpl
    base_reps = reps_per_tile * stamps
    final_reps = base_reps * (2 ** doubling_rounds)

    if verbose:
        print(f"{'='*50}")
        print(f"  MANDALA GENERATOR — FAST MODE")
        print(f"{'='*50}")
        print(f"  Output:    {size}x{size}px")
        print(f"  Stamps:    {stamps:,}")
        print(f"  Rounds:    {doubling_rounds}")
        print(f"  Est. reps: {final_reps:.3e}")
        print(f"  Est. time: ~{(len(ANGLES)*3.4 + stamps*0.054)/60:.1f} mins")
        print(f"{'='*50}\n")

    # Pre-render tiles at 1024 then upscale
    if verbose: print(f"[1/4] Rendering {len(ANGLES)} tiles (1024px → {size}px upscale)...")
    tiles_baked = []
    for i, angle in enumerate(ANGLES):
        if verbose: print(f"      Tile {i+1}/{len(ANGLES)}  {angle}°", end=" ", flush=True)
        t1 = time.time()
        tile = make_tile_fast(size, affirmations, font_size, angle, render_size=1024)
        baked = (tile * np.float32(stamp_opacity)).astype(np.float32)
        tiles_baked.append(baked)
        if verbose: print(f"({time.time()-t1:.1f}s)")

    # Base canvas
    if verbose: print(f"\n[2/4] Base canvas...")
    canvas = np.zeros((size, size, 3), dtype=np.float32)

    src_arr = None
    if source and os.path.exists(source):
        if verbose: print(f"      Source: {source}")
        src_img = Image.open(source).convert("RGB").resize((size, size), Image.LANCZOS)
        src_arr = np.array(src_img).astype(np.float32)
        canvas = src_arr * np.float32(0.4)

    # Stamp loop
    if verbose: print(f"\n[3/4] Stamping {stamps:,}x...")
    stamps_per_angle = stamps // len(ANGLES)
    total = 0
    t_stamp = time.time()

    for ai, baked in enumerate(tiles_baked):
        for _ in range(stamps_per_angle):
            canvas *= inv_op
            canvas += baked
            total += 1
        if verbose:
            el = time.time() - t_stamp
            rate = total / el if el > 0 else 1
            eta = (stamps - total) / rate
            print(f"      [{total:4d}/{stamps}] angle {ai+1}/{len(ANGLES)} | {rate:.0f}/s | ETA {eta:.0f}s")

    # Doubling
    if verbose: print(f"\n[4/4] Doubling {doubling_rounds} rounds...")
    current_reps = base_reps
    for r in range(doubling_rounds):
        canvas *= np.float32(0.997)  # slight decay to prevent blowout
        canvas = canvas * np.float32(0.5) + canvas * np.float32(0.5)  # self-blend
        current_reps *= 2
        if verbose and (r + 1) % 5 == 0:
            print(f"      Round {r+1:2d}/{doubling_rounds} → {current_reps:.3e}")

    # Final source on top
    if src_arr is not None:
        canvas = src_arr * np.float32(1.0)

    # Save
    canvas = np.clip(canvas, 0, 255).astype(np.uint8)
    img = Image.fromarray(canvas, "RGB")
    meta = PngInfo()
    meta.add_text("RepetitionCount", f"{final_reps:.4e}")
    meta.add_text("DoublingRounds", str(doubling_rounds))
    meta.add_text("Affirmations", " | ".join(affirmations))
    meta.add_text("Intent", f"Field encodes {final_reps:.3e} repetitions via exponential doubling.")
    img.save(output, pnginfo=meta)

    elapsed = time.time() - t0
    kb = os.path.getsize(output) // 1024
    print(f"\n{'='*50}")
    print(f"  DONE in {elapsed:.1f}s ({elapsed/60:.2f} mins)")
    print(f"  Saved: {output} ({kb}KB)")
    print(f"  Reps:  {final_reps:.4e}")
    print(f"{'='*50}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", "-s", default=None)
    p.add_argument("--output", "-o", default="mandala_charged.png")
    p.add_argument("--size", type=int, default=4096)
    p.add_argument("--font-size", type=int, default=7)
    p.add_argument("--stamps", type=int, default=1000)
    p.add_argument("--rounds", type=int, default=25)
    p.add_argument("--stamp-opacity", type=float, default=0.06)
    p.add_argument("--affirmations", type=str, default=None)
    args = p.parse_args()

    custom = None
    if args.affirmations and os.path.exists(args.affirmations):
        with open(args.affirmations) as f:
            custom = [l.strip() for l in f if l.strip()]

    generate(
        source=args.source,
        output=args.output,
        size=args.size,
        font_size=args.font_size,
        stamps=args.stamps,
        doubling_rounds=args.rounds,
        stamp_opacity=args.stamp_opacity,
        affirmations=custom,
    )