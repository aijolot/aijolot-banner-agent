from __future__ import annotations

import time
from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse

from app.core.dependencies import get_supabase_client_factory
from app.services.supabase.client import SupabaseClientFactory
from app.db.repositories.audit_reports import AuditReportRepository
from app.db.repositories.campaign_revisions import CampaignRevisionRepository

router = APIRouter(prefix="/campaigns", tags=["previews"])

# The frontend fires /preview + /audit-report the instant a run flips to
# succeeded, racing the background thread's last writes/connection churn. One
# short retry absorbs that transient instead of surfacing a spurious 503.
_READ_RETRIES = 2
_RETRY_DELAY_S = 0.35


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"preview repository unavailable: {exc.__class__.__name__}")


def _read_with_retry(reader: Callable[[], Any]) -> Any:
    last_exc: Exception | None = None
    for attempt in range(_READ_RETRIES + 1):
        try:
            return reader()
        except Exception as exc:  # noqa: BLE001 — transient client/connection errors
            last_exc = exc
            if attempt < _READ_RETRIES:
                time.sleep(_RETRY_DELAY_S)
    assert last_exc is not None
    raise last_exc


def _rls_client(factory: SupabaseClientFactory, authorization: str | None) -> Any:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required for campaign preview access")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token required for campaign preview access")
    client = factory.anon_client()
    postgrest = getattr(client, "postgrest", None)
    auth = getattr(postgrest, "auth", None)
    if callable(auth):
        auth(token)
        return client
    raise HTTPException(status_code=503, detail="RLS-scoped Supabase client unavailable")


@router.get("/{campaign_id}/preview", response_class=HTMLResponse)
def get_campaign_preview(
    campaign_id: str,
    factory: Annotated[SupabaseClientFactory, Depends(get_supabase_client_factory)],
    authorization: Annotated[str | None, Header()] = None,
) -> HTMLResponse:
    """Return latest rendered standalone HTML preview for a campaign via RLS-scoped client."""
    try:
        client = _rls_client(factory, authorization)
        revision = _read_with_retry(
            lambda: CampaignRevisionRepository(client).get_latest_by_campaign_id(campaign_id=campaign_id)
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive around external client config
        raise _unavailable(exc) from exc
    if not revision or not revision.get("html_preview"):
        raise HTTPException(status_code=404, detail="preview not found")
    return HTMLResponse(
        content=str(revision["html_preview"]),
        headers={
            "X-Robots-Tag": "noindex, nofollow",
            "Content-Security-Policy": "default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; script-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        },
    )


@router.get("/{campaign_id}/audit-report")
def get_campaign_audit_report(
    campaign_id: str,
    factory: Annotated[SupabaseClientFactory, Depends(get_supabase_client_factory)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Return latest deterministic audit report for a campaign via RLS-scoped client."""
    try:
        client = _rls_client(factory, authorization)
        report = _read_with_retry(
            lambda: AuditReportRepository(client).get_latest_by_campaign_id(campaign_id=campaign_id)
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive around external client config
        raise _unavailable(exc) from exc
    if not report:
        raise HTTPException(status_code=404, detail="audit report not found")
    return report
