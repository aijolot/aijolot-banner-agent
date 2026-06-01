from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PIL import Image

from app.agents.tools import nano_banana_image
from app.core.settings import Settings
from app.services.banners.usage_guard_service import reset_default_usage_guard_service
from app.services.gemini.fake_image_provider import FakeImageProvider
from app.services.gemini.image_provider import ImageGenerationRequest, ImageProviderUnavailable, _extract_image


SKILL_ROOT = Path(__file__).resolve().parents[2] / "app" / "agents" / "skills"


def _load_skill(skill_id: str):
    path = SKILL_ROOT / skill_id / "impl.py"
    spec = importlib.util.spec_from_file_location(f"test_{skill_id.replace('-', '_')}_impl", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_fake_provider_returns_deterministic_valid_png(tmp_path):
    provider = FakeImageProvider()
    request = ImageGenerationRequest(prompt="premium running shoe abstract hero", aspect_ratio="16:9")

    first = await provider.generate(request)
    second = await provider.generate(request)

    assert first.image_bytes == second.image_bytes
    assert first.mime_type == "image/png"
    assert first.provider == "fake"
    assert first.usage["estimated_cost_usd"] == 0.0
    assert first.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    tmp = tmp_path / "fake-provider-test.png"
    tmp.write_bytes(first.image_bytes)
    with Image.open(tmp) as image:
        assert image.size == (128, 72)
        assert image.format == "PNG"


@pytest.mark.asyncio
async def test_tool_uses_fake_provider_by_default_without_env_or_network(monkeypatch):
    monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    response = await nano_banana_image.generate("safe local demo image")

    assert response.provider == "fake"
    assert response.mime_type == "image/png"
    assert response.image_bytes.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_explicit_real_provider_requires_credentials(monkeypatch):
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "gemini")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ImageProviderUnavailable, match="GOOGLE_API_KEY"):
        await nano_banana_image.generate("should not call external provider")


@pytest.mark.asyncio
async def test_settings_can_explicitly_select_real_provider_without_env(monkeypatch):
    monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    settings = Settings(image_generation_provider="gemini")

    with pytest.raises(ImageProviderUnavailable, match="GOOGLE_API_KEY"):
        await nano_banana_image.generate("settings-selected real provider", settings=settings)


@pytest.mark.asyncio
async def test_image_response_extraction_normalizes_invalid_base64():
    class Inline:
        data = "not-valid-base64%%%"
        mime_type = "image/png"

    class Part:
        inline_data = Inline()

    class Content:
        parts = [Part()]

    class Candidate:
        content = Content()

    class Response:
        candidates = [Candidate()]

    with pytest.raises(ImageProviderUnavailable, match="invalid image bytes"):
        _extract_image(Response())


@pytest.mark.asyncio
async def test_nano_banana_skill_returns_bytes_and_usage_metadata(monkeypatch):
    reset_default_usage_guard_service()
    monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
    skill = _load_skill("nano-banana-image-generate")

    result = await skill.run("abstract apparel sale banner", user_id="user-1")

    assert isinstance(result["image_bytes"], bytes)
    assert result["mime_type"] == "image/png"
    assert result["provider"] == "fake"
    assert result["metadata"]["size_bytes"] == len(result["image_bytes"])
    usage_guard = result["metadata"]["usage_guard"]
    assert usage_guard["user_id"] == "user-1"
    assert usage_guard["count"] == 1
    assert usage_guard["warning"] is False
