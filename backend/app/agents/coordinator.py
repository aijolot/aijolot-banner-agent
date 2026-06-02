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
    """Return the pre-review ADK Workflow as the coordinator.

    The coordinator is a Workflow that runs nodes 1, 3-9 with a
    conditional retry loop. Post-HITL nodes 11-12 are invoked
    separately via build_post_review_coordinator().
    """
    from app.agents.pipeline import build_pre_review_pipeline

    return build_pre_review_pipeline()


def build_post_review_coordinator():
    """Return the post-review ADK Workflow.

    Runs nodes 11-12 after HITL approval.
    """
    from app.agents.pipeline import build_post_review_pipeline

    return build_post_review_pipeline()
