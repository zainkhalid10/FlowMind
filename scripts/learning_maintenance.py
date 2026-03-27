#!/usr/bin/env python3
"""
Automated self-learning maintenance pipeline for FlowMind.

What it does in one run:
1) Replays new review feedback into learning (incremental backfill).
2) Generates a fresh baseline metrics snapshot.
3) Generates a self-learning improvement report.
4) Persists run state for the next incremental execution.

Usage:
  python scripts/learning_maintenance.py
  python scripts/learning_maintenance.py --n-feedback 75
  python scripts/learning_maintenance.py --backfill-limit 200
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from baseline_metrics import compute_metrics
from self_learning_report import compute_report
from backfill_feedback_learning import process_feedback


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "flowmind.db"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_STATE_FILE = DEFAULT_REPORTS_DIR / "learning_maintenance_state.json"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp_path.replace(path)


def latest_baseline_file(reports_dir: Path) -> Path | None:
    candidates = sorted(reports_dir.glob("baseline_metrics_*.json"))
    return candidates[-1] if candidates else None


def write_baseline_snapshot(db_path: Path, reports_dir: Path) -> Path:
    metrics = compute_metrics(db_path)
    out = reports_dir / f"baseline_metrics_{now_stamp()}.json"
    save_json(out, metrics)
    return out


def run_pipeline(
    db_path: Path,
    reports_dir: Path,
    state_file: Path,
    n_feedback: int,
    backfill_limit: int,
    baseline_override: Path | None,
) -> dict:
    reports_dir.mkdir(parents=True, exist_ok=True)

    state = load_json(state_file)
    last_feedback_id = int(state.get("last_feedback_id", 0) or 0)

    baseline_file: Path | None = None
    if baseline_override:
        baseline_file = baseline_override
    else:
        persisted = state.get("baseline_file")
        if persisted:
            p = Path(persisted)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            if p.exists():
                baseline_file = p

    if baseline_file is None:
        baseline_file = latest_baseline_file(reports_dir)

    if baseline_file is None or not baseline_file.exists():
        baseline_file = write_baseline_snapshot(db_path, reports_dir)

    engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        backfill_summary = process_feedback(db, since_id=last_feedback_id, limit=backfill_limit)
    finally:
        db.close()

    current_baseline = write_baseline_snapshot(db_path, reports_dir)

    report = compute_report(db_path=db_path, baseline_path=baseline_file, n_feedback=n_feedback)
    report_path = reports_dir / f"self_learning_report_{now_stamp()}.json"
    save_json(report_path, report)

    run_summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "baseline_file": str(baseline_file),
        "current_baseline_file": str(current_baseline),
        "self_learning_report_file": str(report_path),
        "backfill": backfill_summary,
        "n_feedback": n_feedback,
        "backfill_limit": backfill_limit,
    }

    run_summary_path = reports_dir / f"learning_maintenance_run_{now_stamp()}.json"
    save_json(run_summary_path, run_summary)

    state_update = {
        "last_feedback_id": backfill_summary.get("last_feedback_id", last_feedback_id),
        "baseline_file": str(baseline_file),
        "last_run_utc": run_summary["generated_at_utc"],
        "last_run_file": str(run_summary_path),
        "last_report_file": str(report_path),
        "last_current_baseline_file": str(current_baseline),
    }
    save_json(state_file, state_update)

    run_summary["run_summary_file"] = str(run_summary_path)
    run_summary["state_file"] = str(state_file)
    return run_summary


def main():
    parser = argparse.ArgumentParser(description="Run FlowMind self-learning maintenance pipeline")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite DB")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="Directory for output reports")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE, help="Path for maintenance state file")
    parser.add_argument("--n-feedback", type=int, default=50, help="N feedback split for improvement report")
    parser.add_argument("--backfill-limit", type=int, default=0, help="Max new feedback rows to process per run (0 = all)")
    parser.add_argument("--baseline", type=Path, default=None, help="Optional fixed baseline JSON path")
    args = parser.parse_args()

    db_path = args.db if args.db.is_absolute() else PROJECT_ROOT / args.db
    reports_dir = args.reports_dir if args.reports_dir.is_absolute() else PROJECT_ROOT / args.reports_dir
    state_file = args.state_file if args.state_file.is_absolute() else PROJECT_ROOT / args.state_file
    baseline_override = None
    if args.baseline:
        baseline_override = args.baseline if args.baseline.is_absolute() else PROJECT_ROOT / args.baseline

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    summary = run_pipeline(
        db_path=db_path,
        reports_dir=reports_dir,
        state_file=state_file,
        n_feedback=max(1, int(args.n_feedback)),
        backfill_limit=max(0, int(args.backfill_limit)),
        baseline_override=baseline_override,
    )

    print("Learning maintenance completed.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
