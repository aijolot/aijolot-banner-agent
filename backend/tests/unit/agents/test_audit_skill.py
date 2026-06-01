from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from app.agents.state import BannerAssets, BannerSessionState, Concept
from app.db.repositories.audit_reports import AuditReportRepository
from app.services.banners.html_renderer import render_banner_preview
from app.workflows.banner_creation import run_to_audit

SKILL_ROOT = Path(__file__).resolve().parents[3] / "app" / "agents" / "skills"


def _load_skill(skill_id: str):
    path = SKILL_ROOT / skill_id / "impl.py"
    spec = importlib.util.spec_from_file_location(f"test_{skill_id.replace('-', '_')}_impl", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _concept() -> Concept:
    return Concept(
        layout="hero",
        copy={"headline": "Move brighter", "subheadline": "Save on running gear", "cta": "Shop now"},
        palette_usage={},
        image_prompt="background",
        hierarchy_notes="",
    )


def _assets() -> BannerAssets:
    return BannerAssets(
        webp={320: "https://cdn.example/320.webp", 1280: "https://cdn.example/1280.webp"},
        avif={},
        fallback_jpg={1280: "https://cdn.example/1280.jpg"},
        alt_text_suggestion="Warm running background",
        total_weight_kb_1280_webp=180,
        optimization_report={"avif_skipped": True, "avif_skip_reason": "codec unavailable"},
    )


def test_audit_skill_produces_deterministic_human_review_gate_and_avif_warning() -> None:
    skill = _load_skill("performance-audit")
    state = BannerSessionState(trace_id="trace", session_id="session", brand_id="demo", assets=_assets())
    html = render_banner_preview(_concept(), _assets(), brand={"name": "Demo", "palette": [{"name": "Ink", "hex": "#111111"}]}).html

    report, decision = asyncio.run(skill.run(html, state))
    report2, decision2 = asyncio.run(skill.run(html, state))

    assert decision == "human_review_required"
    assert decision2 == decision
    assert report.model_dump() == report2.model_dump()
    assert report.human_review_required is True
    assert report.overall_pass is True
    assert report.schema_valid is True
    assert report.lighthouse["mode"] == "mock_manual"
    assert report.avif_skipped is True
    assert any(f["code"] == "avif_skipped" and f["severity"] == "warn" for f in report.findings)


def test_audit_skill_fails_invalid_html_without_external_calls() -> None:
    skill = _load_skill("performance-audit")
    state = BannerSessionState(trace_id="trace2", session_id="session2", brand_id="demo")

    report, decision = asyncio.run(skill.run("<div>No document</div>", state))

    assert decision == "escalate_hitl"
    assert report.status == "fail"
    assert report.overall_pass is False
    assert any(f["severity"] == "fail" for f in report.findings)


def test_audit_report_repository_maps_warn_status_and_enriches_runtime_fields() -> None:
    data = {
        "campaign_id": "11111111-1111-1111-1111-111111111111",
        "status": "warn",
        "asset_weight_report": {"status": "pass"},
        "seo_report": {"status": "warn"},
        "findings": [{"severity": "warn", "code": "avif_skipped"}],
        "schema_report": {"valid": True},
        "human_review_required": True,
        "avif_skipped": True,
    }

    normalized = AuditReportRepository._normalize_for_storage(data)
    row = AuditReportRepository._enrich_row(normalized)

    assert normalized["status"] == "pass"
    assert normalized["asset_weight_report"]["avif_skipped"] is True
    assert row["runtime_status"] == "warn"
    assert row["avif_skipped"] is True
    assert row["findings"][0]["code"] == "avif_skipped"


def test_run_to_audit_renders_html_liquid_and_halts_for_human_review() -> None:
    state = BannerSessionState(
        trace_id="trace3",
        session_id="session3",
        brand_id="demo",
        concept=_concept(),
        assets=_assets(),
    )

    result = asyncio.run(run_to_audit(state))

    assert result.html_standalone and "<!doctype html>" in result.html_standalone
    assert result.liquid_section and "aijolot-banner" in result.liquid_section
    assert result.audit_report is not None
    assert result.audit_report.human_review_required is True
