"""Compatibility facade for brand runtime storage.

Runtime storage is Supabase-backed when SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
and BRAND_CONTEXT_TEAM_ID (or SUPABASE_TEAM_ID) are configured. Markdown files
remain available as seed/import sources and as the local dev/test fallback.
"""

from __future__ import annotations

from pathlib import Path

from app.core.settings import MissingSettingsError, Settings
from app.schemas.brand import BrandContext, BrandSummary
from app.services.brands.brand_service import BrandNotFound, BrandService
from app.services.brands.markdown_importer import BrandMarkdownImporter, dump_markdown, split_frontmatter
from app.services.supabase.client import SupabaseClientFactory

BRANDS_DIR = Path(__file__).resolve().parents[3] / "brands"


def _default_service() -> BrandService:
    importer = BrandMarkdownImporter(base_dir=BRANDS_DIR)
    settings = Settings.from_env()
    team_id = settings.brand_context_team_id or settings.supabase_team_id
    has_supabase_credentials = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    if has_supabase_credentials and not team_id:
        raise MissingSettingsError(("BRAND_CONTEXT_TEAM_ID", "SUPABASE_TEAM_ID"))
    try:
        client = SupabaseClientFactory(settings).service_role_client()
    except MissingSettingsError:
        return BrandService(markdown_importer=importer, markdown_writes_dir=BRANDS_DIR)
    return BrandService.from_supabase_client(client, team_id=team_id, markdown_importer=importer)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    return split_frontmatter(text)


def _dump_markdown(brand: BrandContext) -> str:
    return dump_markdown(brand)


def list_brands() -> list[BrandSummary]:
    return _default_service().list_brands()


def get_brand(brand_id: str) -> BrandContext:
    return _default_service().get_brand(brand_id)


def save_brand(brand_id: str, brand: BrandContext) -> BrandContext:
    return _default_service().save_brand(brand_id, brand)


def import_markdown_brand(brand_id: str | None = None, path: str | Path | None = None) -> BrandContext:
    return _default_service().import_markdown(brand_id=brand_id, path=path)
