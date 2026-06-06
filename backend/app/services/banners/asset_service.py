from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Protocol

from app.core.settings import Settings
from app.db.repositories.banner_assets import BannerAssetRepository
from app.services.banners.image_optimizer import ImageOptimizationResult, ImageOptimizer, OptimizedImageVariant
from app.services.supabase.client import SupabaseClientFactory, SupabaseStorageAdapter


class StorageClientProtocol(Protocol):
    def upload(self, *, bucket: str, path: str, data: bytes, content_type: str, upsert: bool = True) -> dict[str, Any]: ...
    def public_url(self, *, bucket: str, path: str) -> str | None: ...


class BannerAssetRepositoryProtocol(Protocol):
    def create_many(self, *, assets: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class StoredAssetResult:
    asset_records: list[dict[str, Any]]
    optimization_report: dict[str, Any]
    upload_report: dict[str, Any]


class BannerAssetService:
    """Optimizes generated image bytes, uploads variants, and records rows."""

    def __init__(
        self,
        *,
        storage_client: StorageClientProtocol,
        asset_repository: BannerAssetRepositoryProtocol,
        bucket: str = "campaign-assets",
        optimizer: ImageOptimizer | None = None,
    ) -> None:
        self.storage_client = storage_client
        self.asset_repository = asset_repository
        self.bucket = bucket
        self.optimizer = optimizer or ImageOptimizer()

    @classmethod
    def from_supabase_client(cls, client: Any, *, bucket: str = "campaign-assets", optimizer: ImageOptimizer | None = None) -> "BannerAssetService":
        return cls(
            storage_client=SupabaseStorageAdapter(client),
            asset_repository=BannerAssetRepository(client),
            bucket=bucket,
            optimizer=optimizer,
        )

    def optimize_upload_and_record(
        self,
        *,
        image_bytes: bytes,
        campaign_id: str,
        revision_id: str,
        banner_variant_id: str | None = None,
        alt_text: str | None = None,
        image_prompt: str | None = None,
        asset_kind: str = "generated_background",
        source_metadata: dict[str, Any] | None = None,
    ) -> StoredAssetResult:
        if not campaign_id:
            raise ValueError("campaign_id is required")
        if not revision_id:
            raise ValueError("revision_id is required")

        optimized = self.optimizer.optimize(image_bytes)
        asset_group_key = _safe_path_part(banner_variant_id or hashlib.sha256(image_bytes).hexdigest()[:16])
        rows: list[dict[str, Any]] = []
        uploaded: list[dict[str, Any]] = []

        for variant in optimized.variants:
            path = self.object_path(
                campaign_id=campaign_id,
                revision_id=revision_id,
                variant=variant,
                asset_kind=asset_kind,
                asset_group_key=asset_group_key,
            )
            upload_result = self.storage_client.upload(
                bucket=self.bucket,
                path=path,
                data=variant.bytes_data,
                content_type=variant.mime_type,
                upsert=True,
            )
            public_url = self.storage_client.public_url(bucket=self.bucket, path=path)
            row = {
                "banner_variant_id": banner_variant_id,
                "revision_id": revision_id,
                "asset_kind": asset_kind,
                "size_key": variant.size_key,
                "width": variant.width,
                "height": variant.height,
                "format": variant.format,
                "storage_path": path,
                "public_url": public_url,
                "alt_text": alt_text,
                "bytes": variant.bytes_size,
                "image_prompt": image_prompt,
                "metadata": {
                    **variant.metadata,
                    "bucket": self.bucket,
                    "asset_group_key": asset_group_key,
                    "mime_type": variant.mime_type,
                    "source": source_metadata or {},
                },
            }
            rows.append(row)
            uploaded.append({"path": path, "bytes": variant.bytes_size, "format": variant.format, "size_key": variant.size_key, "result": upload_result})

        records = self.asset_repository.create_many(assets=rows)
        return StoredAssetResult(
            asset_records=records,
            optimization_report=optimized.report,
            upload_report={"bucket": self.bucket, "uploaded": uploaded, "uploaded_count": len(uploaded)},
        )

    def upload_png(
        self,
        *,
        png_bytes: bytes,
        campaign_id: str,
        revision_id: str,
        asset_group_key: str,
        asset_kind: str = "generated_hero",
        size_key: int = 1280,
        alt_text: str | None = None,
        image_prompt: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upload a single transparent PNG verbatim (alpha preserved — no webp
        re-encode) and record an asset row. Returns the created/echoed row."""
        if not campaign_id or not revision_id:
            raise ValueError("campaign_id and revision_id are required")
        safe_group = _safe_path_part(asset_group_key)
        safe_kind = _safe_path_part(asset_kind)
        path = (
            f"campaigns/{_safe_path_part(campaign_id)}/revisions/{_safe_path_part(revision_id)}/"
            f"{safe_kind}/{safe_group}/{int(size_key)}w.png"
        )
        self.storage_client.upload(bucket=self.bucket, path=path, data=png_bytes, content_type="image/png", upsert=True)
        public_url = self.storage_client.public_url(bucket=self.bucket, path=path)
        row = {
            "revision_id": revision_id,
            "asset_kind": asset_kind,
            "size_key": int(size_key),
            "format": "png",
            "storage_path": path,
            "public_url": public_url,
            "alt_text": alt_text,
            "bytes": len(png_bytes),
            "image_prompt": image_prompt,
            "metadata": {"bucket": self.bucket, "asset_group_key": safe_group, "mime_type": "image/png", "transparent": True, "source": source_metadata or {}},
        }
        try:
            records = self.asset_repository.create_many(assets=[row])
            return records[0] if records else row
        except Exception:  # noqa: BLE001 — recording is best-effort; the URL is what matters
            return row

    @staticmethod
    def object_path(
        *,
        campaign_id: str,
        revision_id: str,
        variant: OptimizedImageVariant,
        asset_kind: str = "generated_background",
        asset_group_key: str,
    ) -> str:
        safe_campaign_id = _safe_path_part(campaign_id)
        safe_revision_id = _safe_path_part(revision_id)
        safe_asset_kind = _safe_path_part(asset_kind)
        safe_asset_group_key = _safe_path_part(asset_group_key)
        return (
            f"campaigns/{safe_campaign_id}/revisions/{safe_revision_id}/"
            f"{safe_asset_kind}/{safe_asset_group_key}/{variant.size_key}w.{variant.format}"
        )


def configured_asset_service() -> BannerAssetService:
    settings = Settings.from_env()
    client = SupabaseClientFactory(settings).service_role_client()
    return BannerAssetService.from_supabase_client(client, bucket=settings.supabase_storage_bucket)


def _safe_path_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    cleaned = cleaned.strip("-")
    if not cleaned:
        raise ValueError("path part must contain at least one safe character")
    return cleaned[:120]
