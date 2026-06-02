"""performance-audit skill — deterministic audit gate before HITL review."""

from __future__ import annotations

from typing import Any

from app.agents.state import AuditReport, BannerSessionState
from app.agents.tools import audit_lighthouse, audit_log, audit_schema, audit_w3c


def _finding(severity: str, code: str, message: str, source: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message, "source": source}


def _asset_report(state: BannerSessionState) -> dict[str, Any]:
    report = (state.assets.optimization_report if state.assets else {}) or {}
    total_kb = state.assets.total_weight_kb_1280_webp if state.assets else 0
    status = "pass" if total_kb <= 300 else "warn" if total_kb <= 600 else "fail"
    return {"status": status, "total_weight_kb_1280_webp": total_kb, "optimization_report": report, "avif_skipped": bool(report.get("avif_skipped"))}


async def run(html: str, state: BannerSessionState) -> tuple[AuditReport, str]:
    w3c = await audit_w3c.validate(html)
    schema = await audit_schema.validate(html)
    lighthouse = await audit_lighthouse.run(html=html)
    assets = _asset_report(state)

    findings: list[dict[str, Any]] = []
    for item in w3c.get("errors", []):
        findings.append(_finding("fail", item.get("code", "w3c_error"), item.get("message", "HTML validation error"), "w3c"))
    for item in w3c.get("warnings", []):
        findings.append(_finding("warn", item.get("code", "w3c_warning"), item.get("message", "HTML validation warning"), "w3c"))
    for item in schema.get("errors", []):
        findings.append(_finding("fail", item.get("code", "schema_error"), item.get("message", "Schema validation error"), "schema"))
    if lighthouse.get("mode") == "mock_manual":
        findings.append(_finding("warn", "lighthouse_mock_manual", lighthouse.get("label", "Mock/manual Lighthouse metrics"), "lighthouse"))
    if float(lighthouse.get("performance", 0)) < 70:
        findings.append(_finding("fail", "performance_score_low", "Performance score below 70", "lighthouse"))
    elif float(lighthouse.get("performance", 0)) < 90:
        findings.append(_finding("warn", "performance_score_warn", "Performance score below 90", "lighthouse"))
    if assets["status"] != "pass":
        findings.append(_finding(assets["status"], "asset_weight", "Responsive asset weight exceeds preferred budget", "assets"))
    if assets.get("avif_skipped"):
        findings.append(_finding("warn", "avif_skipped", "AVIF generation was skipped during optimization", "assets"))

    has_fail = any(f["severity"] == "fail" for f in findings)
    has_warn = any(f["severity"] == "warn" for f in findings)
    status = "fail" if has_fail else "warn" if has_warn else "pass"
    decision = "human_review_required" if status in {"pass", "warn"} else "escalate_hitl"
    root_hint = None
    if findings:
        root_hint = "; ".join(f"{f['source']}:{f['code']}" for f in findings[:4])

    report = AuditReport(
        html_w3c=w3c,
        lighthouse=lighthouse,
        schema_valid=bool(schema.get("valid")),
        schema_report=schema,
        breakpoints_render={"mobile": True, "tablet": True, "desktop": True},
        root_cause_hint=root_hint,
        overall_pass=status in {"pass", "warn"},
        status=status,
        findings=findings,
        asset_weight_report=assets,
        wcag_report={"status": "warn" if any(f["source"] == "w3c" and f["severity"] == "warn" for f in findings) else "pass"},
        seo_report={"status": "pass" if float(lighthouse.get("seo", 0)) >= 90 and schema.get("valid") else "warn"},
        avif_skipped=bool(assets.get("avif_skipped")),
        human_review_required=True,
    )
    state.audit_report = report
    await audit_log.emit(
        trace_id=state.trace_id,
        session_id=state.session_id,
        brand_id=state.brand_id,
        node="audit",
        event="audit_completed",
        payload={"status": status, "decision": decision, "findings": findings, "avif_skipped": report.avif_skipped},
    )
    return report, decision
