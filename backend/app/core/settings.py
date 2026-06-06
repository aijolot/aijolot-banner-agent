"""Application settings loaded explicitly from environment variables.

This module intentionally avoids pydantic-settings so importing the app remains
lightweight and does not require real secrets. Code paths that need an external
service should call the relevant `require_*` method before creating a client.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar, Iterable

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, field_validator


class MissingSettingsError(RuntimeError):
    """Raised when a service-specific code path lacks required configuration."""

    def __init__(self, setting_names: Iterable[str]) -> None:
        names = tuple(setting_names)
        super().__init__(f"Missing required settings: {', '.join(names)}")
        self.setting_names = names


class Settings(BaseModel):
    """Centralized application settings.

    Defaults are safe for local imports/tests. Secret validation is deferred to
    service-specific `require_*` methods so tests and the FastAPI app can import
    without live credentials.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, validate_default=True)

    ENV_MAP: ClassVar[dict[str, str]] = {
        "app_env": "APP_ENV",
        "app_base_url": "APP_BASE_URL",
        "supabase_url": "SUPABASE_URL",
        "supabase_db_url": "SUPABASE_DB_URL",
        "supabase_anon_key": "SUPABASE_ANON_KEY",
        "supabase_service_role_key": "SUPABASE_SERVICE_ROLE_KEY",
        "brand_context_team_id": "BRAND_CONTEXT_TEAM_ID",
        "supabase_team_id": "SUPABASE_TEAM_ID",
        "supabase_store_id": "SUPABASE_STORE_ID",
        "supabase_storage_bucket": "SUPABASE_STORAGE_BUCKET",
        "google_api_key": "GOOGLE_API_KEY",
        "google_cloud_project": "GOOGLE_CLOUD_PROJECT",
        "google_cloud_location": "GOOGLE_CLOUD_LOCATION",
        "gemini_model_pro": "GEMINI_MODEL_PRO",
        "gemini_model_flash": "GEMINI_MODEL_FLASH",
        "gemini_model_image": "GEMINI_MODEL_IMAGE",
        "gemini_embedding_model": "GEMINI_EMBEDDING_MODEL",
        "image_generation_provider": "IMAGE_GENERATION_PROVIDER",
        "daily_cost_cap_usd": "DAILY_COST_CAP_USD",
        "kg_retrieval_top_k": "KG_RETRIEVAL_TOP_K",
        "kg_similarity_threshold": "KG_SIMILARITY_THRESHOLD",
        "shopify_shop_domain": "SHOPIFY_SHOP_DOMAIN",
        "shopify_admin_access_token": "SHOPIFY_ADMIN_ACCESS_TOKEN",
        "shopify_api_version": "SHOPIFY_API_VERSION",
        "shopify_theme_id": "SHOPIFY_THEME_ID",
        "shopify_banner_metafield_namespace": "SHOPIFY_BANNER_METAFIELD_NAMESPACE",
        "shopify_banner_metafield_key": "SHOPIFY_BANNER_METAFIELD_KEY",
        "shopify_publish_dry_run": "SHOPIFY_PUBLISH_DRY_RUN",
        "soft_image_generation_limit_per_15_minutes": "SOFT_IMAGE_GENERATION_LIMIT_PER_15_MINUTES",
        "aijolot_intake_provider": "AIJOLOT_INTAKE_PROVIDER",
        "aijolot_concept_provider": "AIJOLOT_CONCEPT_PROVIDER",
        "aijolot_background_provider": "AIJOLOT_BACKGROUND_PROVIDER",
        "aijolot_refine_provider": "AIJOLOT_REFINE_PROVIDER",
        "kg_embeddings_enabled": "KG_EMBEDDINGS_ENABLED",
    }

    app_env: str = "local"
    app_base_url: AnyHttpUrl = "http://127.0.0.1:8000"

    supabase_url: AnyHttpUrl | None = None
    supabase_db_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    brand_context_team_id: str | None = None
    supabase_team_id: str | None = None
    supabase_store_id: str | None = None
    supabase_storage_bucket: str = "campaign-assets"

    google_api_key: SecretStr | None = None
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"
    gemini_model_pro: str = "gemini-3.1-pro"
    gemini_model_flash: str = "gemini-3.5-flash"
    gemini_model_image: str = "gemini-3.1-pro-image"
    gemini_embedding_model: str = "gemini-embedding-001"
    image_generation_provider: str = "gemini"
    daily_cost_cap_usd: float = Field(default=5.0, ge=0)
    kg_retrieval_top_k: int = Field(default=5, ge=1)
    kg_similarity_threshold: float = Field(default=0.65, ge=0, le=1)

    shopify_shop_domain: str | None = None
    shopify_admin_access_token: SecretStr | None = None
    shopify_api_version: str = "2026-01"
    shopify_theme_id: str | None = None
    shopify_banner_metafield_namespace: str = "aijolot"
    shopify_banner_metafield_key: str = "banner_campaigns"
    shopify_publish_dry_run: bool = True

    soft_image_generation_limit_per_15_minutes: int = Field(default=20, ge=0)

    # Per-feature agentic provider opt-ins. Empty string keeps the deterministic
    # path; set to "gemini" (plus a configured GOOGLE_API_KEY) to enable the
    # Gemini-backed branch, which still falls back to deterministic on error.
    aijolot_intake_provider: str = ""
    aijolot_concept_provider: str = ""
    aijolot_background_provider: str = ""
    aijolot_refine_provider: str = ""
    kg_embeddings_enabled: bool = False

    @field_validator(
        "supabase_db_url",
        "supabase_anon_key",
        "supabase_service_role_key",
        "brand_context_team_id",
        "supabase_team_id",
        "supabase_store_id",
        "google_api_key",
        "google_cloud_project",
        "shopify_shop_domain",
        "shopify_admin_access_token",
        "shopify_theme_id",
        mode="before",
    )
    @classmethod
    def _blank_strings_to_none_for_optional_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return None
            return stripped
        return value

    @field_validator(
        "app_env",
        "google_cloud_location",
        "gemini_model_pro",
        "gemini_model_flash",
        "gemini_model_image",
        "gemini_embedding_model",
        "image_generation_provider",
        "supabase_storage_bucket",
        "shopify_api_version",
        "shopify_banner_metafield_namespace",
        "shopify_banner_metafield_key",
        "aijolot_intake_provider",
        "aijolot_concept_provider",
        "aijolot_background_provider",
        "aijolot_refine_provider",
        mode="before",
    )
    @classmethod
    def _strip_string_fields_without_converting_blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("supabase_url", mode="before")
    @classmethod
    def _blank_url_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the current process environment."""

        values: dict[str, Any] = {}
        for field_name, env_name in cls.ENV_MAP.items():
            value = os.getenv(env_name)
            if value is not None and value.strip() != "":
                values[field_name] = value
        return cls(**values)

    @staticmethod
    def _secret_is_missing(value: SecretStr | None) -> bool:
        return value is None or value.get_secret_value() == ""

    def require_supabase_anon(self) -> tuple[str, str]:
        """Return Supabase URL + anon key or raise if absent."""

        missing = []
        if self.supabase_url is None:
            missing.append("SUPABASE_URL")
        if self._secret_is_missing(self.supabase_anon_key):
            missing.append("SUPABASE_ANON_KEY")
        if missing:
            raise MissingSettingsError(missing)
        assert self.supabase_anon_key is not None
        return str(self.supabase_url), self.supabase_anon_key.get_secret_value()

    def require_supabase_service_role(self) -> tuple[str, str]:
        """Return Supabase URL + service-role key or raise if absent."""

        missing = []
        if self.supabase_url is None:
            missing.append("SUPABASE_URL")
        if self._secret_is_missing(self.supabase_service_role_key):
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if missing:
            raise MissingSettingsError(missing)
        assert self.supabase_service_role_key is not None
        return str(self.supabase_url), self.supabase_service_role_key.get_secret_value()

    def require_google_api_key(self) -> str:
        if self._secret_is_missing(self.google_api_key):
            raise MissingSettingsError(("GOOGLE_API_KEY",))
        assert self.google_api_key is not None
        return self.google_api_key.get_secret_value()

    def has_google_api_key(self) -> bool:
        return not self._secret_is_missing(self.google_api_key)

    def gemini_enabled_for(self, provider_flag: str) -> bool:
        """True when a per-feature flag opts into Gemini AND a key is present.

        ``provider_flag`` is one of the ``aijolot_*_provider`` values. The
        deterministic path stays active unless the flag is exactly ``gemini``.
        """

        return provider_flag.strip().lower() == "gemini" and self.has_google_api_key()

    def require_google_cloud(self) -> tuple[str, str]:
        missing = []
        if not self.google_cloud_project:
            missing.append("GOOGLE_CLOUD_PROJECT")
        if not self.google_cloud_location:
            missing.append("GOOGLE_CLOUD_LOCATION")
        if missing:
            raise MissingSettingsError(missing)
        assert self.google_cloud_project is not None
        return self.google_cloud_project, self.google_cloud_location

    def require_shopify_admin(self) -> tuple[str, str, str]:
        missing = []
        if not self.shopify_shop_domain:
            missing.append("SHOPIFY_SHOP_DOMAIN")
        if self._secret_is_missing(self.shopify_admin_access_token):
            missing.append("SHOPIFY_ADMIN_ACCESS_TOKEN")
        if not self.shopify_api_version:
            missing.append("SHOPIFY_API_VERSION")
        if missing:
            raise MissingSettingsError(missing)
        assert self.shopify_shop_domain is not None
        assert self.shopify_admin_access_token is not None
        return (
            self.shopify_shop_domain,
            self.shopify_admin_access_token.get_secret_value(),
            self.shopify_api_version,
        )
