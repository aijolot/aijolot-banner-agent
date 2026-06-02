"""Pipeline runner — bridge between FastAPI routes and ADK pipelines.

Wraps the ADK Runner + InMemorySessionService to provide a simple
async interface for starting and resuming banner pipelines.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.pipeline import build_post_review_pipeline, build_pre_review_pipeline
from app.agents.state_bridge import init_pipeline_state


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
