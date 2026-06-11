"""AgentJobRunner — executes claimed agent_jobs (Fase 0 backend-poll side).

pg_cron enqueues one scan per team per kind and claims due rows as 'processing'
(claim_due_agent_jobs_fn, SKIP LOCKED). The FastAPI poller at
``GET /api/v1/agent-jobs/process`` hands them to this runner, which dispatches
by kind to a registered handler and marks done/error — never silent.

Handlers are registered by the features that own each scan:
  calendar_scan    → F1 calendar_service.scan_upcoming
  performance_sync → F2 analytics sync + fatigue detection
  catalog_scan     → F3 catalog_signal_service.scan
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

JobHandler = Callable[[dict[str, Any]], dict[str, Any]]


class AgentJobRepositoryProtocol(Protocol):
    def list_processing(self, *, limit: int = 50) -> list[dict[str, Any]]: ...
    def mark_done(self, job_id: str, *, result_summary: dict[str, Any] | None = None) -> dict[str, Any] | None: ...
    def mark_error(self, job_id: str, *, error_detail: str) -> dict[str, Any] | None: ...


class AgentJobRunner:
    def __init__(self, *, jobs: AgentJobRepositoryProtocol, handlers: dict[str, JobHandler] | None = None) -> None:
        self.jobs = jobs
        self.handlers = dict(handlers or {})

    def register(self, kind: str, handler: JobHandler) -> None:
        self.handlers[kind] = handler

    def run_processing_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Execute every claimed job; one bad job never blocks the rest."""
        results: list[dict[str, Any]] = []
        for job in self.jobs.list_processing(limit=limit):
            job_id = str(job.get("id"))
            kind = str(job.get("kind") or "")
            handler = self.handlers.get(kind)
            if handler is None:
                self.jobs.mark_error(job_id, error_detail=f"no handler registered for kind '{kind}'")
                results.append({"id": job_id, "kind": kind, "status": "error", "error": "no_handler"})
                continue
            try:
                summary = handler(dict(job)) or {}
                self.jobs.mark_done(job_id, result_summary=summary)
                results.append({"id": job_id, "kind": kind, "status": "done", "summary": summary})
            except Exception as exc:  # noqa: BLE001 — honest failure per job
                detail = f"{type(exc).__name__}: {exc}"
                self.jobs.mark_error(job_id, error_detail=detail)
                results.append({"id": job_id, "kind": kind, "status": "error", "error": detail[:200]})
        return results
