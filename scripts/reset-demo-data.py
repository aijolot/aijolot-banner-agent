#!/usr/bin/env python3
"""Reset Aijolot demo state safely and idempotently.

Default behavior is local-only: remove deterministic runtime artifacts that are
created by demo/smoke scripts. It never deletes source files, migrations, seeds,
credentials, or user data.

Pass --supabase to additionally run `supabase db reset` when the Supabase CLI is
installed and Docker/Supabase services are available. The script reports the
real CLI result and never pretends that Supabase reset succeeded.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_RUNTIME_DIRS = [ROOT / "demo" / ".runtime"]
LOCAL_RUNTIME_FILES = [ROOT / ".aijolot-demo-smoke.json"]


def reset_local_artifacts() -> list[str]:
    removed: list[str] = []
    for path in LOCAL_RUNTIME_DIRS:
        if path.exists():
            shutil.rmtree(path)
            removed.append(str(path.relative_to(ROOT)))
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").write_text("# local deterministic demo runtime artifacts\n", encoding="utf-8")
    for path in LOCAL_RUNTIME_FILES:
        if path.exists():
            path.unlink()
            removed.append(str(path.relative_to(ROOT)))
    return removed


def run_supabase_reset() -> int:
    if shutil.which("supabase") is None:
        print("supabase db reset: SKIPPED (Supabase CLI not found on PATH)")
        return 2
    print("supabase db reset: running real Supabase CLI reset...")
    completed = subprocess.run(["supabase", "db", "reset"], cwd=ROOT, text=True)
    if completed.returncode == 0:
        print("supabase db reset: PASSED")
    else:
        print(f"supabase db reset: FAILED with exit code {completed.returncode}")
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset local deterministic demo data safely.")
    parser.add_argument("--local-only", action="store_true", help="Only reset local deterministic runtime artifacts (default).")
    parser.add_argument("--supabase", action="store_true", help="Also run real `supabase db reset` if available.")
    args = parser.parse_args(argv)

    removed = reset_local_artifacts()
    if removed:
        print("local deterministic runtime artifacts reset; removed: " + ", ".join(removed))
    else:
        print("local deterministic runtime artifacts reset; nothing to remove")

    if args.supabase:
        return run_supabase_reset()
    if not args.local_only:
        print("Supabase reset not requested. Re-run with --supabase for a real `supabase db reset`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
