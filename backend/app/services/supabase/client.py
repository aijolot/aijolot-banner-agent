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


class SupabaseStorageAdapter:
    """Small storage wrapper used by services and easily replaced in tests."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def upload(self, *, bucket: str, path: str, data: bytes, content_type: str, upsert: bool = True) -> dict[str, Any]:
        file_options = {"content-type": content_type, "upsert": "true" if upsert else "false"}
        result = self.client.storage.from_(bucket).upload(path, data, file_options=file_options)
        if isinstance(result, dict):
            return result
        return {"result": result}

    def public_url(self, *, bucket: str, path: str) -> str | None:
        getter = getattr(self.client.storage.from_(bucket), "get_public_url", None)
        if getter is None:
            return None
        value = getter(path)
        return str(value) if value is not None else None
