from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.core.settings import Settings
from app.services.supabase.client import SupabaseClientFactory, SupabaseStorageAdapter


pytestmark = pytest.mark.integration


def _live_storage_settings() -> Settings:
    settings = Settings.from_env()
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        pytest.skip("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for live storage integration")
    if os.getenv("RUN_SUPABASE_STORAGE_TESTS") not in {"1", "true", "TRUE", "yes"}:
        pytest.skip("set RUN_SUPABASE_STORAGE_TESTS=1 to run live Supabase Storage uploads")
    return settings


def test_storage_adapter_uploads_object_to_supabase_storage() -> None:
    settings = _live_storage_settings()
    client = SupabaseClientFactory(settings).service_role_client()
    storage = SupabaseStorageAdapter(client)
    path = f"integration-tests/task-13/{uuid4()}.png"
    # 1x1 transparent PNG.
    data = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63600000020001e221bc330000000049454e44ae426082"
    )

    result = storage.upload(
        bucket=settings.supabase_storage_bucket,
        path=path,
        data=data,
        content_type="image/png",
        upsert=True,
    )

    assert result is not None
    assert storage.public_url(bucket=settings.supabase_storage_bucket, path=path) is not None
