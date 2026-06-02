from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.services.banners.image_optimizer import ImageOptimizer


def _sample_png(width: int = 1600, height: int = 900) -> bytes:
    image = Image.new("RGB", (width, height), (20, 90, 160))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_optimizer_generates_responsive_webp_and_jpeg_variants() -> None:
    optimizer = ImageOptimizer(breakpoints=(320, 768, 1280))

    result = optimizer.optimize(_sample_png())

    formats = {(variant.size_key, variant.format) for variant in result.variants}
    assert ("320", "webp") in formats
    assert ("768", "webp") in formats
    assert ("1280", "webp") in formats
    assert ("320", "jpg") in formats
    assert ("768", "jpg") in formats
    assert ("1280", "jpg") in formats
    assert result.source_width == 1600
    assert result.source_height == 900
    assert result.report["generated"]["webp"] == 3
    assert result.report["generated"]["jpg"] == 3
    assert result.report["total_variants"] == len(result.variants)
    assert all(variant.bytes_data for variant in result.variants)
    assert all(variant.width <= 1280 for variant in result.variants)


def test_optimizer_never_upscales_small_images() -> None:
    result = ImageOptimizer(breakpoints=(320, 768)).optimize(_sample_png(width=240, height=120))

    assert {variant.width for variant in result.variants} == {240}
    assert {variant.height for variant in result.variants} == {120}
    assert result.report["effective_widths"] == [240]
    assert result.report["generated"]["webp"] == 1
    assert result.report["generated"]["jpg"] == 1


def test_optimizer_reports_avif_skip_or_generates_avif() -> None:
    result = ImageOptimizer(breakpoints=(320,)).optimize(_sample_png())

    if result.report["avif_skipped"]:
        assert result.report["avif_skip_reason"]
        assert all(variant.format != "avif" for variant in result.variants)
    else:
        assert any(variant.format == "avif" for variant in result.variants)
        assert result.report["generated"]["avif"] == 1


def test_optimizer_rejects_empty_or_invalid_input() -> None:
    try:
        ImageOptimizer().optimize(b"")
    except ValueError as exc:
        assert "image_bytes" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")

    try:
        ImageOptimizer().optimize(b"not an image")
    except ValueError as exc:
        assert "supported image" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_optimizer_rejects_oversized_inputs_before_decode() -> None:
    optimizer = ImageOptimizer()
    optimizer.max_input_bytes = 4

    try:
        optimizer.optimize(b"12345")
    except ValueError as exc:
        assert "maximum allowed input size" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_optimizer_rejects_oversized_pixel_dimensions_before_transpose() -> None:
    optimizer = ImageOptimizer()
    optimizer.max_pixels = 4

    try:
        optimizer.optimize(_sample_png(width=3, height=2))
    except ValueError as exc:
        assert "maximum allowed pixels" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
