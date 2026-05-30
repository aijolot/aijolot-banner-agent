"""Coordinator Agent — orchestrates the 12-node banner-creation graph.

Model: gemini-3.1-pro (Gemini 3.1 Pro)
Responsibilities:
- Maintain BannerSessionState across nodes.
- Decide branching: audit pass/fail, immediate vs scheduled, retry root_cause.
- Invoke sub-agents (CreativeDirector, Auditor) as ADK Tools at nodes 5 and 9.
- Enforce HITL gate at node 10 (no bypass).
- Emit observability events to audit_log per node.

Implementation deferred to GH-5 + per-node tickets.
"""

from __future__ import annotations

import os


COORDINATOR_MODEL = os.getenv("GEMINI_MODEL_PRO", "gemini-3.1-pro")


def build_coordinator():
    """Return the ADK root Agent.

    Wiring lands in GH-5 (skeleton) and is extended per ticket as each node
    becomes available.
    """
    raise NotImplementedError("Coordinator wiring lands in GH-5 + per-node tickets.")
