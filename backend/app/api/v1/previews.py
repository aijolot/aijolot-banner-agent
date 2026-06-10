from __future__ import annotations

import time
from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
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


def _scoped_client(factory: SupabaseClientFactory, request: Any, campaign_id: str) -> Any:
    """Team-scoped access like the rest of /api/v1: validate the campaign belongs
    to the caller's team, then read with the service-role client.

    (The previous implementation demanded a real Supabase JWT for an RLS anon
    client — with the demo auth headers it ALWAYS failed with 503. Real JWT/RLS
    returns with the auth project.)
    """
    from app.core.auth import require_user_context
    from app.db.repositories.campaigns import CampaignRepository

    context = require_user_context(request)
    client = factory.service_role_client()
    campaign = _read_with_retry(
        lambda: CampaignRepository(client).get(campaign_id=campaign_id, team_id=context.team_id)
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")
    return client


@router.get("/{campaign_id}/preview", response_class=HTMLResponse)
def get_campaign_preview(
    campaign_id: str,
    request: Request,
    factory: Annotated[SupabaseClientFactory, Depends(get_supabase_client_factory)],
) -> HTMLResponse:
    """Latest rendered standalone HTML preview, scoped to the caller's team."""
    try:
        client = _scoped_client(factory, request, campaign_id)
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
    request: Request,
    factory: Annotated[SupabaseClientFactory, Depends(get_supabase_client_factory)],
) -> dict[str, Any]:
    """Latest deterministic audit report, scoped to the caller's team."""
    try:
        client = _scoped_client(factory, request, campaign_id)
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
