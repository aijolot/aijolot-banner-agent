"""Art Direction runtime — per-variant concept proposal with evidence + iteration.

Executes the `art-direction` skill contract: from a Brief-Ready campaign it
composes layout (KG) + per-variant copy + themed backgrounds + a featured product
(from the catalog, with grounded rationale) + a shot/model treatment, producing
one Art Concept per personalization variant. Supports an iteration loop: designer
feedback re-runs the affected step. (Distinct from art_direction_service.py, which
persists the background_mode/hero_style/fold art-direction record.)
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.settings import MissingSettingsError, Settings
from app.schemas.art_concepts import (
    ArtConceptsRequest,
    ArtConceptsResponse,
    ArtConceptVariant,
    ConceptProductRef,
)
from app.services.banners.async_run import run_coro
from app.services.banners.brand_resolver import resolve_brand_context
from app.services.supabase.client import SupabaseClientFactory
from app.workflows.banner_creation import _load_runtime_skill


class CampaignNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


# Deterministic per-segment model treatments (concept narratives — [LLM-GENERATED]).
_MODEL_TREATMENTS = {
    "male": "El perfume presentado en un layout de outfit masculino; luz direccional, sin rostro en foco.",
    "female": "Modelo aplicándose el perfume frente al espejo, atuendo acorde a la estación; luz suave.",
    "vip": "Set premium minimalista, materiales nobles, producto protagonista.",
    "unisex": "Composición editorial neutra; el producto es el protagonista.",
}


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class RevisionRepositoryProtocol(Protocol):
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...


class CatalogRepositoryProtocol(Protocol):
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...


class ArtConceptService:
    def __init__(
        self,
        *,
        campaigns: CampaignRepositoryProtocol | None = None,
        revisions: RevisionRepositoryProtocol | None = None,
        catalog: CatalogRepositoryProtocol | None = None,
        settings: Settings | None = None,
        team_id: str | None = None,
    ) -> None:
        self.campaigns = campaigns
        self.revisions = revisions
        self.catalog = catalog
        self.settings = settings
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, settings: Settings | None = None, team_id: str | None = None) -> "ArtConceptService":
        from app.db.repositories.campaign_catalog import CampaignCatalogRepository
        from app.db.repositories.campaign_revisions import CampaignRevisionRepository
        from app.db.repositories.campaigns import CampaignRepository

        return cls(
            campaigns=CampaignRepository(client),
            revisions=CampaignRevisionRepository(client),
            catalog=CampaignCatalogRepository(client),
            settings=settings,
            team_id=team_id,
        )

    def propose_concepts(self, campaign_id: str, request: ArtConceptsRequest) -> ArtConceptsResponse:
        campaign = self._get_campaign(campaign_id)
        brief = (campaign or {}).get("structured_brief") or {}
        brand = resolve_brand_context(campaign or {"id": campaign_id})
        revision = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) if self.revisions else None
        catalog = self._catalog_context(campaign_id)
        specs = self._variant_specs(brief)
        return run_coro(self._compose(campaign_id, brief, brand, revision, catalog, specs, request))

    # --- composition -----------------------------------------------------

    async def _compose(self, campaign_id, brief, brand, revision, catalog, specs, request) -> ArtConceptsResponse:
        layout_skill = _load_runtime_skill("layout-retrieve")
        concept_skill = _load_runtime_skill("banner-concept-draft")
        bg_skill = _load_runtime_skill("background-options-generate")

        brief_for_skills = {"structured_brief": brief}
        # 1 — layout from the KG.
        try:
            layout_docs = await layout_skill.run(brief_for_skills, brand)
        except Exception:  # noqa: BLE001
            layout_docs = []
        layout_title = layout_docs[0]["title"] if layout_docs else "Hero split layout"
        layout_source = "[KG-RETRIEVED]" if layout_docs else "[DETERMINISTIC]"

        # 2 — backgrounds (one pool, assigned per variant for variety).
        concept_for_bg = (revision or {}).get("concept") or {"copy": {}, "layout": layout_title, "image_prompt": ""}
        try:
            bg_options, bg_source = await bg_skill.run(concept_for_bg, brand, count=max(len(specs), 1), settings=self.settings)
        except Exception:  # noqa: BLE001
            bg_options, bg_source = [], "deterministic"

        # 3 — featured product (catalog, grounded).
        product, product_rationale, product_tag = self._pick_product(catalog)

        promo = str(brief.get("promo") or "")
        feedback = (request.feedback or "").strip()
        concepts: list[ArtConceptVariant] = []
        copy_source = "deterministic"
        for index, spec in enumerate(specs):
            audience = spec["audience"]
            goal = str(brief.get("goal") or "")
            # Iteration: fold feedback into the copy step for the focused variant (or all).
            if feedback and (not request.focus_variant or request.focus_variant == spec["key"]) and request.focus in (None, "copy"):
                goal = f"{goal} — ajuste del diseñador: {feedback}"
            copy = await concept_skill.copy_for_audience(
                campaign={"structured_brief": {**brief, "goal": goal, "audience": audience}},
                brand_context=brand,
                catalog_context=catalog,
                best_practices=None,
                layout_hint=layout_title,
                audience=audience,
                settings=self.settings,
                cost_guard=None,
            )
            if copy.get("headline") and self.settings is not None and getattr(self.settings, "has_google_api_key", lambda: False)():
                copy_source = "gemini"
            treatment = _MODEL_TREATMENTS.get(spec["key"]) or _MODEL_TREATMENTS.get(_segment_kind(spec))
            shot_type = "usage" if treatment else "hero"
            bg = bg_options[index % len(bg_options)] if bg_options else None
            background = {"name": getattr(bg, "name", "Gradiente de marca"), "description": getattr(bg, "description", ""), "css": getattr(bg, "css", "")} if bg else {}
            concepts.append(
                ArtConceptVariant(
                    variant_key=spec["key"],
                    label=spec["label"],
                    customer_tag=spec.get("customer_tag"),
                    audience=audience,
                    shot_type=shot_type,
                    layout=layout_title,
                    layout_source=layout_source,
                    copy=copy,
                    background=background,
                    product=product,
                    product_rationale=product_rationale,
                    model_treatment=treatment,
                    rationale=_rationale(spec, product, treatment, promo),
                    origin_tags={
                        "layout": layout_source,
                        "copy": "[LLM-GENERATED]" if copy_source == "gemini" else "[DETERMINISTIC]",
                        "background": "[LLM-GENERATED]",
                        "product": product_tag,
                        "model_treatment": "[LLM-GENERATED]" if treatment else "[MISSING]",
                    },
                )
            )
        return ArtConceptsResponse(
            campaign_id=campaign_id,
            revision_id=str(revision["id"]) if revision and revision.get("id") else request.revision_id,
            personalization_dimension=str(brief.get("personalization_dimension") or ""),
            source="gemini" if copy_source == "gemini" else bg_source,
            concepts=concepts,
            metadata={"iterated": bool(feedback), "focus": request.focus, "focus_variant": request.focus_variant},
        )

    # --- helpers ---------------------------------------------------------

    def _variant_specs(self, brief: dict[str, Any]) -> list[dict[str, Any]]:
        raw = brief.get("personalization_variants") or []
        specs = []
        for entry in raw:
            key = str((entry or {}).get("key") or "").strip()
            if key:
                specs.append({
                    "key": key,
                    "label": str(entry.get("label") or key.title()),
                    "audience": str(entry.get("audience") or brief.get("audience") or ""),
                    "customer_tag": entry.get("customer_tag"),
                })
        if not specs:
            specs = [{"key": "default", "label": "Audiencia única", "audience": str(brief.get("audience") or ""), "customer_tag": None}]
        return specs

    def _catalog_context(self, campaign_id: str) -> dict[str, Any] | None:
        if self.catalog is None:
            return None
        try:
            snapshot = self.catalog.get_latest_by_campaign_id(campaign_id=campaign_id)
        except Exception:  # noqa: BLE001
            return None
        if not snapshot:
            return None
        return {"items": [i for i in (snapshot.get("items") or []) if i.get("title")], "discount_rule": snapshot.get("discount_rule") or {}}

    @staticmethod
    def _pick_product(catalog: dict[str, Any] | None) -> tuple[ConceptProductRef | None, str, str]:
        items = (catalog or {}).get("items") or []
        if not items:
            # Recommend-Nothing: no product to feature.
            return None, "Sin productos en el snapshot del catálogo — sincroniza/selecciona productos. [MISSING]", "[MISSING]"

        def _stock(i):
            try:
                return int(i.get("stock") or 0)
            except (TypeError, ValueError):
                return 0

        ranked = sorted(items, key=_stock, reverse=True)
        top = ranked[0]
        stock = _stock(top)
        price = top.get("price") if isinstance(top.get("price"), (int, float)) else top.get("sale_price")
        ref = ConceptProductRef(
            title=str(top.get("title") or ""),
            sku=top.get("sku"),
            price=float(price) if isinstance(price, (int, float)) else None,
            image_url=top.get("image_url"),
        )
        if stock > 0:
            rationale = f"Mayor stock disponible ({stock}) en el snapshot. [PROVIDER] · Ajuste al tema a validar con A/B. [HYPOTHESIS]"
        else:
            rationale = "Producto destacado del catálogo (sin dato de stock). [PROVIDER] · Desempeño a validar. [HYPOTHESIS]"
        return ref, rationale, "[PROVIDER]"

    def _get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        if self.campaigns is None:
            return None
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign


def _segment_kind(spec: dict[str, Any]) -> str:
    tag = (spec.get("customer_tag") or "").lower()
    aud = (spec.get("audience") or "").lower()
    if "male" in tag or "hombre" in aud:
        return "male"
    if "female" in tag or "mujer" in aud:
        return "female"
    if "vip" in tag or "vip" in aud:
        return "vip"
    if "unisex" in (spec.get("key") or ""):
        return "unisex"
    return ""


def _rationale(spec, product, treatment, promo) -> str:
    parts = [f"Concepto para «{spec['label']}» (audiencia: {spec['audience']})."]
    if product is not None:
        parts.append(f"Producto destacado: {product.title}.")
    if treatment:
        parts.append(f"Tratamiento usage: {treatment}")
    if promo:
        parts.append(f"Oferta: {promo}.")
    return " ".join(parts)


def _configured_service_for_team(team_id_override: str | None = None) -> ArtConceptService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        return ArtConceptService(settings=settings, team_id=team_id)
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return ArtConceptService.from_supabase_client(client, settings=settings, team_id=team_id)


def configured_service() -> ArtConceptService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> ArtConceptService:
    return _configured_service_for_team(team_id)
