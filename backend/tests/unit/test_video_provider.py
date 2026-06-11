"""C2 — video provider boundary: fake determinism, gating, honest degradation."""

from __future__ import annotations

import asyncio

import pytest

from app.agents.tools import veo_video
from app.services.gemini.fake_video_provider import FakeVideoProvider
from app.services.gemini.video_provider import (
    VideoGenerationRequest,
    VideoProviderUnavailable,
)


def test_fake_provider_is_deterministic() -> None:
    request = VideoGenerationRequest(prompt="a slow drift over a perfume scene", duration_seconds=6)
    first = asyncio.run(FakeVideoProvider().generate(request))
    second = asyncio.run(FakeVideoProvider().generate(request))
    assert first.video_bytes == second.video_bytes
    assert first.poster_bytes == second.poster_bytes
    assert first.mime_type == "video/mp4"
    assert first.video_bytes[4:8] == b"ftyp"
    assert first.usage["billable"] is False


def test_duration_is_clamped_4_to_8() -> None:
    assert VideoGenerationRequest(prompt="x", duration_seconds=2).clamped_duration() == 4
    assert VideoGenerationRequest(prompt="x", duration_seconds=30).clamped_duration() == 8
    assert VideoGenerationRequest(prompt="x", duration_seconds=6).clamped_duration() == 6


def test_reference_image_becomes_poster() -> None:
    request = VideoGenerationRequest(prompt="x", reference_image=(b"png-bytes", "image/png"))
    result = asyncio.run(FakeVideoProvider().generate(request))
    assert result.poster_bytes == b"png-bytes"


def test_selector_defaults_to_fake_and_gates_real(monkeypatch) -> None:
    monkeypatch.delenv("VIDEO_GENERATION_PROVIDER", raising=False)
    assert type(veo_video.select_provider()).__name__ == "FakeVideoProvider"
    monkeypatch.setenv("VIDEO_GENERATION_PROVIDER", "fake")
    assert type(veo_video.select_provider()).__name__ == "FakeVideoProvider"
    monkeypatch.setenv("VIDEO_GENERATION_PROVIDER", "veo")
    assert type(veo_video.select_provider()).__name__ == "GeminiVeoProvider"
    monkeypatch.setenv("VIDEO_GENERATION_PROVIDER", "weird")
    with pytest.raises(VideoProviderUnavailable):
        veo_video.select_provider()


def test_real_provider_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from app.core.settings import Settings
    from app.services.gemini.video_provider import GeminiVeoProvider

    provider = GeminiVeoProvider(settings=Settings())
    with pytest.raises(VideoProviderUnavailable):
        asyncio.run(provider.generate(VideoGenerationRequest(prompt="x")))
