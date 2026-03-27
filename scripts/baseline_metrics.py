#!/usr/bin/env python3
"""
Generate a reproducible baseline metrics snapshot from FlowMind's SQLite database.

Usage:
  python scripts/baseline_metrics.py
  python scripts/baseline_metrics.py --db flowmind.db --out reports/baseline.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "flowmind.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports"


def query_one(cursor: sqlite3.Cursor, sql: str, params: tuple = ()):
    cursor.execute(sql, params)
    return cursor.fetchone()


def query_all(cursor: sqlite3.Cursor, sql: str, params: tuple = ()):
    cursor.execute(sql, params)
    return cursor.fetchall()


def safe_round(value, digits: int = 2):
    if value is None:
        return None
    return round(float(value), digits)


def compute_metrics(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    metrics = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_path": str(db_path),
        "counts": {},
        "features": {},
        "reviews": {},
        "timing": {},
        "integration": {},
    }

    metrics["counts"]["users"] = query_one(cur, "SELECT COUNT(*) AS c FROM users")["c"]
    metrics["counts"]["parsed_files"] = query_one(cur, "SELECT COUNT(*) AS c FROM parsed_files")["c"]
    metrics["counts"]["features"] = query_one(cur, "SELECT COUNT(*) AS c FROM features")["c"]
    metrics["counts"]["review_assignments"] = query_one(cur, "SELECT COUNT(*) AS c FROM review_assignments")["c"]
    metrics["counts"]["review_feedback"] = query_one(cur, "SELECT COUNT(*) AS c FROM review_feedback")["c"]

    quality_row = query_one(
        cur,
        """
        SELECT
            AVG(quality_score) AS avg_q,
            MIN(quality_score) AS min_q,
            MAX(quality_score) AS max_q
        FROM features
        """,
    )

    metrics["features"]["average_quality_score"] = safe_round(quality_row["avg_q"])
    metrics["features"]["min_quality_score"] = quality_row["min_q"]
    metrics["features"]["max_quality_score"] = quality_row["max_q"]

    status_rows = query_all(
        cur,
        "SELECT client_review_status, COUNT(*) AS c FROM features GROUP BY client_review_status ORDER BY c DESC",
    )
    metrics["features"]["client_review_status_distribution"] = {
        (row["client_review_status"] or "unknown"): row["c"] for row in status_rows
    }

    source_rows = query_all(
        cur,
        "SELECT source, COUNT(*) AS c FROM features GROUP BY source ORDER BY c DESC",
    )
    metrics["features"]["source_distribution"] = {
        (row["source"] or "unknown"): row["c"] for row in source_rows
    }

    features_with_file = query_one(
        cur,
        "SELECT COUNT(*) AS c FROM features WHERE file_id IS NOT NULL",
    )["c"]
    parsed_files_count = metrics["counts"]["parsed_files"]
    metrics["features"]["avg_features_per_file"] = (
        safe_round(features_with_file / parsed_files_count) if parsed_files_count else None
    )

    action_rows = query_all(
        cur,
        "SELECT action, COUNT(*) AS c FROM review_feedback GROUP BY action ORDER BY c DESC",
    )
    action_distribution = {(row["action"] or "unknown"): row["c"] for row in action_rows}
    metrics["reviews"]["action_distribution"] = action_distribution

    approve = action_distribution.get("approve", 0)
    reject = action_distribution.get("reject", 0)
    request_modification = action_distribution.get("request_modification", 0)
    decision_total = approve + reject + request_modification

    metrics["reviews"]["approval_rate"] = (
        safe_round(approve / decision_total, 4) if decision_total else None
    )
    metrics["reviews"]["decision_count"] = decision_total

    assignment_totals = query_one(
        cur,
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN submitted_at IS NOT NULL THEN 1 ELSE 0 END) AS completed
        FROM review_assignments
        """,
    )
    total_assignments = assignment_totals["total"] or 0
    completed_assignments = assignment_totals["completed"] or 0

    metrics["reviews"]["assignments_total"] = total_assignments
    metrics["reviews"]["assignments_completed"] = completed_assignments
    metrics["reviews"]["assignment_completion_rate"] = (
        safe_round(completed_assignments / total_assignments, 4) if total_assignments else None
    )

    duration_rows = query_all(
        cur,
        """
        SELECT
            (julianday(submitted_at) - julianday(created_at)) * 24.0 AS hours
        FROM review_assignments
        WHERE submitted_at IS NOT NULL
          AND created_at IS NOT NULL
        """,
    )

    durations = [float(row["hours"]) for row in duration_rows if row["hours"] is not None and row["hours"] >= 0]
    metrics["timing"]["avg_assignment_turnaround_hours"] = safe_round(mean(durations), 2) if durations else None
    metrics["timing"]["samples_for_turnaround"] = len(durations)

    integration_row = query_one(
        cur,
        """
        SELECT
            COUNT(*) AS runs,
            COALESCE(SUM(items_count), 0) AS items,
            COALESCE(SUM(success_count), 0) AS successes
        FROM integration_log
        """,
    )
    runs = integration_row["runs"] or 0
    items = integration_row["items"] or 0
    successes = integration_row["successes"] or 0

    metrics["integration"]["runs"] = runs
    metrics["integration"]["items_processed"] = items
    metrics["integration"]["items_successful"] = successes
    metrics["integration"]["success_rate"] = safe_round(successes / items, 4) if items else None

    conn.close()
    return metrics


def build_output_path(custom_output: Path | None) -> Path:
    if custom_output:
        custom_output.parent.mkdir(parents=True, exist_ok=True)
        return custom_output

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"baseline_metrics_{timestamp}.json"


def main():
    parser = argparse.ArgumentParser(description="Generate FlowMind baseline metrics snapshot.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database file")
    parser.add_argument("--out", type=Path, default=None, help="Output JSON path")
    args = parser.parse_args()

    db_path = args.db if args.db.is_absolute() else (PROJECT_ROOT / args.db)
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    metrics = compute_metrics(db_path)
    out_path = build_output_path(args.out if args.out and args.out.is_absolute() else (PROJECT_ROOT / args.out) if args.out else None)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"Baseline metrics saved to: {out_path}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
