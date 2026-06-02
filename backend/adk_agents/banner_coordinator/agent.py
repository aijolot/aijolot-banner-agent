"""Banner Coordinator — ADK entry point for `adk web`.

Supports two modes via PIPELINE_MODE env var:

  intake_only (default):
    Chat agent that collects Campaign fields one at a time via Gemini Flash.
    Validates the chat interface in `adk web` end-to-end.

  full:
    The complete pre-review pipeline (nodes 1, 3-9) as a SequentialAgent.
    Requires campaign data in session state — not a chat interface.

Run:
    cd backend && pip install -e .
    export GOOGLE_API_KEY=<from https://aistudio.google.com>
    adk web --agents_dir backend/adk_agents

    # For full pipeline mode:
    PIPELINE_MODE=full adk web --agents_dir backend/adk_agents
"""

from __future__ import annotations

import os
from pathlib import Path

from google.adk.agents import Agent

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "app" / "agents" / "prompts"
_INTAKE_PROMPT = (_PROMPTS_DIR / "intake.md").read_text(encoding="utf-8")
_COORDINATOR_PROMPT = (_PROMPTS_DIR / "coordinator.md").read_text(encoding="utf-8")

FLASH_MODEL = os.getenv("GEMINI_MODEL_FLASH", "gemini-2.5-flash")
PIPELINE_MODE = os.getenv("PIPELINE_MODE", "intake_only").strip().lower()


def _build_intake_agent() -> Agent:
    """Chat agent for intake-only mode (default)."""
    system_instruction = f"""{_COORDINATOR_PROMPT}

---
You are currently running in **intake-only mode** for a hackathon demo. Only the
campaign-intake skill is wired. When you have all 7 Campaign fields, output a
final JSON block:

```json
{{
  "goal": "...",
  "audience": "...",
  "cta": "...",
  "tone": "...",
  "urgency": "...",
  "placement": "...",
  "deadline": null
}}
```

Then say: "Listo. Cuando confirme el admin pasamos a la stage de Arte."
Until then, ask ONE missing field at a time. Mirror the admin's tone.

---
## campaign-intake prompt
{_INTAKE_PROMPT}
"""
    return Agent(
        name="banner_coordinator",
        model=FLASH_MODEL,
        description=(
            "Shopify Banner Agent — intake-only mode. Captures a banner campaign "
            "(goal, audience, cta, tone, urgency, placement, deadline) "
            "conversationally and produces structured JSON."
        ),
        instruction=system_instruction,
    )


def _build_full_pipeline():
    """Full pre-review pipeline (nodes 1, 3-9)."""
    from app.agents.pipeline import build_pre_review_pipeline

    return build_pre_review_pipeline()


# Export root_agent for `adk web` discovery
if PIPELINE_MODE == "full":
    root_agent = _build_full_pipeline()
else:
    root_agent = _build_intake_agent()
