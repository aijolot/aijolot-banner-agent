"""Banner Coordinator — minimal runnable agent for adk web demo.

Hackathon-stage scope: only the intake skill is wired (Gemini Flash). The rest
of the 12-node graph is stubbed in app.agents.{graph,coordinator}.py. This
lets us validate the chat interface in `adk web` end-to-end with a real model
while the full graph lands per GH tickets.

Run:
    cd backend && pip install -e .
    export GOOGLE_API_KEY=<from https://aistudio.google.com>
    adk web --agents_dir backend/app/agents

Then open the printed URL and chat. The agent will collect Campaign fields
one at a time and return a final JSON when complete.
"""

from __future__ import annotations

import os
from pathlib import Path

from google.adk.agents import Agent


_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "app" / "agents" / "prompts"
_INTAKE_PROMPT = (_PROMPTS_DIR / "intake.md").read_text(encoding="utf-8")
_COORDINATOR_PROMPT = (_PROMPTS_DIR / "coordinator.md").read_text(encoding="utf-8")


# Model resolution. The .env spec uses Gemini 3.x; if those aliases are not
# yet available on your project, override at run time:
#   GEMINI_MODEL_FLASH=gemini-2.5-flash adk web ...
FLASH_MODEL = os.getenv("GEMINI_MODEL_FLASH", "gemini-2.5-flash")


SYSTEM_INSTRUCTION = f"""{_COORDINATOR_PROMPT}

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


root_agent = Agent(
    name="banner_coordinator",
    model=FLASH_MODEL,
    description=(
        "Shopify Banner Agent — intake-only mode. Captures a banner campaign "
        "(goal, audience, cta, tone, urgency, placement, deadline) "
        "conversationally and produces structured JSON."
    ),
    instruction=SYSTEM_INSTRUCTION,
)
