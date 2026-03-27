#!/usr/bin/env python3
"""
Backfill self-learning from historical review feedback.

This script replays existing review feedback into the agent's
feedback learning loop so future extractions benefit from past decisions.

Usage:
  python scripts/backfill_feedback_learning.py
  python scripts/backfill_feedback_learning.py --since-id 120
  python scripts/backfill_feedback_learning.py --limit 200
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Ensure project root import path
PROJECT_ROOT = Path(__file__).resolve().parent.parent

import os
import sys

sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from sqlalchemy.orm import Session

from database import Feature, ReviewAssignment, ReviewFeedback, SessionLocal
from rag_agent import get_agent


def process_feedback(db: Session, since_id: int = 0, limit: int = 0) -> dict:
    query = db.query(ReviewFeedback).filter(ReviewFeedback.id > since_id).order_by(ReviewFeedback.id.asc())
    if limit and limit > 0:
        query = query.limit(limit)

    rows = query.all()

    total = 0
    updated_total = 0
    promoted_total = 0
    demoted_total = 0
    per_action = {"approve": 0, "reject": 0, "request_modification": 0}

    for rf in rows:
        feature = db.query(Feature).filter(Feature.id == rf.req_id).first()
        if not feature:
            continue

        assignment = db.query(ReviewAssignment).filter(ReviewAssignment.file_id == rf.file_id).order_by(ReviewAssignment.created_at.desc()).first()
        owner_user_id = getattr(feature, "user_id", None) or (assignment.manager_id if assignment else None)

        if owner_user_id is None:
            continue

        agent = get_agent(user_id=owner_user_id)
        result = agent.learn_from_feedback(
            feature_text=feature.description or "",
            category=feature.category or "features",
            action=rf.action or "",
            title=(feature.title or "").strip(),
            comment=rf.comment or "",
            file_id=rf.file_id,
            req_id=rf.req_id,
        )

        total += 1
        action = (rf.action or "").strip().lower()
        if action in per_action:
            per_action[action] += 1

        updated_total += int(result.get("updated_patterns", 0) or 0)
        promoted_total += int(result.get("promoted_patterns", 0) or 0)
        demoted_total += int(result.get("demoted_patterns", 0) or 0)

    return {
        "processed_feedback_rows": total,
        "updated_patterns": updated_total,
        "promoted_patterns": promoted_total,
        "demoted_patterns": demoted_total,
        "actions": per_action,
        "last_feedback_id": rows[-1].id if rows else since_id,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill feedback-driven self-learning from review history")
    parser.add_argument("--since-id", type=int, default=0, help="Only process feedback rows with id greater than this")
    parser.add_argument("--limit", type=int, default=0, help="Max feedback rows to process")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = process_feedback(db, since_id=args.since_id, limit=args.limit)
        print("Backfill complete")
        for k, v in summary.items():
            print(f"{k}: {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
