"""Tiered KG retrieval: vector RPC, DB-lexical, and static-floor fallback."""

from __future__ import annotations

import asyncio

import pytest

from app.agents.tools import kg
from app.core.settings import Settings


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeRpcClient:
    """Minimal stand-in exposing .rpc(name, params).execute()."""

    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return self

    def execute(self):
        return _FakeResult(self._rows)


def _settings(**overrides) -> Settings:
    base = dict(kg_embeddings_enabled=False, kg_similarity_threshold=0.5, kg_retrieval_top_k=5)
    base.update(overrides)
    return Settings(**base)


def test_static_floor_is_returned_without_supabase(monkeypatch):
    monkeypatch.setattr(kg, "_settings", lambda: _settings())
    monkeypatch.setattr(kg, "_supabase_client", lambda settings: None)
    docs = asyncio.run(kg.retrieve("cta urgency hero", kinds=["best_practice"], top_k=2))
    assert docs
    assert {d["source"] for d in docs} == {"static"}


def test_vector_branch_uses_rpc_and_filters_by_threshold(monkeypatch):
    rows = [
        {"id": "11111111-1111-1111-1111-111111111111", "kind": "liquid_pattern", "title": "Hero split", "body": "x", "metadata": {}, "brand_id": None, "score": 0.81},
        {"id": "22222222-2222-2222-2222-222222222222", "kind": "liquid_pattern", "title": "Weak match", "body": "y", "metadata": {}, "brand_id": None, "score": 0.20},
    ]
    fake = _FakeRpcClient(rows)
    monkeypatch.setattr(kg, "_settings", lambda: _settings(kg_embeddings_enabled=True, google_api_key="k"))
    monkeypatch.setattr(kg, "_supabase_client", lambda settings: fake)

    async def _fake_embed(texts, **kwargs):
        return [[0.0] * 768]

    monkeypatch.setattr("app.agents.tools.gemini_embed.embed", _fake_embed)

    docs = asyncio.run(kg.retrieve("hero split product copy", kinds=["liquid_pattern"], top_k=3))
    titles = [d["title"] for d in docs]
    assert "Hero split" in titles  # above threshold, db_vector source
    assert "Weak match" not in titles  # below kg_similarity_threshold=0.5
    assert any(d["source"] == "db_vector" for d in docs)
    assert fake.calls and fake.calls[0][0] == "match_kg_documents"


def test_merge_floor_dedupes_and_respects_top_k():
    primary = [
        {"id": "a", "kind": "liquid_pattern", "title": "Hero split", "body": "", "metadata": {}, "brand_id": None, "score": 0.9, "source": "db_vector"},
    ]
    floor = [
        (5.0, {"id": "b", "kind": "liquid_pattern", "title": "Hero split", "body": "", "metadata": {}, "brand_id": None, "score": 5.0, "source": "static"}),
        (4.0, {"id": "c", "kind": "best_practice", "title": "CTA verb", "body": "", "metadata": {}, "brand_id": None, "score": 4.0, "source": "static"}),
    ]
    merged = kg._merge_floor(primary, floor, top_k=5)
    titles = [d["title"] for d in merged]
    assert titles == ["Hero split", "CTA verb"]  # dup "Hero split" dropped, order preserved
    assert kg._merge_floor(primary, floor, top_k=1) == primary
