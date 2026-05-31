"""FastAPI dependency boundaries for shared settings and external clients."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends

from app.core.settings import Settings
from app.services.supabase.client import SupabaseClientFactory


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process settings, cached for stable request-time dependencies."""

    return Settings.from_env()


def get_supabase_client_factory(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupabaseClientFactory:
    """Create a lazy Supabase client factory for the current dependency graph."""

    return SupabaseClientFactory(settings=settings)


def get_supabase_anon_client(
    factory: Annotated[SupabaseClientFactory, Depends(get_supabase_client_factory)],
) -> Any:
    """FastAPI dependency returning a lazily-created Supabase anon client."""

    return factory.anon_client()


def get_supabase_service_role_client(
    factory: Annotated[SupabaseClientFactory, Depends(get_supabase_client_factory)],
) -> Any:
    """FastAPI dependency returning a lazily-created service-role client."""

    return factory.service_role_client()
