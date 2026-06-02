from __future__ import annotations

import pytest

from app.schemas.performance import OptimizationProposalCreate, PerformanceSnapshotCreate
from app.services.banners.performance_service import CampaignNotFound, InvalidPerformanceMetric, PerformanceService

TEAM_A = "team-a"
TEAM_B = "team-b"
CAMPAIGN_ID = "00000000-0000-0000-0000-000000000101"
OTHER_CAMPAIGN_ID = "00000000-0000-0000-0000-000000000102"
REVISION_ID = "00000000-0000-0000-0000-000000000201"
PROPOSED_REVISION_ID = "00000000-0000-0000-0000-000000000202"


class InMemoryCampaigns:
    def __init__(self) -> None:
        self.rows = {
            CAMPAIGN_ID: {"id": CAMPAIGN_ID, "team_id": TEAM_A, "selected_revision_id": REVISION_ID},
            OTHER_CAMPAIGN_ID: {"id": OTHER_CAMPAIGN_ID, "team_id": TEAM_B, "selected_revision_id": REVISION_ID},
        }

    def get(self, *, campaign_id: str, team_id: str | None = None):
        row = self.rows.get(campaign_id)
        if row and (team_id is None or row["team_id"] == team_id):
            return row
        return None


class InMemoryRevisions:
    def __init__(self) -> None:
        other_revision = "00000000-0000-0000-0000-000000000299"
        self.rows = {
            REVISION_ID: {"id": REVISION_ID, "campaign_id": CAMPAIGN_ID},
            PROPOSED_REVISION_ID: {"id": PROPOSED_REVISION_ID, "campaign_id": CAMPAIGN_ID},
            other_revision: {"id": other_revision, "campaign_id": OTHER_CAMPAIGN_ID},
        }

    def get(self, *, revision_id: str):
        return self.rows.get(revision_id)


class InMemorySnapshots:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.next_n = 1

    def list_by_campaign_id(self, *, campaign_id: str, limit: int = 20):
        return [row for row in reversed(self.rows) if row["campaign_id"] == campaign_id][:limit]

    def create(self, *, data: dict):
        row = {"id": f"snapshot-{self.next_n}", "created_at": f"2026-06-0{self.next_n}T00:00:00Z", **data}
        self.next_n += 1
        self.rows.append(row)
        return row


class InMemoryInsights:
    def __init__(self) -> None:
        self.rows = [
            {"id": "insight-team", "team_id": TEAM_A, "campaign_id": None, "segment_key": "global", "tag": "asset_weight", "insight": "Images lighter than 150KB tend to perform better", "lift_label": "+mock", "source": {"seed": True}, "created_at": "2026-06-01T00:00:00Z"},
            {"id": "insight-campaign", "team_id": TEAM_A, "campaign_id": CAMPAIGN_ID, "segment_key": "hero", "tag": "cta", "insight": "Short CTA copy reads faster", "lift_label": "+manual", "source": {"manual": True}, "created_at": "2026-06-02T00:00:00Z"},
            {"id": "insight-other-team", "team_id": TEAM_B, "campaign_id": None, "segment_key": "global", "tag": "private", "insight": "Do not leak", "lift_label": "n/a", "source": {}, "created_at": "2026-06-03T00:00:00Z"},
        ]

    def list_for_team_and_campaign(self, *, team_id: str, campaign_id: str, limit: int = 20):
        return [row for row in self.rows if row["team_id"] == team_id and row.get("campaign_id") in (None, campaign_id)][:limit]


class InMemoryProposals:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.next_n = 1

    def list_by_campaign_id(self, *, campaign_id: str, limit: int = 20):
        return [row for row in reversed(self.rows) if row["campaign_id"] == campaign_id][:limit]

    def create(self, *, data: dict):
        row = {"id": f"proposal-{self.next_n}", "status": "draft", "created_at": "2026-06-01T00:00:00Z", "updated_at": "2026-06-01T00:00:00Z", **data}
        self.next_n += 1
        self.rows.append(row)
        return row


def _service(team_id: str = TEAM_A) -> PerformanceService:
    return PerformanceService(
        campaigns=InMemoryCampaigns(),
        revisions=InMemoryRevisions(),
        snapshots=InMemorySnapshots(),
        insights=InMemoryInsights(),
        proposals=InMemoryProposals(),
        team_id=team_id,
    )


def test_create_manual_snapshot_derives_rates_and_returns_non_live_provenance() -> None:
    service = _service()

    snapshot = service.create_snapshot(
        CAMPAIGN_ID,
        PerformanceSnapshotCreate(
            revision_id=REVISION_ID,
            window_start="2026-06-01T00:00:00Z",
            window_end="2026-06-02T00:00:00Z",
            impressions=1000,
            clicks=125,
            conversions=25,
            load_p75_ms=420,
            weight_saved_pct=0.18,
            segment_breakdown=[{"segment": "mobile", "ctr": 0.14}],
        ),
    )

    assert snapshot.campaign_id == CAMPAIGN_ID
    assert snapshot.source == "manual"
    assert snapshot.live_analytics is False
    assert snapshot.data_source_label == "Manual/mock metrics — not live analytics"
    assert snapshot.ctr == pytest.approx(0.125)
    assert snapshot.conversion_rate == pytest.approx(0.2)


def test_summary_lists_latest_snapshots_seeded_insights_and_proposals_without_cross_team_leak() -> None:
    service = _service()
    service.create_snapshot(CAMPAIGN_ID, PerformanceSnapshotCreate(revision_id=REVISION_ID, impressions=50, clicks=5, conversions=1))
    proposal = service.create_proposal(
        CAMPAIGN_ID,
        OptimizationProposalCreate(
            source_revision_id=REVISION_ID,
            proposed_revision_id=PROPOSED_REVISION_ID,
            segment_key="hero",
            rationale="Create a V2 with shorter copy for returning visitors.",
            projected_lift={"ctr": "+5% mock"},
        ),
    )

    summary = service.get_campaign_performance(CAMPAIGN_ID)

    assert summary.campaign_id == CAMPAIGN_ID
    assert summary.live_analytics is False
    assert "not live analytics" in summary.metrics_note.lower()
    assert summary.latest_snapshot is not None
    assert [insight.id for insight in summary.insights] == ["insight-team", "insight-campaign"]
    assert summary.proposals[0].id == proposal.id
    assert "Do not leak" not in summary.model_dump_json()


def test_campaign_scope_is_enforced_for_reads_and_writes() -> None:
    service = _service(team_id=TEAM_A)

    with pytest.raises(CampaignNotFound):
        service.get_campaign_performance(OTHER_CAMPAIGN_ID)
    with pytest.raises(CampaignNotFound):
        service.create_snapshot(OTHER_CAMPAIGN_ID, PerformanceSnapshotCreate(revision_id=REVISION_ID, impressions=1))


def test_rejects_invalid_rate_overrides() -> None:
    service = _service()

    with pytest.raises(InvalidPerformanceMetric):
        service.create_snapshot(CAMPAIGN_ID, PerformanceSnapshotCreate(revision_id=REVISION_ID, impressions=10, clicks=1, ctr=1.2))


def test_rejects_inconsistent_counts_even_when_denominator_is_zero() -> None:
    service = _service()

    with pytest.raises(InvalidPerformanceMetric):
        service.create_snapshot(CAMPAIGN_ID, PerformanceSnapshotCreate(revision_id=REVISION_ID, impressions=0, clicks=1))
    with pytest.raises(InvalidPerformanceMetric):
        service.create_snapshot(CAMPAIGN_ID, PerformanceSnapshotCreate(revision_id=REVISION_ID, impressions=0, clicks=0, conversions=1))


def test_rejects_revision_ids_that_do_not_belong_to_campaign() -> None:
    service = _service()
    other_revision = "00000000-0000-0000-0000-000000000299"

    with pytest.raises(CampaignNotFound):
        service.create_snapshot(CAMPAIGN_ID, PerformanceSnapshotCreate(revision_id=other_revision, impressions=1))
    with pytest.raises(CampaignNotFound):
        service.create_proposal(
            CAMPAIGN_ID,
            OptimizationProposalCreate(source_revision_id=other_revision, rationale="Must not cross-link revisions."),
        )
