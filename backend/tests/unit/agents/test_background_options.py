"""F7 — AI background options: deterministic fallback, sanitization, service."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from app.schemas.backgrounds import BackgroundOption, BackgroundOptionsOutput, BackgroundOptionsRequest

SKILLS = Path(__file__).resolve().parents[3] / "app" / "agents" / "skills"


def _load_skill(skill_id: str) -> Any:
    path = SKILLS / skill_id / "impl.py"
    spec = importlib.util.spec_from_file_location(f"test_{skill_id.replace('-', '_')}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _brand() -> Any:
    normalize = _load_skill("brand-context-load").normalize_brand_context
    return normalize(
        {"id": "demo", "name": "Demo", "palette": [{"name": "Ink", "hex": "#0a0a23"}, {"name": "Canvas", "hex": "#fafafa"}, {"name": "Coral", "hex": "#ff5a5f"}]}
    )


CONCEPT = {"copy": {"headline": "Weekend promo"}, "layout": "hero split", "palette_usage": {}}


def test_sanitize_css_strips_dangerous_tokens() -> None:
    skill = _load_skill("background-options-generate")
    dirty = "@import url(http://evil.test/x.css); .aijolot-banner{background:url(https://cdn.evil/x.png);color:red;width:expression(alert(1));}"
    clean = skill.sanitize_css(dirty)
    assert "@import" not in clean
    assert "http" not in clean
    assert "expression(" not in clean
    assert "background:" in clean


def test_sanitize_html_strips_scripts_and_handlers() -> None:
    skill = _load_skill("background-options-generate")
    dirty = '<section class="aijolot-banner" onclick="x()"><script>alert(1)</script></section>'
    clean = skill.sanitize_html(dirty)
    assert "<script" not in clean.lower()
    assert "onclick" not in clean.lower()
    assert "aijolot-banner" in clean


def test_fallback_options_without_key(monkeypatch) -> None:
    skill = _load_skill("background-options-generate")

    class FakeSettings:
        def has_google_api_key(self) -> bool:
            return False

    monkeypatch.setattr(skill, "Settings", type("S", (), {"from_env": staticmethod(lambda: FakeSettings())}))
    options, source = asyncio.run(skill.run(CONCEPT, _brand(), count=3))

    assert source == "deterministic"
    assert len(options) == 3
    for opt in options:
        assert isinstance(opt, BackgroundOption)
        assert ".aijolot-banner" in opt.css
        assert "http" not in opt.css


def test_gemini_options_are_sanitized(monkeypatch) -> None:
    skill = _load_skill("background-options-generate")

    class FakeSettings:
        def has_google_api_key(self) -> bool:
            return True

    monkeypatch.setattr(skill, "Settings", type("S", (), {"from_env": staticmethod(lambda: FakeSettings())}))

    async def fake_generate(prompt, *, model=None, structured=None):
        return BackgroundOptionsOutput(
            options=[
                BackgroundOption(name="Good", description="ok", css=".aijolot-banner{background:linear-gradient(#000,#fff);color:#fff;}", html="<section class='aijolot-banner'></section>", rationale="r"),
                BackgroundOption(name="Bad", description="evil", css="@import url(http://evil/x);", html="<script>x()</script>", rationale="r"),
            ]
        )

    monkeypatch.setattr(skill.gemini_text, "generate", fake_generate)

    class AllowGuard:
        def check_and_reserve(self, est, **_):
            return type("R", (), {"allowed": True, "estimated_usd": est})()

    options, source = asyncio.run(skill.run(CONCEPT, _brand(), count=2, cost_guard=AllowGuard()))

    assert source == "gemini"
    assert len(options) == 2
    assert options[0].name == "Good" and "linear-gradient" in options[0].css
    # The invalid second option was replaced with a deterministic fallback gradient.
    assert "@import" not in options[1].css
    assert ".aijolot-banner" in options[1].css


def test_cost_cap_denial_falls_back(monkeypatch) -> None:
    skill = _load_skill("background-options-generate")

    class FakeSettings:
        def has_google_api_key(self) -> bool:
            return True

    monkeypatch.setattr(skill, "Settings", type("S", (), {"from_env": staticmethod(lambda: FakeSettings())}))

    class DenyGuard:
        def check_and_reserve(self, est, **_):
            return type("R", (), {"allowed": False, "estimated_usd": est})()

    options, source = asyncio.run(skill.run(CONCEPT, _brand(), count=3, cost_guard=DenyGuard()))
    assert source == "deterministic"
    assert len(options) == 3


# --- service ---------------------------------------------------------------


class FakeCampaigns:
    def get(self, *, campaign_id, team_id=None):
        return {"id": campaign_id, "title": "Promo", "structured_brief": {"tone": "energetic"}}


class FakeRevisions:
    def __init__(self) -> None:
        self.rows = {"rev-1": {"id": "rev-1", "campaign_id": "cid-1", "concept": CONCEPT}}

    def get(self, *, revision_id):
        return self.rows.get(revision_id)

    def get_latest_by_campaign_id(self, *, campaign_id):
        rows = [r for r in self.rows.values() if r["campaign_id"] == campaign_id]
        return rows[-1] if rows else None


def test_service_returns_options_with_inmemory_repos() -> None:
    from app.services.banners.background_service import BackgroundOptionsService

    svc = BackgroundOptionsService(campaigns=FakeCampaigns(), revisions=FakeRevisions(), team_id="team-1")
    resp = svc.generate_options("cid-1", BackgroundOptionsRequest(count=3))

    assert resp.campaign_id == "cid-1"
    assert resp.revision_id == "rev-1"
    assert len(resp.options) == 3
    assert all(".aijolot-banner" in o.css for o in resp.options)


def test_service_unknown_revision_raises() -> None:
    from app.services.banners.background_service import BackgroundOptionsService, RevisionNotFound

    svc = BackgroundOptionsService(campaigns=FakeCampaigns(), revisions=FakeRevisions(), team_id="team-1")
    with pytest.raises(RevisionNotFound):
        svc.generate_options("cid-1", BackgroundOptionsRequest(revision_id="nope"))
