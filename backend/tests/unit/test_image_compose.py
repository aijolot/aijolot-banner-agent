"""Chroma-key compose util — green field → transparent PNG."""

from __future__ import annotations

import io

from PIL import Image

from app.services.gemini.image_compose import chroma_key_to_png, transparent_fraction


def _green_with_red_square(size=64, square=24) -> bytes:
    im = Image.new("RGB", (size, size), (0, 255, 0))  # pure chroma green
    off = (size - square) // 2
    for y in range(off, off + square):
        for x in range(off, off + square):
            im.putpixel((x, y), (220, 40, 30))  # opaque red subject
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_green_is_keyed_out_subject_kept() -> None:
    png = chroma_key_to_png(_green_with_red_square())
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    assert im.mode == "RGBA"
    w, h = im.size
    # corner (green) → transparent; center (red subject) → opaque.
    assert im.getpixel((1, 1))[3] == 0
    assert im.getpixel((w // 2, h // 2))[3] > 200


def test_transparent_fraction_reports_keyed_area() -> None:
    png = chroma_key_to_png(_green_with_red_square(size=64, square=24))
    frac = transparent_fraction(png)
    # 64x64 minus a 24x24 subject → most of the frame is transparent.
    assert 0.6 < frac < 0.95


def test_invalid_bytes_raise() -> None:
    import pytest

    with pytest.raises(ValueError):
        chroma_key_to_png(b"not an image")
