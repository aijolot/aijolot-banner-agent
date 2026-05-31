"""Lazy Supabase client factory.

No external clients are instantiated at import time. FastAPI dependencies and
services should request a client through this boundary so tests can override it.
"""

from __future__ import annotations

from typing import Any

from supabase import create_client

from app.core.settings import Settings


class SupabaseClientFactory:
    """Create and cache Supabase clients only when requested."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._anon_client: Any | None = None
        self._service_role_client: Any | None = None

    def anon_client(self) -> Any:
        if self._anon_client is None:
            url, key = self._settings.require_supabase_anon()
            self._anon_client = create_client(url, key)
        return self._anon_client

    def service_role_client(self) -> Any:
        if self._service_role_client is None:
            url, key = self._settings.require_supabase_service_role()
            self._service_role_client = create_client(url, key)
        return self._service_role_client
