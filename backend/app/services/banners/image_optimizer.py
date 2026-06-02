from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError, features


@dataclass(frozen=True)
class OptimizedImageVariant:
    size_key: str
    width: int
    height: int
    format: str
    mime_type: str
    bytes_data: bytes
    bytes_size: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageOptimizationResult:
    variants: list[OptimizedImageVariant]
    source_width: int
    source_height: int
    source_format: str | None
    report: dict[str, Any]


class ImageOptimizer:
    """Pillow-backed optimizer for responsive banner image assets.

    The optimizer is intentionally deterministic: fixed breakpoints, quality,
    method, and non-progressive outputs. AVIF is optional and reported as skipped
    when the local Pillow build cannot encode it.
    """

    default_breakpoints = (320, 768, 1280, 1920)
    max_input_bytes = 10 * 1024 * 1024
    max_pixels = 16_000_000

    def __init__(
        self,
        *,
        breakpoints: tuple[int, ...] | list[int] | None = None,
        webp_quality: int = 78,
        jpeg_quality: int = 82,
        avif_quality: int = 60,
    ) -> None:
        self.breakpoints = tuple(sorted(set(breakpoints or self.default_breakpoints)))
        self.webp_quality = webp_quality
        self.jpeg_quality = jpeg_quality
        self.avif_quality = avif_quality

    def optimize(self, image_bytes: bytes) -> ImageOptimizationResult:
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")
        if len(image_bytes) > self.max_input_bytes:
            raise ValueError("image_bytes exceeds maximum allowed input size")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(image_bytes)) as opened:
                    if opened.width * opened.height > self.max_pixels:
                        raise ValueError("image dimensions exceed maximum allowed pixels")
                    source = ImageOps.exif_transpose(opened)
                    if source.mode not in ("RGB", "RGBA"):
                        source = source.convert("RGBA" if "A" in source.getbands() else "RGB")
                    source_width, source_height = source.size
                    source_format = opened.format
                    source_bytes = len(image_bytes)

                    variants: list[OptimizedImageVariant] = []
                    generated_counts: dict[str, int] = {"webp": 0, "jpg": 0, "avif": 0}

                    effective_widths = self._effective_widths(source_width)
                    for target_width in effective_widths:
                        resized = self._resize(source, target_width)
                        size_key = str(resized.width)
                        variants.append(self._encode_variant(resized, size_key=size_key, format_name="WEBP"))
                        generated_counts["webp"] += 1
                        variants.append(self._encode_variant(resized, size_key=size_key, format_name="JPEG"))
                        generated_counts["jpg"] += 1

                    avif_skip_reason = self._avif_skip_reason()
                    if avif_skip_reason is None:
                        for target_width in effective_widths:
                            resized = self._resize(source, target_width)
                            size_key = str(resized.width)
                            try:
                                variants.append(self._encode_variant(resized, size_key=size_key, format_name="AVIF"))
                                generated_counts["avif"] += 1
                            except Exception as exc:  # pragma: no cover - depends on optional codec runtime
                                avif_skip_reason = f"AVIF encode failed: {exc}"
                                generated_counts["avif"] = 0
                                variants = [variant for variant in variants if variant.format != "avif"]
                                break
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("image_bytes must contain a supported image") from exc
        except Image.DecompressionBombWarning as exc:
            raise ValueError("image dimensions exceed maximum allowed pixels") from exc

        report: dict[str, Any] = {
            "source": {
                "width": source_width,
                "height": source_height,
                "format": source_format,
                "bytes": source_bytes,
            },
            "breakpoints": list(self.breakpoints),
            "effective_widths": effective_widths,
            "generated": generated_counts,
            "total_variants": len(variants),
            "formats": sorted({variant.format for variant in variants}),
        }
        if avif_skip_reason is not None:
            report["avif_skipped"] = True
            report["avif_skip_reason"] = avif_skip_reason
        else:
            report["avif_skipped"] = False

        return ImageOptimizationResult(
            variants=variants,
            source_width=source_width,
            source_height=source_height,
            source_format=source_format,
            report=report,
        )

    def _effective_widths(self, source_width: int) -> list[int]:
        return sorted({min(width, source_width) for width in self.breakpoints if width > 0})

    def _resize(self, image: Image.Image, target_width: int) -> Image.Image:
        width, height = image.size
        output_width = min(target_width, width)
        if output_width == width:
            return image.copy()
        output_height = max(1, round(height * (output_width / width)))
        return image.resize((output_width, output_height), Image.Resampling.LANCZOS)

    def _encode_variant(self, image: Image.Image, *, size_key: str, format_name: str) -> OptimizedImageVariant:
        output = BytesIO()
        normalized = self._normalize_for_format(image, format_name)
        save_kwargs: dict[str, Any]
        ext: str
        mime_type: str
        fmt = format_name.upper()
        if fmt == "WEBP":
            save_kwargs = {"quality": self.webp_quality, "method": 6}
            ext = "webp"
            mime_type = "image/webp"
        elif fmt == "JPEG":
            save_kwargs = {"quality": self.jpeg_quality, "optimize": True, "progressive": False}
            ext = "jpg"
            mime_type = "image/jpeg"
        elif fmt == "AVIF":
            save_kwargs = {"quality": self.avif_quality}
            ext = "avif"
            mime_type = "image/avif"
        else:  # pragma: no cover - internal guard
            raise ValueError(f"unsupported format: {format_name}")
        normalized.save(output, format=fmt, **save_kwargs)
        data = output.getvalue()
        return OptimizedImageVariant(
            size_key=size_key,
            width=normalized.width,
            height=normalized.height,
            format=ext,
            mime_type=mime_type,
            bytes_data=data,
            bytes_size=len(data),
            metadata={"quality": save_kwargs.get("quality")},
        )

    @staticmethod
    def _normalize_for_format(image: Image.Image, format_name: str) -> Image.Image:
        if format_name.upper() in {"JPEG", "AVIF"} and image.mode != "RGB":
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "RGBA":
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image.convert("RGB"))
            return background
        if format_name.upper() == "WEBP" and image.mode not in ("RGB", "RGBA"):
            return image.convert("RGBA" if "A" in image.getbands() else "RGB")
        return image.copy()

    @staticmethod
    def _avif_skip_reason() -> str | None:
        try:
            import pillow_avif  # type: ignore[import-not-found]  # noqa: F401
        except Exception:
            pass
        # Pillow features.check("avif") is available in newer builds; SAVE keys
        # catches plugin registration in older builds.
        try:
            if features.check("avif"):
                return None
        except Exception:
            pass
        try:
            if "AVIF" in Image.SAVE:
                return None
        except Exception:
            pass
        return "Pillow AVIF encoder is not available"
