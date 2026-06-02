"""ADK Tool: multi-breakpoint image optimization and asset persistence."""

from __future__ import annotations

from typing import Any

from app.agents.state import BannerAssets
from app.services.banners.asset_service import BannerAssetService, configured_asset_service
from app.services.banners.image_optimizer import ImageOptimizer, OptimizedImageVariant


async def optimize(
    image_bytes: bytes,
    *,
    alt_text_hint: str,
    campaign_id: str | None = None,
    revision_id: str | None = None,
    banner_variant_id: str | None = None,
    mime_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    image_prompt: str | None = None,
    asset_service: BannerAssetService | None = None,
) -> BannerAssets:
    """Optimize image bytes and optionally store durable Supabase assets.

    When campaign_id and revision_id are supplied, variants are uploaded and
    recorded through BannerAssetService. Without them, the tool still returns a
    deterministic local optimization report for graph/unit use without storage.
    """

    source_metadata = {**(metadata or {})}
    if mime_type:
        source_metadata.setdefault("mime_type", mime_type)

    if campaign_id and revision_id:
        service = asset_service or configured_asset_service()
        stored = service.optimize_upload_and_record(
            image_bytes=image_bytes,
            campaign_id=campaign_id,
            revision_id=revision_id,
            banner_variant_id=banner_variant_id,
            alt_text=alt_text_hint,
            image_prompt=image_prompt,
            source_metadata=source_metadata,
        )
        return _assets_from_records(
            records=stored.asset_records,
            alt_text_hint=alt_text_hint,
            report={**stored.optimization_report, "upload": stored.upload_report},
        )

    optimized = ImageOptimizer().optimize(image_bytes)
    return _assets_from_variants(optimized.variants, alt_text_hint=alt_text_hint, report=optimized.report)


def _assets_from_records(*, records: list[dict[str, Any]], alt_text_hint: str, report: dict[str, Any]) -> BannerAssets:
    webp: dict[int, str] = {}
    avif: dict[int, str] = {}
    fallback_jpg: dict[int, str] = {}
    weight_1280_webp = 0.0
    for record in records:
        size_key = int(record.get("size_key") or record.get("width") or 0)
        if size_key <= 0:
            continue
        locator = str(record.get("public_url") or record.get("storage_path"))
        fmt = str(record.get("format") or "").lower()
        if fmt == "webp":
            webp[size_key] = locator
            if size_key == 1280:
                weight_1280_webp = round(float(record.get("bytes") or 0) / 1024, 2)
        elif fmt == "avif":
            avif[size_key] = locator
        elif fmt in {"jpg", "jpeg"}:
            fallback_jpg[size_key] = locator
    return BannerAssets(
        webp=webp,
        avif=avif,
        fallback_jpg=fallback_jpg,
        alt_text_suggestion=alt_text_hint,
        total_weight_kb_1280_webp=weight_1280_webp,
        asset_records=records,
        optimization_report=report,
    )


def _assets_from_variants(variants: list[OptimizedImageVariant], *, alt_text_hint: str, report: dict[str, Any]) -> BannerAssets:
    records: list[dict[str, Any]] = []
    for variant in variants:
        records.append(
            {
                "size_key": variant.size_key,
                "width": variant.width,
                "height": variant.height,
                "format": variant.format,
                "storage_path": f"memory://optimized/{variant.size_key}w.{variant.format}",
                "bytes": variant.bytes_size,
                "metadata": {"mime_type": variant.mime_type, **variant.metadata},
            }
        )
    return _assets_from_records(records=records, alt_text_hint=alt_text_hint, report=report)
