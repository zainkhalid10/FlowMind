#!/usr/bin/env python3
"""
Performance benchmark for FlowMind.
Verifies NFR: "20-page document within 45 seconds on standard server hardware."
Run from project root: python scripts/benchmark_performance.py [--pdf path/to/file.pdf]
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

TARGET_SECONDS = 45.0


class MockUploadFile:
    """Minimal UploadFile for benchmark."""
    def __init__(self, path: Path):
        self.filename = path.name
        self._path = path

    async def read(self):
        with open(self._path, "rb") as f:
            return f.read()

    async def seek(self, offset: int):
        pass


async def run_benchmark(pdf_path: Path) -> dict:
    """Run full pipeline and return timing."""
    from database import SessionLocal, User, init_db
    from auth import get_password_hash
    from flowmind import _analyze_with_agent_internal, UPLOAD_DIR

    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "bench@test.com").first()
        if not user:
            user = User(
                email="bench@test.com",
                username="benchuser",
                hashed_password=get_password_hash("bench123"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        file = MockUploadFile(pdf_path)
        t0 = time.perf_counter()
        result = await _analyze_with_agent_internal(
            file, user_id=user.id, db_session=db
        )
        t1 = time.perf_counter()
        total = t1 - t0

        return {
            "total": total,
            "success": result.get("view_id") is not None or "response" in str(result),
            "result": result,
        }
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="FlowMind performance benchmark")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Path to PDF (default: FYP report or uploads)",
    )
    args = parser.parse_args()

    pdf_path = args.pdf
    if not pdf_path:
        candidates = [
            PROJECT_ROOT / "FYP1-FinalReport-F25_387-D-Flowmind.pdf",
            PROJECT_ROOT / "uploads" / "FYP1-FinalReport-F25_387-D-Flowmind.pdf",
        ]
        pdf_path = next((p for p in candidates if p.exists()), None)

    if not pdf_path or not pdf_path.exists():
        print("ERROR: No PDF found. Use: --pdf path/to/20page.pdf")
        print("  Or place FYP1-FinalReport-F25_387-D-Flowmind.pdf in project root.")
        sys.exit(1)

    page_count = 0
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
    except Exception:
        pass

    print(f"Benchmark: {pdf_path.name}")
    if page_count:
        print(f"  Pages: {page_count}")
    print(f"  Target: {TARGET_SECONDS}s (NFR: 20-page doc in 45s)")
    print()

    result = asyncio.run(run_benchmark(pdf_path))
    total = result["total"]
    passed = total <= TARGET_SECONDS

    print(f"  Total: {total:.1f}s")
    print(f"  Target: {TARGET_SECONDS}s")
    if passed:
        print(f"  Result: PASS")
    else:
        print(f"  Result: FAIL (exceeded by {total - TARGET_SECONDS:.1f}s)")
    print()
    print("Note: VLM on CPU can exceed 45s. With GPU or FLOWMIND_USE_VLM=false,")
    print("      OCR+RAG-only timing may meet the target.")


if __name__ == "__main__":
    main()
