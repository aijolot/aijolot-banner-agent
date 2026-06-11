from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from app.db.repositories.brand_contexts import BrandContextRepository
from app.schemas.brand import BrandContext, BrandSummary
from app.schemas.brand_discovery import BrandDiscoverySnapshot
from app.schemas.brand_recommendations import ApplyDiscoveryRecommendationsRequest
from app.services.brands.apply_recommendations import merge_discovery_recommendations
from app.services.brands.markdown_importer import BrandMarkdownImporter, dump_markdown


class BrandNotFound(Exception):
    """Raised when no runtime or seed brand exists for a requested id."""


class DiscoveryPersistenceUnavailable(Exception):
    """Raised when discovery snapshot persistence needs Supabase but it is not configured."""


class BrandContextRepositoryProtocol(Protocol):
    def list(self, *, team_id: str) -> list[dict[str, Any]]: ...
    def get_by_slug(self, *, team_id: str, slug: str) -> dict[str, Any] | None: ...
    def upsert(
        self,
        *,
        team_id: str,
        slug: str,
        data: dict[str, Any],
        store_id: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]: ...
    def update_fields(self, *, team_id: str, slug: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class BrandService:
    """Brand runtime service.

    Supabase is authoritative when a repository and team_id are configured.
    Markdown remains the seed/import source and local fallback when Supabase is
    not configured for dev/test.
    """

    def __init__(
        self,
        *,
        repository: BrandContextRepositoryProtocol | None = None,
        team_id: str | None = None,
        markdown_importer: BrandMarkdownImporter | None = None,
        markdown_writes_dir: Path | str | None = None,
    ) -> None:
        self.repository = repository
        self.team_id = team_id
        self.markdown_importer = markdown_importer or BrandMarkdownImporter()
        self.markdown_writes_dir = Path(markdown_writes_dir) if markdown_writes_dir is not None else self.markdown_importer.base_dir

    @classmethod
    def from_supabase_client(
        cls,
        client: Any,
        *,
        team_id: str | None = None,
        markdown_importer: BrandMarkdownImporter | None = None,
    ) -> "BrandService":
        return cls(repository=BrandContextRepository(client), team_id=team_id, markdown_importer=markdown_importer)

    @property
    def supabase_enabled(self) -> bool:
        return self.repository is not None and bool(self.team_id)

    def list_brands(self) -> list[BrandSummary]:
        if self.supabase_enabled:
            assert self.repository is not None and self.team_id is not None
            rows = self.repository.list(team_id=self.team_id)
            return [self._summary_from_record(row) for row in rows]
        return [BrandSummary(id=brand.id, name=brand.name, palette=brand.palette) for brand in self.markdown_importer.list_seed_brands()]

    def get_brand(self, brand_id: str) -> BrandContext:
        if self.supabase_enabled:
            assert self.repository is not None and self.team_id is not None
            row = self.repository.get_by_slug(team_id=self.team_id, slug=brand_id)
            if row is None:
                raise BrandNotFound(brand_id)
            return self._brand_from_record(row)
        try:
            return self.markdown_importer.load_id(brand_id)
        except FileNotFoundError as exc:
            raise BrandNotFound(brand_id) from exc

    def save_brand(self, brand_id: str, brand: BrandContext) -> BrandContext:
        brand = BrandContext(**{**brand.model_dump(), "id": brand_id})
        if self.supabase_enabled:
            assert self.repository is not None and self.team_id is not None
            record = self.repository.upsert(team_id=self.team_id, slug=brand_id, data=self._record_payload_from_brand(brand))
            return self._brand_from_record(record) if record else brand
        self.markdown_writes_dir.mkdir(parents=True, exist_ok=True)
        output_path = BrandMarkdownImporter(base_dir=self.markdown_writes_dir).path_for_id(brand_id)
        output_path.write_text(dump_markdown(brand), encoding="utf-8")
        return brand

    def apply_discovery_recommendations(
        self, brand_id: str, request: ApplyDiscoveryRecommendationsRequest
    ) -> BrandContext:
        """Merge ONLY the user-accepted discovery recommendations into the brand and persist.

        Merge semantics live in ``apply_recommendations.merge_discovery_recommendations``;
        invalid requests raise ``RecommendationApplyError`` (a ValueError -> 422 at the
        route layer). An empty request is a validated no-op: the current brand is
        returned without a write.
        """
        brand = self.get_brand(brand_id)  # BrandNotFound -> 404 at the route layer
        merged = merge_discovery_recommendations(brand, request)
        if merged == brand:
            return brand
        return self.save_brand(brand_id, merged)

    def import_markdown(self, *, brand_id: str | None = None, path: str | Path | None = None) -> BrandContext:
        if path is not None:
            brand = self.markdown_importer.load_path(path)
        elif brand_id is not None:
            brand = self.markdown_importer.load_id(brand_id)
        else:
            raise ValueError("brand_id or path is required")
        return self.save_brand(brand.id, brand) if self.supabase_enabled else brand

    def import_all_markdown(self) -> list[BrandContext]:
        brands = self.markdown_importer.list_seed_brands()
        if not self.supabase_enabled:
            return brands
        return [self.save_brand(brand.id, brand) for brand in brands]

    # Discovery snapshots are raw evidence, not approved brand context, so they
    # round-trip through the brand_contexts.discovery_snapshot column without
    # ever appearing on the BrandContext model.

    def get_discovery_snapshot(self, brand_id: str) -> dict[str, Any] | None:
        """Latest persisted discovery snapshot for a brand, or None."""
        if not self.supabase_enabled:
            return None
        assert self.repository is not None and self.team_id is not None
        row = self.repository.get_by_slug(team_id=self.team_id, slug=brand_id)
        if row is None:
            raise BrandNotFound(brand_id)
        snapshot = row.get("discovery_snapshot")
        return dict(snapshot) if isinstance(snapshot, dict) else None

    def save_discovery_snapshot(
        self, brand_id: str, snapshot: BrandDiscoverySnapshot | dict[str, Any]
    ) -> dict[str, Any]:
        """Persist the latest discovery snapshot for an existing brand row."""
        if not self.supabase_enabled:
            raise DiscoveryPersistenceUnavailable("discovery snapshots require Supabase runtime storage")
        assert self.repository is not None and self.team_id is not None
        validated = snapshot if isinstance(snapshot, BrandDiscoverySnapshot) else BrandDiscoverySnapshot.model_validate(snapshot)
        payload = validated.model_dump(mode="json")  # datetimes -> ISO strings for JSONB
        updated = self.repository.update_fields(team_id=self.team_id, slug=brand_id, data={"discovery_snapshot": payload})
        if updated is None:
            raise BrandNotFound(brand_id)
        return payload

    @staticmethod
    def _summary_from_record(row: dict[str, Any]) -> BrandSummary:
        return BrandSummary(id=str(row.get("slug") or row.get("id")), name=row["name"], palette=row.get("palette") or [])

    @classmethod
    def _brand_from_record(cls, row: dict[str, Any]) -> BrandContext:
        metadata = row.get("source_metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        voice = row.get("voice") or {}
        if not isinstance(voice, dict):
            voice = {}
        required = row.get("required_phrases") or voice.get("required_phrases") or []
        prohibited = row.get("prohibited_words") or voice.get("prohibited_words") or []
        voice = {**voice, "required_phrases": required, "prohibited_words": prohibited}
        directives = row.get("image_style_directives") or metadata.get("image_style_directives") or []
        if isinstance(directives, str):
            directives = [line.strip(" -") for line in directives.splitlines() if line.strip(" -")]
        shopify = metadata.get("shopify") or {"store_domain": metadata.get("store_domain") or "unknown.myshopify.com"}
        color_system = row.get("color_system")
        if color_system is None:
            color_system = metadata.get("color_system")
        # Full typography (incl. approved/discarded fonts) lives in typography_system;
        # the legacy typography column stays {display, body} for old readers.
        typography = row.get("typography_system")
        if not isinstance(typography, dict) or not typography:
            typography = row.get("typography") or {}
        return BrandContext(
            id=str(row.get("slug") or row.get("id")),
            name=row["name"],
            palette=row.get("palette") or [],
            color_system=color_system,
            typography=typography,
            voice=voice,
            logo_url=row.get("logo_url"),
            image_style_directives=directives,
            shopify=shopify,
            notes=metadata.get("notes") or row.get("description") or "",
        )

    @staticmethod
    def _record_payload_from_brand(brand: BrandContext) -> dict[str, Any]:
        data = brand.model_dump()
        voice = data.get("voice") or {}
        directives = data.get("image_style_directives") or []
        typography_system = data.get("typography") or {}
        # Legacy column keeps the historical two-key shape; the full dump
        # (headline/accent/approved_fonts/discarded_fonts) goes to typography_system.
        legacy_typography = {
            "display": typography_system.get("display", "Space Grotesk"),
            "body": typography_system.get("body", "Inter"),
        }
        return {
            "name": data["name"],
            "description": data.get("notes") or None,
            "palette": data.get("palette") or [],
            "color_system": data.get("color_system"),
            "typography": legacy_typography,
            "typography_system": typography_system,
            "voice": voice,
            "required_phrases": voice.get("required_phrases") or [],
            "prohibited_words": voice.get("prohibited_words") or [],
            "image_style_directives": "\n".join(directives) if isinstance(directives, list) else directives,
            "logo_url": data.get("logo_url"),
            "source_file_path": f"brands/{brand.id}.md" if brand.id else None,
            "source_metadata": {
                "source": "markdown_or_api",
                "shopify": data.get("shopify") or {},
                "notes": data.get("notes") or "",
                "image_style_directives": directives,
            },
        }
