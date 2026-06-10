from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Protocol, cast
from uuid import uuid4

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.banner_layout_variants import BannerLayoutVariantRepository
from app.db.repositories.banner_variants import BannerVariantRepository
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.db.repositories.generation_runs import GenerationRunRepository
from app.db.repositories.refinement_requests import RefinementRequestRepository
from app.schemas.generation import (
    ApplyEditsRequest,
    CampaignPlanResponse,
    CampaignRevisionResponse,
    GenerationRunResponse,
    RegenerateRequest,
    RegenerateResponse,
    StructuredEdit,
    VariantSelectionResponse,
)
from app.schemas.typography import ArtDirection, clamp_layout, coerce_pairing, coerce_runs
from app.services.banners.generation_run_service import GenerationRunService
from app.services.supabase.client import SupabaseClientFactory

import re as _re

_HEX_RE = _re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _valid_hex(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if _HEX_RE.match(text) else None


def _clamp_layout_dict(layout: dict[str, Any]) -> dict[str, Any]:
    """Project a (possibly partial) camelCase layout patch onto safe ranges."""
    ad = ArtDirection(
        display="Space Grotesk",
        body="Inter",
        text_x=layout.get("textX", 6),
        text_y=layout.get("textY", 50),
        text_w=layout.get("textW", 48),
        text_align=layout.get("textAlign", "left"),
        hero_x=layout.get("heroX", 74),
        hero_y=layout.get("heroY", 50),
        hero_w=layout.get("heroW", 46),
        hero_h=layout.get("heroH", 80),
        hero_behind=bool(layout.get("heroBehind", False)),
    )
    return clamp_layout(ad)


# Copy sections that accept per-section ink / type-scale edits (W0.3).
_TEXT_SECTIONS = ("headline", "subheadline", "eyebrow", "cta")
_TYPE_SCALE_MIN, _TYPE_SCALE_MAX = 0.5, 2.5


def _apply_structured_edits(concept: dict[str, Any], edit: StructuredEdit) -> dict[str, Any]:
    """Pure, server-clamped patch of a revision concept — NO agent, NO Gemini.

    Layout → clamp_layout; fonts → allow-list; ink → hex (global or per-section);
    type_scale → clamped multiplier per section; copy → verbatim text.
    Only present keys are patched (true structured patch, not a full replace).
    """
    out = dict(concept or {})
    art = dict(out.get("art_direction") or {})
    if edit.layout is not None:
        merged = {**(art.get("layout") or {}), **edit.layout.model_dump(exclude_none=True)}
        art["layout"] = _clamp_layout_dict(merged)
    if edit.fonts is not None:
        cur = dict(art.get("fonts") or {})
        display, body = coerce_pairing(edit.fonts.display or cur.get("display") or "", edit.fonts.body or cur.get("body") or "")
        art["fonts"] = {**cur, "display": display, "body": body, "source": "manual-edit"}
    if edit.ink is not None:
        if isinstance(edit.ink, dict):
            sections = dict(art.get("ink_sections") or {})
            for key, value in edit.ink.items():
                hexv = _valid_hex(value)
                if key in _TEXT_SECTIONS and hexv:
                    sections[key] = hexv
            if sections:
                art["ink_sections"] = sections
        else:
            ink = _valid_hex(edit.ink)
            if ink:
                art["ink"] = ink
                # A global ink resets stale per-section overrides.
                art.pop("ink_sections", None)
    if edit.type_scale is not None:
        scales = dict(art.get("type_scale") or {})
        for key, value in edit.type_scale.items():
            if key not in _TEXT_SECTIONS:
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            scales[key] = round(min(_TYPE_SCALE_MAX, max(_TYPE_SCALE_MIN, num)), 2)
        if scales:
            art["type_scale"] = scales
    if art:
        out["art_direction"] = art
    if edit.copy is not None:
        cur_copy = dict(out.get("copy") or {})
        for key in ("headline", "subheadline", "eyebrow", "cta"):
            value = getattr(edit.copy, key)
            if value is not None:
                cur_copy[key] = value
        out["copy"] = cur_copy
    return out


class RevisionServiceError(Exception):
    pass


class CampaignNotFound(RevisionServiceError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class RevisionNotFound(RevisionServiceError):
    def __init__(self, revision_id: str) -> None:
        super().__init__(f"revision '{revision_id}' not found")
        self.revision_id = revision_id


class VariantNotFound(RevisionServiceError):
    def __init__(self, variant_id: str) -> None:
        super().__init__(f"variant '{variant_id}' not found")
        self.variant_id = variant_id


class RefinementRequestNotFound(RevisionServiceError):
    def __init__(self, refinement_request_id: str) -> None:
        super().__init__(f"refinement request '{refinement_request_id}' not found")
        self.refinement_request_id = refinement_request_id


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...
    def update(self, *, campaign_id: str, data: dict[str, Any], team_id: str | None = None) -> dict[str, Any] | None: ...


class RevisionRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, *, revision_id: str) -> dict[str, Any] | None: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...
    def list_by_campaign_id(self, *, campaign_id: str) -> list[dict[str, Any]]: ...
    def update(self, *, revision_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class VariantRepositoryProtocol(Protocol):
    def create_many(self, *, variants: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def get(self, *, variant_id: str) -> dict[str, Any] | None: ...
    def list_by_revision_id(self, *, revision_id: str) -> list[dict[str, Any]]: ...


class LayoutVariantRepositoryProtocol(Protocol):
    def create_many(self, *, variants: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def list_by_revision_id(self, *, revision_id: str) -> list[dict[str, Any]]: ...


class RefinementRequestRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, *, refinement_request_id: str) -> dict[str, Any] | None: ...
    def update(self, *, refinement_request_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class RevisionService:
    def __init__(
        self,
        *,
        campaigns: CampaignRepositoryProtocol,
        revisions: RevisionRepositoryProtocol,
        variants: VariantRepositoryProtocol,
        layout_variants: LayoutVariantRepositoryProtocol,
        refinement_requests: RefinementRequestRepositoryProtocol,
        generation_runs: GenerationRunService,
        team_id: str | None = None,
    ) -> None:
        self.campaigns = campaigns
        self.revisions = revisions
        self.variants = variants
        self.layout_variants = layout_variants
        self.refinement_requests = refinement_requests
        self.generation_runs = generation_runs
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "RevisionService":
        return cls(
            campaigns=CampaignRepository(client),
            revisions=CampaignRevisionRepository(client),
            variants=BannerVariantRepository(client),
            layout_variants=BannerLayoutVariantRepository(client),
            refinement_requests=RefinementRequestRepository(client),
            generation_runs=GenerationRunService.from_supabase_client(client, team_id=team_id),
            team_id=team_id,
        )

    def list_revisions(self, campaign_id: str) -> list[CampaignRevisionResponse]:
        self._get_campaign(campaign_id)
        return [self._revision_response(row) for row in self.revisions.list_by_campaign_id(campaign_id=campaign_id)]

    def select_variant(self, campaign_id: str, variant_id: str) -> VariantSelectionResponse:
        campaign = self._get_campaign(campaign_id)
        variant = self.variants.get(variant_id=variant_id)
        if variant is None:
            raise VariantNotFound(variant_id)
        revision = self.revisions.get(revision_id=str(variant["revision_id"]))
        if revision is None or str(revision.get("campaign_id")) != campaign_id:
            raise VariantNotFound(variant_id)

        previous_revision_id = campaign.get("selected_revision_id")
        if previous_revision_id and str(previous_revision_id) != str(revision["id"]):
            previous = self.revisions.get(revision_id=str(previous_revision_id))
            if previous and previous.get("status") == "selected":
                self.revisions.update(revision_id=str(previous_revision_id), data={"status": "superseded"})

        updated_revision = self.revisions.update(revision_id=str(revision["id"]), data={"status": "selected"}) or revision
        updated_campaign = self.campaigns.update(
            campaign_id=campaign_id,
            team_id=self.team_id,
            data={"selected_revision_id": str(revision["id"]), "status": "draft"},
        ) or {**campaign, "selected_revision_id": str(revision["id"]), "status": "draft"}
        return VariantSelectionResponse(
            campaign_id=campaign_id,
            selected_revision_id=str(updated_revision["id"]),
            selected_variant_id=variant_id,
            campaign_status=str(updated_campaign.get("status") or "draft"),
            revision=self._revision_response(updated_revision),
        )

    # --- Iterative campaign plan (gate before the costly build) ---------------

    def start_plan_run(self, campaign_id: str, request: RegenerateRequest | None = None) -> GenerationRunResponse:
        """Kick off the cheap PLAN phase (concept + wireframe, no image)."""
        self._get_campaign(campaign_id)
        request = request or RegenerateRequest()
        if getattr(self.generation_runs, "orchestrator", None) is None:
            raise MissingSettingsError(("orchestrator",))
        run, _revision_id = self.generation_runs.start_plan_run(campaign_id, started_by=request.requested_by)
        return run

    def get_plan(self, campaign_id: str) -> CampaignPlanResponse:
        """Return the latest pending plan (status='plan') for the campaign."""
        self._get_campaign(campaign_id)
        revision = self._latest_plan_revision(campaign_id)
        if revision is None:
            raise RevisionNotFound("plan")
        return self._plan_response(revision)

    def iterate_plan(self, campaign_id: str, request: RegenerateRequest) -> GenerationRunResponse:
        """Re-draft the plan with the user's feedback. Never re-runs image work."""
        self._get_campaign(campaign_id)
        if getattr(self.generation_runs, "orchestrator", None) is None:
            raise MissingSettingsError(("orchestrator",))
        prompt = _normalize_prompt(request.prompt or "Refina el plan")
        # W0.1 — only EXPLICIT targets (a scoped UI control) are routed here; a
        # free-text prompt is interpreted inside the plan phase (refinement-interpret)
        # grounded in the previous concept, so "la fuente no contrasta" lands on the
        # ink — not on a background regen.
        targets: list[str] | None = None
        if request.target_nodes:
            from app.workflows.banner_creation import _load_runtime_skill

            normalize_targets = _load_runtime_skill("refinement-route").normalize_targets
            # Plan iteration must NEVER touch image generation — strip it from targets.
            targets = [t for t in normalize_targets(request.target_nodes, prompt) if t != "image"] or None
        run, _revision_id = self.generation_runs.start_plan_run(
            campaign_id, prompt=prompt, targets=targets, started_by=request.requested_by
        )
        return run

    def approve_plan(self, campaign_id: str, request: RegenerateRequest | None = None) -> RegenerateResponse:
        """Approve the latest plan and run the costly BUILD phase. Idempotent: a
        second approve finds no pending plan (it was flipped to selected) and 404s."""
        self._get_campaign(campaign_id)
        request = request or RegenerateRequest()
        if getattr(self.generation_runs, "orchestrator", None) is None:
            raise MissingSettingsError(("orchestrator",))
        plan_revision = self._latest_plan_revision(campaign_id)
        if plan_revision is None:
            raise RevisionNotFound("plan")
        run, revision_id = self.generation_runs.start_build_run(
            campaign_id,
            plan_revision=plan_revision,
            started_by=request.requested_by,
            parent_run_id=plan_revision.get("generation_run_id"),
        )
        revision = self.revisions.get(revision_id=str(revision_id)) if revision_id else None
        if revision is None:
            revision = self.revisions.get(revision_id=str(plan_revision["id"])) or plan_revision
        return RegenerateResponse(generation_run=run, revision=self._revision_response(revision))

    def _latest_plan_revision(self, campaign_id: str) -> dict[str, Any] | None:
        rows = [r for r in self.revisions.list_by_campaign_id(campaign_id=campaign_id) if str(r.get("status")) == "plan"]
        if not rows:
            return None
        return max(rows, key=lambda r: int(r.get("revision_number") or 0))

    def _plan_response(self, revision: dict[str, Any]) -> CampaignPlanResponse:
        concept = dict(revision.get("concept") or {})
        plan = dict(concept.get("plan") or {})
        return CampaignPlanResponse(
            revision_id=str(revision["id"]),
            campaign_id=str(revision["campaign_id"]),
            generation_run_id=str(revision["generation_run_id"]) if revision.get("generation_run_id") else None,
            status=str(revision.get("status") or "plan"),
            theme=str(plan.get("theme") or ""),
            typography=dict(plan.get("typography") or {}),
            color_guidance=dict(plan.get("color_guidance") or {}),
            product_intent=list(plan.get("product_intent") or []),
            copy_preview=dict(plan.get("copy_preview") or {}),
            layout_note=str(plan.get("layout_note") or ""),
            hierarchy_notes=str(plan.get("hierarchy_notes") or ""),
            wireframe=dict(plan.get("wireframe") or {}),
            decision_trace=dict(plan.get("decision_trace") or {}),
            creative_mode=str(plan.get("creative_mode") or "composite"),
            include_humans=bool(plan.get("include_humans")),
            mode_rationale=str(plan.get("mode_rationale") or ""),
            mode_source=str(plan.get("mode_source") or "agent"),
            estimated_image_cost_note=str(plan.get("estimated_image_cost_note") or ""),
        )

    def regenerate(self, campaign_id: str, request: RegenerateRequest) -> RegenerateResponse:
        campaign = self._get_campaign(campaign_id)
        refinement = None
        if request.refinement_request_id:
            refinement = self.refinement_requests.get(refinement_request_id=request.refinement_request_id)
            if refinement is None or str(refinement.get("campaign_id")) != campaign_id:
                raise RefinementRequestNotFound(request.refinement_request_id)

        prompt = _normalize_prompt(request.prompt or (refinement or {}).get("prompt") or "Refine banner")
        source_revision_id = request.source_revision_id or (refinement or {}).get("source_revision_id") or campaign.get("selected_revision_id")
        source_revision = self._source_revision(campaign_id=campaign_id, source_revision_id=source_revision_id)

        # F9 — agentic refine: when an orchestrator is wired, re-run the relevant
        # pipeline nodes to produce a genuinely new revision with real artifacts.
        # Otherwise (tests / in-memory) keep the deterministic copy bookkeeping.
        if getattr(self.generation_runs, "orchestrator", None) is not None:
            return self._agentic_regenerate(
                campaign_id=campaign_id, request=request, prompt=prompt, source_revision=source_revision, refinement=refinement
            )

        parent_run_id = source_revision.get("generation_run_id")
        run = self.generation_runs.start_generation_run(
            campaign_id,
            request=_run_request(parent_run_id=parent_run_id, started_by=request.requested_by, prompt=prompt),
        )
        revision = self._create_revised_revision(campaign_id=campaign_id, source_revision=source_revision, run=run, prompt=prompt)
        previous_revision_id = campaign.get("selected_revision_id")
        if previous_revision_id and str(previous_revision_id) != str(revision["id"]):
            previous = self.revisions.get(revision_id=str(previous_revision_id))
            if previous and previous.get("status") == "selected":
                self.revisions.update(revision_id=str(previous_revision_id), data={"status": "superseded"})
        self.campaigns.update(
            campaign_id=campaign_id,
            team_id=self.team_id,
            data={"selected_revision_id": str(revision["id"]), "status": "draft"},
        )
        if refinement is not None:
            self.refinement_requests.update(
                refinement_request_id=str(refinement["id"]),
                data={
                    "status": "succeeded",
                    "result_revision_id": str(revision["id"]),
                    "result_summary": f"Created revision {revision['revision_number']} from requested changes.",
                    "finished_at": _utc_now_iso(),
                },
            )
        return RegenerateResponse(
            generation_run=run,
            revision=self._revision_response(revision),
            refinement_request_id=str(refinement["id"]) if refinement else None,
        )

    def edit(self, campaign_id: str, request: RegenerateRequest) -> RegenerateResponse:
        """Banner-edit: scoped, non-destructive edit of an assembled revision (F-edit)."""
        campaign = self._get_campaign(campaign_id)
        refinement = None
        if request.refinement_request_id:
            refinement = self.refinement_requests.get(refinement_request_id=request.refinement_request_id)
            if refinement is None or str(refinement.get("campaign_id")) != campaign_id:
                raise RefinementRequestNotFound(request.refinement_request_id)
        prompt = _normalize_prompt(request.prompt or (refinement or {}).get("prompt") or "Edit banner")
        source_revision_id = request.source_revision_id or (refinement or {}).get("source_revision_id") or campaign.get("selected_revision_id")
        source_revision = self._source_revision(campaign_id=campaign_id, source_revision_id=source_revision_id)
        if getattr(self.generation_runs, "orchestrator", None) is None:
            # No orchestrator (in-memory/tests) → fall back to the deterministic copy path.
            return self.regenerate(campaign_id, request)

        from app.workflows.banner_creation import _load_runtime_skill

        normalize_targets = _load_runtime_skill("refinement-route").normalize_targets
        targets = normalize_targets(request.target_nodes, prompt)
        refinement_id = str(refinement["id"]) if refinement is not None else None
        def _finalize_refinement(outcome: Any) -> None:
            if refinement_id is None:
                return
            rid = getattr(outcome, "revision_id", None)
            self.refinement_requests.update(
                refinement_request_id=refinement_id,
                data={
                    "status": "succeeded" if getattr(outcome, "status", None) == "succeeded" else "failed",
                    "result_revision_id": str(rid) if rid else None,
                    "result_summary": f"Banner edit ({', '.join(targets)}).",
                    "finished_at": _utc_now_iso(),
                },
            )
        run, revision_id = self.generation_runs.start_banner_edit_run(
            campaign_id, source_revision=source_revision, prompt=prompt, targets=targets,
            started_by=request.requested_by, parent_run_id=source_revision.get("generation_run_id"),
            on_complete=_finalize_refinement if refinement_id else None,
        )
        revision = self.revisions.get(revision_id=str(revision_id)) if revision_id else None
        if revision is None:
            revision = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) or source_revision
        return RegenerateResponse(
            generation_run=run,
            revision=self._revision_response(revision),
            refinement_request_id=str(refinement["id"]) if refinement else None,
        )

    def apply_edits(self, campaign_id: str, request: ApplyEditsRequest) -> RegenerateResponse:
        """Direct, INSTANT edit (move/resize/color/font/copy) — NO agent, NO Gemini.

        Patches the source revision's concept (clamped/coerced for safety) and
        creates a new selected revision with a bookkeeping run, so the canvas history
        stays uniform while guaranteeing no node/model execution.
        """
        campaign = self._get_campaign(campaign_id)
        edit = request.structured_changes
        source_revision = self._source_revision(
            campaign_id=campaign_id,
            source_revision_id=request.source_revision_id or campaign.get("selected_revision_id"),
        )
        patched_concept = _apply_structured_edits(source_revision.get("concept") or {}, edit)
        run = self._direct_edit_run(
            campaign_id, parent_run_id=source_revision.get("generation_run_id"), started_by=request.requested_by
        )
        latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) or source_revision
        revision_number = int(latest.get("revision_number") or 0) + 1
        revision = self.revisions.create(
            data={
                "campaign_id": campaign_id,
                "generation_run_id": run.id,
                "revision_number": revision_number,
                "status": "selected",
                "concept": patched_concept,
                "liquid_config": dict(source_revision.get("liquid_config") or {}),
                "html_preview": source_revision.get("html_preview"),
                "preview_storage_path": source_revision.get("preview_storage_path"),
            }
        )
        if source_revision.get("status") == "selected":
            self.revisions.update(revision_id=str(source_revision["id"]), data={"status": "superseded"})
        self._copy_layout_variants(str(source_revision["id"]), str(revision["id"]), "manual edit")
        self._copy_banner_variants_with_edits(str(source_revision["id"]), str(revision["id"]), edit, patched_concept)
        previous_revision_id = campaign.get("selected_revision_id")
        if previous_revision_id and str(previous_revision_id) not in (str(revision["id"]), str(source_revision["id"])):
            previous = self.revisions.get(revision_id=str(previous_revision_id))
            if previous and previous.get("status") == "selected":
                self.revisions.update(revision_id=str(previous_revision_id), data={"status": "superseded"})
        self.campaigns.update(
            campaign_id=campaign_id,
            team_id=self.team_id,
            data={"selected_revision_id": str(revision["id"]), "status": "draft"},
        )
        return RegenerateResponse(generation_run=run, revision=self._revision_response(revision))

    def _direct_edit_run(self, campaign_id: str, *, parent_run_id: Any, started_by: str | None) -> GenerationRunResponse:
        """A bookkeeping run row for an agent-free direct edit (status succeeded)."""
        row = self.generation_runs.run_repository.create(
            data={
                "campaign_id": campaign_id,
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "run_type": "refinement",
                "status": "succeeded",
                "frontend_step": "review_publish",
                "adk_trace_id": str(uuid4()),
                "started_by": started_by,
                "started_at": _utc_now_iso(),
                "finished_at": _utc_now_iso(),
                "metadata": {"facade_version": "direct-edit", "no_agent": True},
            }
        )
        return GenerationRunService._run_response_from_record(row)

    def _copy_banner_variants_with_edits(
        self, source_revision_id: str, new_revision_id: str, edit: StructuredEdit, patched_concept: dict[str, Any]
    ) -> None:
        rows = self.variants.list_by_revision_id(revision_id=source_revision_id)
        if not rows:
            rows = _default_banner_variants(source_revision_id)
        ink = (patched_concept.get("art_direction") or {}).get("ink")
        copy_edit = edit.copy
        runs_by_id = edit.headline_runs or {}
        copies: list[dict[str, Any]] = []
        for row in rows:
            new = {**_without_identity(row), "revision_id": new_revision_id}
            if copy_edit is not None:
                if copy_edit.headline is not None:
                    new["headline"] = copy_edit.headline
                if copy_edit.subheadline is not None:
                    new["subheadline"] = copy_edit.subheadline
                if copy_edit.eyebrow is not None:
                    new["eyebrow"] = copy_edit.eyebrow
                if copy_edit.cta is not None:
                    new["cta_text"] = copy_edit.cta
            rule = dict(new.get("audience_rule") or {})
            headline = str(new.get("headline") or "")
            explicit = runs_by_id.get(str(row.get("id")))
            if explicit is not None:
                coerced = coerce_runs(explicit, headline, ink=ink)
                if coerced:
                    rule["headline_runs"] = coerced
                else:
                    rule.pop("headline_runs", None)
            elif copy_edit is not None and copy_edit.headline is not None and rule.get("headline_runs"):
                # Headline changed → re-validate stale runs against the new text (clears on mismatch).
                coerced = coerce_runs(rule.get("headline_runs"), headline, ink=ink)
                if coerced:
                    rule["headline_runs"] = coerced
                else:
                    rule.pop("headline_runs", None)
            new["audience_rule"] = rule
            copies.append(new)
        self.variants.create_many(variants=copies)

    def _agentic_regenerate(
        self,
        *,
        campaign_id: str,
        request: RegenerateRequest,
        prompt: str,
        source_revision: dict[str, Any],
        refinement: dict[str, Any] | None,
    ) -> RegenerateResponse:
        from app.workflows.banner_creation import _load_runtime_skill

        normalize_targets = _load_runtime_skill("refinement-route").normalize_targets
        targets = normalize_targets(request.target_nodes, prompt)
        # Finalize the refinement request with the REAL outcome once the (possibly
        # background) run ends — not the synchronous "running" status, which would
        # mislabel a successful background refine as failed.
        refinement_id = str(refinement["id"]) if refinement is not None else None
        def _finalize_refinement(outcome: Any) -> None:
            if refinement_id is None:
                return
            rid = getattr(outcome, "revision_id", None)
            self.refinement_requests.update(
                refinement_request_id=refinement_id,
                data={
                    "status": "succeeded" if getattr(outcome, "status", None) == "succeeded" else "failed",
                    "result_revision_id": str(rid) if rid else None,
                    "result_summary": f"Agentic refine ({', '.join(targets)}).",
                    "finished_at": _utc_now_iso(),
                },
            )
        run, revision_id = self.generation_runs.start_refinement_run(
            campaign_id,
            prompt=prompt,
            targets=targets,
            started_by=request.requested_by,
            parent_run_id=source_revision.get("generation_run_id"),
            on_complete=_finalize_refinement if refinement_id else None,
        )
        # The orchestrator already created/promoted the new revision + pointed the
        # campaign at it. Read it back for the response.
        revision = None
        if revision_id:
            revision = self.revisions.get(revision_id=str(revision_id))
        if revision is None:
            revision = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) or source_revision
        return RegenerateResponse(
            generation_run=run,
            revision=self._revision_response(revision),
            refinement_request_id=str(refinement["id"]) if refinement else None,
        )

    def _create_revised_revision(
        self, *, campaign_id: str, source_revision: dict[str, Any], run: GenerationRunResponse, prompt: str
    ) -> dict[str, Any]:
        latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) or source_revision
        revision_number = int(latest.get("revision_number") or 0) + 1
        concept = dict(source_revision.get("concept") or {})
        concept["revision_note"] = prompt
        concept["revision_source_id"] = str(source_revision["id"])
        liquid_config = dict(source_revision.get("liquid_config") or {})
        liquid_config["revision_note"] = prompt
        html_preview = _append_revision_marker(source_revision.get("html_preview"), revision_number, prompt)
        revision = self.revisions.create(
            data={
                "campaign_id": campaign_id,
                "generation_run_id": run.id,
                "revision_number": revision_number,
                "status": "selected",
                "concept": concept,
                "liquid_config": liquid_config,
                "html_preview": html_preview,
                "preview_storage_path": None,
            }
        )
        if source_revision.get("status") == "selected":
            self.revisions.update(revision_id=str(source_revision["id"]), data={"status": "superseded"})
        self._copy_layout_variants(str(source_revision["id"]), str(revision["id"]), prompt)
        self._copy_banner_variants(str(source_revision["id"]), str(revision["id"]), prompt)
        return revision

    def _copy_layout_variants(self, source_revision_id: str, new_revision_id: str, prompt: str) -> None:
        rows = self.layout_variants.list_by_revision_id(revision_id=source_revision_id)
        if not rows:
            rows = _default_layout_variants(source_revision_id)
        copies = []
        for row in rows:
            config = dict(row.get("config") or {})
            config["revision_note"] = prompt
            copies.append({**_without_identity(row), "revision_id": new_revision_id, "config": config})
        self.layout_variants.create_many(variants=copies)

    def _copy_banner_variants(self, source_revision_id: str, new_revision_id: str, prompt: str) -> None:
        rows = self.variants.list_by_revision_id(revision_id=source_revision_id)
        if not rows:
            rows = _default_banner_variants(source_revision_id)
        copies = []
        for row in rows:
            headline = str(row.get("headline") or row.get("segment_label") or "Banner")
            copies.append({**_without_identity(row), "revision_id": new_revision_id, "headline": f"{headline} — revised"})
        self.variants.create_many(variants=copies)

    def _source_revision(self, *, campaign_id: str, source_revision_id: Any) -> dict[str, Any]:
        if source_revision_id:
            revision = self.revisions.get(revision_id=str(source_revision_id))
            if revision is None or str(revision.get("campaign_id")) != campaign_id:
                raise RevisionNotFound(str(source_revision_id))
            return revision
        latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
        if latest is None:
            raise RevisionNotFound("latest")
        return latest

    def _get_campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _revision_response(self, row: dict[str, Any]) -> CampaignRevisionResponse:
        revision_id = str(row["id"])
        return CampaignRevisionResponse(
            id=revision_id,
            campaign_id=str(row["campaign_id"]),
            generation_run_id=str(row["generation_run_id"]) if row.get("generation_run_id") else None,
            revision_number=int(row.get("revision_number") or 0),
            status=str(row.get("status") or "draft"),
            concept=dict(row.get("concept") or {}),
            liquid_config=dict(row.get("liquid_config") or {}),
            html_preview=cast(str | None, row.get("html_preview")),
            preview_storage_path=cast(str | None, row.get("preview_storage_path")),
            created_at=str(row["created_at"]) if row.get("created_at") is not None else None,
            layout_variants=[cast(Any, item) for item in self.layout_variants.list_by_revision_id(revision_id=revision_id)],
            variants=[cast(Any, item) for item in self.variants.list_by_revision_id(revision_id=revision_id)],
        )


def _configured_service_for_team(team_id_override: str | None = None) -> RevisionService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_TEAM_ID"))
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return RevisionService.from_supabase_client(client, team_id=team_id)


def configured_service() -> RevisionService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> RevisionService:
    return _configured_service_for_team(team_id)


def _run_request(*, parent_run_id: Any, started_by: str | None, prompt: str) -> Any:
    from app.schemas.generation import GenerationRunCreate

    return GenerationRunCreate(
        run_type="refinement",
        parent_run_id=str(parent_run_id) if parent_run_id else None,
        started_by=started_by,
        metadata={"facade_version": "task-16-deterministic-revision", "prompt": prompt},
    )


def _without_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"id", "created_at"}}


def _normalize_prompt(value: Any) -> str:
    prompt = " ".join(str(value or "Refine banner").split())
    return (prompt or "Refine banner")[:8000]


def _append_revision_marker(html_value: Any, revision_number: int, prompt: str) -> str:
    base = str(html_value or "<section class='aijolot-banner'></section>")
    safe_prompt = html.escape(_normalize_prompt(prompt), quote=True).replace("--", "&#45;&#45;")
    return f"{base}\n<!-- revision {revision_number}: {safe_prompt} -->"


def _default_layout_variants(revision_id: str) -> list[dict[str, Any]]:
    from app.workflows.banner_creation import DETERMINISTIC_LAYOUT_VARIANT_KEYS

    return [
        {
            "revision_id": revision_id,
            "key": key,
            "name": f"Hero layout {key}",
            "description": f"Deterministic MVP layout {key}",
            "layout_type": "split" if key == "A" else ("centered" if key == "B" else "media_first"),
            "is_recommended": key == "A",
            "config": {"variant_key": key},
        }
        for key in DETERMINISTIC_LAYOUT_VARIANT_KEYS
    ]


def _default_banner_variants(revision_id: str) -> list[dict[str, Any]]:
    return [
        {
            "revision_id": revision_id,
            "segment_key": "default",
            "segment_label": "Default audience",
            "audience_rule": {},
            "eyebrow": "Limited offer",
            "headline": "Fresh picks for you",
            "subheadline": "Deterministic MVP banner copy",
            "cta_text": "Shop now",
            "cta_url": "/collections/all",
            "palette": {},
        }
    ]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
