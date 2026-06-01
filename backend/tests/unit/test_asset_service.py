from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from PIL import Image

from app.agents.tools import image_optim
from app.services.banners.asset_service import BannerAssetService
from app.services.banners.image_optimizer import ImageOptimizer


class FakeStorageClient:
    def __init__(self) -> None:
        self.uploads: list[dict[str, Any]] = []

    def upload(self, *, bucket: str, path: str, data: bytes, content_type: str, upsert: bool = True) -> dict[str, Any]:
        self.uploads.append(
            {"bucket": bucket, "path": path, "data": data, "content_type": content_type, "upsert": upsert}
        )
        return {"path": path}

    def public_url(self, *, bucket: str, path: str) -> str | None:
        return f"https://cdn.example.test/{bucket}/{path}"


class FakeAssetRepository:
    def __init__(self) -> None:
        self.assets: list[dict[str, Any]] = []

    def create_many(self, *, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.assets.extend(dict(asset) for asset in assets)
        return [{"id": f"asset-{idx}", **asset} for idx, asset in enumerate(assets, start=1)]


def _sample_png() -> bytes:
    image = Image.new("RGB", (1024, 512), (200, 80, 40))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_asset_service_uploads_variants_and_records_banner_assets() -> None:
    storage = FakeStorageClient()
    repo = FakeAssetRepository()
    service = BannerAssetService(
        storage_client=storage,
        asset_repository=repo,
        bucket="campaign-assets",
        optimizer=ImageOptimizer(breakpoints=(320,)),
    )

    result = service.optimize_upload_and_record(
        image_bytes=_sample_png(),
        campaign_id="campaign-1",
        revision_id="revision-1",
        alt_text="Orange product hero",
        image_prompt="prompt",
        source_metadata={"provider": "fake"},
    )

    assert len(storage.uploads) >= 2
    assert len(result.asset_records) == len(storage.uploads)
    assert result.upload_report["uploaded_count"] == len(storage.uploads)
    first = result.asset_records[0]
    assert first["revision_id"] == "revision-1"
    assert first["asset_kind"] == "generated_background"
    assert first["storage_path"].startswith("campaigns/campaign-1/revisions/revision-1/generated_background/")
    assert first["storage_path"].endswith("/320w.webp") or first["storage_path"].endswith("/320w.jpg")
    assert first["public_url"].startswith("https://cdn.example.test/campaign-assets/")
    assert first["alt_text"] == "Orange product hero"
    assert first["metadata"]["source"] == {"provider": "fake"}
    assert {upload["content_type"] for upload in storage.uploads} >= {"image/webp", "image/jpeg"}


def test_asset_service_paths_are_unique_per_banner_variant() -> None:
    first_storage = FakeStorageClient()
    second_storage = FakeStorageClient()
    image_bytes = _sample_png()
    base_kwargs = {
        "image_bytes": image_bytes,
        "campaign_id": "campaign-1",
        "revision_id": "revision-1",
    }

    BannerAssetService(
        storage_client=first_storage,
        asset_repository=FakeAssetRepository(),
        optimizer=ImageOptimizer(breakpoints=(320,)),
    ).optimize_upload_and_record(**base_kwargs, banner_variant_id="variant-A")
    BannerAssetService(
        storage_client=second_storage,
        asset_repository=FakeAssetRepository(),
        optimizer=ImageOptimizer(breakpoints=(320,)),
    ).optimize_upload_and_record(**base_kwargs, banner_variant_id="variant-B")

    assert {upload["path"] for upload in first_storage.uploads}.isdisjoint(
        {upload["path"] for upload in second_storage.uploads}
    )


def test_asset_service_requires_campaign_and_revision() -> None:
    service = BannerAssetService(
        storage_client=FakeStorageClient(),
        asset_repository=FakeAssetRepository(),
        optimizer=ImageOptimizer(breakpoints=(320,)),
    )

    with pytest.raises(ValueError):
        service.optimize_upload_and_record(image_bytes=_sample_png(), campaign_id="", revision_id="rev")
    with pytest.raises(ValueError):
        service.optimize_upload_and_record(image_bytes=_sample_png(), campaign_id="camp", revision_id="")


@pytest.mark.asyncio
async def test_image_optim_tool_uses_injected_asset_service() -> None:
    storage = FakeStorageClient()
    repo = FakeAssetRepository()
    service = BannerAssetService(
        storage_client=storage,
        asset_repository=repo,
        optimizer=ImageOptimizer(breakpoints=(320,)),
    )

    assets = await image_optim.optimize(
        _sample_png(),
        alt_text_hint="Alt text",
        campaign_id="campaign-1",
        revision_id="revision-1",
        mime_type="image/png",
        metadata={"generation_provider": "fake"},
        asset_service=service,
    )

    assert assets.webp[320].endswith("/320w.webp")
    assert assets.fallback_jpg[320].endswith("/320w.jpg")
    assert assets.alt_text_suggestion == "Alt text"
    assert assets.asset_records
    assert assets.optimization_report["upload"]["uploaded_count"] == len(storage.uploads)
    assert repo.assets[0]["metadata"]["source"]["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_image_optim_tool_without_storage_makes_no_external_calls() -> None:
    assets = await image_optim.optimize(_sample_png(), alt_text_hint="Alt only")

    assert assets.webp[320].startswith("memory://optimized/")
    assert assets.fallback_jpg[320].startswith("memory://optimized/")
    assert assets.asset_records
    assert "avif_skipped" in assets.optimization_report
