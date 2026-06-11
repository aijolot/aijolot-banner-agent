"""F1 — /api/v1/calendar: events, settings, manual scan → accept desde la UI."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
TEAM = "44444444-4444-4444-4444-444444444444"
AUTH = {"X-Aijolot-User-Id": "user-cal", "X-Aijolot-Team-Id": TEAM, "X-Aijolot-Store-Id": "store-cal"}


def test_calendar_fails_closed_without_context() -> None:
    assert client.get("/api/v1/calendar/events").status_code == 401


def test_events_settings_and_manual_scan_flow(monkeypatch) -> None:
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_TEAM_ID"):
        monkeypatch.delenv(var, raising=False)

    events = client.get("/api/v1/calendar/events", headers=AUTH)
    assert events.status_code == 200
    slugs = {e["slug"] for e in events.json()["events"]}
    assert "el-buen-fin" in slugs and "hot-sale" in slugs

    settings = client.get("/api/v1/calendar/settings", headers=AUTH)
    assert settings.status_code == 200
    assert settings.json()["lead_time_days"] == 14

    # Widen the window so the scan always catches at least one date, any day of year.
    saved = client.put("/api/v1/calendar/settings", headers=AUTH, json={"lead_time_days": 90})
    assert saved.json()["lead_time_days"] == 90

    scan = client.post("/api/v1/calendar/scan", headers=AUTH, json={})
    assert scan.status_code == 200
    body = scan.json()
    assert body["enabled"] is True
    rows = body["suggestion_rows"]
    assert rows, "a 90-day window must always contain an upcoming commercial date"
    assert all(r["id"] and r["slug"] and r["status"] == "pending" for r in rows)

    # The UI accepts straight from the scan result → campaign created.
    accepted = client.post(f"/api/v1/suggestions/{rows[0]['id']}/accept", headers=AUTH)
    assert accepted.status_code == 200
    assert accepted.json()["campaign_id"]

    # Re-scan is idempotent: the accepted row keeps its status, no duplicates.
    rescan = client.post("/api/v1/calendar/scan", headers=AUTH, json={})
    again = [r for r in rescan.json()["suggestion_rows"] if r["slug"] == rows[0]["slug"]]
    assert again and again[0]["status"] == "accepted"
