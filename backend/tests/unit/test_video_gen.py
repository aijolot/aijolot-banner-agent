"""C2 — video_gen: double gate (flag + cost) and explicit degradation to image."""

from __future__ import annotations

import asyncio

from app.services.banners.video_gen import generate_video, motion_prompt


class _Settings:
    def __init__(self, *, enabled: bool, provider: str | None = None):
        self.video_generation_enabled = enabled
        self.video_generation_provider = provider

    def has_google_api_key(self) -> bool:
        return False


class _Guard:
    def __init__(self, *, allow: bool):
        self.allow = allow
        self.reservations: list[float] = []

    def check_and_reserve(self, est):
        self.reservations.append(est)

        class _R:
            allowed = self.allow
            estimated_usd = est

        return _R()


def _gen(settings, guard, monkeypatch=None, provider_env=None):
    return asyncio.run(generate_video(
        "subtle drift", settings=settings, cost_guard=guard, campaign_id="c-1",
        reference_image=(b"poster", "image/png"),
    ))


def test_disabled_flag_degrades_without_touching_providers(monkeypatch) -> None:
    monkeypatch.delenv("VIDEO_GENERATION_PROVIDER", raising=False)
    response, meta, cost = _gen(_Settings(enabled=False), _Guard(allow=True))
    assert response is None
    assert meta["degraded"] is True
    assert meta["reason"] == "video_generation_disabled"
    assert cost == 0.0


def test_fake_provider_generates_without_cost(monkeypatch) -> None:
    monkeypatch.delenv("VIDEO_GENERATION_PROVIDER", raising=False)
    guard = _Guard(allow=True)
    response, meta, cost = _gen(_Settings(enabled=True), guard)
    assert response is not None
    assert meta["is_real_provider"] is False
    assert cost == 0.0
    assert guard.reservations == []  # fake provider never reserves budget


def test_cost_cap_denial_degrades_to_image_not_fake(monkeypatch) -> None:
    """In production (real provider) a denied reservation must NOT silently fake."""
    monkeypatch.setenv("VIDEO_GENERATION_PROVIDER", "veo")
    guard = _Guard(allow=False)
    response, meta, cost = _gen(_Settings(enabled=True, provider="veo"), guard)
    assert response is None
    assert meta["degraded"] is True
    assert meta["reason"] == "cost_cap"
    assert guard.reservations and guard.reservations[0] >= 0.4 * 4
    assert cost == 0.0


def test_real_provider_failure_degrades_explicitly(monkeypatch) -> None:
    monkeypatch.setenv("VIDEO_GENERATION_PROVIDER", "veo")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response, meta, cost = _gen(_Settings(enabled=True, provider="veo"), _Guard(allow=True))
    assert response is None
    assert meta["degraded"] is True
    assert "generation_failed" in meta["reason"]


def test_motion_prompt_adds_loop_directives() -> None:
    prompt = motion_prompt("A cinematic perfume scene.")
    assert "seamless loop" in prompt
    assert "no cuts" in prompt
    assert "NO text" in prompt
