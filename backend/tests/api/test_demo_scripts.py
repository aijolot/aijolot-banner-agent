from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2].parent


def _safe_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("SUPABASE_", "SHOPIFY_", "GEMINI_", "GOOGLE_")) or key in {
            "AIJOLOT_INTAKE_PROVIDER",
            "CAMPAIGN_STORE_ID",
        }:
            env.pop(key, None)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def test_reset_demo_data_script_is_idempotent_and_safe() -> None:
    script = ROOT / "scripts" / "reset-demo-data.py"
    assert script.exists()

    first = subprocess.run([sys.executable, str(script), "--local-only"], cwd=ROOT, env=_safe_env(), text=True, capture_output=True, timeout=60)
    second = subprocess.run([sys.executable, str(script), "--local-only"], cwd=ROOT, env=_safe_env(), text=True, capture_output=True, timeout=60)

    assert first.returncode == 0, first.stderr + first.stdout
    assert second.returncode == 0, second.stderr + second.stdout
    assert "local deterministic runtime artifacts reset" in second.stdout.lower()


def test_smoke_demo_flow_runs_twice_with_deterministic_fallback() -> None:
    script = ROOT / "scripts" / "smoke-demo-flow.py"
    assert script.exists()

    for _ in range(2):
        result = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=_safe_env(), text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stderr + result.stdout
        assert "DETERMINISTIC FALLBACK" in result.stdout
        assert "smoke demo flow passed" in result.stdout.lower()


def test_demo_docs_constrain_non_mvp_claims() -> None:
    demo_script = (ROOT / "docs" / "demo-script.md").read_text(encoding="utf-8")
    for required in [
        "PDF/Figma/brandbook",
        "seeded locked resources",
        "Custom model/persona",
        "AVIF",
        "Lighthouse",
        "A/B/C",
        "static deterministic retrieval",
    ]:
        assert required in demo_script

    for name in [
        "avocado-black-friday.md",
        "onboarding-scheduled.md",
        "apparel-vip-product-launch.md",
    ]:
        path = ROOT / "demo" / "scenarios" / name
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Demo constraints" in content
        assert "Deterministic fallback" in content
