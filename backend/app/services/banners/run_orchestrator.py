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
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.agents.state import BannerAssets, BannerSessionState, Campaign as StateCampaign, Concept as StateConcept, Variant as StateVariant
from app.core.settings import Settings
from app.schemas.decision_trace import build_concept_trace
from app.core.i18n import campaign_lang, lang_name as i18n_lang_name, t as i18n_t
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
        art_directions: Any = None,
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
        self.art_directions = art_directions
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
        lang = campaign_lang(campaign_row)
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
            catalog_context = self._load_catalog_context(campaign_id, campaign_row)
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
            recorder.succeed(node, {"retrieved": len(best_practices), "sources": _kg_sources_payload(best_practices)})

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
            background, _bg_source = await self._refine_background(concept, brand)
            art_direction = await self._propose_art_direction(concept, brand, lang=lang)
            art_direction = {
                **art_direction,
                **(await self._resolve_creative_mode(
                    campaign_id=campaign_id, campaign_state=campaign_state, brand=brand, prev_art={}, lang=lang
                )),
            }
            fonts = art_direction.get("fonts") or {}
            decision_trace = build_concept_trace(concept=concept, best_practices=best_practices, brand=brand, lang=lang).model_dump()
            recorder.succeed(
                node,
                {
                    "layout": _short(concept.layout),
                    "fonts": f"{fonts.get('display')}/{fonts.get('body')}",
                    "headline": _short(concept.copy.get("headline", "")),
                    "layout_source": (concept.source_refs[0]["title"] if concept.source_refs else None),
                    "layout_candidates": len(layout_candidates),
                    "targets": sorted(target_set) or None,
                    "background": (background or {}).get("name") if background else None,
                    "decision_trace": decision_trace,
                },
            )

            # Persist the revision shell now so assets can be linked by revision_id.
            revision = self._create_revision(
                campaign_id=campaign_id, run_id=run_id, concept=concept, background=background
            )
            revision_id = str(revision["id"])
            layout_rows = self._create_layout_variants(revision_id, concept)
            compose_report: dict[str, Any] = {}
            variant_rows = await self._create_variant_banners(
                revision_id=revision_id, concept=concept, campaign_state=campaign_state,
                campaign_row=campaign_row, brand=brand, catalog_context=catalog_context, best_practices=best_practices,
                text_ink=_bg_text_ink(background), compose_report=compose_report,
                compose_heroes=str(art_direction.get("creative_mode") or "composite") == "composite",
            )
            banner_variant_id = str(variant_rows[0]["id"]) if variant_rows else None

            # Nodes 6–9 (image → optimize → render → audit) + promote. Shared with
            # the approve/build phase via _assemble_and_audit.
            return await self._assemble_and_audit(
                run_id=run_id,
                campaign_id=campaign_id,
                recorder=recorder,
                concept=concept,
                brand=brand,
                campaign_state=campaign_state,
                state_variants=state_variants,
                variant_rows=variant_rows,
                revision_id=revision_id,
                banner_variant_id=banner_variant_id,
                background=background,
                art_direction=art_direction,
                fonts=fonts,
                total_cost=total_cost,
                is_refine=is_refine,
                target_set=target_set,
                metadata_extra=({"hero_compose": compose_report} if compose_report else None),
                decision_trace=decision_trace,
                cta_url=self._destination_url(campaign_row),
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

    async def _assemble_and_audit(
        self,
        *,
        run_id: str,
        campaign_id: str,
        recorder: "_EventRecorder",
        concept: Any,
        brand: Any,
        campaign_state: StateCampaign,
        state_variants: list[StateVariant],
        variant_rows: list[dict[str, Any]],
        revision_id: str,
        banner_variant_id: str | None,
        background: dict[str, Any] | None,
        art_direction: dict[str, Any] | None,
        fonts: dict[str, Any],
        total_cost: float = 0.0,
        is_refine: bool = False,
        target_set: set[str] | None = None,
        metadata_extra: dict[str, Any] | None = None,
        decision_trace: dict[str, Any] | None = None,
        cta_url: str | None = None,
    ) -> OrchestratorOutcome:
        """Nodes 6–9 (image → optimize → render → audit) + promote.

        Shared back half of the pipeline: used by the single-pass ``execute`` and
        by ``execute_build_phase`` (approve-the-plan path). Has its own
        try/except so a failure here is recorded honestly with the right node.
        """
        target_set = target_set or set()
        node = ""
        try:
            creative_mode = str((art_direction or {}).get("creative_mode") or "composite")
            full_bleed = creative_mode in ("full_picture", "video")

            # 6 — image (cost-gated; degrades to free fake provider)
            node = "generate_image"
            recorder.start(node)
            image_bytes, image_meta, image_cost = await self._generate_image(
                concept=concept, brand=brand, campaign_id=campaign_id, art_direction=art_direction
            )
            total_cost += image_cost
            recorder.succeed(
                node,
                {
                    "provider": image_meta.get("provider"),
                    "size_bytes": image_meta.get("size_bytes"),
                    "creative_mode": creative_mode,
                },
                cost_usd=image_cost,
            )

            # 6b — video (C2): only in video mode; degrades to the image banner.
            video_url: str | None = None
            video_degraded_reason: str | None = None
            if creative_mode == "video":
                node = "generate_video"
                recorder.start(node)
                from app.services.banners.video_gen import generate_video, motion_prompt

                video_response, video_meta, video_cost = await generate_video(
                    motion_prompt(str(image_meta.get("refined_prompt") or getattr(concept, "image_prompt", "") or "")),
                    settings=self.settings,
                    cost_guard=self.cost_guard,
                    campaign_id=campaign_id,
                    reference_image=(image_bytes, "image/png"),
                )
                total_cost += video_cost
                if video_response is not None and self.asset_service is not None:
                    try:
                        video_row = self.asset_service.upload_video(
                            video_bytes=video_response.video_bytes,
                            campaign_id=campaign_id,
                            revision_id=revision_id,
                            asset_group_key="hero-clip",
                            mime_type=video_response.mime_type,
                            video_prompt=_short(video_response.prompt, 300),
                        )
                        video_url = video_row.get("public_url")
                    except Exception:  # noqa: BLE001
                        video_url = None
                if video_response is not None and self.asset_service is None:
                    video_degraded_reason = "no_storage"
                elif video_response is None:
                    video_degraded_reason = str(video_meta.get("reason") or "generation_failed")
                elif not video_url:
                    video_degraded_reason = "upload_failed"
                # Asset-weight budget (LCP guard): warn > 1.5MB, heavy > 3MB.
                clip_bytes = int(video_meta.get("size_bytes") or 0)
                weight_status = "heavy" if clip_bytes > 3_000_000 else ("warn" if clip_bytes > 1_500_000 else "ok")
                recorder.succeed(
                    node,
                    {
                        "provider": video_meta.get("provider"),
                        "duration_s": video_meta.get("duration_seconds"),
                        "size_bytes": video_meta.get("size_bytes"),
                        "weight_status": weight_status if not video_degraded_reason else None,
                        "video_degraded": bool(video_degraded_reason),
                        "degraded_reason": video_degraded_reason,
                    },
                    cost_usd=video_cost,
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
            liquid_section = await self._render_liquid(concept, liquid_variants, brand, assets, campaign_state.placement, cta_url=cta_url)
            preview_path = _first_asset_path(assets)
            image_url = _first_asset_public_url(assets)
            # Surface the generated image + background onto the concept so the
            # canvas Banner renders them (not just the standalone html_preview).
            concept_dict = _concept_dict(concept)
            if full_bleed and image_url and art_direction is not None:
                # C1 — full-picture: the generated scene IS the banner background.
                # No chroma/compose; copy legibility comes from measured ink + scrim.
                layout_for_zone = dict(art_direction.get("layout") or {})
                from app.services.banners.contrast import adaptive_ink_and_scrim

                contrast = adaptive_ink_and_scrim(image_bytes, layout_for_zone)
                try:
                    fold = int((art_direction.get("fold_percentage") or 55))
                except (TypeError, ValueError):
                    fold = 55
                text_x = float(layout_for_zone.get("textX") or 6.0)
                text_w = float(layout_for_zone.get("textW") or 48.0)
                focal_x = max(0.0, min(100.0, 100.0 - (text_x + text_w / 2.0)))
                art_direction = {
                    **art_direction,
                    "full_bleed": True,
                    "ink": contrast["ink"],
                    "scrim": {"dir": contrast["scrim_dir"], "alpha": contrast["scrim_alpha"]},
                    "focal": {"x": round(focal_x, 1), "y": fold},
                    **({"video": {"url": video_url, "poster_url": image_url}} if creative_mode == "video" and video_url else {}),
                }
                background = {
                    "name": "Escena completa generada",
                    "description": "Imagen full-bleed generada por el agente (modo full picture).",
                    "css": "",
                    "html": "",
                    "image_url": image_url,
                }
            if background:
                concept_dict["background"] = background
            if decision_trace:
                concept_dict["decision_trace"] = decision_trace
            if image_url:
                concept_dict["generated_art"] = [{"public_url": image_url, "storage_path": preview_path, "shot_type": "hero"}]
            if art_direction:
                layout = art_direction.get("layout") or {}
                review_report = None
                # Visual self-review: render the banner at the 3 breakpoints, have a
                # vision model critique each, and auto-correct the desktop composition.
                # Best-effort + gated on vision availability (needs Chromium + Gemini).
                if self.settings.has_google_api_key():
                    try:
                        review_spec = self._banner_review_spec(concept, background, variant_rows, art_direction, image_url)
                        from app.services.banners.banner_review import review_and_correct

                        reviewed = await review_and_correct(review_spec, max_iters=2)
                        layout = reviewed.get("layout") or layout
                        review_report = reviewed.get("report")
                        # If the review stripped low-contrast headline colors, mirror that
                        # onto every variant's stored runs (shared background → shared fix).
                        orig_runs = review_spec.get("headlineRuns") or []
                        fixed_runs = reviewed.get("headline_runs") or []
                        if orig_runs and fixed_runs and any(o.get("color") and not f.get("color") for o, f in zip(orig_runs, fixed_runs)):
                            self._strip_variant_run_colors(variant_rows)
                    except Exception:  # noqa: BLE001 — never fail assembly over review
                        review_report = None
                concept_dict["art_direction"] = {
                    "fonts": art_direction.get("fonts") or fonts,
                    "layout": layout,
                    # Full-bleed ink was MEASURED against the generated scene (C1);
                    # composed banners keep the contrast-from-background heuristic.
                    "ink": (art_direction.get("ink") if art_direction.get("full_bleed") else _bg_text_ink(background)),
                    **({k: art_direction[k] for k in ("creative_mode", "include_humans", "mode_rationale", "mode_source", "full_bleed", "scrim", "focal", "video", "ink_sections", "type_scale") if art_direction.get(k) is not None}),
                    **({"review": review_report} if review_report else {}),
                }
            self.revisions.update(
                revision_id=revision_id,
                data=_json_safe(
                    {
                        "html_preview": html_standalone,
                        "preview_storage_path": preview_path,
                        "liquid_config": self._liquid_config(concept, liquid_section, campaign_state.placement, image_url=image_url, cta_url=cta_url, brand=brand),
                        "concept": concept_dict,
                    }
                ),
            )
            recorder.succeed(node, {"html_bytes": len(html_standalone), "has_liquid": bool(liquid_section), "image": bool(image_url), "background": (background or {}).get("name"), **({"video": bool((art_direction or {}).get("video"))} if creative_mode == "video" else {})})

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
            # campaign at it. Mirrors the regenerate bookkeeping. (For the build
            # phase this also flips the "plan" revision to "selected".)
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
                    **(metadata_extra or {}),
                },
            )
        except Exception as exc:  # noqa: BLE001 — honest failure: record + surface
            if node:
                recorder.fail(node, {"error": type(exc).__name__, "detail": _short(str(exc), 280)})
            return OrchestratorOutcome(
                status="failed",
                frontend_step=recorder.last_frontend_step or "render_audit",
                events=recorder.events,
                error_message=f"{type(exc).__name__}: {exc}"[:500],
                total_cost_usd=round(total_cost, 6),
                metadata={"facade_version": "f5-run-orchestrator", "failed_node": node, **(metadata_extra or {})},
            )

    async def execute_plan_phase(
        self,
        *,
        run_id: str,
        campaign_row: dict[str, Any],
        prompt: str | None = None,
        targets: list[str] | None = None,
    ) -> OrchestratorOutcome:
        """Cheap, deterministic-friendly PLAN phase: nodes 1–5 only.

        Drafts the concept + art direction + background (all FLASH-text/cheap and
        degrade without a key), builds a readable plan + a wireframe spec (no
        generated image), and persists a revision with ``status="plan"`` as the
        resume point. Never runs image/optimize/render/audit, never promotes.
        ``prompt``/``targets`` switch it into plan-iterate mode (re-draft the plan
        with the user's feedback).
        """
        campaign_id = str(campaign_row["id"])
        lang = campaign_lang(campaign_row)
        is_refine = bool(prompt) or bool(targets)
        target_set = set(targets or [])
        recorder = _EventRecorder(run_id=run_id)
        node = ""
        try:
            node = "load_brand_context"
            recorder.start(node)
            brand = self._resolve_brand(campaign_row)
            recorder.succeed(node, {"brand_id": brand.id, "name": brand.name})

            node = "intake_campaign_idea"
            recorder.start(node)
            campaign_state = self._campaign_from_row(campaign_row, brand)
            catalog_context = self._load_catalog_context(campaign_id, campaign_row)
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

            node = "capture_user_personalization"
            recorder.start(node)
            state_variants = [StateVariant(customer_tag="all", intent_delta="default")]
            recorder.succeed(node, {"segments": len(state_variants)})

            # W0.1 — grounded plan-iterate: interpret the feedback into directed
            # ops over the PREVIOUS plan instead of re-drafting everything. Loaded
            # BEFORE research so iterations reuse the cached KG retrieval.
            prev_concept: dict[str, Any] = {}
            if is_refine:
                latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
                if latest and str(latest.get("status") or "") == "plan":
                    prev_concept = dict(latest.get("concept") or {})
            research_cache = dict(prev_concept.get("research_cache") or {})

            node = "research_best_practices"
            recorder.start(node)
            if is_refine and research_cache.get("best_practices") is not None:
                # Plan-iterate: the KG corpus didn't change between iterations —
                # reuse the previous run's retrieval instead of re-querying
                # (this is what made every iteration recompute from scratch).
                best_practices = list(research_cache.get("best_practices") or [])
                recorder.succeed(
                    node,
                    {"retrieved": len(best_practices), "reused_from_previous_plan": True,
                     "sources": _kg_sources_payload(best_practices)},
                )
            else:
                best_practices = await self._run_skill("best-practices-retrieve", campaign_state, brand)
                recorder.succeed(node, {"retrieved": len(best_practices), "sources": _kg_sources_payload(best_practices)})

            node = "draft_banner_concept"
            recorder.start(node)

            rplan = None
            if is_refine:
                rplan = await self._interpret_refinement(prompt or "", targets, prev_concept or None)
                target_set = set(rplan.targets)

            needs_redraft = (
                (not is_refine)
                or (not prev_concept)
                or (rplan is not None and rplan.has("redraft_concept", "edit_copy", "adjust_layout"))
            )
            layout_candidates = list(research_cache.get("layout_candidates") or [])
            if needs_redraft:
                if not (is_refine and layout_candidates):
                    layout_candidates = await self._run_layout_retrieve(campaign_state, brand)
                concept = await self._run_concept(
                    campaign_state, brand, state_variants, best_practices, layout_candidates, catalog_context,
                    refine_instruction=(prompt or "") if is_refine else "",
                )
            else:
                concept = _dict_to_concept(prev_concept)
            if is_refine and prompt:
                concept.copy["revision_note"] = _short(prompt, 280)
                concept.hierarchy_notes = f"Refine: {_short(prompt, 120)}; {concept.hierarchy_notes}"

            # Background: only (re)generate when the user asked for it.
            prev_background = dict(prev_concept.get("background") or {}) or None
            decor_skipped = False
            background_changed = False
            if not is_refine or prev_background is None:
                background, _bg_source = await self._refine_background(concept, brand)
                background_changed = background is not None
            else:
                bg_op = next((o for o in rplan.ops if o.op in ("change_background", "change_decor")), None) if rplan else None
                if bg_op is None:
                    background = prev_background
                elif bg_op.op == "change_decor" and not self.settings.has_google_api_key():
                    # Directed decor swaps need the LLM; deterministically replacing
                    # the background would be exactly the bug we're fixing — keep it.
                    background = prev_background
                    decor_skipped = True
                else:
                    new_bg, bg_source = await self._refine_background(
                        concept, brand,
                        instruction=(bg_op.instruction or prompt or ""),
                        base_background=prev_background,
                    )
                    if bg_op.op == "change_decor" and bg_source != "gemini":
                        background = prev_background
                        decor_skipped = True
                    else:
                        background = new_bg or prev_background
                        background_changed = new_bg is not None

            # Art direction: keep fonts/layout stable across patch-only iterations.
            prev_art = dict(prev_concept.get("art_direction") or {})
            if needs_redraft or not prev_art:
                art_direction = await self._propose_art_direction(concept, brand, lang=lang)
            else:
                art_direction = prev_art
            fonts = art_direction.get("fonts") or {}

            # C0 — creative mode: user override (art_directions.mode_source='user')
            # is authoritative; patch-only iterates keep the previous plan's mode;
            # otherwise the agent recommends (LLM + deterministic vertical rules).
            mode = await self._resolve_creative_mode(
                campaign_id=campaign_id,
                campaign_state=campaign_state,
                brand=brand,
                prev_art=prev_art if not needs_redraft else {},
                lang=lang,
            )

            # El placement deja de ser un paso manual previo: el agente propone
            # el SET de piezas (dónde, cuántas, formato) como consecuencia del
            # brief. Patch-only iterates conservan la propuesta anterior.
            prev_plan_block = dict(prev_concept.get("plan") or {})
            if not needs_redraft and prev_plan_block.get("placement_plan"):
                placement_plan = dict(prev_plan_block["placement_plan"])
            else:
                placement_skill = _load_runtime_skill("placement-plan-recommend")
                placement_plan = (
                    await placement_skill.recommend(
                        campaign_row, brand,
                        creative_mode=str(mode.get("creative_mode") or "composite"),
                        settings=self.settings, cost_guard=self.cost_guard, lang=lang,
                    )
                ).model_dump()

            # Directed ink ops (contrast complaints / explicit text colors).
            ink_override: str | None = None
            ink_sections: dict[str, str] = dict(prev_art.get("ink_sections") or {})
            for op in (rplan.ops if rplan else []):
                if op.op != "set_ink":
                    continue
                value = op.value or _inverted_or_contrast_ink(prev_art.get("ink"), background)
                if op.section:
                    ink_sections[op.section] = value
                else:
                    ink_override = value

            # Directed image-scene op: the user corrected WHAT the image should
            # show. The override is the new scene seed; it survives patch-only
            # iterations and is dropped on a full concept redraft (new concept →
            # new brief-grounded scene).
            image_op = next((o for o in (rplan.ops if rplan else []) if o.op == "set_image_prompt"), None)
            if image_op is not None and (image_op.instruction or prompt or "").strip():
                image_prompt_override: str | None = _short((image_op.instruction or prompt or "").strip(), 600)
                image_prompt_source = "user"
            elif not needs_redraft and prev_art.get("image_prompt_override"):
                image_prompt_override = str(prev_art["image_prompt_override"])
                image_prompt_source = str(prev_art.get("image_prompt_source") or "user")
            else:
                image_prompt_override = None
                image_prompt_source = "agent"

            decision_trace = build_concept_trace(concept=concept, best_practices=best_practices, brand=brand, lang=lang).model_dump()
            recorder.succeed(
                node,
                {
                    "layout": _short(concept.layout),
                    "fonts": f"{fonts.get('display')}/{fonts.get('body')}",
                    "headline": _short(concept.copy.get("headline", "")),
                    "background": (background or {}).get("name") if background else None,
                    "background_changed": background_changed,
                    "decor_skipped_no_llm": decor_skipped or None,
                    "reused_previous_concept": (not needs_redraft) or None,
                    "interpreted_ops": (rplan.op_names() if rplan else None),
                    "interpret_source": (rplan.source if rplan else None),
                    "decision_trace": decision_trace,
                    "creative_mode": mode.get("creative_mode"),
                    "include_humans": mode.get("include_humans"),
                    "placement_pieces": len(placement_plan.get("pieces") or []),
                    "phase": "plan",
                },
            )

            # Persist the plan revision (status="plan") — NO image/render/audit.
            revision = self._create_revision(
                campaign_id=campaign_id, run_id=run_id, concept=concept, background=background, status="plan"
            )
            revision_id = str(revision["id"])
            concept_dict = _concept_dict(concept)
            if background:
                concept_dict["background"] = background
            # Ink precedence: directed op > previous plan's ink (when the
            # background didn't change) > contrast-from-background.
            if ink_override:
                ink = ink_override
            elif not background_changed and prev_art.get("ink"):
                ink = str(prev_art["ink"])
            else:
                ink = _bg_text_ink(background)
            final_art_direction = {
                "fonts": art_direction.get("fonts") or fonts,
                "layout": art_direction.get("layout") or {},
                "ink": ink,
                **({"ink_sections": ink_sections} if ink_sections else {}),
                **({"image_prompt_override": image_prompt_override, "image_prompt_source": image_prompt_source}
                   if image_prompt_override else {}),
                **mode,
            }
            concept_dict["art_direction"] = final_art_direction
            concept_dict["decision_trace"] = decision_trace
            # Research cache: lets the next plan-iterate skip the KG round-trip.
            concept_dict["research_cache"] = {
                "best_practices": _json_safe(best_practices),
                "layout_candidates": _json_safe(layout_candidates),
            }
            concept_dict["plan"] = self._build_campaign_plan(
                concept=concept,
                background=background,
                art_direction=final_art_direction,
                campaign_row=campaign_row,
                campaign_state=campaign_state,
                revision_id=revision_id,
                run_id=run_id,
                lang=lang,
            )
            concept_dict["plan"]["decision_trace"] = decision_trace
            concept_dict["plan"]["placement_plan"] = placement_plan
            concept_dict["plan"]["creative_mode"] = mode.get("creative_mode")
            concept_dict["plan"]["include_humans"] = bool(mode.get("include_humans"))
            concept_dict["plan"]["mode_rationale"] = str(mode.get("mode_rationale") or "")
            concept_dict["plan"]["mode_source"] = str(mode.get("mode_source") or "agent")
            # image_plan — the EXACT prompt the build will send to the image model,
            # plus the editable scene seed. Shown in the plan so the user corrects
            # the image BEFORE paying for the build (op: set_image_prompt).
            scene_seed = image_prompt_override or str(getattr(concept, "image_prompt", "") or "")
            planned_image_prompt = await _load_runtime_skill("image-prompt-refine").run(
                {"image_prompt": scene_seed, "layout": getattr(concept, "layout", "")},
                brand_context=brand,
                art_direction=final_art_direction,
            )
            wants_video = str(mode.get("creative_mode") or "") == "video"
            concept_dict["plan"]["image_plan"] = {
                "scene": scene_seed,
                "prompt": planned_image_prompt,
                "source": image_prompt_source if image_prompt_override else "agent",
                "creative_mode": str(mode.get("creative_mode") or "composite"),
                "video_requested": wants_video,
                "video_enabled": bool(getattr(self.settings, "video_generation_enabled", False)),
            }
            self.revisions.update(revision_id=revision_id, data=_json_safe({"concept": concept_dict}))

            return OrchestratorOutcome(
                status="succeeded",
                frontend_step="concept",
                events=recorder.events,
                revision_id=revision_id,
                total_cost_usd=0.0,
                metadata={
                    "facade_version": "plan-phase",
                    "phase": "plan",
                    "awaiting_approval": True,
                    "refine_targets": sorted(target_set) if is_refine else None,
                    "interpreted_ops": (rplan.op_names() if rplan else None),
                    "interpret_source": (rplan.source if rplan else None),
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
                metadata={"facade_version": "plan-phase", "failed_node": node},
            )

    async def execute_build_phase(
        self,
        *,
        run_id: str,
        campaign_row: dict[str, Any],
        plan_revision: dict[str, Any],
    ) -> OrchestratorOutcome:
        """Approve-the-plan BUILD phase: reuse the approved creative verbatim and
        run the costly nodes 6–9 on the existing plan revision, then promote it.

        The concept/background/art-direction are read back from the plan revision
        (no re-draft), so what the user approved is exactly what gets built. Early
        nodes (1–4) are re-emitted cheaply so the 5-step progress UI completes.
        """
        campaign_id = str(campaign_row["id"])
        recorder = _EventRecorder(run_id=run_id)
        node = ""
        try:
            node = "load_brand_context"
            recorder.start(node)
            brand = self._resolve_brand(campaign_row)
            recorder.succeed(node, {"brand_id": brand.id, "name": brand.name})

            node = "intake_campaign_idea"
            recorder.start(node)
            campaign_state = self._campaign_from_row(campaign_row, brand)
            catalog_context = self._load_catalog_context(campaign_id, campaign_row)
            recorder.succeed(node, {"goal": campaign_state.goal, "source": "approved_plan"})

            node = "capture_user_personalization"
            recorder.start(node)
            state_variants = [StateVariant(customer_tag="all", intent_delta="default")]
            recorder.succeed(node, {"segments": len(state_variants)})

            node = "research_best_practices"
            recorder.start(node)
            best_practices = await self._run_skill("best-practices-retrieve", campaign_state, brand)
            recorder.succeed(node, {"retrieved": len(best_practices), "sources": _kg_sources_payload(best_practices)})

            # Reuse the APPROVED creative verbatim (no re-draft): the plan is the contract.
            node = "draft_banner_concept"
            recorder.start(node)
            cdict = dict(plan_revision.get("concept") or {})
            concept = _dict_to_concept(cdict)
            background = cdict.get("background")
            art_direction = cdict.get("art_direction") or {}
            fonts = art_direction.get("fonts") or {}
            recorder.succeed(
                node,
                {
                    "layout": _short(concept.layout),
                    "source": "approved_plan",
                    "fonts": f"{fonts.get('display')}/{fonts.get('body')}",
                },
            )

            revision_id = str(plan_revision["id"])
            self._create_layout_variants(revision_id, concept)
            compose_report: dict[str, Any] = {}
            variant_rows = await self._create_variant_banners(
                revision_id=revision_id,
                concept=concept,
                campaign_state=campaign_state,
                campaign_row=campaign_row,
                brand=brand,
                catalog_context=catalog_context,
                best_practices=best_practices,
                text_ink=_bg_text_ink(background),
                compose_report=compose_report,
                compose_heroes=str((art_direction or {}).get("creative_mode") or "composite") == "composite",
            )
            banner_variant_id = str(variant_rows[0]["id"]) if variant_rows else None

            return await self._assemble_and_audit(
                run_id=run_id,
                campaign_id=campaign_id,
                recorder=recorder,
                concept=concept,
                brand=brand,
                campaign_state=campaign_state,
                state_variants=state_variants,
                variant_rows=variant_rows,
                revision_id=revision_id,
                banner_variant_id=banner_variant_id,
                background=background,
                art_direction=art_direction,
                fonts=fonts,
                total_cost=0.0,
                is_refine=False,
                target_set=set(),
                metadata_extra={"phase": "build", **({"hero_compose": compose_report} if compose_report else {})},
                decision_trace=dict((plan_revision.get("concept") or {}).get("decision_trace") or {}) or None,
                cta_url=self._destination_url(campaign_row),
            )
        except Exception as exc:  # noqa: BLE001 — honest failure: record + surface
            if node:
                recorder.fail(node, {"error": type(exc).__name__, "detail": _short(str(exc), 280)})
            return OrchestratorOutcome(
                status="failed",
                frontend_step=recorder.last_frontend_step or "intake_context",
                events=recorder.events,
                error_message=f"{type(exc).__name__}: {exc}"[:500],
                metadata={"facade_version": "build-phase", "failed_node": node},
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
                fresh = await self._run_concept(
                    campaign_state, brand, [StateVariant(customer_tag="all", intent_delta="default")], [], None, None,
                    refine_instruction=prompt,
                )
                fresh_dict = _concept_dict(fresh)
                if {"copy", "concept"} & target_set:
                    cdict["copy"] = {**cdict.get("copy", {}), **fresh_dict.get("copy", {})}
                    edited.append("copy")
                if "layout" in target_set:
                    cdict["layout"] = fresh_dict.get("layout", cdict["layout"])
                    cdict["source_refs"] = fresh_dict.get("source_refs", cdict.get("source_refs", []))
                    edited.append("layout")
            if {"background", "decor"} & target_set:
                base_bg = dict(cdict.get("background") or {}) or None
                directed = "decor" in target_set
                if directed and not self.settings.has_google_api_key():
                    # A directed decor swap can't be honored deterministically —
                    # keep the current background instead of replacing it (W0.1).
                    edited.append("background_kept(decor_no_llm)")
                else:
                    bg, bg_source = await self._refine_background(
                        _dict_to_concept(cdict), brand,
                        instruction=prompt if directed else "",
                        base_background=base_bg if directed else None,
                    )
                    if directed and bg_source != "gemini":
                        edited.append("background_kept(decor_no_llm)")
                    elif bg:
                        cdict["background"] = bg
                        edited.append("background")
            if "ink" in target_set:
                art = dict(cdict.get("art_direction") or {})
                art["ink"] = _inverted_or_contrast_ink(art.get("ink"), cdict.get("background"))
                cdict["art_direction"] = art
                edited.append("ink")
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
            _edit_cta_url = self._destination_url(campaign_row)
            liquid_section = await self._render_liquid(concept_model, _liquid_variants_from_rows(variant_rows), brand, assets, campaign_state.placement, cta_url=_edit_cta_url)
            self.revisions.update(revision_id=revision_id, data=_json_safe({"html_preview": html_standalone, "preview_storage_path": preview_path, "liquid_config": self._liquid_config(concept_model, liquid_section, campaign_state.placement, image_url=_first_asset_public_url(assets), cta_url=_edit_cta_url, brand=brand), "concept": cdict}))
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
            language=str(structured.get("language") or "es"),
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
        *,
        refine_instruction: str = "",
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
            refine_instruction=refine_instruction,
        )

    def _load_catalog_context(self, campaign_id: str, campaign_row: dict[str, Any] | None = None) -> dict[str, Any] | None:
        snapshot_items: list[dict[str, Any]] = []
        discount_rule: dict[str, Any] = {}
        if self.catalog is not None:
            try:
                snapshot = self.catalog.get_latest_by_campaign_id(campaign_id=campaign_id)
            except Exception:  # noqa: BLE001 — catalog grounding is best-effort
                snapshot = None
            if snapshot:
                snapshot_items = [i for i in (snapshot.get("items") or []) if i.get("title")]
                discount_rule = snapshot.get("discount_rule") or {}
        # Campaign-level products picked in the brief take precedence and ground the
        # concept even when no catalog snapshot exists; the snapshot fills the rest.
        brief_items = _brief_product_items(campaign_row)
        def _dup(item: dict[str, Any]) -> bool:
            gid = str(item.get("shopify_product_gid") or item.get("shopify_gid") or "")
            title = str(item.get("title") or "").lower()
            for b in brief_items:
                if (gid and gid == str(b.get("shopify_product_gid") or "")) or (title and title == str(b.get("title") or "").lower()):
                    return True
            return False
        items = brief_items + [i for i in snapshot_items if not _dup(i)]
        if not items and not discount_rule:
            return None
        return {"items": items, "discount_rule": discount_rule}

    @staticmethod
    def _destination_url(campaign_row: dict[str, Any]) -> str:
        """The CTA destination from the brief, defaulting to the storefront catalog."""
        structured = campaign_row.get("structured_brief") or {}
        if not isinstance(structured, dict):
            structured = dict(getattr(structured, "model_dump", lambda: {})() or {})
        url = str(structured.get("destination_url") or "").strip()
        return url or "/collections/all"

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

    async def _generate_image(
        self, *, concept: Any, brand: Any, campaign_id: str, art_direction: dict[str, Any] | None = None
    ) -> tuple[bytes, dict[str, Any], float]:
        from app.services.banners.image_gen import generate_image

        prompt_skill = _load_runtime_skill("image-prompt-refine")
        # A user-corrected scene (plan's image_plan / op set_image_prompt) replaces
        # the concept's scene seed verbatim — the plan is the contract.
        override = str((art_direction or {}).get("image_prompt_override") or "").strip()
        prompt_input: Any = (
            {"image_prompt": override, "layout": getattr(concept, "layout", "")} if override else concept
        )
        refined_prompt = await prompt_skill.run(prompt_input, brand_context=brand, art_direction=art_direction)
        image_bytes, meta, cost = await generate_image(
            refined_prompt,
            settings=self.settings,
            cost_guard=self.cost_guard,
            campaign_id=campaign_id,
            concept=concept,
        )
        meta["refined_prompt"] = refined_prompt
        meta["prompt_source"] = "user" if override else "agent"
        return image_bytes, meta, cost

    async def _compose_variant_hero(
        self,
        *,
        spec: dict[str, Any],
        concept: Any,
        campaign_id: str,
        revision_id: str,
        campaign_state: StateCampaign | None = None,
        brand: Any = None,
    ) -> tuple[str | None, str]:
        """Generate a campaign-styled, background-removed product hero for a variant.

        Feeds the variant's REAL product photo to Nano Banana Pro as a reference and
        asks for a composition (bottle + campaign props) on a flat chroma-green field,
        then keys the green out to a transparent PNG so the creative background shows
        through. Returns ``(public_url | None, status)``; a ``chroma_failed`` first
        attempt is retried ONCE with a reinforced chroma instruction (W0.2), and the
        status is surfaced so failures are never silent.
        """
        product_url = str(spec.get("product_image_url") or "").strip()
        if not product_url:
            return None, "no_image"
        if self.asset_service is None:
            return None, "no_storage"

        import httpx

        from app.services.gemini.image_compose import chroma_key_to_png, transparent_fraction

        try:
            with httpx.Client(timeout=20.0) as http:
                resp = http.get(product_url)
            if resp.status_code >= 400 or not resp.content:
                return None, "ref_fetch_failed"
            ref_bytes = resp.content
            ref_mime = resp.headers.get("content-type", "image/jpeg").split(";")[0] or "image/jpeg"
        except Exception:  # noqa: BLE001
            return None, "ref_fetch_failed"

        scene = await self._propose_art_scene(
            concept=concept, brand=brand, product_title=str(spec.get("product_title") or "the featured product"),
            campaign_state=campaign_state,
        )
        prompt = self._hero_compose_prompt(spec=spec, concept=concept, scene=scene)
        from app.services.banners.image_gen import generate_image as _gen

        async def _attempt(attempt_prompt: str) -> tuple[bytes | None, str]:
            try:
                raw_bytes, meta, _cost = await _gen(
                    attempt_prompt,
                    settings=self.settings,
                    cost_guard=self.cost_guard,
                    campaign_id=campaign_id,
                    aspect_ratio="3:4",
                    concept=concept,
                    reference_images=((ref_bytes, ref_mime),),
                )
            except Exception:  # noqa: BLE001 — generation failed; fall back to product photo
                return None, "error"
            if not meta.get("is_real_provider"):
                # Fake provider has no chroma field to key — not a usable transparent hero.
                return None, "fake_provider"
            try:
                keyed = chroma_key_to_png(raw_bytes)
            except ValueError:
                return None, "chroma_failed"
            # Sanity: a clean cut-out keys out a large green margin. If little was removed,
            # the model rendered a full scene instead of flat green (un-keyable).
            if transparent_fraction(keyed) < 0.25:
                return None, "chroma_failed"
            return keyed, "ok"

        png, status = await _attempt(prompt)
        if png is None and status == "chroma_failed":
            # W0.2 — ONE reinforced retry: product shots must come back on chroma
            # green so the background can be keyed out; never silently accept a
            # baked-in scene.
            png, status = await _attempt(_CHROMA_RETRY_PREFIX + prompt)
            if png is not None:
                status = "ok_retry"
        if png is None:
            return None, status
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
            return row.get("public_url"), status
        except Exception:  # noqa: BLE001
            return None, "upload_failed"

    async def _propose_art_scene(self, *, concept: Any, brand: Any, product_title: str, campaign_state: StateCampaign) -> str:
        """Creative-concept step for the IMAGE: an agent reads the brief and proposes a
        SHORT, campaign-specific scene (props + lighting/mood) for the hero — instead of
        a hardcoded theme. Returns '' (caller uses a neutral studio fallback) when Gemini
        is unavailable. Deliberately NO default props (no citrus/fruit unless the brief
        is about that), so each campaign gets its own concept."""
        if not self.settings.has_google_api_key():
            return ""
        copy = getattr(concept, "copy", None) or {}
        headline = copy.get("headline") if isinstance(copy, dict) else ""
        goal = getattr(campaign_state, "goal", "") or ""
        tone = _brand_tone(brand) or ""
        prompt = (
            "You are an art director defining the VISUAL CONCEPT for a CUT-OUT ecommerce hero of this product: "
            f"{product_title}. The product will be isolated on a transparent background, so propose only 2-3 small "
            "FLOATING props/accents plus a lighting style that genuinely fit THIS campaign — derive them from the "
            "brief; do NOT default to fruit/citrus or any preset theme unless the campaign is explicitly about that.\n"
            f"Campaign goal: {_short(goal, 120)}\nHeadline: {_short(headline, 90)}\nBrand tone: {_short(tone, 80)}\n"
            "HARD CONSTRAINTS: the props must FLOAT around the product — NO environment, NO scene, NO floor, NO "
            "table or pedestal, NO room, NO plants/foliage, NO horizon, NO background imagery. NO text, NO logos, "
            "NO people. Keep it minimal (the product is the hero).\n"
            "Return JSON {scene} — one concise sentence: the floating props + lighting style only (no product "
            "description, no background/color instructions)."
        )
        try:
            from app.agents.tools import gemini_text
            from app.schemas.typography import ArtScene

            result = await gemini_text.generate(prompt, model=gemini_text.FLASH_MODEL, structured=ArtScene)
            return _short(getattr(result, "scene", "") or "", 240)
        except Exception:  # noqa: BLE001 — scene proposal is best-effort
            return ""

    @staticmethod
    def _hero_compose_prompt(*, spec: dict[str, Any], concept: Any, scene: str = "") -> str:
        product = str(spec.get("product_title") or "the featured product")
        copy = getattr(concept, "copy", None) or {}
        headline = copy.get("headline") if isinstance(copy, dict) else ""
        # The scene comes from the per-campaign visual-concept agent. When absent, use a
        # NEUTRAL studio direction (no preset theme) and let the model infer from the mood.
        scene_line = (
            f"Visual concept: {scene}"
            if scene
            else "Compose a few tasteful props and lighting that fit the campaign mood (infer from the headline); "
            "keep it elegant and minimal — do not invent a specific unrelated theme."
        )
        return (
            f"E-commerce banner HERO cut-out of THIS exact product: {product}. "
            "Use the provided product photo as the visual reference — keep the bottle/package real shape, "
            "colors and label EXACTLY; do not invent a different product. "
            f"Campaign mood: {_short(headline, 80)}. {scene_line} "
            "The props must FLOAT next to the product — NO environment, NO floor, NO table/pedestal, NO room, NO "
            "plants, NO horizon, NO surface the product rests on. Premium, minimal; the product is the hero. "
            "ABSOLUTELY NO TEXT of any kind in the image: no words, letters, numbers, prices, percentages, '%', "
            "'OFF', taglines, captions, watermarks, logos or labels added on top — text is added later by the banner. "
            "CRITICAL OUTPUT RULE: render the product and floating props on a PERFECTLY UNIFORM, FLAT, SOLID PURE "
            "GREEN background (hex #00FF00 chroma green) filling the ENTIRE frame to every edge. No checkerboard, no "
            "gradient, no scenery, no floor, no cast shadow on a surface — only the cut-out subject + floating props "
            "on flat #00FF00 so the green keys out to transparency. Portrait 3:4, product centered with generous "
            "empty green margins around it (do not let the product or props touch the frame edges)."
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
        self, concept: Any, variants: list[StateVariant], brand: Any, assets: Any, placement: str, cta_url: str | None = None
    ) -> str:
        skill = _load_runtime_skill("liquid-section-build")
        payload = await skill.run(concept, variants, brand, assets=assets, placement=placement, cta_url=cta_url)
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

    def _create_revision(self, *, campaign_id: str, run_id: str, concept: Any, background: dict[str, Any] | None = None, status: str = "draft") -> dict[str, Any]:
        latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
        revision_number = int((latest or {}).get("revision_number") or 0) + 1
        concept_dict = _concept_dict(concept)
        if background:
            concept_dict["background"] = background
        # Created as draft; promoted to "selected" only once the pipeline
        # finishes (see _promote_revision). A mid-pipeline failure therefore
        # leaves an inert draft instead of a half-built "selected" revision.
        # The plan phase passes status="plan" to persist a resume point that is
        # NOT yet a selectable revision (no image/render/audit ran).
        return self.revisions.create(
            data={
                "campaign_id": campaign_id,
                "generation_run_id": run_id,
                "revision_number": revision_number,
                "status": status,
                "concept": _json_safe(concept_dict),
                "liquid_config": {},
                "html_preview": None,
                "preview_storage_path": None,
            }
        )

    def _strip_variant_run_colors(self, variant_rows: list[dict[str, Any]]) -> None:
        """Drop low-contrast headline run colors on every variant (review verdict)."""
        for row in variant_rows or []:
            rule = row.get("audience_rule") or {}
            runs = rule.get("headline_runs")
            if not runs:
                continue
            new_runs = [{**r, "color": None} for r in runs]
            new_rule = {**rule, "headline_runs": new_runs}
            row["audience_rule"] = new_rule
            try:
                self.variants.update(variant_id=str(row["id"]), data=_json_safe({"audience_rule": new_rule}))
            except Exception:  # noqa: BLE001 — best-effort
                pass

    @staticmethod
    def _banner_review_spec(
        concept: Any,
        background: dict[str, Any] | None,
        variant_rows: list[dict[str, Any]],
        art_direction: dict[str, Any],
        image_url: str | None,
    ) -> dict[str, Any]:
        """Build the render spec the visual review screenshots (primary variant)."""
        row = variant_rows[0] if variant_rows else {}
        fp = (row.get("audience_rule") or {}).get("featured_product") or {}
        copy = getattr(concept, "copy", None) or {}
        bg_css = (background or {}).get("css") or ""
        fonts = art_direction.get("fonts") or {}
        return {
            "eyebrow": row.get("eyebrow") or copy.get("eyebrow") or "",
            "headline": row.get("headline") or copy.get("headline") or "",
            "headlineRuns": (row.get("audience_rule") or {}).get("headline_runs") or None,
            "sub": row.get("subheadline") or copy.get("subheadline") or "",
            "cta": row.get("cta_text") or copy.get("cta") or "",
            "promo": row.get("cta_text") or copy.get("cta") or "",
            "imageUrl": (None if art_direction.get("full_bleed") else (fp.get("product_hero_url") or fp.get("product_image_url") or image_url)),
            "bgImageUrl": ((background or {}).get("image_url") if art_direction.get("full_bleed") else None),
            "bgFocal": art_direction.get("focal"),
            "scrim": art_direction.get("scrim"),
            "videoUrl": ((art_direction.get("video") or {}).get("url")),
            "posterUrl": ((art_direction.get("video") or {}).get("poster_url")),
            "imageUrls": [
                str(r.get("product_hero_url") or r.get("product_image_url"))
                for r in ((row.get("audience_rule") or {}).get("featured_products") or [])
                if (r.get("product_hero_url") or r.get("product_image_url"))
            ] or None,
            "bgCss": bg_css,
            "displayFont": fonts.get("display") or "Space Grotesk",
            "bodyFont": fonts.get("body") or "Inter",
            "textColor": art_direction.get("ink") or _bg_text_ink(background),
            "inkSections": art_direction.get("ink_sections") or None,
            "typeScale": art_direction.get("type_scale") or None,
            "layout": art_direction.get("layout") or {},
        }

    @staticmethod
    def _plan_wireframe_spec(
        concept: Any,
        background: dict[str, Any] | None,
        art_direction: dict[str, Any],
    ) -> dict[str, Any]:
        """The ``bannerLiveHTML`` ``live`` spec for the deterministic plan wireframe.

        Same shape the canvas/review renderer expects, but ``imageUrl=""`` so the
        frontend draws a placeholder hero box instead of a generated image.
        """
        copy = getattr(concept, "copy", None) or {}
        fonts = art_direction.get("fonts") or {}
        return {
            "eyebrow": copy.get("eyebrow") or "",
            "headline": copy.get("headline") or "",
            "headlineRuns": None,
            "sub": copy.get("subheadline") or "",
            "cta": copy.get("cta") or "",
            "promo": copy.get("cta") or "",
            "imageUrl": "",
            "bgCss": (background or {}).get("css") or "",
            "displayFont": fonts.get("display") or "Space Grotesk",
            "bodyFont": fonts.get("body") or "Inter",
            "textColor": art_direction.get("ink") or _bg_text_ink(background),
            "inkSections": art_direction.get("ink_sections") or None,
            "typeScale": art_direction.get("type_scale") or None,
            "layout": art_direction.get("layout") or {},
        }

    def _build_campaign_plan(
        self,
        *,
        concept: Any,
        background: dict[str, Any] | None,
        art_direction: dict[str, Any],
        campaign_row: dict[str, Any],
        campaign_state: StateCampaign,
        revision_id: str,
        run_id: str,
        lang: str = "es",
    ) -> dict[str, Any]:
        """Readable, deterministic plan block stored on the revision concept.

        Surfaces WHAT will be generated (typography, color classes, product/theme
        intent) + a wireframe spec, so the user can iterate before the costly build.
        Every user-facing string here is in the campaign language — image prompts
        stay English internally and are never shown verbatim.
        """
        copy = getattr(concept, "copy", None) or {}
        fonts = art_direction.get("fonts") or {}
        # Product intent per personalization variant (falls back to a single default).
        specs = self._variant_specs(campaign_row, campaign_state)
        product_intent: list[dict[str, Any]] = []
        for spec in specs:
            product_intent.append(
                {
                    "segment_label": spec.get("label"),
                    "audience": spec.get("audience"),
                    "product_title": spec.get("product_title"),
                    "product_gid": spec.get("product_gid"),
                    "has_hero_planned": bool(spec.get("product_image_url")),
                }
            )
        if not product_intent:
            product_intent = [
                {
                    "segment_label": "Default audience",
                    "audience": campaign_state.audience,
                    "product_title": None,
                    "product_gid": None,
                    "has_hero_planned": False,
                }
            ]
        # Theme shown to the user: the model writes `theme_note` in the campaign
        # language; the raw image_prompt is an internal English artifact and only
        # acceptable as a fallback when the campaign itself is in English.
        theme = _short(str(copy.get("theme_note") or ""), 280)
        if not theme:
            if lang == "en":
                theme = _short(getattr(concept, "image_prompt", "") or getattr(concept, "hierarchy_notes", ""), 280)
            else:
                theme = i18n_t(lang, "plan.theme_fallback", goal=_short(campaign_state.goal, 160))
        source_refs = list(getattr(concept, "source_refs", None) or [])
        selected_ref = next((r for r in source_refs if r.get("selected")), None)
        layout_note = (
            i18n_t(lang, "plan.layout_kg", title=str(selected_ref.get("title") or "").split(" — ")[0].strip())
            if selected_ref
            else _short(getattr(concept, "layout", ""), 160)
        )
        return {
            "revision_id": revision_id,
            "generation_run_id": run_id,
            "status": "plan",
            "theme": theme,
            "typography": {
                "display": fonts.get("display"),
                "body": fonts.get("body"),
                "rationale": fonts.get("rationale") or "",
            },
            "color_guidance": {
                "background_name": (background or {}).get("name"),
                "background_description": (background or {}).get("description"),
                "palette_usage": dict(getattr(concept, "palette_usage", None) or {}),
                "text_ink": art_direction.get("ink") or _bg_text_ink(background),
            },
            "product_intent": product_intent,
            "copy_preview": {
                "eyebrow": copy.get("eyebrow"),
                "headline": copy.get("headline"),
                "subheadline": copy.get("subheadline"),
                "cta": copy.get("cta"),
            },
            "layout_note": layout_note,
            "hierarchy_notes": _short(getattr(concept, "hierarchy_notes", ""), 400),
            "wireframe": self._plan_wireframe_spec(concept, background, art_direction),
            "estimated_image_cost_note": i18n_t(lang, "plan.cost_note"),
        }

    async def _style_headline(self, headline: str, brand: Any, *, ink: str | None = None) -> list[dict[str, Any]]:
        """Optionally split a headline into styled runs (emphasize 1-2 key words with
        weight/italic/underline/color/size) to communicate more. Returns [] (plain)
        when Gemini is unavailable or the runs don't faithfully reconstruct the text."""
        text = str(headline or "").strip()
        if not text or not self.settings.has_google_api_key():
            return []
        from app.schemas.typography import HeadlineStyle, coerce_runs

        contrast = (
            "The banner background is BRIGHT, so any color you use MUST be DARK/high-contrast (deep, saturated, "
            "not pastel or bright)."
            if not _is_dark(ink)
            else "The banner background is DARK, so any color you use MUST be LIGHT/high-contrast."
        )
        prompt = (
            "You are a type-savvy art director. Split this banner HEADLINE into runs and emphasize the 1-2 most "
            "important words to communicate more — primarily via bold (b), italic (i), underline (u) and a larger "
            "size (scale up to ~1.6); you MAY also tint a key word with a color, but " + contrast + " "
            "Keep it tasteful (most words plain). "
            "CRITICAL: the run texts concatenated MUST equal the headline EXACTLY — do not add, drop or change words.\n"
            f"HEADLINE: {text}\nReturn JSON {{runs:[{{text,b,i,u,color,scale}}]}}."
        )
        try:
            from app.agents.tools import gemini_text

            result = await gemini_text.generate(prompt, model=gemini_text.FLASH_MODEL, structured=HeadlineStyle)
        except Exception:  # noqa: BLE001 — styling is best-effort
            return []
        return coerce_runs(getattr(result, "runs", []) or [], text, ink=ink)

    async def _propose_art_direction(self, concept: Any, brand: Any, *, lang: str = "es") -> dict[str, Any]:
        """Propose typography + banner composition (positions in %, never px).

        The agent picks a display/body font pairing (NOT locked to brand fonts) and
        places the copy block and hero over a fixed-aspect 1440 banner using percent
        coordinates, so the composition scales across breakpoints. Deterministic
        defaults when Gemini is unavailable.
        """
        from app.schemas.typography import (
            BODY_FONTS,
            DISPLAY_FONTS,
            ArtDirection,
            clamp_layout,
            coerce_pairing,
        )

        default_layout = clamp_layout(ArtDirection(display="Space Grotesk", body="Inter"))
        default = {
            "fonts": {"display": "Space Grotesk", "body": "Inter", "rationale": "", "source": "deterministic"},
            "layout": default_layout,
        }
        if not self.settings.has_google_api_key():
            return default
        copy = getattr(concept, "copy", None) or {}
        headline = copy.get("headline") if isinstance(copy, dict) else ""
        tone = _brand_tone(brand) or ""
        prompt = (
            "You are an art director composing a WIDE ecommerce hero banner (1440px, ~2.4:1). "
            "The background fills the whole banner; a product HERO image (cut-out, transparent) sits on one side "
            "and the COPY block (headline+subhead+CTA) on the other. They may slightly overlap.\n"
            f"Campaign headline: {_short(headline, 90)}. Mood/tone: {_short(tone, 80)}. "
            f"Layout note: {_short(getattr(concept, 'layout', ''), 90)}.\n"
            f"Pick ONE display font (headline) from: {', '.join(DISPLAY_FONTS)}.\n"
            f"Pick ONE body font from: {', '.join(BODY_FONTS)}.\n"
            "Then place the composition with PERCENT values (0-100, never pixels): text_x (copy left edge), "
            "text_y (copy vertical center), text_w (copy width), text_align (left/center/right), and hero_x/hero_y "
            "(hero center) + hero_w (hero width) + hero_h (hero height, may exceed 100 to crop-grow). "
            "Typical: copy on the left (text_x~6, text_w~46) with the hero on the right (hero_x~76). "
            "You MAY be bolder: grow the hero (hero_w up to ~80) and set hero_behind=true so the product sits "
            "BEHIND the copy as a large backdrop element (then keep the copy legible over it) — do this only when it "
            "strengthens the concept, otherwise keep them side by side without bad collision. "
            "Return JSON for all fields with a one-line rationale "
            f"(write the rationale in {i18n_lang_name(lang)} — it is shown to the user)."
        )
        try:
            from app.agents.tools import gemini_text

            result = await gemini_text.generate(prompt, model=gemini_text.FLASH_MODEL, structured=ArtDirection)
        except Exception:  # noqa: BLE001 — art direction is best-effort
            return default
        display, body = coerce_pairing(getattr(result, "display", ""), getattr(result, "body", ""))
        try:
            result.display, result.body = display, body
            layout = clamp_layout(result)
        except Exception:  # noqa: BLE001
            layout = default_layout
        return {
            "fonts": {"display": display, "body": body, "rationale": _short(getattr(result, "rationale", ""), 120), "source": "gemini"},
            "layout": layout,
        }

    async def _refine_background(
        self,
        concept: Any,
        brand: Any,
        *,
        instruction: str = "",
        base_background: dict[str, Any] | None = None,
        lang: str = "es",
    ) -> tuple[dict[str, Any] | None, str]:
        """Generate (or directed-edit, W0.1) a background. Returns (background, source).

        ``source`` is 'gemini' | 'deterministic' | 'none' — callers doing directed
        decor edits must keep the previous background when the LLM didn't run.
        """
        skill = _load_runtime_skill("background-options-generate")
        try:
            options, source = await skill.run(
                concept, brand, count=1, settings=self.settings, cost_guard=self.cost_guard,
                instruction=instruction, base_background=base_background, lang=lang,
            )
        except Exception:  # noqa: BLE001 — background is best-effort in refine
            return None, "none"
        if not options:
            return None, "none"
        top = options[0]
        return {"name": top.name, "description": top.description, "css": top.css, "html": top.html}, source

    async def _resolve_creative_mode(
        self,
        *,
        campaign_id: str,
        campaign_state: StateCampaign,
        brand: Any,
        prev_art: dict[str, Any] | None = None,
        lang: str = "es",
    ) -> dict[str, Any]:
        """C0 — resolve creative_mode/include_humans for this plan."""
        stored = None
        if self.art_directions is not None:
            try:
                stored = self.art_directions.get_by_campaign_id(campaign_id=campaign_id)
            except Exception:  # noqa: BLE001 — mode resolution must never sink a plan
                stored = None
        if stored and str(stored.get("mode_source") or "") == "user":
            return {
                "creative_mode": str(stored.get("creative_mode") or "composite"),
                "include_humans": bool(stored.get("include_humans")),
                "mode_rationale": i18n_t(lang, "mode.user"),
                "mode_source": "user",
            }
        prev = dict(prev_art or {})
        if prev.get("creative_mode"):
            return {
                "creative_mode": str(prev.get("creative_mode")),
                "include_humans": bool(prev.get("include_humans")),
                "mode_rationale": str(prev.get("mode_rationale") or ""),
                "mode_source": str(prev.get("mode_source") or "agent"),
            }
        skill = _load_runtime_skill("creative-mode-recommend")
        rec = await skill.recommend(
            campaign_state, brand, placement=getattr(campaign_state, "placement", "") or "",
            settings=self.settings, cost_guard=self.cost_guard, lang=lang,
        )
        return {
            "creative_mode": rec.creative_mode,
            "include_humans": rec.include_humans,
            "mode_rationale": rec.rationale,
            "mode_source": "agent",
        }

    async def _interpret_refinement(
        self, prompt: str, targets: list[str] | None, prev_concept: dict[str, Any] | None
    ) -> Any:
        """Interpret a refinement prompt into directed ops (refinement-interpret, W0.1)."""
        skill = _load_runtime_skill("refinement-interpret")
        return await skill.interpret(
            prompt, targets=targets, concept=prev_concept, settings=self.settings, cost_guard=self.cost_guard
        )

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
        text_ink: str | None = None,
        compose_report: dict[str, Any] | None = None,
        compose_heroes: bool = True,
    ) -> list[dict[str, Any]]:
        """One banner_variant per personalization variant, each with its own copy.

        W0.2: the base variant features ALL brief products (up to 3) — each gets its
        own chroma-keyed hero cut-out — instead of collapsing to a single product.
        Compose failures are collected into ``compose_report`` (never silent).
        """

        def _warn(product_title: Any, status: str) -> None:
            if compose_report is None:
                return
            if status in ("chroma_failed", "error", "upload_failed", "ref_fetch_failed"):
                compose_report.setdefault("hero_compose_warnings", []).append(
                    {"product": _short(str(product_title or "?"), 60), "status": status}
                )

        specs = self._variant_specs(campaign_row, campaign_state)
        concept_skill = _load_runtime_skill("banner-concept-draft")
        base_copy = concept.copy or {}
        cta_url = self._destination_url(campaign_row)
        brief_products = [p for p in _brief_product_items(campaign_row) if p.get("image_url")][:3]
        rows: list[dict[str, Any]] = []
        for index, spec in enumerate(specs):
            # Each variant features its own product (when chosen): ground the copy on a
            # catalog context filtered to that product, so men→Mandarin Sky, women→My Way.
            variant_catalog = _variant_catalog_context(catalog_context, spec)
            has_own_product = bool(spec.get("product_gid") or spec.get("product_title"))
            featured_products: list[dict[str, Any]] = []
            # Compose a campaign-styled, background-removed hero from the variant's
            # real product photo (transparent PNG). None → Canvas uses the raw photo.
            if compose_heroes and has_own_product and spec.get("product_image_url"):
                hero_url, hero_status = await self._compose_variant_hero(
                    spec=spec, concept=concept, campaign_id=campaign_row["id"], revision_id=revision_id,
                    campaign_state=campaign_state, brand=brand,
                )
                if hero_url:
                    spec = {**spec, "product_hero_url": hero_url}
                _warn(spec.get("product_title"), hero_status)
            elif compose_heroes and index == 0 and brief_products:
                # Base variant + multi-product brief: one cut-out PER brief product.
                for p_index, product in enumerate(brief_products):
                    pspec = {
                        "key": f"{spec['key']}-p{p_index + 1}",
                        "product_title": product.get("title"),
                        "product_image_url": product.get("image_url"),
                        "product_gid": product.get("shopify_product_gid"),
                    }
                    hero_url, hero_status = await self._compose_variant_hero(
                        spec=pspec, concept=concept, campaign_id=campaign_row["id"], revision_id=revision_id,
                        campaign_state=campaign_state, brand=brand,
                    )
                    if hero_url:
                        pspec["product_hero_url"] = hero_url
                    _warn(pspec.get("product_title"), hero_status)
                    ref = _variant_product_ref(pspec)
                    ref["hero_status"] = hero_status
                    featured_products.append(ref)
                if featured_products:
                    spec = {
                        **spec,
                        "product_title": featured_products[0].get("product_title"),
                        "product_image_url": featured_products[0].get("product_image_url"),
                        **({"product_hero_url": featured_products[0]["product_hero_url"]}
                           if featured_products[0].get("product_hero_url") else {}),
                    }
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
            final_headline = copy.get("headline") or campaign_state.goal
            headline_runs = await self._style_headline(final_headline, brand, ink=text_ink)
            rows.append(
                {
                    "revision_id": revision_id,
                    "segment_key": spec["key"],
                    "segment_label": spec["label"],
                    "customer_tag": spec.get("customer_tag"),
                    "audience_rule": {
                        "audience": spec["audience"],
                        "tag": spec.get("customer_tag"),
                        **({"featured_product": _variant_product_ref(spec)} if (has_own_product or featured_products) else {}),
                        **({"featured_products": featured_products} if featured_products else {}),
                        **({"headline_runs": headline_runs} if headline_runs else {}),
                    },
                    "eyebrow": copy.get("eyebrow") or spec["label"],
                    "headline": final_headline,
                    "subheadline": copy.get("subheadline"),
                    "cta_text": copy.get("cta") or campaign_state.cta,
                    "cta_url": cta_url,
                    "palette": dict(concept.palette_usage or {}),
                }
            )
        return self.variants.create_many(variants=_json_safe(rows))

    def _liquid_config(self, concept: Any, liquid_section: str, placement: str, *, image_url: str | None = None, cta_url: str | None = None, brand: Any = None) -> dict[str, Any]:
        copy = concept.copy if hasattr(concept.copy, "get") else {}
        # Resolve brand palette tokens → hex so Shopify inline styles match the preview.
        _hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
        palette: dict[str, str] = {}
        if brand is not None:
            brand_data: dict[str, Any] = (
                brand if isinstance(brand, dict)
                else (brand.model_dump() if hasattr(brand, "model_dump") else (brand.dict() if hasattr(brand, "dict") else {}))
            )
            for color in brand_data.get("palette") or []:
                c: dict[str, Any] = color if isinstance(color, dict) else (color.model_dump() if hasattr(color, "model_dump") else {})
                name = str(c.get("name") or "").strip()
                hex_val = str(c.get("hex") or "").strip()
                if name and _hex_re.match(hex_val):
                    palette[name] = hex_val.upper()
        pu = concept.palette_usage or {}

        def _resolve(key: str, fallback: str) -> str:
            token = str(pu.get(key) or "")
            val = palette.get(token, token)
            return val if _hex_re.match(val) else fallback

        return {
            "section": liquid_section,
            "placement": placement,
            "layout": _short(concept.layout, 120),
            "headline": _short(copy.get("headline") or "", 200),
            "subheadline": _short(copy.get("subheadline") or "", 300),
            "eyebrow": _short(copy.get("eyebrow") or "", 100),
            "cta_text": _short(copy.get("cta") or "", 80),
            "cta_url": cta_url or "/collections/all",
            "image_url": image_url or "",
            "alt_text": _short(copy.get("headline") or "", 120),
            "palette_bg": _resolve("background", "#F4F1EA"),
            "palette_text": _resolve("text", "#111827"),
            "palette_cta_bg": _resolve("cta_background", "#2563EB"),
            "palette_cta_text": _resolve("cta_text", "#FFFFFF"),
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
    """Builds ordered generation_events with REAL wall-clock timestamps/durations.

    ``created_at`` is the actual time the event happened (nudged forward by 1µs
    when two events land in the same microsecond, so ordering stays strict) and
    ``duration_ms`` is measured from the node's matching start() — the 0/1 ms
    placeholders the timeline used to show were synthetic.
    """

    def __init__(self, *, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[dict[str, Any]] = []
        self._last_ts = datetime.now(timezone.utc)
        self._node_started: dict[str, float] = {}
        self.last_frontend_step: str | None = None

    def _next_ts(self) -> str:
        now = datetime.now(timezone.utc)
        if now <= self._last_ts:
            now = self._last_ts + timedelta(microseconds=1)
        self._last_ts = now
        return now.isoformat()

    def _elapsed_ms(self, node_key: str) -> int:
        started = self._node_started.pop(node_key, None)
        if started is None:
            return 0
        return max(0, int((time.monotonic() - started) * 1000))

    def start(self, node_key: str) -> None:
        step = frontend_step_for_node(node_key)
        self.last_frontend_step = step
        self._node_started[node_key] = time.monotonic()
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
                "duration_ms": self._elapsed_ms(node_key),
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
                "duration_ms": self._elapsed_ms(node_key),
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


def _coerce_price(value: Any) -> float | None:
    """Best-effort numeric price from a brief product (e.g. "1,299.00" or "$12.99")."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = re.search(r"\d+(?:[.,]\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


_CHROMA_RETRY_PREFIX = (
    "STRICT RETRY — your previous output violated the background rule. The background MUST be "
    "100% flat, solid, pure chroma green #00FF00 covering the ENTIRE frame edge-to-edge with "
    "NOTHING else: no scene, no gradient, no floor, no environment, no shadows cast on surfaces. "
    "Render ONLY the cut-out subject and floating props over flat #00FF00. "
)


def _kg_sources_payload(docs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Compact KG citations for a generation event (F4 explicability)."""
    out: list[dict[str, Any]] = []
    for doc in (docs or [])[:5]:
        title = str(doc.get("title") or "").strip()
        if not title:
            continue
        out.append(
            {
                "id": str(doc.get("id")) if doc.get("id") else None,
                "kind": str(doc.get("kind") or "kg_doc"),
                "title": title,
                "score": doc.get("score") if isinstance(doc.get("score"), (int, float)) else None,
            }
        )
    return out


def _brief_product_items(campaign_row: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Catalog-shaped items from the campaign-level ``products`` picked in the brief."""
    if not campaign_row:
        return []
    structured = campaign_row.get("structured_brief") or {}
    if not isinstance(structured, dict):
        structured = dict(getattr(structured, "model_dump", lambda: {})() or {})
    out: list[dict[str, Any]] = []
    for product in structured.get("products") or []:
        if not isinstance(product, dict):
            continue
        title = str(product.get("product_title") or "").strip()
        gid = product.get("product_gid")
        if not title and not gid:
            continue
        item: dict[str, Any] = {
            "title": title or "Featured product",
            "shopify_product_gid": gid,
            "image_url": product.get("product_image_url"),
            "from_brief": True,
        }
        price = _coerce_price(product.get("price"))
        if price is not None:
            item["price"] = price
        out.append(item)
    return out


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


def _hex_luminance(hexstr: str) -> float | None:
    c = (hexstr or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) < 6:
        return None
    try:
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _inverted_or_contrast_ink(current_ink: str | None, background: dict[str, Any] | None) -> str:
    """Grounded auto-ink for a contrast complaint (W0.1).

    The user said the CURRENT ink doesn't read — so flip it (dark↔light) when we
    know it; otherwise fall back to contrast-from-background.
    """
    lum = _hex_luminance(current_ink or "")
    if lum is not None:
        return "#FFFFFF" if lum < 0.5 else "#111111"
    return _bg_text_ink(background) or "#111111"


def _bg_text_ink(background: dict[str, Any] | None) -> str | None:
    """Pick a copy color that CONTRASTS with the background, derived from the bg's
    base color luminance (not a nested `color:` which may be a white panel/CTA). Dark
    ink on a light/bright background, light ink on a dark one — so the headline is
    always legible regardless of what color the LLM put first in the CSS."""
    css = (background or {}).get("css") or ""
    # Prefer an explicit background-color; else the first hex in a background declaration.
    m = re.search(r"background(?:-color)?\s*:\s*[^;]*?(#[0-9a-fA-F]{3,8})", css)
    base = m.group(1) if m else None
    lum = _hex_luminance(base) if base else None
    if lum is None:
        # No parseable base color → assume a bright/summer surface, use dark ink.
        return "#111111"
    return "#111111" if lum >= 0.5 else "#FFFFFF"


def _is_dark(color: str | None) -> bool:
    """True if a hex color is dark (low luminance). Defaults to True (assume dark ink)."""
    c = (color or "#111111").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) < 6:
        return True
    try:
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return True
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 0.5


def _short(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]
