from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000401"
TEAM_ID = "00000000-0000-0000-0000-000000000001"
OTHER_TEAM_ID = "00000000-0000-0000-0000-000000000002"
USER_ID = "00000000-0000-0000-0000-000000000601"
DEMO_HEADERS = {
    "Authorization": f"Bearer demo:{USER_ID}:{TEAM_ID}",
}


class FakeCampaigns:
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        if campaign_id == CAMPAIGN_ID and team_id == TEAM_ID:
            return {"id": campaign_id, "team_id": team_id}
        return None


class FakeRevisions:
    def __init__(self, html_preview: str | None = "<section class='aijolot-banner'>Backend preview</section>") -> None:
        self.html_preview = html_preview

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        if campaign_id != CAMPAIGN_ID or self.html_preview is None:
            return None
        return {"id": "revision-1", "campaign_id": campaign_id, "html_preview": self.html_preview}


DEFAULT_REPORT = {"id": "audit-1", "status": "pass", "schema_report": {"valid": True}}


class FakeAuditReports:
    def __init__(self, report: dict[str, Any] | None = DEFAULT_REPORT) -> None:
        self.report = report

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        return self.report if campaign_id == CAMPAIGN_ID else None


class FakeRepos:
    def __init__(self, *, html_preview: str | None = "<section class='aijolot-banner'>Backend preview</section>", report: dict[str, Any] | None = DEFAULT_REPORT) -> None:
        self.campaigns = FakeCampaigns()
        self.revisions = FakeRevisions(html_preview)
        self.audit_reports = FakeAuditReports(report)


def test_preview_and_audit_accept_demo_bearer_and_return_backend_artifacts(monkeypatch) -> None:
    from app.api.v1 import previews

    monkeypatch.setattr(previews, "_REPOSITORY_FACTORY", lambda _context: FakeRepos())

    preview = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/preview", headers={**DEMO_HEADERS, "Accept": "text/html"})
    audit = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/audit-report", headers=DEMO_HEADERS)

    assert preview.status_code == 200
    assert "aijolot-banner" in preview.text
    assert "script-src 'none'" in preview.headers["content-security-policy"]
    assert audit.status_code == 200
    assert audit.json()["schema_report"] == {"valid": True}


def test_preview_and_audit_fail_closed_without_context(monkeypatch) -> None:
    from app.api.v1 import previews

    monkeypatch.setattr(previews, "_REPOSITORY_FACTORY", lambda _context: FakeRepos())

    assert client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/preview").status_code == 401
    assert client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/audit-report").status_code == 401


def test_preview_and_audit_hide_cross_team_campaigns(monkeypatch) -> None:
    from app.api.v1 import previews

    monkeypatch.setattr(previews, "_REPOSITORY_FACTORY", lambda _context: FakeRepos())
    headers = {"Authorization": f"Bearer demo:{USER_ID}:{OTHER_TEAM_ID}"}

    assert client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/preview", headers=headers).status_code == 404
    assert client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/audit-report", headers=headers).status_code == 404


def test_preview_and_audit_return_404_when_artifacts_missing(monkeypatch) -> None:
    from app.api.v1 import previews

    monkeypatch.setattr(previews, "_REPOSITORY_FACTORY", lambda _context: FakeRepos(html_preview=None, report=None))

    assert client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/preview", headers=DEMO_HEADERS).status_code == 404
    assert client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/audit-report", headers=DEMO_HEADERS).status_code == 404


def test_service_role_preview_artifacts_are_local_demo_only(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv("SUPABASE_TEAM_ID", TEAM_ID)

    preview = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/preview", headers=DEMO_HEADERS)
    audit = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/audit-report", headers=DEMO_HEADERS)

    assert preview.status_code == 503
    assert audit.status_code == 503
