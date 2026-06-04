"""F6 — KG-grounded layout in the banner concept.

Covers the new layout-retrieve skill (placement-led query against the
`liquid_pattern` kind) and banner-concept-draft's use of layout_candidates to
ground its layout + record provenance in Concept.source_refs, with a clean
deterministic fallback when retrieval is empty.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import Any

from app.agents.state import Concept

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
    return normalize({"id": "demo", "name": "Demo", "palette": [{"name": "Ink", "hex": "#111111"}, {"name": "Canvas", "hex": "#FFFFFF"}]})


def _candidates() -> list[dict[str, Any]]:
    return [
        {
            "id": "kg-announce",
            "kind": "liquid_pattern",
            "title": "Announcement bar — slim promo strip",
            "metadata": {"category": "announcement_bar", "applicable_when": "announcement_bar placement, sitewide promos"},
            "score": 3.0,
        },
        {
            "id": "kg-hero",
            "kind": "liquid_pattern",
            "title": "Hero split section — product image + copy column",
            "metadata": {"category": "hero_layout", "applicable_when": "hero_main Shopify section with product image"},
            "score": 1.0,
        },
    ]


def test_layout_retrieve_queries_liquid_pattern_kind(monkeypatch) -> None:
    skill = _load_skill("layout-retrieve")
    captured: dict[str, Any] = {}

    async def fake_retrieve(query, *, kinds=None, brand_id=None, top_k=5, **_):
        captured["query"] = query
        captured["kinds"] = kinds
        captured["brand_id"] = brand_id
        return [{"id": "x", "kind": "liquid_pattern", "title": "Hero", "metadata": {}, "score": 1.0}]

    monkeypatch.setattr(skill.kg, "retrieve", fake_retrieve)
    campaign = {"goal": "Promo de fin de semana", "tone": "energetic", "placement": "hero_main", "audience": "mujeres"}
    docs = asyncio.run(skill.run(campaign, _brand()))

    assert captured["kinds"] == ["liquid_pattern"]
    assert captured["brand_id"] == "demo"
    assert "hero_main" in captured["query"]
    assert len(docs) == 1 and docs[0]["kind"] == "liquid_pattern"


def test_concept_grounds_layout_in_matching_candidate() -> None:
    concept_skill = _load_skill("banner-concept-draft")
    campaign = {"goal": "Weekend promo", "audience": "young women", "cta": "Shop now", "tone": "energetic", "urgency": "high", "placement": "hero_main"}

    concept = concept_skill.draft_concept(
        campaign=campaign,
        brand_context=_brand(),
        layout_candidates=_candidates(),
    )

    assert isinstance(concept, Concept)
    # Placement-matched candidate (hero) wins over the higher-scored announcement bar.
    assert "Hero split section" in concept.layout
    assert concept.source_refs
    selected = [r for r in concept.source_refs if r.get("selected")]
    assert len(selected) == 1
    assert selected[0]["id"] == "kg-hero"
    assert selected[0]["category"] == "hero_layout"
    assert "KG layout: Hero split section" in concept.hierarchy_notes


def test_concept_falls_back_to_deterministic_layout_without_candidates() -> None:
    concept_skill = _load_skill("banner-concept-draft")
    campaign = {"goal": "Weekend promo", "audience": "young women", "cta": "Shop now", "tone": "energetic", "urgency": "high", "placement": "hero_main"}

    concept = concept_skill.draft_concept(campaign=campaign, brand_context=_brand(), layout_candidates=None)

    assert concept.source_refs == []
    assert "split layout" in concept.layout
    assert "% fold" in concept.layout


def test_concept_default_source_refs_is_empty() -> None:
    # Backward-compat: a concept built without F6 inputs still validates.
    concept = Concept(layout="x", copy={}, palette_usage={}, image_prompt="p", hierarchy_notes="h")
    assert concept.source_refs == []
