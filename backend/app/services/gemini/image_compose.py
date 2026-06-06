"""Chroma-key a generated hero onto a transparent background.

Nano Banana Pro does not reliably emit a true alpha channel (it tends to paint a
fake checkerboard or a baked backdrop). So we instead ask it to compose the
subject on a flat, pure chroma-green field and key that green out here — classic
chroma keying — to get a clean transparent PNG the banner background shows through.

Pillow-only (ImageMath band math, no numpy): build a green-dominance mask, set it
as alpha, suppress green spill on the edges, and feather slightly.
"""

from __future__ import annotations

import io

from PIL import Image, ImageChops, ImageFilter, ImageMath

# Default green-screen key. The compose prompt asks for pure #00FF00.
_GREEN_THRESHOLD = 90   # green channel must exceed this to be "background"
_GREEN_DELTA = 30       # and exceed red/blue by at least this much


def chroma_key_to_png(
    image_bytes: bytes,
    *,
    threshold: int = _GREEN_THRESHOLD,
    delta: int = _GREEN_DELTA,
    feather: float = 0.8,
    spill: bool = True,
) -> bytes:
    """Return a transparent PNG with the green chroma field removed.

    Raises ValueError if the input can't be decoded.
    """

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise ValueError("could not decode image for chroma key") from exc

    r, g, b = im.split()
    # background mask = 255 where green is dominant (the chroma field), else 0.
    bg = ImageMath.unsafe_eval(
        "convert(255 * ((g > t) & (g > (r + d)) & (g > (b + d))), 'L')",
        r=r, g=g, b=b, t=threshold, d=delta,
    )
    # alpha = inverse of the background mask (opaque on the subject).
    alpha = ImageChops.invert(bg)
    if feather and feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=feather))

    if spill:
        # Green-spill suppression: where the pixel is greenish, cap the green
        # channel to the brighter of red/blue so cutout edges don't fringe green.
        rb_max = ImageChops.lighter(r, b)
        g = ImageMath.unsafe_eval("convert(min(g, rb), 'L')", g=g, rb=rb_max)

    out = Image.merge("RGBA", (r, g, b, alpha))
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def transparent_fraction(png_bytes: bytes) -> float:
    """Fraction of fully/near transparent pixels — a quick keyed-out sanity check."""
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    alpha = im.getchannel("A")
    hist = alpha.histogram()
    transparent = sum(hist[0:16])
    total = im.size[0] * im.size[1]
    return transparent / total if total else 0.0


__all__ = ["chroma_key_to_png", "transparent_fraction"]
