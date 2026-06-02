"""SkillAgent — wraps a skill impl.py as an ADK BaseAgent.

Each SkillAgent reads inputs from session.state, calls the skill's
async run() function, writes outputs back to session.state, and emits
audit_log events for observability.
"""

from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Callable

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from app.agents.tools import audit_log

_SKILLS_DIR = Path(__file__).resolve().parent / "skills"


def _load_skill_module(skill_id: str):
    """Dynamically import a skill's impl module."""
    module_name = skill_id.replace("-", "_")
    impl_path = _SKILLS_DIR / skill_id / "impl.py"
    if not impl_path.exists():
        raise FileNotFoundError(f"Skill impl not found: {impl_path}")
    spec = importlib.util.spec_from_file_location(
        f"app.agents.skills.{module_name}.impl", impl_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillAgent(BaseAgent):
    """ADK agent that wraps a single skill impl.run() call.

    Parameters:
        name: ADK agent name (must be valid Python identifier).
        skill_id: Skill directory name (e.g. "brand-context-load").
        node_key: Graph node key for audit_log events.
        read_state: Extracts run() kwargs from session.state dict.
        write_state: Writes run() result back to session.state dict.
        escalate_on_done: If True, sets escalate=True after execution
            (used by audit node to break LoopAgent).
    """

    skill_id: str
    node_key: str
    read_state: Callable[[dict[str, Any]], dict[str, Any]]
    write_state: Callable[[dict[str, Any], Any], dict[str, Any]]
    escalate_on_done: bool = False

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        skill_module = _load_skill_module(self.skill_id)

        # Emit start event
        t0 = time.monotonic()
        await audit_log.emit(
            trace_id=state.get("trace_id", ""),
            session_id=state.get("session_id", ""),
            brand_id=state.get("brand_id", ""),
            node=self.node_key,
            event="node_started",
        )

        # Read inputs and call skill
        kwargs = self.read_state(state)
        try:
            result = await skill_module.run(**kwargs)
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            await audit_log.emit(
                trace_id=state.get("trace_id", ""),
                session_id=state.get("session_id", ""),
                brand_id=state.get("brand_id", ""),
                node=self.node_key,
                event="node_failed",
                duration_ms=duration_ms,
                payload={"error": str(exc)},
            )
            raise

        # Write outputs to state
        delta = self.write_state(state, result)
        for key, value in delta.items():
            state[key] = value

        duration_ms = int((time.monotonic() - t0) * 1000)
        await audit_log.emit(
            trace_id=state.get("trace_id", ""),
            session_id=state.get("session_id", ""),
            brand_id=state.get("brand_id", ""),
            node=self.node_key,
            event="node_completed",
            duration_ms=duration_ms,
        )

        # Check if audit node wants to control the loop
        should_escalate = self.escalate_on_done
        if callable(getattr(self, "_should_escalate", None)):
            should_escalate = self._should_escalate(state, result)

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(
                    f"[{self.node_key}] completed in {duration_ms}ms"
                )],
            ),
            actions=EventActions(
                stateDelta=delta,
                escalate=should_escalate or None,
            ),
        )


class AuditSkillAgent(SkillAgent):
    """Specialized SkillAgent for the audit node (node 9).

    Controls the LoopAgent: escalates on pass/warn (exit loop),
    does NOT escalate on retry (loop continues).
    """

    escalate_on_done: bool = False  # controlled dynamically

    def _should_escalate(self, state: dict[str, Any], result: Any) -> bool:
        """Return True to exit the LoopAgent (audit passed or retries exhausted)."""
        if isinstance(result, tuple) and len(result) == 2:
            _report, decision = result
        else:
            decision = state.get("audit_decision", "escalate_hitl")

        if decision in ("pass", "human_review_required", "escalate_hitl"):
            return True

        # Retry: check if retries are exhausted
        retries = state.get("retries", {})
        target_node = "draft_banner_concept" if "node_5" in decision else "render_html"
        current = retries.get(target_node, 0)
        max_retries = 2
        if current >= max_retries:
            state["audit_decision"] = "escalate_hitl"
            return True

        # Increment retry counter and continue loop
        retries[target_node] = current + 1
        state["retries"] = retries
        return False
