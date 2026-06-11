"""Fase 0 — SuggestionService: dedupe, lifecycle, accept dispatch, job runner."""

from __future__ import annotations

import pytest

from app.core.settings import MissingSettingsError
from app.services.banners.agent_job_runner import AgentJobRunner
from app.services.banners.suggestion_service import (
    InMemoryAgentSuggestions,
    SuggestionNotActionable,
    SuggestionNotFound,
    SuggestionService,
)

TEAM_A = "team-a"


def _service(**callbacks):
    return SuggestionService(suggestions=InMemoryAgentSuggestions(), team_id=TEAM_A, **callbacks)


def test_upsert_by_dedupe_key_is_idempotent_and_refreshes_pending() -> None:
    svc = _service()
    first = svc.upsert_by_dedupe_key(kind="calendar_event", dedupe_key="calendar:buen-fin:2026", title="Buen Fin 2026")
    second = svc.upsert_by_dedupe_key(
        kind="calendar_event", dedupe_key="calendar:buen-fin:2026", title="Buen Fin 2026", rationale="actualizado"
    )
    assert first["id"] == second["id"]
    assert second["rationale"] == "actualizado"
    assert len(svc.list()) == 1


def test_upsert_never_resurrects_acted_suggestions() -> None:
    svc = _service(create_campaign=lambda payload: "cmp-1")
    row = svc.upsert_by_dedupe_key(kind="catalog_signal", dedupe_key="catalog:lowstock:gid1", title="Liquida X")
    svc.accept(str(row["id"]))
    again = svc.upsert_by_dedupe_key(kind="catalog_signal", dedupe_key="catalog:lowstock:gid1", title="Liquida X v2")
    assert again["id"] == row["id"]
    assert again["status"] == "accepted"  # not flipped back to pending
    assert svc.list(status="pending") == []


def test_accept_calendar_creates_campaign_with_payload_brief() -> None:
    seen: list[dict] = []

    def create_campaign(payload):
        seen.append(payload)
        return "cmp-42"

    svc = _service(create_campaign=create_campaign)
    row = svc.upsert_by_dedupe_key(
        kind="calendar_event", dedupe_key="calendar:navidad:2026", title="Navidad",
        payload={"title": "Campaña Navidad", "structured_brief": {"goal": "Promo navideña"}},
    )
    result = svc.accept(str(row["id"]))
    assert result.campaign_id == "cmp-42"
    assert seen[0]["structured_brief"]["goal"] == "Promo navideña"
    assert result.suggestion.status == "accepted"
    # Accepting twice is a conflict, not a double-create.
    with pytest.raises(SuggestionNotActionable):
        svc.accept(str(row["id"]))


def test_accept_performance_requires_refinement_callback() -> None:
    svc = _service()  # no callbacks wired
    row = svc.upsert_by_dedupe_key(kind="performance_refresh", dedupe_key="perf:cmp-1:w1", title="Refresh CTR")
    with pytest.raises(MissingSettingsError):
        svc.accept(str(row["id"]))


def test_dismiss_and_not_found() -> None:
    svc = _service()
    row = svc.upsert_by_dedupe_key(kind="calendar_event", dedupe_key="k", title="t")
    dismissed = svc.dismiss(str(row["id"]))
    assert dismissed.status == "dismissed"
    with pytest.raises(SuggestionNotFound):
        svc.dismiss("00000000-0000-0000-0000-00000000dead")


def test_expire_stale_flips_past_expirations() -> None:
    svc = _service()
    svc.upsert_by_dedupe_key(kind="calendar_event", dedupe_key="old", title="pasado", expires_at="2020-01-01T00:00:00+00:00")
    svc.upsert_by_dedupe_key(kind="calendar_event", dedupe_key="new", title="futuro", expires_at="2099-01-01T00:00:00+00:00")
    assert svc.expire_stale() == 1
    pending = svc.list(status="pending")
    assert [r.title for r in pending] == ["futuro"]


# --- AgentJobRunner ----------------------------------------------------------


class _Jobs:
    def __init__(self, rows):
        self.rows = rows
        self.done: list[tuple] = []
        self.errors: list[tuple] = []

    def list_processing(self, *, limit=50):
        return list(self.rows)

    def mark_done(self, job_id, *, result_summary=None):
        self.done.append((job_id, result_summary))

    def mark_error(self, job_id, *, error_detail):
        self.errors.append((job_id, error_detail))


def test_job_runner_dispatches_and_isolates_failures() -> None:
    jobs = _Jobs([
        {"id": "j1", "kind": "catalog_scan", "team_id": TEAM_A},
        {"id": "j2", "kind": "calendar_scan", "team_id": TEAM_A},
        {"id": "j3", "kind": "unknown_kind", "team_id": TEAM_A},
    ])

    def ok_handler(job):
        return {"suggestions": 2}

    def boom_handler(job):
        raise RuntimeError("scan exploded")

    runner = AgentJobRunner(jobs=jobs, handlers={"catalog_scan": ok_handler, "calendar_scan": boom_handler})
    results = runner.run_processing_jobs()

    assert [r["status"] for r in results] == ["done", "error", "error"]
    assert jobs.done == [("j1", {"suggestions": 2})]
    assert [e[0] for e in jobs.errors] == ["j2", "j3"]
    assert "scan exploded" in jobs.errors[0][1]
    assert "no handler" in jobs.errors[1][1]
