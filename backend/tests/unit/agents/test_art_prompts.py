"""F8 — descriptive art/model prompts + art generation."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from app.schemas.art_prompts import (
    ArtPromptsRequest,
    GenerateArtRequest,
    ModelPromptsRequest,
    PromptOption,
    PromptOptionsOutput,
)

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
    return normalize({"id": "demo", "name": "Demo", "palette": [{"name": "Ink", "hex": "#111111"}, {"name": "Canvas", "hex": "#ffffff"}]})


CONCEPT = {"copy": {"headline": "Weekend promo"}, "image_prompt": "clean studio scene with featured product", "layout": "hero"}


def _no_key(monkeypatch, skill) -> None:
    class FakeSettings:
        def has_google_api_key(self) -> bool:
            return False

    monkeypatch.setattr(skill, "Settings", type("S", (), {"from_env": staticmethod(lambda: FakeSettings())}))


def test_hero_prompts_are_distinct_and_sanitized(monkeypatch) -> None:
    skill = _load_skill("art-prompt-propose")
    _no_key(monkeypatch, skill)
    options, source = asyncio.run(skill.run(CONCEPT, _brand(), shot_type="hero", count=3))

    assert source == "deterministic"
    assert [o.label for o in options] == ["A", "B", "C"]
    prompts = {o.prompt for o in options}
    assert len(prompts) == 3  # distinct stylistic directions
    for o in options:
        # image-prompt-refine sanitization removes forbidden bake-in terms.
        assert "logo" not in o.prompt.lower()
        assert o.prompt.strip()


def test_usage_prompts_share_subject_vary_angle(monkeypatch) -> None:
    skill = _load_skill("art-prompt-propose")
    _no_key(monkeypatch, skill)
    options, source = asyncio.run(skill.run(CONCEPT, _brand(), shot_type="usage", count=4, background_ref="Sunset gradient"))

    assert source == "deterministic"
    assert [o.angle for o in options] == ["front", "three_quarter", "top_down", "in_use"]
    assert all(o.background_ref == "Sunset gradient" for o in options)


def test_model_prompts_fallback(monkeypatch) -> None:
    skill = _load_skill("art-prompt-propose")
    _no_key(monkeypatch, skill)
    options, source = asyncio.run(skill.propose_models(CONCEPT, _brand(), gender="female", base_prompt="serum bottle", count=3))

    assert source == "deterministic"
    assert len(options) == 3
    assert all("serum bottle" in o.prompt or "serum" in o.prompt.lower() for o in options)


def test_gemini_prompts_sanitized(monkeypatch) -> None:
    skill = _load_skill("art-prompt-propose")

    class FakeSettings:
        def has_google_api_key(self) -> bool:
            return True

    monkeypatch.setattr(skill, "Settings", type("S", (), {"from_env": staticmethod(lambda: FakeSettings())}))
    monkeypatch.setattr(skill, "_guard_allows", lambda *a, **k: True)

    async def fake_generate(prompt, *, model=None, structured=None):
        return PromptOptionsOutput(
            options=[
                PromptOption(label="A", description="d1", prompt="studio scene with big LOGO and text overlay"),
                PromptOption(label="B", description="d2", prompt="lifestyle scene, soft light"),
            ]
        )

    monkeypatch.setattr(skill.gemini_text, "generate", fake_generate)
    options, source = asyncio.run(skill.run(CONCEPT, _brand(), shot_type="hero", count=2))

    assert source == "gemini"
    assert len(options) == 2
    # image-prompt-refine should neutralize the baked-in logo/text directive.
    assert "text overlay" not in options[0].prompt.lower()


# --- service ---------------------------------------------------------------


class FakeCampaigns:
    def get(self, *, campaign_id, team_id=None):
        return {"id": campaign_id, "title": "Promo", "structured_brief": {"tone": "energetic"}}


class FakeRevisions:
    def __init__(self) -> None:
        self.rows = {"rev-1": {"id": "rev-1", "campaign_id": "cid-1", "concept": dict(CONCEPT)}}
        self.updates: list[dict] = []

    def get(self, *, revision_id):
        return self.rows.get(revision_id)

    def get_latest_by_campaign_id(self, *, campaign_id):
        rows = [r for r in self.rows.values() if r["campaign_id"] == campaign_id]
        return rows[-1] if rows else None

    def update(self, *, revision_id, data):
        self.rows[revision_id].update(data)
        self.updates.append({"revision_id": revision_id, **data})
        return self.rows[revision_id]


def test_service_propose_and_generate_inmemory() -> None:
    from app.services.banners.art_service import ArtService

    revisions = FakeRevisions()
    svc = ArtService(campaigns=FakeCampaigns(), revisions=revisions, asset_service=None, team_id="team-1")

    proposed = svc.propose_art_prompts("cid-1", ArtPromptsRequest(shot_type="usage", count=3))
    assert proposed.revision_id == "rev-1"
    assert len(proposed.options) == 3

    # No GOOGLE_API_KEY in clean test env → image gen degrades to fake provider.
    result = svc.generate_art("cid-1", GenerateArtRequest(prompt="studio scene", shot_type="hero"))
    assert result.revision_id == "rev-1"
    assert result.asset is not None
    assert result.prompt.strip()
    # Generated art recorded on the revision concept.
    assert revisions.rows["rev-1"]["concept"].get("generated_art")


def test_service_unknown_revision_raises() -> None:
    from app.services.banners.art_service import ArtService, RevisionNotFound

    svc = ArtService(campaigns=FakeCampaigns(), revisions=FakeRevisions(), team_id="team-1")
    with pytest.raises(RevisionNotFound):
        svc.propose_art_prompts("cid-1", ArtPromptsRequest(revision_id="nope"))
