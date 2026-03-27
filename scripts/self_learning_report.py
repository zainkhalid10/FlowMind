#!/usr/bin/env python3
"""
Generate a measured self-learning improvement report.

Compares baseline metrics with post-feedback windows using proxies:
- precision proxy = approval_rate
- approval rate
- turnaround hours

Usage:
  python scripts/self_learning_report.py --baseline reports/baseline_metrics_YYYYMMDD_HHMMSS.json --n-feedback 50
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "flowmind.db"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"


def safe_ratio(a: float, b: float):
    if b == 0:
        return None
    return a / b


def safe_delta(new_v, old_v):
    if new_v is None or old_v is None:
        return None
    return new_v - old_v


def fetch_feedback_rows(cur: sqlite3.Cursor):
    cur.execute(
        """
        SELECT id, action, created_at
        FROM review_feedback
        WHERE created_at IS NOT NULL
        ORDER BY datetime(created_at) ASC
        """
    )
    return cur.fetchall()


def action_metrics(rows):
    counts = {"approve": 0, "reject": 0, "request_modification": 0}
    for row in rows:
        action = (row["action"] or "").strip().lower()
        if action in counts:
            counts[action] += 1

    decisions = counts["approve"] + counts["reject"] + counts["request_modification"]
    approval_rate = safe_ratio(counts["approve"], decisions)

    return {
        "decision_count": decisions,
        "action_distribution": counts,
        "approval_rate": approval_rate,
        "precision_proxy": approval_rate,
    }


def turnaround_metrics(cur: sqlite3.Cursor, split_ts: str | None, before: bool):
    if not split_ts:
        cur.execute(
            """
            SELECT (julianday(submitted_at) - julianday(created_at)) * 24.0 AS hours
            FROM review_assignments
            WHERE submitted_at IS NOT NULL AND created_at IS NOT NULL
            """
        )
    else:
        if before:
            cur.execute(
                """
                SELECT (julianday(submitted_at) - julianday(created_at)) * 24.0 AS hours
                FROM review_assignments
                WHERE submitted_at IS NOT NULL
                  AND created_at IS NOT NULL
                  AND datetime(submitted_at) <= datetime(?)
                """,
                (split_ts,),
            )
        else:
            cur.execute(
                """
                SELECT (julianday(submitted_at) - julianday(created_at)) * 24.0 AS hours
                FROM review_assignments
                WHERE submitted_at IS NOT NULL
                  AND created_at IS NOT NULL
                  AND datetime(submitted_at) > datetime(?)
                """,
                (split_ts,),
            )

    rows = cur.fetchall()
    values = [float(r["hours"]) for r in rows if r["hours"] is not None and float(r["hours"]) >= 0]
    if not values:
        return {"samples": 0, "avg_hours": None}
    return {"samples": len(values), "avg_hours": sum(values) / len(values)}


def feature_quality_metrics(cur: sqlite3.Cursor, split_ts: str | None, before: bool):
    if not split_ts:
        cur.execute("SELECT AVG(quality_score) AS avg_q FROM features")
    else:
        if before:
            cur.execute(
                "SELECT AVG(quality_score) AS avg_q FROM features WHERE datetime(updated_at) <= datetime(?)",
                (split_ts,),
            )
        else:
            cur.execute(
                "SELECT AVG(quality_score) AS avg_q FROM features WHERE datetime(updated_at) > datetime(?)",
                (split_ts,),
            )
    row = cur.fetchone()
    return None if row is None or row["avg_q"] is None else float(row["avg_q"])


def compute_report(db_path: Path, baseline_path: Path, n_feedback: int):
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    feedback_rows = fetch_feedback_rows(cur)
    split_ts = None
    if feedback_rows and len(feedback_rows) >= n_feedback:
        split_ts = feedback_rows[n_feedback - 1]["created_at"]

    if split_ts:
        before_rows = feedback_rows[:n_feedback]
        after_rows = feedback_rows[n_feedback:]
    else:
        # If not enough feedbacks, use all as "after" and baseline as "before"
        before_rows = []
        after_rows = feedback_rows

    before_metrics = action_metrics(before_rows)
    after_metrics = action_metrics(after_rows)

    before_turnaround = turnaround_metrics(cur, split_ts, before=True)
    after_turnaround = turnaround_metrics(cur, split_ts, before=False)

    before_quality = feature_quality_metrics(cur, split_ts, before=True)
    after_quality = feature_quality_metrics(cur, split_ts, before=False)

    baseline_approval = (((baseline.get("reviews") or {}).get("approval_rate")))
    baseline_turnaround = (((baseline.get("timing") or {}).get("avg_assignment_turnaround_hours")))
    baseline_quality = (((baseline.get("features") or {}).get("average_quality_score")))

    current_all = action_metrics(feedback_rows)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_feedback_split": n_feedback,
        "db_path": str(db_path),
        "baseline_file": str(baseline_path),
        "split_timestamp": split_ts,
        "baseline": {
            "approval_rate": baseline_approval,
            "precision_proxy": baseline_approval,
            "turnaround_hours": baseline_turnaround,
            "avg_quality_score": baseline_quality,
        },
        "window_before_n_feedback": {
            **before_metrics,
            "turnaround": before_turnaround,
            "avg_quality_score": before_quality,
        },
        "window_after_n_feedback": {
            **after_metrics,
            "turnaround": after_turnaround,
            "avg_quality_score": after_quality,
        },
        "current_overall": {
            **current_all,
            "turnaround": turnaround_metrics(cur, split_ts=None, before=False),
            "avg_quality_score": feature_quality_metrics(cur, split_ts=None, before=False),
            "total_feedback_events": len(feedback_rows),
        },
        "improvement_vs_baseline": {
            "approval_rate_delta": safe_delta(current_all.get("approval_rate"), baseline_approval),
            "precision_proxy_delta": safe_delta(current_all.get("precision_proxy"), baseline_approval),
            "turnaround_hours_delta": safe_delta(
                (turnaround_metrics(cur, split_ts=None, before=False).get("avg_hours")),
                baseline_turnaround,
            ),
            "avg_quality_score_delta": safe_delta(
                feature_quality_metrics(cur, split_ts=None, before=False),
                baseline_quality,
            ),
        },
    }

    conn.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Generate self-learning improvement report")
    parser.add_argument("--baseline", type=Path, required=True, help="Path to baseline metrics JSON")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite DB")
    parser.add_argument("--n-feedback", type=int, default=50, help="Split point N for before/after feedback window")
    parser.add_argument("--out", type=Path, default=None, help="Optional output file path")
    args = parser.parse_args()

    db_path = args.db if args.db.is_absolute() else (PROJECT_ROOT / args.db)
    baseline_path = args.baseline if args.baseline.is_absolute() else (PROJECT_ROOT / args.baseline)

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    if not baseline_path.exists():
        raise SystemExit(f"Baseline file not found: {baseline_path}")

    report = compute_report(db_path, baseline_path, args.n_feedback)

    if args.out:
        out_path = args.out if args.out.is_absolute() else (PROJECT_ROOT / args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = DEFAULT_REPORTS_DIR / f"self_learning_report_{ts}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Self-learning report saved to: {out_path}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
