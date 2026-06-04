"""Pipeline runner — bridge between FastAPI routes and ADK pipelines.

Wraps the ADK Runner + InMemorySessionService to provide a simple
async interface for starting and resuming banner pipelines.
"""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, AsyncGenerator

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.pipeline import build_post_review_pipeline, build_pre_review_pipeline
from app.agents.state import BannerSessionState
from app.agents.state_bridge import init_pipeline_state
from app.services.gemini.fake_image_provider import FakeImageProvider
from app.workflows.banner_creation import frontend_step_for_node, ordered_node_keys


@dataclass(frozen=True)
class AgenticArtifactBundle:
    agent_mode: str
    concept: dict[str, Any]
    refined_image_prompt: str
    image_asset: dict[str, Any]
    optimized_asset: dict[str, Any]
    html_preview: str
    liquid_payload: dict[str, Any]
    audit_result: dict[str, Any]
    events: list[dict[str, Any]]
    provenance: dict[str, str]


class AgenticGenerationAdapter:
    """Safe boundary for producing generation artifacts from agent skills.

    deterministic_demo executes existing deterministic skill functions directly
    with fake/local providers. adk_pipeline is kept explicit for future work and
    cannot accidentally run external providers from the generation service.
    """

    def __init__(self, *, mode: str = "deterministic_demo") -> None:
        if mode not in {"deterministic_demo", "adk_pipeline"}:
            raise ValueError(f"unsupported agentic generation mode: {mode}")
        self.mode = mode

    async def generate(
        self,
        *,
        campaign: dict[str, Any],
        campaign_id: str,
        run_id: str,
        trace_id: str,
        team_id: str | None = None,
        started_by: str | None = None,
    ) -> AgenticArtifactBundle:
        if self.mode == "adk_pipeline":
            # Preserve the graph topology for future opt-in execution without
            # duplicating it or running it implicitly from the MVP demo path.
            build_pre_review_pipeline()
            raise NotImplementedError("adk_pipeline generation mode is feature-flagged for future integration")
        return await self._generate_deterministic_demo(
            campaign=campaign,
            campaign_id=campaign_id,
            run_id=run_id,
            trace_id=trace_id,
            team_id=team_id,
            started_by=started_by,
        )

    async def _generate_deterministic_demo(
        self,
        *,
        campaign: dict[str, Any],
        campaign_id: str,
        run_id: str,
        trace_id: str,
        team_id: str | None,
        started_by: str | None,
    ) -> AgenticArtifactBundle:
        brand_skill = _load_runtime_skill("brand-context-load")
        personalization_skill = _load_runtime_skill("user-personalization")
        practices_skill = _load_runtime_skill("best-practices-retrieve")
        concept_skill = _load_runtime_skill("banner-concept-draft")
        prompt_skill = _load_runtime_skill("image-prompt-refine")
        image_skill = _load_runtime_skill("nano-banana-image-generate")
        optimize_skill = _load_runtime_skill("image-asset-optimize")
        html_skill = _load_runtime_skill("banner-html-seo-render")
        liquid_skill = _load_runtime_skill("liquid-section-build")
        audit_skill = _load_runtime_skill("performance-audit")

        brand = await brand_skill.run(brand_context=_brand_context_for_campaign(campaign))
        variants = await personalization_skill.run(campaign, customer_tags=_customer_tags_for_campaign(campaign), max_variants=3)
        best_practices = await practices_skill.run(campaign, brand, top_k=5)
        concept = await concept_skill.run(campaign=campaign, brand_context=brand, variants=variants, best_practices=best_practices)
        refined_prompt = await prompt_skill.run(concept, brand_context=brand)

        image = await image_skill.run(
            refined_prompt,
            provider=FakeImageProvider(),
            user_id=started_by,
            team_id=team_id,
            campaign_id=campaign_id,
        )
        assets = await optimize_skill.run(
            image["image_bytes"],
            alt_text_hint=concept.copy.get("headline", "Banner image"),
            mime_type=image.get("mime_type"),
            metadata=image.get("metadata"),
            image_prompt=refined_prompt,
        )
        html_preview = _ensure_aijolot_marker(await html_skill.run(concept, assets, brand=brand))
        liquid_payload = await liquid_skill.run(concept, variants, brand, assets=assets, placement=_placement_for_campaign(campaign))

        audit_state = BannerSessionState(trace_id=trace_id, session_id=run_id, brand_id=brand.id, brand_context=brand, campaign=None, variants=variants, concept=concept, assets=assets)
        audit_report, audit_decision = await audit_skill.run(html_preview, audit_state)

        provenance = {
            "agent_mode": "deterministic_demo",
            "image_provider": str(image.get("provider") or "fake"),
            "kg_provider": "static",
            "audit_provider": "deterministic_local",
            "shopify_provider": "not_called",
        }
        concept_payload = concept.model_dump()
        concept_payload["refined_image_prompt"] = refined_prompt
        concept_payload["best_practices"] = best_practices
        concept_payload["provider_provenance"] = provenance

        return AgenticArtifactBundle(
            agent_mode="deterministic_demo",
            concept=concept_payload,
            refined_image_prompt=refined_prompt,
            image_asset={k: v for k, v in image.items() if k != "image_bytes"},
            optimized_asset=assets.model_dump(),
            html_preview=html_preview,
            liquid_payload={**dict(liquid_payload), "config": {**dict(liquid_payload.get("config") or {}), "safe_to_publish": False}},
            audit_result={**audit_report.model_dump(), "audit_decision": audit_decision, "avif_skipped": True},
            events=_deterministic_agent_events(provenance=provenance, concept=concept_payload),
            provenance=provenance,
        )


@lru_cache(maxsize=16)
def _load_runtime_skill(skill_id: str) -> Any:
    path = Path(__file__).resolve().parent / "skills" / skill_id / "impl.py"
    spec = importlib.util.spec_from_file_location(f"aijolot_agentic_{skill_id.replace('-', '_')}_impl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"runtime skill not found: {skill_id}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise RuntimeError(f"runtime skill has no run() function: {skill_id}")
    return module


def _brand_context_for_campaign(campaign: dict[str, Any]) -> dict[str, Any]:
    brand_context = campaign.get("brand_context")
    if isinstance(brand_context, dict):
        return brand_context
    structured_brief = campaign.get("structured_brief")
    brief: dict[str, Any] = structured_brief if isinstance(structured_brief, dict) else {}
    return {
        "id": str(campaign.get("brand_id") or campaign.get("team_id") or "aijolot_demo"),
        "name": str(campaign.get("brand_name") or "Aijolot Demo Brand"),
        "palette": [{"name": "Ink", "hex": "#111111"}, {"name": "Canvas", "hex": "#FFFFFF"}, {"name": "Aijolot Accent", "hex": "#7C3AED"}],
        "voice": {"tone": [str(brief.get("tone") or "premium")], "prohibited_words": [], "required_phrases": []},
        "image_style_directives": ["clean ecommerce photography", "premium minimal set"],
        "shopify": {"store_domain": "demo.myshopify.com", "default_placement": "hero"},
        "notes": "Deterministic demo brand context; no live brand fetch.",
    }


def _customer_tags_for_campaign(campaign: dict[str, Any]) -> list[str]:
    brief = campaign.get("structured_brief") if isinstance(campaign.get("structured_brief"), dict) else {}
    audience = str(brief.get("audience") or campaign.get("raw_brief") or "")
    tags = ["default"]
    if "vip" in audience.lower():
        tags.append("vip")
    if any(token in audience.lower() for token in ("deal", "sale", "discount", "black friday")):
        tags.append("deal_seeker")
    return tags


def _placement_for_campaign(campaign: dict[str, Any]) -> str:
    brief = campaign.get("structured_brief") if isinstance(campaign.get("structured_brief"), dict) else {}
    return str(brief.get("placement") or "hero")


def _ensure_aijolot_marker(html: str) -> str:
    if "aijolot-banner" in html:
        return html
    return html.replace("</body>", "<!-- aijolot-banner deterministic-agentic-preview --></body>") if "</body>" in html else f"{html}\n<!-- aijolot-banner deterministic-agentic-preview -->"


def _deterministic_agent_events(*, provenance: dict[str, str], concept: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    child_substeps = {
        "draft_banner_concept": ["image-prompt-refine"],
        "render_html": ["liquid-section-build", "render_join"],
    }
    for index, node_key in enumerate(ordered_node_keys()):
        step = frontend_step_for_node(node_key)
        events.append({
            "node_key": node_key,
            "frontend_step": step,
            "status": "started",
            "input_summary": {"summary": f"Deterministic Task 10 input for {node_key}"},
            "output_summary": {},
            "duration_ms": 0,
            "cost_usd": 0.0,
        })
        output_summary: dict[str, Any] = {"summary": f"Deterministic Task 10 output for {node_key}"}
        if node_key == "draft_banner_concept":
            output_summary["headline"] = ((concept.get("copy") or {}).get("headline") or "")
        if node_key in child_substeps:
            output_summary["substeps"] = child_substeps[node_key]
        events.append({
            "node_key": node_key,
            "frontend_step": step,
            "status": "succeeded",
            "input_summary": {},
            "output_summary": output_summary,
            "duration_ms": 1 + index,
            "cost_usd": 0.0,
        })
    return events


# Frontend progress step mapping (matches GenerationRunService events)
NODE_TO_FRONTEND_STEP = {
    "load_brand_context": "intake_context",
    "capture_user_personalization": "intake_context",
    "research_best_practices": "intake_context",
    "draft_banner_concept": "concept",
    "refine_image_prompt": "concept",
    "generate_image": "image",
    "optimize_assets": "image",
    "render_html": "render_audit",
    "render_liquid": "render_audit",
    "audit": "render_audit",
    "schedule_or_publish": "review_publish",
    "publish_to_shopify": "review_publish",
}

FRONTEND_PROGRESS_STEPS = [
    {"key": "intake_context", "label": "Brand & Context"},
    {"key": "concept", "label": "Creative Concept"},
    {"key": "image", "label": "Image Generation"},
    {"key": "render_audit", "label": "Render & Audit"},
    {"key": "review_publish", "label": "Review & Publish"},
]


class PipelineRunner:
    """Manages ADK pipeline execution with session persistence."""

    def __init__(self):
        self._session_service = InMemorySessionService()
        self._sessions: dict[str, dict[str, Any]] = {}

    async def start(
        self,
        *,
        brand_id: str,
        campaign: dict[str, Any],
        trace_id: str | None = None,
        session_id: str | None = None,
        **extra: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run the pre-review pipeline (nodes 1, 3-9).

        Yields event dicts with:
          - node_key: str
          - frontend_step: str
          - status: "started" | "completed" | "failed"
          - duration_ms: int (on completed)
          - message: str
        """
        sid = session_id or str(uuid.uuid4())
        tid = trace_id or str(uuid.uuid4())

        initial_state = init_pipeline_state(
            trace_id=tid,
            session_id=sid,
            brand_id=brand_id,
            campaign=campaign,
            **extra,
        )

        pipeline = build_pre_review_pipeline()
        runner = Runner(
            app_name="banner_pipeline",
            agent=pipeline,
            session_service=self._session_service,
        )

        session = await self._session_service.create_session(
            app_name="banner_pipeline",
            user_id="system",
            state=initial_state,
        )

        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text("start pipeline")],
            ),
        ):
            if not event.author or event.author == "system":
                continue

            node_key = self._extract_node_key(event)
            yield {
                "node_key": node_key,
                "frontend_step": NODE_TO_FRONTEND_STEP.get(node_key, "unknown"),
                "status": "completed",
                "message": self._extract_message(event),
                "session_id": session.id,
            }

        # Store final state for HITL resume
        final_session = await self._session_service.get_session(
            app_name="banner_pipeline",
            user_id="system",
            session_id=session.id,
        )
        self._sessions[session.id] = dict(final_session.state)

        yield {
            "node_key": "hitl_review",
            "frontend_step": "review_publish",
            "status": "awaiting_review",
            "message": "Pipeline paused for human review",
            "session_id": session.id,
            "state": final_session.state,
        }

    async def resume(
        self,
        session_id: str,
        hitl_decision: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run the post-review pipeline (nodes 11-12) after HITL approval."""
        stored_state = self._sessions.get(session_id, {})
        stored_state["hitl_decision"] = hitl_decision

        pipeline = build_post_review_pipeline()
        runner = Runner(
            app_name="banner_pipeline_post",
            agent=pipeline,
            session_service=self._session_service,
        )

        session = await self._session_service.create_session(
            app_name="banner_pipeline_post",
            user_id="system",
            state=stored_state,
        )

        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text("resume after approval")],
            ),
        ):
            if not event.author or event.author == "system":
                continue

            node_key = self._extract_node_key(event)
            yield {
                "node_key": node_key,
                "frontend_step": NODE_TO_FRONTEND_STEP.get(node_key, "review_publish"),
                "status": "completed",
                "message": self._extract_message(event),
                "session_id": session.id,
            }

    def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve stored session state for inspection."""
        return self._sessions.get(session_id)

    @staticmethod
    def _extract_node_key(event) -> str:
        """Extract the node key from an ADK event's author field."""
        author = event.author or ""
        # SkillAgent sets author to its name (e.g. "brand_context_load")
        # Map back to node_key convention
        return author

    @staticmethod
    def _extract_message(event) -> str:
        """Extract text content from an ADK event."""
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    return part.text
        return ""


# Module-level singleton for convenience
_runner: PipelineRunner | None = None


def get_pipeline_runner() -> PipelineRunner:
    global _runner
    if _runner is None:
        _runner = PipelineRunner()
    return _runner
