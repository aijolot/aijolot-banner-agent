"""F5 — real generation orchestrator.

Runs the implemented banner pipeline node-by-node against a persisted campaign
and writes genuine artifacts (revision + banner/layout variants + preview +
audit report) instead of the deterministic Task-10 stub. Every node emits a
real ``generation_events`` pair (started/succeeded) with durations and cost.

Design constraints (see plan F5):
- Deterministic-friendly: the heavy creative skills (concept, render, liquid,
  audit) are deterministic; only image generation and KG retrieval reach
  Gemini/providers, and both degrade gracefully (fake image provider when no
  key, static KG floor). So the pipeline produces a *structurally real*
  revision even without ``GOOGLE_API_KEY``.
- Cost-capped: the paid image path is gated by :class:`CostGuard`; a denial (or
  no real provider configured) falls back to the free fake provider so the
  banner still renders.
- Repos are injected, so unit tests can exercise the full path with in-memory
  fakes and no Supabase.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.agents.state import BannerAssets, BannerSessionState, Campaign as StateCampaign, Concept as StateConcept, Variant as StateVariant
from app.core.settings import Settings
from app.services.gemini.cost_guard import CostGuard, get_default_cost_guard
from app.workflows.banner_creation import (
    DETERMINISTIC_LAYOUT_VARIANT_KEYS,
    _load_runtime_skill,
    frontend_step_for_node,
)

# Nodes this orchestrator actually executes (pre-HITL). The trailing review/
# publish nodes are owned by the HITL + publisher flow (F10) and are not run
# here; the run still reports `review_publish` as the terminal frontend step
# because, on success, the banner is ready for human review.
_PIPELINE_NODES: tuple[str, ...] = (
    "load_brand_context",
    "intake_campaign_idea",
    "capture_user_personalization",
    "research_best_practices",
    "draft_banner_concept",
    "generate_image",
    "optimize_assets",
    "render_html",
    "audit",
)

_TERMINAL_FRONTEND_STEP = "review_publish"
_AUDIT_DB_STATUSES = {"pending", "pass", "fail", "escalated"}


class RevisionRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...
    def update(self, *, revision_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class VariantRepositoryProtocol(Protocol):
    def create_many(self, *, variants: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class LayoutVariantRepositoryProtocol(Protocol):
    def create_many(self, *, variants: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class AuditReportRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...
    def update(self, *, campaign_id: str, data: dict[str, Any], team_id: str | None = None) -> dict[str, Any] | None: ...


@dataclass
class OrchestratorOutcome:
    """Result of one pipeline run, consumed by GenerationRunService."""

    status: str  # "succeeded" | "failed"
    frontend_step: str
    events: list[dict[str, Any]] = field(default_factory=list)
    revision_id: str | None = None
    error_message: str | None = None
    total_cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class RunOrchestrator:
    """Executes the implemented pipeline segment and persists artifacts."""

    def __init__(
        self,
        *,
        revisions: RevisionRepositoryProtocol,
        variants: VariantRepositoryProtocol,
        layout_variants: LayoutVariantRepositoryProtocol,
        audit_reports: AuditReportRepositoryProtocol,
        campaigns: CampaignRepositoryProtocol,
        catalog: Any = None,
        asset_service: Any = None,
        settings: Settings | None = None,
        cost_guard: CostGuard | None = None,
        team_id: str | None = None,
    ) -> None:
        self.revisions = revisions
        self.variants = variants
        self.layout_variants = layout_variants
        self.audit_reports = audit_reports
        self.campaigns = campaigns
        self.catalog = catalog
        self.asset_service = asset_service
        self.settings = settings or Settings.from_env()
        self.cost_guard = cost_guard or get_default_cost_guard(self.settings)
        self.team_id = team_id

    async def execute(
        self,
        *,
        run_id: str,
        campaign_row: dict[str, Any],
        prompt: str | None = None,
        targets: list[str] | None = None,
    ) -> OrchestratorOutcome:
        """Run the pipeline and persist a real revision.

        ``prompt``/``targets`` switch the run into agentic-refine mode (F9): the
        concept is re-drafted with the refinement note, and a fresh AI background
        is attached when ``background`` is a target.
        """
        campaign_id = str(campaign_row["id"])
        is_refine = bool(prompt) or bool(targets)
        target_set = set(targets or [])
        recorder = _EventRecorder(run_id=run_id)
        total_cost = 0.0
        node = ""
        try:
            # 1 — brand context (defensive: synthesize defaults if not resolvable)
            node = "load_brand_context"
            recorder.start(node)
            brand = self._resolve_brand(campaign_row)
            recorder.succeed(node, {"brand_id": brand.id, "name": brand.name})

            # 2 — intake (brief already captured; synthesize, never re-prompt here).
            # Fold the selected catalog products + promo/discount into the brief so
            # the concept copy adapts to the real products and the offer.
            node = "intake_campaign_idea"
            recorder.start(node)
            campaign_state = self._campaign_from_row(campaign_row, brand)
            catalog_context = self._load_catalog_context(campaign_id)
            promo_text = self._promo_text(campaign_row, catalog_context)
            if promo_text and promo_text.lower() not in campaign_state.cta.lower():
                campaign_state.cta = _short(f"{campaign_state.cta} · {promo_text}", 60)
            recorder.succeed(
                node,
                {
                    "goal": campaign_state.goal,
                    "placement": campaign_state.placement,
                    "source": "structured_brief",
                    "catalog_items": len((catalog_context or {}).get("items") or []),
                    "promo": promo_text or None,
                },
            )

            # 3 — personalization (default single segment for the initial run)
            node = "capture_user_personalization"
            recorder.start(node)
            state_variants = [StateVariant(customer_tag="all", intent_delta="default")]
            recorder.succeed(node, {"segments": len(state_variants)})

            # 4 — best practices (KG tiered retrieval; static floor → never empty)
            node = "research_best_practices"
            recorder.start(node)
            best_practices = await self._run_skill(
                "best-practices-retrieve", campaign_state, brand
            )
            recorder.succeed(node, {"retrieved": len(best_practices)})

            # 5 — concept (grounded in KG liquid_pattern layouts when available)
            node = "draft_banner_concept"
            recorder.start(node)
            layout_candidates = await self._run_layout_retrieve(campaign_state, brand)
            concept = await self._run_concept(
                campaign_state, brand, state_variants, best_practices, layout_candidates, catalog_context
            )
            if is_refine and prompt:
                # Record the refinement intent on the concept so the new revision
                # is traceable and the canvas can surface what changed.
                concept.copy["revision_note"] = _short(prompt, 280)
                concept.hierarchy_notes = f"Refine: {_short(prompt, 120)}; {concept.hierarchy_notes}"
            # Always generate + attach an AI background so the assembled banner
            # (and the canvas) shows a real themed background, not a flat default.
            background = await self._refine_background(concept, brand)
            recorder.succeed(
                node,
                {
                    "layout": _short(concept.layout),
                    "headline": _short(concept.copy.get("headline", "")),
                    "layout_source": (concept.source_refs[0]["title"] if concept.source_refs else None),
                    "layout_candidates": len(layout_candidates),
                    "targets": sorted(target_set) or None,
                    "background": (background or {}).get("name") if background else None,
                },
            )

            # Persist the revision shell now so assets can be linked by revision_id.
            revision = self._create_revision(
                campaign_id=campaign_id, run_id=run_id, concept=concept, background=background
            )
            revision_id = str(revision["id"])
            layout_rows = self._create_layout_variants(revision_id, concept)
            variant_rows = await self._create_variant_banners(
                revision_id=revision_id, concept=concept, campaign_state=campaign_state,
                campaign_row=campaign_row, brand=brand, catalog_context=catalog_context, best_practices=best_practices,
            )
            banner_variant_id = str(variant_rows[0]["id"]) if variant_rows else None

            # 6 — image (cost-gated; degrades to free fake provider)
            node = "generate_image"
            recorder.start(node)
            image_bytes, image_meta, image_cost = await self._generate_image(
                concept=concept, brand=brand, campaign_id=campaign_id
            )
            total_cost += image_cost
            recorder.succeed(
                node,
                {"provider": image_meta.get("provider"), "size_bytes": image_meta.get("size_bytes")},
                cost_usd=image_cost,
            )

            # 7 — optimize + persist assets
            node = "optimize_assets"
            recorder.start(node)
            assets = await self._optimize_assets(
                image_bytes=image_bytes,
                concept=concept,
                campaign_id=campaign_id,
                revision_id=revision_id,
                banner_variant_id=banner_variant_id,
                image_meta=image_meta,
            )
            # The asset upload report can embed SDK objects (Supabase
            # UploadResponse) that break json.dumps in the Liquid payload builder
            # and the jsonb writes. Sanitize once, here, so every downstream
            # consumer sees plain primitives.
            assets.optimization_report = _json_safe(assets.optimization_report)
            assets.asset_records = _json_safe(assets.asset_records)
            recorder.succeed(node, {"weight_kb": round(assets.total_weight_kb_1280_webp, 2)})

            # 8 — render HTML + Liquid section
            node = "render_html"
            recorder.start(node)
            html_standalone = await self._render_html(concept, assets, brand)
            # Render the Liquid with one variant per personalization tag so the
            # storefront section switches copy by customer tag (served-by-tag).
            liquid_variants = _liquid_variants_from_rows(variant_rows)
            liquid_section = await self._render_liquid(concept, liquid_variants, brand, assets, campaign_state.placement)
            preview_path = _first_asset_path(assets)
            image_url = _first_asset_public_url(assets)
            # Surface the generated image + background onto the concept so the
            # canvas Banner renders them (not just the standalone html_preview).
            concept_dict = _concept_dict(concept)
            if background:
                concept_dict["background"] = background
            if image_url:
                concept_dict["generated_art"] = [{"public_url": image_url, "storage_path": preview_path, "shot_type": "hero"}]
            self.revisions.update(
                revision_id=revision_id,
                data=_json_safe(
                    {
                        "html_preview": html_standalone,
                        "preview_storage_path": preview_path,
                        "liquid_config": self._liquid_config(concept, liquid_section, campaign_state.placement),
                        "concept": concept_dict,
                    }
                ),
            )
            recorder.succeed(node, {"html_bytes": len(html_standalone), "has_liquid": bool(liquid_section), "image": bool(image_url), "background": (background or {}).get("name")})

            # 9 — audit
            node = "audit"
            recorder.start(node)
            audit_report = await self._run_audit(
                html_standalone, concept, assets, brand, campaign_state, state_variants
            )
            self._persist_audit(
                campaign_id=campaign_id, revision_id=revision_id, run_id=run_id, audit_report=audit_report
            )
            recorder.succeed(
                node,
                {"status": audit_report.status, "overall_pass": audit_report.overall_pass},
            )

            # Promote the new revision: supersede any prior selection, point the
            # campaign at it. Mirrors the regenerate bookkeeping.
            self._promote_revision(campaign_id=campaign_id, revision_id=revision_id)

            return OrchestratorOutcome(
                status="succeeded",
                frontend_step=_TERMINAL_FRONTEND_STEP,
                events=recorder.events,
                revision_id=revision_id,
                total_cost_usd=round(total_cost, 6),
                metadata={
                    "facade_version": "f9-refine-orchestrator" if is_refine else "f5-run-orchestrator",
                    "image_provider": image_meta.get("provider"),
                    "audit_status": audit_report.status,
                    "variants": len(variant_rows),
                    "refine_targets": sorted(target_set) if is_refine else None,
                },
            )
        except Exception as exc:  # noqa: BLE001 — honest failure: record + surface
            if node:
                recorder.fail(node, {"error": type(exc).__name__, "detail": _short(str(exc), 280)})
            return OrchestratorOutcome(
                status="failed",
                frontend_step=recorder.last_frontend_step or "intake_context",
                events=recorder.events,
                error_message=f"{type(exc).__name__}: {exc}"[:500],
                total_cost_usd=round(total_cost, 6),
                metadata={"facade_version": "f5-run-orchestrator", "failed_node": node},
            )

    async def edit_revision(
        self,
        *,
        run_id: str,
        campaign_row: dict[str, Any],
        source_revision: dict[str, Any],
        prompt: str,
        targets: list[str],
    ) -> OrchestratorOutcome:
        """Banner-edit: a scoped, non-destructive edit of an assembled revision.

        Edits ONLY the targeted layer(s) (copy / background / image), carries the
        rest forward from the source, re-renders + re-audits, and persists a new
        superseding revision. Reuses the orchestrator's render/audit/persist path.
        """
        campaign_id = str(campaign_row["id"])
        target_set = set(targets or [])
        recorder = _EventRecorder(run_id=run_id)
        total_cost = 0.0
        node = ""
        try:
            node = "load_brand_context"
            recorder.start(node)
            brand = self._resolve_brand(campaign_row)
            campaign_state = self._campaign_from_row(campaign_row, brand)
            recorder.succeed(node, {"brand_id": brand.id, "targets": sorted(target_set)})

            # concept dict carried forward (preserves background/generated_art/etc.)
            cdict = dict(source_revision.get("concept") or {})
            cdict.setdefault("copy", {})
            cdict.setdefault("palette_usage", {})
            cdict.setdefault("layout", "Hero split layout")
            cdict.setdefault("image_prompt", "")
            cdict.setdefault("hierarchy_notes", "")

            node = "draft_banner_concept"
            recorder.start(node)
            edited = []
            if {"copy", "concept", "layout"} & target_set:
                fresh = await self._run_concept(campaign_state, brand, [StateVariant(customer_tag="all", intent_delta="default")], [], None, None)
                fresh_dict = _concept_dict(fresh)
                if {"copy", "concept"} & target_set:
                    cdict["copy"] = {**cdict.get("copy", {}), **fresh_dict.get("copy", {})}
                    edited.append("copy")
                if "layout" in target_set:
                    cdict["layout"] = fresh_dict.get("layout", cdict["layout"])
                    cdict["source_refs"] = fresh_dict.get("source_refs", cdict.get("source_refs", []))
                    edited.append("layout")
            if "background" in target_set:
                bg = await self._refine_background(_dict_to_concept(cdict), brand)
                if bg:
                    cdict["background"] = bg
                    edited.append("background")
            cdict["copy"]["revision_note"] = _short(prompt, 280)
            recorder.succeed(node, {"edited": edited or ["(none — image only)"]})

            revision = self._create_revision(campaign_id=campaign_id, run_id=run_id, concept=_dict_to_concept(cdict), background=cdict.get("background"))
            # _create_revision dumps the Concept model (drops extras); re-store the
            # full dict so background/generated_art survive.
            revision = self.revisions.update(revision_id=str(revision["id"]), data={"concept": _json_safe(cdict)}) or revision
            revision_id = str(revision["id"])
            self._create_layout_variants(revision_id, _dict_to_concept(cdict))
            variant_rows = await self._copy_or_regenerate_variants(revision_id, source_revision, cdict, campaign_state, brand, "copy" in target_set)

            # image: regenerate only when targeted (or no source image to preserve)
            node = "generate_image"
            recorder.start(node)
            source_url = _last_generated_image(source_revision)
            if "image" in target_set or not source_url:
                image_bytes, image_meta, image_cost = await self._generate_image(concept=_dict_to_concept(cdict), brand=brand, campaign_id=campaign_id)
                total_cost += image_cost
                assets = await self._optimize_assets(image_bytes=image_bytes, concept=_dict_to_concept(cdict), campaign_id=campaign_id, revision_id=revision_id, banner_variant_id=(str(variant_rows[0]["id"]) if variant_rows else None), image_meta=image_meta)
                assets.optimization_report = _json_safe(assets.optimization_report)
                assets.asset_records = _json_safe(assets.asset_records)
                preview_path = _first_asset_path(assets)
                recorder.succeed(node, {"provider": image_meta.get("provider"), "regenerated": True})
            else:
                assets = _assets_from_url(source_url, cdict.get("copy", {}).get("headline") or "Banner")
                preview_path = source_revision.get("preview_storage_path")
                recorder.succeed(node, {"preserved_image": True})

            node = "render_html"
            recorder.start(node)
            concept_model = _dict_to_concept(cdict)
            html_standalone = await self._render_html(concept_model, assets, brand)
            liquid_section = await self._render_liquid(concept_model, _liquid_variants_from_rows(variant_rows), brand, assets, campaign_state.placement)
            self.revisions.update(revision_id=revision_id, data=_json_safe({"html_preview": html_standalone, "preview_storage_path": preview_path, "liquid_config": self._liquid_config(concept_model, liquid_section, campaign_state.placement), "concept": cdict}))
            recorder.succeed(node, {"html_bytes": len(html_standalone)})

            node = "audit"
            recorder.start(node)
            audit_report = await self._run_audit(html_standalone, concept_model, assets, brand, campaign_state, [StateVariant(customer_tag="all", intent_delta="default")])
            self._persist_audit(campaign_id=campaign_id, revision_id=revision_id, run_id=run_id, audit_report=audit_report)
            recorder.succeed(node, {"status": audit_report.status})

            self._promote_revision(campaign_id=campaign_id, revision_id=revision_id)
            return OrchestratorOutcome(
                status="succeeded", frontend_step=_TERMINAL_FRONTEND_STEP, events=recorder.events,
                revision_id=revision_id, total_cost_usd=round(total_cost, 6),
                metadata={"facade_version": "f-banner-edit", "edited_targets": sorted(target_set), "audit_status": audit_report.status},
            )
        except Exception as exc:  # noqa: BLE001
            if node:
                recorder.fail(node, {"error": type(exc).__name__, "detail": _short(str(exc), 280)})
            return OrchestratorOutcome(status="failed", frontend_step=recorder.last_frontend_step or "render_audit", events=recorder.events, error_message=f"{type(exc).__name__}: {exc}"[:500], metadata={"facade_version": "f-banner-edit", "failed_node": node})

    async def _copy_or_regenerate_variants(self, revision_id, source_revision, cdict, campaign_state, brand, regenerate_copy):
        """Carry the source's N variants forward; regenerate per-variant copy only
        when copy is the edit target (NEVER collapse N variants into one)."""
        source_variants = []
        try:
            source_variants = self.variants.list_by_revision_id(revision_id=str(source_revision["id"]))  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            source_variants = []
        if source_variants:
            concept_skill = _load_runtime_skill("banner-concept-draft") if regenerate_copy else None
            rows = []
            for v in source_variants:
                row = {k: v.get(k) for k in ("segment_key", "segment_label", "customer_tag", "audience_rule", "eyebrow", "headline", "subheadline", "cta_text", "cta_url", "palette")}
                row["revision_id"] = revision_id
                if regenerate_copy and concept_skill is not None:
                    rule = v.get("audience_rule") or {}
                    audience = rule.get("audience") or v.get("segment_label") or campaign_state.audience
                    # Keep this variant's featured product grounded when regenerating copy.
                    fp = rule.get("featured_product") or {}
                    variant_catalog = _variant_catalog_context(
                        None,
                        {
                            "product_gid": fp.get("product_gid"),
                            "product_title": fp.get("product_title"),
                            "product_image_url": fp.get("product_image_url"),
                        },
                    ) if fp else None
                    copy = await concept_skill.copy_for_audience(
                        campaign=campaign_state, brand_context=brand, catalog_context=variant_catalog, best_practices=None,
                        layout_hint=cdict.get("layout", ""), audience=audience, settings=self.settings, cost_guard=self.cost_guard,
                    )
                    row["eyebrow"] = copy.get("eyebrow") or row.get("eyebrow")
                    row["headline"] = copy.get("headline") or row.get("headline")
                    row["subheadline"] = copy.get("subheadline") or row.get("subheadline")
                    row["cta_text"] = copy.get("cta") or row.get("cta_text")
                rows.append(row)
            return self.variants.create_many(variants=_json_safe(rows))
        # No source variants → single default from the edited concept.
        copy = cdict.get("copy", {})
        rows = [{
            "revision_id": revision_id, "segment_key": "default", "segment_label": "Default audience",
            "audience_rule": {}, "eyebrow": copy.get("eyebrow"), "headline": copy.get("headline") or campaign_state.goal,
            "subheadline": copy.get("subheadline"), "cta_text": copy.get("cta") or campaign_state.cta,
            "cta_url": "/collections/all", "palette": dict(cdict.get("palette_usage") or {}),
        }]
        return self.variants.create_many(variants=_json_safe(rows))

    # --- node helpers -----------------------------------------------------

    def _resolve_brand(self, campaign_row: dict[str, Any]) -> Any:
        from app.services.banners.brand_resolver import resolve_brand_context

        return resolve_brand_context(campaign_row)

    def _campaign_from_row(self, campaign_row: dict[str, Any], brand: Any) -> StateCampaign:
        structured = campaign_row.get("structured_brief") or {}
        if not isinstance(structured, dict):
            structured = dict(getattr(structured, "model_dump", lambda: {})() or {})
        tone = structured.get("tone") or _brand_tone(brand) or "confident"
        deadline = _parse_deadline(structured.get("deadline"))
        return StateCampaign(
            goal=structured.get("goal") or "Promote featured products",
            audience=structured.get("audience") or "All shoppers",
            cta=structured.get("cta") or "Shop now",
            tone=tone,
            urgency=structured.get("urgency") or "medium",
            placement=structured.get("placement") or "hero_main",
            deadline=deadline,
        )

    async def _run_skill(self, skill_id: str, campaign: Any, brand: Any) -> list[dict[str, Any]]:
        skill = _load_runtime_skill(skill_id)
        return await skill.run(campaign=campaign, brand_context=brand)

    async def _run_layout_retrieve(self, campaign: StateCampaign, brand: Any) -> list[dict[str, Any]]:
        skill = _load_runtime_skill("layout-retrieve")
        try:
            return await skill.run(campaign, brand)
        except Exception:  # noqa: BLE001 — layout grounding is best-effort; concept falls back
            return []

    async def _run_concept(
        self,
        campaign: StateCampaign,
        brand: Any,
        variants: list[StateVariant],
        best_practices: list[dict[str, Any]],
        layout_candidates: list[dict[str, Any]] | None = None,
        catalog_context: dict[str, Any] | None = None,
    ) -> Any:
        skill = _load_runtime_skill("banner-concept-draft")
        return await skill.run(
            campaign=campaign,
            brand_context=brand,
            variants=variants,
            best_practices=best_practices,
            layout_candidates=layout_candidates,
            catalog_context=catalog_context,
            settings=self.settings,
            cost_guard=self.cost_guard,
        )

    def _load_catalog_context(self, campaign_id: str) -> dict[str, Any] | None:
        if self.catalog is None:
            return None
        try:
            snapshot = self.catalog.get_latest_by_campaign_id(campaign_id=campaign_id)
        except Exception:  # noqa: BLE001 — catalog grounding is best-effort
            return None
        if not snapshot:
            return None
        items = [i for i in (snapshot.get("items") or []) if i.get("title")]
        return {"items": items, "discount_rule": snapshot.get("discount_rule") or {}}

    @staticmethod
    def _promo_text(campaign_row: dict[str, Any], catalog_context: dict[str, Any] | None) -> str:
        # Prefer the campaign promo label, then the brief's parsed promo, then a %
        # from the promo rule or the catalog snapshot discount rule.
        label = str(campaign_row.get("promo_label") or "").strip()
        if label:
            return _short(label, 40)
        structured = campaign_row.get("structured_brief") or {}
        brief_promo = structured.get("promo") if isinstance(structured, dict) else ""
        if brief_promo:
            return _short(str(brief_promo), 40)
        rule = catalog_context.get("discount_rule") if catalog_context else None
        candidates: list[Any] = [campaign_row.get("promo_rule")]
        if isinstance(rule, dict):
            candidates.extend([rule.get("label"), rule.get("percent"), rule.get("value")])
        for cand in candidates:
            if cand in (None, ""):
                continue
            text = str(cand)
            if isinstance(cand, (int, float)) and not isinstance(cand, bool):
                return f"{int(cand)}% OFF"
            return _short(text, 40)
        return ""

    async def _generate_image(self, *, concept: Any, brand: Any, campaign_id: str) -> tuple[bytes, dict[str, Any], float]:
        from app.services.banners.image_gen import generate_image

        prompt_skill = _load_runtime_skill("image-prompt-refine")
        refined_prompt = await prompt_skill.run(concept, brand_context=brand)
        return await generate_image(
            refined_prompt,
            settings=self.settings,
            cost_guard=self.cost_guard,
            campaign_id=campaign_id,
            concept=concept,
        )

    async def _compose_variant_hero(
        self,
        *,
        spec: dict[str, Any],
        concept: Any,
        campaign_id: str,
        revision_id: str,
    ) -> str | None:
        """Generate a campaign-styled, background-removed product hero for a variant.

        Feeds the variant's REAL product photo to Nano Banana Pro as a reference and
        asks for a composition (bottle + campaign props) on a flat chroma-green field,
        then keys the green out to a transparent PNG so the creative background shows
        through. Returns the hero's public URL, or None (caller falls back to the raw
        product photo) when there is no product image, no storage, or generation fails.
        """
        product_url = str(spec.get("product_image_url") or "").strip()
        if not product_url or self.asset_service is None:
            return None

        import httpx

        from app.services.gemini.image_compose import chroma_key_to_png, transparent_fraction

        try:
            with httpx.Client(timeout=20.0) as http:
                resp = http.get(product_url)
            if resp.status_code >= 400 or not resp.content:
                return None
            ref_bytes = resp.content
            ref_mime = resp.headers.get("content-type", "image/jpeg").split(";")[0] or "image/jpeg"
        except Exception:  # noqa: BLE001
            return None

        prompt = self._hero_compose_prompt(spec=spec, concept=concept)
        from app.services.banners.image_gen import generate_image as _gen

        try:
            raw_bytes, meta, _cost = await _gen(
                prompt,
                settings=self.settings,
                cost_guard=self.cost_guard,
                campaign_id=campaign_id,
                aspect_ratio="3:4",
                concept=concept,
                reference_images=((ref_bytes, ref_mime),),
            )
        except Exception:  # noqa: BLE001 — generation failed; fall back to product photo
            return None
        if not meta.get("is_real_provider"):
            # Fake provider has no chroma field to key — not a usable transparent hero.
            return None
        try:
            png = chroma_key_to_png(raw_bytes)
        except ValueError:
            return None
        # Sanity: a real cutout removes a meaningful chunk of background; if almost
        # nothing was keyed, the model likely ignored the green field — skip it.
        if transparent_fraction(png) < 0.08:
            return None
        try:
            row = self.asset_service.upload_png(
                png_bytes=png,
                campaign_id=campaign_id,
                revision_id=revision_id,
                asset_group_key=f"hero-{spec.get('key') or 'v'}",
                asset_kind="generated_hero",
                alt_text=str(spec.get("product_title") or "Producto"),
                image_prompt=_short(prompt, 300),
            )
            return row.get("public_url")
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _hero_compose_prompt(*, spec: dict[str, Any], concept: Any) -> str:
        product = str(spec.get("product_title") or "the featured product")
        copy = getattr(concept, "copy", None) or {}
        headline = copy.get("headline") if isinstance(copy, dict) else ""
        mood = getattr(concept, "image_prompt", "") or ""
        layout = getattr(concept, "layout", "") or ""
        return (
            f"E-commerce banner HERO image of THIS exact product: {product}. "
            "Use the provided product photo as the visual reference — keep the bottle/package real shape, "
            "colors and label EXACTLY; do not invent a different product. "
            f"Campaign mood: {_short(headline, 80)}. {_short(mood, 180)}. "
            "Compose tasteful campaign props around the product that fit the theme (e.g. for a summer citrus "
            "promo: floating mandarin/orange slices, juicy splashes, warm sun bokeh) — elegant, premium, not cluttered. "
            "CRITICAL OUTPUT RULE: render the product and props on a PERFECTLY UNIFORM, FLAT, SOLID PURE GREEN "
            "background (hex #00FF00 chroma green) that fills the entire frame. No checkerboard, no gradient, no "
            "scenery, no floor, no shadows on a surface — just the cutout subject on flat #00FF00 green so the "
            "green can be keyed out to transparency. Portrait 3:4 framing, product centered with breathing room."
        )

    async def _optimize_assets(
        self,
        *,
        image_bytes: bytes,
        concept: Any,
        campaign_id: str,
        revision_id: str,
        banner_variant_id: str | None,
        image_meta: dict[str, Any],
    ) -> Any:
        skill = _load_runtime_skill("image-asset-optimize")
        alt_hint = concept.copy.get("headline") or "Banner"
        mime_type = image_meta.get("mime_type")
        image_prompt = image_meta.get("prompt")
        # Durable upload requires both an asset_service and campaign/revision ids.
        # Without a configured storage backend (tests / no-Supabase), fall back to
        # the in-memory optimization path so the banner still renders.
        if self.asset_service is not None:
            try:
                return await skill.run(
                    image_bytes,
                    alt_hint,
                    campaign_id=campaign_id,
                    revision_id=revision_id,
                    banner_variant_id=banner_variant_id,
                    mime_type=mime_type,
                    image_prompt=image_prompt,
                    asset_service=self.asset_service,
                )
            except Exception:  # noqa: BLE001 — upload failed; degrade to in-memory optimize
                pass
        return await skill.run(
            image_bytes,
            alt_hint,
            mime_type=mime_type,
            image_prompt=image_prompt,
        )

    async def _render_html(self, concept: Any, assets: Any, brand: Any) -> str:
        skill = _load_runtime_skill("banner-html-seo-render")
        return await skill.run(concept, assets, brand)

    async def _render_liquid(
        self, concept: Any, variants: list[StateVariant], brand: Any, assets: Any, placement: str
    ) -> str:
        skill = _load_runtime_skill("liquid-section-build")
        payload = await skill.run(concept, variants, brand, assets=assets, placement=placement)
        if isinstance(payload, dict):
            return str(payload.get("section") or "")
        return str(payload or "")

    async def _run_audit(
        self,
        html: str,
        concept: Any,
        assets: Any,
        brand: Any,
        campaign: StateCampaign,
        variants: list[StateVariant],
    ) -> Any:
        skill = _load_runtime_skill("performance-audit")
        state = BannerSessionState(
            trace_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            brand_id=getattr(brand, "id", "default"),
            brand_context=brand,
            campaign=campaign,
            variants=variants,
            concept=concept,
            assets=assets,
            html_standalone=html,
        )
        report, _decision = await skill.run(html, state)
        return report

    # --- persistence helpers ---------------------------------------------

    def _create_revision(self, *, campaign_id: str, run_id: str, concept: Any, background: dict[str, Any] | None = None) -> dict[str, Any]:
        latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
        revision_number = int((latest or {}).get("revision_number") or 0) + 1
        concept_dict = _concept_dict(concept)
        if background:
            concept_dict["background"] = background
        # Created as draft; promoted to "selected" only once the pipeline
        # finishes (see _promote_revision). A mid-pipeline failure therefore
        # leaves an inert draft instead of a half-built "selected" revision.
        return self.revisions.create(
            data={
                "campaign_id": campaign_id,
                "generation_run_id": run_id,
                "revision_number": revision_number,
                "status": "draft",
                "concept": _json_safe(concept_dict),
                "liquid_config": {},
                "html_preview": None,
                "preview_storage_path": None,
            }
        )

    async def _refine_background(self, concept: Any, brand: Any) -> dict[str, Any] | None:
        skill = _load_runtime_skill("background-options-generate")
        try:
            options, _source = await skill.run(concept, brand, count=1, settings=self.settings, cost_guard=self.cost_guard)
        except Exception:  # noqa: BLE001 — background is best-effort in refine
            return None
        if not options:
            return None
        top = options[0]
        return {"name": top.name, "description": top.description, "css": top.css, "html": top.html}

    def _create_layout_variants(self, revision_id: str, concept: Any) -> list[dict[str, Any]]:
        layout_label = _short(concept.layout, 80)
        rows = [
            {
                "revision_id": revision_id,
                "key": key,
                "name": f"Hero layout {key}",
                "description": layout_label if key == "A" else f"Layout option {key}",
                "layout_type": "split" if key == "A" else ("centered" if key == "B" else "media_first"),
                "is_recommended": key == "A",
                "config": {"variant_key": key, "layout": layout_label},
            }
            for key in DETERMINISTIC_LAYOUT_VARIANT_KEYS
        ]
        return self.layout_variants.create_many(variants=rows)

    def _variant_specs(self, campaign_row: dict[str, Any], campaign: StateCampaign) -> list[dict[str, Any]]:
        structured = campaign_row.get("structured_brief") or {}
        if not isinstance(structured, dict):
            structured = dict(getattr(structured, "model_dump", lambda: {})() or {})
        raw = structured.get("personalization_variants") or []
        specs: list[dict[str, Any]] = []
        for entry in raw:
            key = str((entry or {}).get("key") or "").strip()
            if not key:
                continue
            specs.append(
                {
                    "key": key,
                    "label": str(entry.get("label") or key.title()),
                    "audience": str(entry.get("audience") or campaign.audience),
                    "customer_tag": entry.get("customer_tag"),
                    "product_gid": entry.get("product_gid"),
                    "product_title": entry.get("product_title"),
                    "product_image_url": entry.get("product_image_url"),
                }
            )
        if not specs:
            specs = [{"key": "default", "label": "Default audience", "audience": campaign.audience, "customer_tag": None}]
        return specs

    async def _create_variant_banners(
        self,
        *,
        revision_id: str,
        concept: Any,
        campaign_state: StateCampaign,
        campaign_row: dict[str, Any],
        brand: Any,
        catalog_context: dict[str, Any] | None,
        best_practices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """One banner_variant per personalization variant, each with its own copy."""
        specs = self._variant_specs(campaign_row, campaign_state)
        concept_skill = _load_runtime_skill("banner-concept-draft")
        base_copy = concept.copy or {}
        rows: list[dict[str, Any]] = []
        for index, spec in enumerate(specs):
            # Each variant features its own product (when chosen): ground the copy on a
            # catalog context filtered to that product, so men→Mandarin Sky, women→My Way.
            variant_catalog = _variant_catalog_context(catalog_context, spec)
            has_own_product = bool(spec.get("product_gid") or spec.get("product_title"))
            # Compose a campaign-styled, background-removed hero from the variant's
            # real product photo (transparent PNG). None → Canvas uses the raw photo.
            if has_own_product and spec.get("product_image_url"):
                hero_url = await self._compose_variant_hero(
                    spec=spec, concept=concept, campaign_id=campaign_row["id"], revision_id=revision_id
                )
                if hero_url:
                    spec = {**spec, "product_hero_url": hero_url}
            if index == 0 and spec["audience"] == campaign_state.audience and not has_own_product:
                # Reuse the already-generated primary concept copy for the base variant.
                copy = {k: base_copy.get(k) for k in ("eyebrow", "headline", "subheadline", "cta")}
            else:
                copy = await concept_skill.copy_for_audience(
                    campaign=campaign_state,
                    brand_context=brand,
                    catalog_context=variant_catalog,
                    best_practices=best_practices,
                    layout_hint=concept.layout,
                    audience=spec["audience"],
                    settings=self.settings,
                    cost_guard=self.cost_guard,
                )
            rows.append(
                {
                    "revision_id": revision_id,
                    "segment_key": spec["key"],
                    "segment_label": spec["label"],
                    "customer_tag": spec.get("customer_tag"),
                    "audience_rule": {
                        "audience": spec["audience"],
                        "tag": spec.get("customer_tag"),
                        **({"featured_product": _variant_product_ref(spec)} if has_own_product else {}),
                    },
                    "eyebrow": copy.get("eyebrow") or spec["label"],
                    "headline": copy.get("headline") or campaign_state.goal,
                    "subheadline": copy.get("subheadline"),
                    "cta_text": copy.get("cta") or campaign_state.cta,
                    "cta_url": "/collections/all",
                    "palette": dict(concept.palette_usage or {}),
                }
            )
        return self.variants.create_many(variants=_json_safe(rows))

    def _liquid_config(self, concept: Any, liquid_section: str, placement: str) -> dict[str, Any]:
        return {
            "section": liquid_section,
            "placement": placement,
            "layout": _short(concept.layout, 120),
        }

    def _persist_audit(self, *, campaign_id: str, revision_id: str, run_id: str, audit_report: Any) -> None:
        status = audit_report.status if audit_report.status in _AUDIT_DB_STATUSES else (
            "pass" if audit_report.overall_pass else "fail"
        )
        self.audit_reports.create(
            data=_json_safe(
                {
                    "campaign_id": campaign_id,
                    "revision_id": revision_id,
                    "generation_run_id": run_id,
                    "html_w3c": _as_dict(audit_report.html_w3c),
                    "lighthouse": dict(audit_report.lighthouse or {}),
                    "schema_valid": bool(audit_report.schema_valid),
                    "breakpoints_render": dict(audit_report.breakpoints_render or {}),
                    "asset_weight_report": dict(audit_report.asset_weight_report or {}),
                    "wcag_report": dict(audit_report.wcag_report or {}),
                    "seo_report": dict(audit_report.seo_report or {}),
                    "root_cause_hint": audit_report.root_cause_hint,
                    "retry_count": 0,
                    "status": status,
                }
            )
        )

    def _promote_revision(self, *, campaign_id: str, revision_id: str) -> None:
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id) or {}
        previous_revision_id = campaign.get("selected_revision_id")
        if previous_revision_id and str(previous_revision_id) != revision_id:
            previous = None
            try:
                previous = self.revisions.get(revision_id=str(previous_revision_id))  # type: ignore[attr-defined]
            except AttributeError:
                previous = None
            if previous and previous.get("status") == "selected":
                self.revisions.update(revision_id=str(previous_revision_id), data={"status": "superseded"})
        # Flip the freshly built draft to the selected revision.
        self.revisions.update(revision_id=revision_id, data={"status": "selected"})
        self.campaigns.update(
            campaign_id=campaign_id,
            team_id=self.team_id,
            data={"selected_revision_id": revision_id, "status": "draft"},
        )


class _EventRecorder:
    """Builds ordered generation_events with unique, monotonic timestamps."""

    def __init__(self, *, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[dict[str, Any]] = []
        self._base = datetime.now(timezone.utc)
        self._seq = 0
        self.last_frontend_step: str | None = None

    def _next_ts(self) -> str:
        ts = (self._base + timedelta(microseconds=self._seq)).isoformat()
        self._seq += 1
        return ts

    def start(self, node_key: str) -> None:
        step = frontend_step_for_node(node_key)
        self.last_frontend_step = step
        self.events.append(
            {
                "generation_run_id": self.run_id,
                "node_key": node_key,
                "frontend_step": step,
                "status": "started",
                "input_summary": {"summary": f"Running {node_key}"},
                "output_summary": {},
                "duration_ms": 0,
                "cost_usd": 0.0,
                "created_at": self._next_ts(),
            }
        )

    def succeed(self, node_key: str, output: dict[str, Any], *, cost_usd: float = 0.0) -> None:
        step = frontend_step_for_node(node_key)
        self.last_frontend_step = step
        self.events.append(
            {
                "generation_run_id": self.run_id,
                "node_key": node_key,
                "frontend_step": step,
                "status": "succeeded",
                "input_summary": {},
                "output_summary": output,
                "duration_ms": 1,
                "cost_usd": round(float(cost_usd), 6),
                "created_at": self._next_ts(),
            }
        )

    def fail(self, node_key: str, output: dict[str, Any]) -> None:
        step = frontend_step_for_node(node_key)
        self.last_frontend_step = step
        self.events.append(
            {
                "generation_run_id": self.run_id,
                "node_key": node_key,
                "frontend_step": step,
                "status": "failed",
                "input_summary": {},
                "output_summary": output,
                "duration_ms": 1,
                "cost_usd": 0.0,
                "created_at": self._next_ts(),
            }
        )


def _json_safe(value: Any) -> Any:
    """Coerce a payload into JSON-serializable primitives before a jsonb write.

    Asset/optimization reports can carry SDK objects (e.g. Supabase
    ``UploadResponse``) that PostgREST cannot serialize. Falling back to ``str``
    for anything exotic keeps persistence robust without losing the data shape.
    """
    return json.loads(json.dumps(value, default=str))


def _concept_dict(concept: Any) -> dict[str, Any]:
    if hasattr(concept, "model_dump"):
        return concept.model_dump()
    return dict(concept or {})


def _liquid_variants_from_rows(variant_rows: list[dict[str, Any]]) -> list[StateVariant]:
    """Map persisted banner_variants → state Variants with per-tag copy_override
    so the Liquid section renders served-by-customer-tag personalization."""
    out: list[StateVariant] = []
    for row in variant_rows or []:
        override = {
            k: str(row.get(src))
            for k, src in (("headline", "headline"), ("subheadline", "subheadline"), ("eyebrow", "eyebrow"), ("cta", "cta_text"))
            if row.get(src)
        }
        out.append(
            StateVariant(
                customer_tag=str(row.get("customer_tag") or row.get("segment_key") or "default"),
                intent_delta=str(row.get("segment_label") or ""),
                copy_override=override or None,
            )
        )
    return out or [StateVariant(customer_tag="default", intent_delta="default")]


def _dict_to_concept(cdict: dict[str, Any]) -> StateConcept:
    """Build a Concept model from a stored concept dict (extras ignored)."""
    return StateConcept(
        layout=str(cdict.get("layout") or "Hero split layout"),
        copy=dict(cdict.get("copy") or {}),
        palette_usage=dict(cdict.get("palette_usage") or {}),
        image_prompt=str(cdict.get("image_prompt") or "featured product scene"),
        hierarchy_notes=str(cdict.get("hierarchy_notes") or ""),
        source_refs=list(cdict.get("source_refs") or []),
    )


def _last_generated_image(revision: dict[str, Any]) -> str | None:
    """Most recent generated product image URL stored on the revision concept."""
    concept = revision.get("concept") or {}
    art = concept.get("generated_art") or []
    for entry in reversed(art):
        url = (entry or {}).get("public_url") if isinstance(entry, dict) else None
        if url:
            return str(url)
    return None


def _assets_from_url(url: str, alt: str) -> BannerAssets:
    """Reconstruct a minimal BannerAssets pointing at a preserved image URL."""
    return BannerAssets(
        webp={1280: url},
        avif={},
        fallback_jpg={1280: url},
        alt_text_suggestion=alt,
        total_weight_kb_1280_webp=0.0,
        asset_records=[{"public_url": url, "size_key": 1280, "format": "webp", "storage_path": url}],
        optimization_report={"preserved": True},
    )


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"value": value}


def _brand_tone(brand: Any) -> str | None:
    voice = getattr(brand, "voice", None)
    tone = getattr(voice, "tone", None) if voice is not None else None
    if isinstance(tone, (list, tuple)) and tone:
        return ", ".join(str(t) for t in tone)
    if isinstance(tone, str) and tone.strip():
        return tone
    return None


def _parse_deadline(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _first_asset_path(assets: Any) -> str | None:
    records = getattr(assets, "asset_records", None) or []
    for record in records:
        path = record.get("storage_path") if isinstance(record, dict) else None
        if path:
            return str(path)
    return None


def _first_asset_public_url(assets: Any) -> str | None:
    """Public URL of the largest webp asset (for the canvas image)."""
    records = getattr(assets, "asset_records", None) or []
    webp = [r for r in records if isinstance(r, dict) and str(r.get("format") or "").lower() == "webp" and r.get("public_url")]
    pool = webp or [r for r in records if isinstance(r, dict) and r.get("public_url")]
    if not pool:
        return None
    best = max(pool, key=lambda r: int(r.get("size_key") or r.get("width") or 0))
    return str(best.get("public_url"))


def _variant_product_ref(spec: dict[str, Any]) -> dict[str, Any]:
    """The featured-product reference recorded on a variant (for the assembly/publish)."""
    ref: dict[str, Any] = {}
    for key in ("product_gid", "product_title", "product_image_url", "product_hero_url"):
        value = spec.get(key)
        if value:
            ref[key] = value
    return ref


def _variant_catalog_context(catalog_context: dict[str, Any] | None, spec: dict[str, Any]) -> dict[str, Any] | None:
    """Catalog context scoped to a variant's featured product.

    If the variant names a product, surface that product first (matched from the
    snapshot by GID/title, or synthesized from the variant's own fields when it is
    not in the snapshot) so the per-variant copy is grounded on the right product.
    Falls back to the shared catalog context when the variant has no product.
    """
    gid = str(spec.get("product_gid") or "").strip()
    title = str(spec.get("product_title") or "").strip()
    if not gid and not title:
        return catalog_context

    items = list((catalog_context or {}).get("items") or [])
    matched: dict[str, Any] | None = None
    for item in items:
        item_gid = str(item.get("shopify_product_gid") or item.get("shopify_gid") or "")
        item_title = str(item.get("title") or "")
        if (gid and item_gid == gid) or (title and item_title.lower() == title.lower()):
            matched = item
            break
    if matched is None:
        matched = {
            "title": title or "Featured product",
            "shopify_product_gid": gid or None,
            "image_url": spec.get("product_image_url"),
        }
    discount_rule = (catalog_context or {}).get("discount_rule") or {}
    return {"items": [matched], "discount_rule": discount_rule}


def _short(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]
