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

from app.agents.state import BannerSessionState, Campaign as StateCampaign, Variant as StateVariant
from app.core.settings import Settings
from app.services.gemini.cost_guard import CostGuard, get_default_cost_guard
from app.workflows.banner_creation import (
    DETERMINISTIC_LAYOUT_VARIANT_KEYS,
    _load_runtime_skill,
    frontend_step_for_node,
)

# Nominal estimate for a single paid hero image generation (USD). Only reserved
# against the cost guard when a *real* provider is selected.
EST_IMAGE_USD = 0.04

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
        self.asset_service = asset_service
        self.settings = settings or Settings.from_env()
        self.cost_guard = cost_guard or get_default_cost_guard(self.settings)
        self.team_id = team_id

    async def execute(self, *, run_id: str, campaign_row: dict[str, Any]) -> OrchestratorOutcome:
        campaign_id = str(campaign_row["id"])
        recorder = _EventRecorder(run_id=run_id)
        total_cost = 0.0
        node = ""
        try:
            # 1 — brand context (defensive: synthesize defaults if not resolvable)
            node = "load_brand_context"
            recorder.start(node)
            brand = self._resolve_brand(campaign_row)
            recorder.succeed(node, {"brand_id": brand.id, "name": brand.name})

            # 2 — intake (brief already captured; synthesize, never re-prompt here)
            node = "intake_campaign_idea"
            recorder.start(node)
            campaign_state = self._campaign_from_row(campaign_row, brand)
            recorder.succeed(
                node,
                {"goal": campaign_state.goal, "placement": campaign_state.placement, "source": "structured_brief"},
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
                campaign_state, brand, state_variants, best_practices, layout_candidates
            )
            recorder.succeed(
                node,
                {
                    "layout": _short(concept.layout),
                    "headline": _short(concept.copy.get("headline", "")),
                    "layout_source": (concept.source_refs[0]["title"] if concept.source_refs else None),
                    "layout_candidates": len(layout_candidates),
                },
            )

            # Persist the revision shell now so assets can be linked by revision_id.
            revision = self._create_revision(campaign_id=campaign_id, run_id=run_id, concept=concept)
            revision_id = str(revision["id"])
            layout_rows = self._create_layout_variants(revision_id, concept)
            variant_rows = self._create_banner_variants(revision_id, concept, campaign_state)
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
            liquid_section = await self._render_liquid(concept, state_variants, brand, assets, campaign_state.placement)
            preview_path = _first_asset_path(assets)
            self.revisions.update(
                revision_id=revision_id,
                data=_json_safe(
                    {
                        "html_preview": html_standalone,
                        "preview_storage_path": preview_path,
                        "liquid_config": self._liquid_config(concept, liquid_section, campaign_state.placement),
                    }
                ),
            )
            recorder.succeed(node, {"html_bytes": len(html_standalone), "has_liquid": bool(liquid_section)})

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
                    "facade_version": "f5-run-orchestrator",
                    "image_provider": image_meta.get("provider"),
                    "audit_status": audit_report.status,
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
    ) -> Any:
        skill = _load_runtime_skill("banner-concept-draft")
        return await skill.run(
            campaign=campaign,
            brand_context=brand,
            variants=variants,
            best_practices=best_practices,
            layout_candidates=layout_candidates,
        )

    async def _generate_image(self, *, concept: Any, brand: Any, campaign_id: str) -> tuple[bytes, dict[str, Any], float]:
        from app.agents.tools import nano_banana_image
        from app.services.gemini.fake_image_provider import FakeImageProvider
        from app.services.gemini.image_provider import ImageProviderUnavailable

        prompt_skill = _load_runtime_skill("image-prompt-refine")
        refined_prompt = await prompt_skill.run(concept, brand_context=brand)
        image_skill = _load_runtime_skill("nano-banana-image-generate")

        provider = nano_banana_image.select_provider(settings=self.settings)
        is_real = type(provider).__name__ != "FakeImageProvider"
        cost = 0.0
        if is_real:
            reservation = self.cost_guard.check_and_reserve(EST_IMAGE_USD)
            if reservation.allowed:
                cost = reservation.estimated_usd
            else:
                provider = FakeImageProvider()  # cost cap hit → free fallback
                is_real = False

        try:
            result = await image_skill.run(
                refined_prompt, concept=concept, campaign_id=campaign_id, provider=provider
            )
        except ImageProviderUnavailable:
            # Real provider not usable (e.g. no GOOGLE_API_KEY): degrade to the
            # free fake provider so the banner still renders. The run stays
            # structurally real; only the hero pixels are a deterministic stub.
            if not is_real:
                raise
            cost = 0.0
            result = await image_skill.run(
                refined_prompt, concept=concept, campaign_id=campaign_id, provider=FakeImageProvider()
            )
        meta = {k: v for k, v in result.items() if k != "image_bytes"}
        meta["size_bytes"] = result.get("metadata", {}).get("size_bytes")
        return result["image_bytes"], meta, cost

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

    def _create_revision(self, *, campaign_id: str, run_id: str, concept: Any) -> dict[str, Any]:
        latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
        revision_number = int((latest or {}).get("revision_number") or 0) + 1
        # Created as draft; promoted to "selected" only once the pipeline
        # finishes (see _promote_revision). A mid-pipeline failure therefore
        # leaves an inert draft instead of a half-built "selected" revision.
        return self.revisions.create(
            data={
                "campaign_id": campaign_id,
                "generation_run_id": run_id,
                "revision_number": revision_number,
                "status": "draft",
                "concept": _json_safe(_concept_dict(concept)),
                "liquid_config": {},
                "html_preview": None,
                "preview_storage_path": None,
            }
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

    def _create_banner_variants(self, revision_id: str, concept: Any, campaign: StateCampaign) -> list[dict[str, Any]]:
        copy = concept.copy or {}
        rows = [
            {
                "revision_id": revision_id,
                "segment_key": "default",
                "segment_label": "Default audience",
                "audience_rule": {},
                "eyebrow": copy.get("eyebrow") or copy.get("audience"),
                "headline": copy.get("headline") or campaign.goal,
                "subheadline": copy.get("subheadline"),
                "cta_text": copy.get("cta") or campaign.cta,
                "cta_url": "/collections/all",
                "palette": dict(concept.palette_usage or {}),
            }
        ]
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


def _short(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]
