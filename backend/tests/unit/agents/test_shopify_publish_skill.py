from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SKILL_PATH = Path(__file__).resolve().parents[3] / "app" / "agents" / "skills" / "shopify-theme-publish" / "impl.py"


def _load_skill_module():
    spec = importlib.util.spec_from_file_location("shopify_theme_publish_skill_test", SKILL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_shopify_publish_skill_passes_team_context(monkeypatch) -> None:
    module = _load_skill_module()
    captured = {}

    class FakePublisher:
        def publish_campaign(self, campaign_id: str):
            captured["campaign_id"] = campaign_id
            return SimpleNamespace(shopify_resource_id=None, id="job-1")

    def fake_configured_publisher(*, team_id: str | None = None):
        captured["team_id"] = team_id
        return FakePublisher()

    monkeypatch.setattr(module, "configured_publisher", fake_configured_publisher)

    result = await module.run(SimpleNamespace(campaign_id="campaign-1", team_id="team-1"))

    assert captured == {"team_id": "team-1", "campaign_id": "campaign-1"}
    assert result.shopify_section_id == "job-1"


@pytest.mark.asyncio
async def test_shopify_publish_skill_requires_team_context() -> None:
    module = _load_skill_module()

    with pytest.raises(ValueError, match="team_id is required"):
        await module.run(SimpleNamespace(campaign_id="campaign-1"))
