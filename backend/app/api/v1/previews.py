from __future__ import annotations

from typing import Any, NamedTuple

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.core.auth import UserContext, require_user_context
from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.audit_reports import AuditReportRepository
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.services.supabase.client import SupabaseClientFactory

router = APIRouter(prefix="/campaigns", tags=["previews"])


class ArtifactRepositories(NamedTuple):
    campaigns: CampaignRepository
    revisions: CampaignRevisionRepository
    audit_reports: AuditReportRepository


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"preview repository unavailable: {exc.__class__.__name__}")


def _configured_repositories_for_context(context: UserContext) -> ArtifactRepositories:
    """Return service-role repositories scoped by explicit request team context.

    Preview/audit reads are backend-backed for the local demo bearer/header context
    used by the static frontend. They still fail closed when Supabase settings are
    absent or incomplete, and campaign ownership is checked before artifacts are
    read so service-role access is not exposed cross-team.
    """

    settings = Settings.from_env()
    if settings.app_env.lower() not in {"local", "test", "development", "dev", "demo"}:
        raise MissingSettingsError(("APP_ENV local/demo required for service-role preview artifacts",))
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    if not has_supabase_signal:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_TEAM_ID"))
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    client = SupabaseClientFactory(settings).service_role_client()
    return ArtifactRepositories(
        campaigns=CampaignRepository(client),
        revisions=CampaignRevisionRepository(client),
        audit_reports=AuditReportRepository(client),
    )


_REPOSITORY_FACTORY = _configured_repositories_for_context


def _repositories_for_request(request: Request) -> tuple[UserContext, ArtifactRepositories]:
    context = require_user_context(request)
    return context, _REPOSITORY_FACTORY(context)


@router.get("/{campaign_id}/preview", response_class=HTMLResponse)
def get_campaign_preview(campaign_id: str, request: Request) -> HTMLResponse:
    """Return latest rendered standalone HTML preview for an owned campaign."""
    try:
        context, repos = _repositories_for_request(request)
        campaign = repos.campaigns.get(campaign_id=campaign_id, team_id=context.team_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="resource not found")
        revision = repos.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
    except HTTPException:
        raise
    except MissingSettingsError as exc:
        raise _unavailable(exc) from exc
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
def get_campaign_audit_report(campaign_id: str, request: Request) -> dict[str, Any]:
    """Return latest deterministic audit report for an owned campaign."""
    try:
        context, repos = _repositories_for_request(request)
        campaign = repos.campaigns.get(campaign_id=campaign_id, team_id=context.team_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="resource not found")
        report = repos.audit_reports.get_latest_by_campaign_id(campaign_id=campaign_id)
    except HTTPException:
        raise
    except MissingSettingsError as exc:
        raise _unavailable(exc) from exc
    except Exception as exc:  # pragma: no cover - defensive around external client config
        raise _unavailable(exc) from exc
    if not report:
        raise HTTPException(status_code=404, detail="audit report not found")
    return report
