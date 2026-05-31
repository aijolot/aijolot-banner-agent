from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ENV_NAMES = (
    "APP_ENV",
    "APP_BASE_URL",
    "SUPABASE_URL",
    "SUPABASE_DB_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "BRAND_CONTEXT_TEAM_ID",
    "SUPABASE_TEAM_ID",
    "SUPABASE_STORAGE_BUCKET",
    "GOOGLE_API_KEY",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "GEMINI_MODEL_PRO",
    "GEMINI_MODEL_FLASH",
    "GEMINI_MODEL_IMAGE",
    "GEMINI_EMBEDDING_MODEL",
    "IMAGE_GENERATION_PROVIDER",
    "DAILY_COST_CAP_USD",
    "KG_RETRIEVAL_TOP_K",
    "KG_SIMILARITY_THRESHOLD",
    "SHOPIFY_SHOP_DOMAIN",
    "SHOPIFY_ADMIN_ACCESS_TOKEN",
    "SHOPIFY_API_VERSION",
    "SHOPIFY_THEME_ID",
    "SHOPIFY_BANNER_METAFIELD_NAMESPACE",
    "SHOPIFY_BANNER_METAFIELD_KEY",
    "SOFT_IMAGE_GENERATION_LIMIT_PER_15_MINUTES",
)


def test_settings_load_defaults_without_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_NAMES:
        monkeypatch.delenv(key, raising=False)

    from app.core.settings import Settings

    settings = Settings.from_env()

    assert settings.app_env == "local"
    assert str(settings.app_base_url) == "http://127.0.0.1:8000/"
    assert settings.gemini_model_pro == "gemini-3.1-pro"
    assert settings.gemini_model_flash == "gemini-3.5-flash"
    assert settings.gemini_model_image == "gemini-3.1-pro-image"
    assert settings.gemini_embedding_model == "text-embedding-005"
    assert settings.image_generation_provider == "gemini"
    assert settings.supabase_storage_bucket == "campaign-assets"
    assert settings.google_cloud_location == "us-central1"
    assert settings.daily_cost_cap_usd == 5.0
    assert settings.kg_retrieval_top_k == 5
    assert settings.kg_similarity_threshold == 0.65
    assert settings.shopify_api_version == "2026-01"
    assert settings.shopify_banner_metafield_namespace == "aijolot"
    assert settings.shopify_banner_metafield_key == "banner_campaigns"
    assert settings.soft_image_generation_limit_per_15_minutes == 20
    assert settings.supabase_url is None
    assert settings.supabase_db_url is None
    assert settings.supabase_anon_key is None
    assert settings.supabase_service_role_key is None
    assert settings.brand_context_team_id is None
    assert settings.supabase_team_id is None
    assert settings.google_cloud_project is None


def test_settings_loads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://placeholder@localhost/postgres")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-placeholder")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-placeholder")
    monkeypatch.setenv("BRAND_CONTEXT_TEAM_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("SUPABASE_TEAM_ID", "00000000-0000-0000-0000-000000000002")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "assets-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-placeholder")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "project-placeholder")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
    monkeypatch.setenv("GEMINI_MODEL_PRO", "gemini-pro-test")
    monkeypatch.setenv("GEMINI_MODEL_FLASH", "gemini-flash-test")
    monkeypatch.setenv("GEMINI_MODEL_IMAGE", "gemini-image-test")
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "embedding-test")
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "disabled")
    monkeypatch.setenv("DAILY_COST_CAP_USD", "9.5")
    monkeypatch.setenv("KG_RETRIEVAL_TOP_K", "9")
    monkeypatch.setenv("KG_SIMILARITY_THRESHOLD", "0.77")
    monkeypatch.setenv("SHOPIFY_SHOP_DOMAIN", "store.example.test")
    monkeypatch.setenv("SHOPIFY_ADMIN_ACCESS_TOKEN", "shopify-placeholder")
    monkeypatch.setenv("SHOPIFY_API_VERSION", "2026-04")
    monkeypatch.setenv("SHOPIFY_THEME_ID", "123456")
    monkeypatch.setenv("SHOPIFY_BANNER_METAFIELD_NAMESPACE", "namespace-test")
    monkeypatch.setenv("SHOPIFY_BANNER_METAFIELD_KEY", "key-test")
    monkeypatch.setenv("SOFT_IMAGE_GENERATION_LIMIT_PER_15_MINUTES", "7")

    from app.core.settings import Settings

    settings = Settings.from_env()

    assert settings.app_env == "test"
    assert str(settings.app_base_url) == "https://api.example.test/"
    assert str(settings.supabase_url) == "https://example.supabase.co/"
    assert settings.supabase_db_url == "postgresql://placeholder@localhost/postgres"
    assert settings.require_supabase_anon() == ("https://example.supabase.co/", "anon-placeholder")
    assert settings.require_supabase_service_role() == (
        "https://example.supabase.co/",
        "service-placeholder",
    )
    assert settings.brand_context_team_id == "00000000-0000-0000-0000-000000000001"
    assert settings.supabase_team_id == "00000000-0000-0000-0000-000000000002"
    assert settings.supabase_storage_bucket == "assets-test"
    assert settings.require_google_api_key() == "google-placeholder"
    assert settings.require_google_cloud() == ("project-placeholder", "europe-west1")
    assert settings.gemini_model_pro == "gemini-pro-test"
    assert settings.gemini_model_flash == "gemini-flash-test"
    assert settings.gemini_model_image == "gemini-image-test"
    assert settings.gemini_embedding_model == "embedding-test"
    assert settings.image_generation_provider == "disabled"
    assert settings.daily_cost_cap_usd == 9.5
    assert settings.kg_retrieval_top_k == 9
    assert settings.kg_similarity_threshold == 0.77
    assert settings.shopify_shop_domain == "store.example.test"
    assert settings.require_shopify_admin() == (
        "store.example.test",
        "shopify-placeholder",
        "2026-04",
    )
    assert settings.shopify_api_version == "2026-04"
    assert settings.shopify_theme_id == "123456"
    assert settings.shopify_banner_metafield_namespace == "namespace-test"
    assert settings.shopify_banner_metafield_key == "key-test"
    assert settings.soft_image_generation_limit_per_15_minutes == 7


def test_settings_env_map_covers_relevant_env_example_names() -> None:
    from app.core.settings import Settings

    env_example = Path(__file__).parents[3] / ".env.example"
    example_names = {
        line.split("=", 1)[0]
        for line in env_example.read_text().splitlines()
        if line and not line.startswith("#") and not line.startswith("NEXT_PUBLIC_")
    }

    assert set(Settings.ENV_MAP.values()) == example_names


def test_secret_fields_are_redacted_and_unwrapped_only_by_require_methods() -> None:
    from app.core.settings import Settings

    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-placeholder",
        supabase_service_role_key="service-placeholder",
        google_api_key="google-placeholder",
        shopify_shop_domain="store.example.test",
        shopify_admin_access_token="shopify-placeholder",
    )

    rendered = repr(settings)
    dumped = settings.model_dump()

    for raw_value in (
        "anon-placeholder",
        "service-placeholder",
        "google-placeholder",
        "shopify-placeholder",
    ):
        assert raw_value not in rendered
        assert raw_value not in str(dumped)

    assert settings.require_supabase_anon()[1] == "anon-placeholder"
    assert settings.require_supabase_service_role()[1] == "service-placeholder"
    assert settings.require_google_api_key() == "google-placeholder"
    assert settings.require_shopify_admin()[1] == "shopify-placeholder"


def test_blank_env_values_are_ignored_and_defaults_survive(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.settings import Settings

    monkeypatch.setenv("APP_ENV", "")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "   ")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "")
    monkeypatch.setenv("DAILY_COST_CAP_USD", "")
    monkeypatch.setenv("KG_RETRIEVAL_TOP_K", "")
    monkeypatch.setenv("KG_SIMILARITY_THRESHOLD", "")
    monkeypatch.setenv("SHOPIFY_BANNER_METAFIELD_NAMESPACE", "")

    settings = Settings.from_env()

    assert settings.app_env == "local"
    assert settings.supabase_anon_key is None
    assert settings.google_cloud_location == "us-central1"
    assert settings.supabase_storage_bucket == "campaign-assets"
    assert settings.daily_cost_cap_usd == 5.0
    assert settings.kg_retrieval_top_k == 5
    assert settings.kg_similarity_threshold == 0.65
    assert settings.shopify_banner_metafield_namespace == "aijolot"


def test_blank_optional_constructor_values_become_none() -> None:
    from app.core.settings import Settings

    settings = Settings(
        supabase_url="",
        supabase_db_url="",
        supabase_anon_key="",
        google_cloud_project="",
        shopify_admin_access_token="",
    )

    assert settings.supabase_url is None
    assert settings.supabase_db_url is None
    assert settings.supabase_anon_key is None
    assert settings.google_cloud_project is None
    assert settings.shopify_admin_access_token is None


def test_strict_supabase_validation_only_when_requested() -> None:
    from app.core.settings import MissingSettingsError, Settings

    settings = Settings()

    with pytest.raises(MissingSettingsError) as exc_info:
        settings.require_supabase_service_role()

    message = str(exc_info.value)
    assert "SUPABASE_URL" in message
    assert "SUPABASE_SERVICE_ROLE_KEY" in message


def test_supabase_anon_validation_only_when_requested() -> None:
    from app.core.settings import MissingSettingsError, Settings

    settings = Settings()

    with pytest.raises(MissingSettingsError) as exc_info:
        settings.require_supabase_anon()

    message = str(exc_info.value)
    assert "SUPABASE_URL" in message
    assert "SUPABASE_ANON_KEY" in message


def test_google_require_behavior() -> None:
    from app.core.settings import MissingSettingsError, Settings

    settings = Settings()

    with pytest.raises(MissingSettingsError) as api_exc_info:
        settings.require_google_api_key()
    assert "GOOGLE_API_KEY" in str(api_exc_info.value)

    with pytest.raises(MissingSettingsError) as cloud_exc_info:
        settings.require_google_cloud()
    assert "GOOGLE_CLOUD_PROJECT" in str(cloud_exc_info.value)

    configured = Settings(google_api_key="google-placeholder", google_cloud_project="project-placeholder")
    assert configured.require_google_api_key() == "google-placeholder"
    assert configured.require_google_cloud() == ("project-placeholder", "us-central1")


def test_shopify_require_behavior() -> None:
    from app.core.settings import MissingSettingsError, Settings

    with pytest.raises(MissingSettingsError) as exc_info:
        Settings().require_shopify_admin()

    message = str(exc_info.value)
    assert "SHOPIFY_SHOP_DOMAIN" in message
    assert "SHOPIFY_ADMIN_ACCESS_TOKEN" in message
    assert "SHOPIFY_API_VERSION" not in message

    settings = Settings(
        shopify_shop_domain="store.example.test",
        shopify_admin_access_token="shopify-placeholder",
    )
    assert settings.require_shopify_admin() == (
        "store.example.test",
        "shopify-placeholder",
        "2026-01",
    )


def test_dependency_get_settings_is_cached_and_clearable(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.dependencies import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "first")
    first = get_settings()
    monkeypatch.setenv("APP_ENV", "second")
    second = get_settings()
    assert first is second
    assert second.app_env == "first"

    get_settings.cache_clear()
    assert get_settings().app_env == "second"


def test_supabase_client_factory_is_lazy_and_uses_injected_create_client(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("app.services.supabase.client")
    calls: list[tuple[str, str]] = []

    def fake_create_client(url: str, key: str) -> object:
        calls.append((url, key))
        return {"url": url, "key": key}

    monkeypatch.setattr(module, "create_client", fake_create_client)

    from app.core.settings import Settings
    from app.services.supabase.client import SupabaseClientFactory

    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-placeholder",
    )
    factory = SupabaseClientFactory(settings=settings)

    assert calls == []
    client = factory.service_role_client()

    assert calls == [("https://example.supabase.co/", "service-placeholder")]
    assert client == {"url": "https://example.supabase.co/", "key": "service-placeholder"}
    assert factory.service_role_client() is client


def test_get_supabase_client_uses_settings_dependency_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import dependencies
    from app.core.settings import Settings

    class FakeFactory:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        def service_role_client(self) -> object:
            return {"env": self.settings.app_env}

    monkeypatch.setattr(dependencies, "SupabaseClientFactory", FakeFactory)
    factory = dependencies.get_supabase_client_factory(Settings(app_env="unit"))
    client = dependencies.get_supabase_service_role_client(factory)

    assert client == {"env": "unit"}


def test_supabase_client_dependencies_use_factory_override_without_reconstructing() -> None:
    from app.core import dependencies

    class FakeFactory:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def anon_client(self) -> object:
            self.calls.append("anon")
            return {"client": "anon"}

        def service_role_client(self) -> object:
            self.calls.append("service")
            return {"client": "service"}

    factory = FakeFactory()

    assert dependencies.get_supabase_anon_client(factory) == {"client": "anon"}
    assert dependencies.get_supabase_service_role_client(factory) == {"client": "service"}
    assert factory.calls == ["anon", "service"]
