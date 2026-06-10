"""Art Direction runtime — per-variant concept proposal + iteration."""

from __future__ import annotations

import pytest

from app.schemas.art_concepts import ArtConceptsRequest
from app.services.banners.art_concept_service import ArtConceptService, CampaignNotFound

CID = "cid-1"


class FakeCampaigns:
    def __init__(self, brief):
        self.brief = brief

    def get(self, *, campaign_id, team_id=None):
        if campaign_id != CID:
            return None
        return {"id": campaign_id, "title": "Promo verano", "structured_brief": self.brief}


class FakeRevisions:
    def get_latest_by_campaign_id(self, *, campaign_id):
        return {"id": "rev-1", "campaign_id": campaign_id, "concept": {"copy": {"headline": "x"}, "layout": "hero", "image_prompt": ""}}


class FakeCatalog:
    def get_latest_by_campaign_id(self, *, campaign_id):
        return {"items": [
            {"title": "Afnan 9PM EDP 100ml", "sku": "AF-9PM", "price": 999, "stock": 40},
            {"title": "212 Heroes EDP 80ml", "sku": "212-H", "price": 1400, "stock": 12},
        ], "discount_rule": {}}


def _service(brief):
    return ArtConceptService(campaigns=FakeCampaigns(brief), revisions=FakeRevisions(), catalog=FakeCatalog(), team_id="team-1")


def test_proposes_one_concept_per_variant_with_evidence():
    brief = {
        "goal": "Promo de verano de perfumes cítricos", "audience": "jóvenes", "cta": "Comprar", "urgency": "high", "placement": "Home · Hero",
        "promo": "15% OFF", "personalization_dimension": "gender",
        "personalization_variants": [
            {"key": "male", "label": "Hombre", "audience": "hombres jóvenes", "customer_tag": "gender:male"},
            {"key": "female", "label": "Mujer", "audience": "mujeres jóvenes", "customer_tag": "gender:female"},
        ],
    }
    resp = _service(brief).propose_concepts(CID, ArtConceptsRequest())

    assert resp.personalization_dimension == "gender"
    assert {c.variant_key for c in resp.concepts} == {"male", "female"}
    for c in resp.concepts:
        assert c.layout
        assert c.copy.get("headline")
        assert c.product is not None and c.product.title
        assert "[PROVIDER]" in c.product_rationale
        assert c.shot_type == "usage" and c.model_treatment
        assert c.origin_tags["product"] == "[PROVIDER]"
    assert resp.concepts[0].product.title.startswith("Afnan")


def test_default_single_concept_without_variants():
    brief = {"goal": "Promo", "audience": "todos", "cta": "Comprar", "urgency": "low", "placement": "Home · Hero"}
    resp = _service(brief).propose_concepts(CID, ArtConceptsRequest())
    assert len(resp.concepts) == 1
    assert resp.concepts[0].variant_key == "default"
    assert resp.concepts[0].shot_type == "hero"


def test_no_product_recommends_nothing():
    brief = {"goal": "Promo", "audience": "todos", "cta": "Comprar", "urgency": "low", "placement": "Home · Hero"}

    class EmptyCatalog:
        def get_latest_by_campaign_id(self, *, campaign_id):
            return {"items": [], "discount_rule": {}}

    svc = ArtConceptService(campaigns=FakeCampaigns(brief), revisions=FakeRevisions(), catalog=EmptyCatalog(), team_id="team-1")
    resp = svc.propose_concepts(CID, ArtConceptsRequest())
    c = resp.concepts[0]
    assert c.product is None
    assert "[MISSING]" in c.product_rationale


def test_unknown_campaign_raises():
    with pytest.raises(CampaignNotFound):
        _service({}).propose_concepts("nope", ArtConceptsRequest())


def test_feedback_iteration_alters_copy_input():
    brief = {"goal": "Promo verano", "audience": "jóvenes", "cta": "Comprar", "urgency": "high", "placement": "Home · Hero",
             "personalization_variants": [{"key": "male", "label": "Hombre", "audience": "hombres", "customer_tag": "gender:male"}]}
    resp = _service(brief).propose_concepts(CID, ArtConceptsRequest(feedback="más urgente y veraniego", focus="copy", focus_variant="male"))
    assert resp.metadata["iterated"] is True
    assert resp.concepts[0].copy.get("headline")


# --- W0.2: brief products outrank the stock heuristic -----------------------


def test_pick_product_prefers_brief_products_over_stock() -> None:
    catalog = {
        "items": [
            {"title": "Snapshot top-stock", "stock": 999, "price": 10.0},
            {"title": "Elegido en brief", "stock": 0, "from_brief": True, "image_url": "https://cdn/b.jpg"},
        ]
    }
    ref, _rationale, tag = ArtConceptService._pick_product(catalog)
    assert ref is not None
    assert ref.title == "Elegido en brief"
    assert tag == "[PROVIDER]"


def test_pick_product_stock_still_ranks_within_brief_group() -> None:
    catalog = {
        "items": [
            {"title": "Brief bajo stock", "stock": 1, "from_brief": True},
            {"title": "Brief alto stock", "stock": 50, "from_brief": True},
        ]
    }
    ref, _r, _t = ArtConceptService._pick_product(catalog)
    assert ref.title == "Brief alto stock"
