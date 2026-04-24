"""
SRS-oriented requirement validation and documented classification basis.

Used to reject empty, garbage, or non-informative lines before persisting / showing
structured requirements. Optional strict mode requires classic SRS modal language.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Formats FlowMind is built for (IEEE-style SRS inputs: narrative + diagrams in office/PDF).
SRS_SUPPORTED_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
)


@dataclass
class RequirementValidationResult:
    accepted: bool
    reasons: List[str] = field(default_factory=list)
    codes: List[str] = field(default_factory=list)


def classification_basis_summary() -> str:
    """
    How functional vs non-functional (and related) categories are decided in this codebase.
    Mirrors the intent of rag_agent.RequirementsExtractionAgent._classify_requirement_improved.
    """
    return (
        "Classification basis (high level): "
        "(1) User / story phrasing ('As a …', 'I want …', 'so that') → user requirements. "
        "(2) Non-functional: quality attributes or measurable constraints — performance, latency, "
        "security, encryption, authentication, reliability, availability, scalability, usability, "
        "maintainability, portability, compatibility, or patterns like 'within N ms', uptime %, RPS, "
        "concurrent users — but not when the sentence is clearly about a business action "
        "(payment, booking, API call, calculation, etc.); those stay functional. "
        "(3) Business: policy, regulation, compliance, stakeholder, KPI-style wording. "
        "(4) Otherwise default to functional (system behaviour / capability). "
        "Extractor section headings also influence grouping before this refinement."
    )


def is_srs_supported_upload(filename: str) -> Tuple[bool, List[str]]:
    """Return (ok, reasons) for upload filename extension."""
    if not filename or not str(filename).strip():
        return False, ["EMPTY_FILENAME"]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SRS_SUPPORTED_EXTENSIONS:
        return False, [
            f"UNSUPPORTED_EXTENSION:{ext or '(none)'}",
            f"Expected one of: {', '.join(SRS_SUPPORTED_EXTENSIONS)}",
        ]
    return True, []


def _strict_srs_enabled() -> bool:
    return os.getenv("FLOWMIND_SRS_STRICT_VALIDATION", "0").strip() == "1"


def _letter_ratio(s: str) -> float:
    letters = sum(1 for c in s if c.isalpha())
    return letters / max(1, len(s))


def _non_alnum_ratio(s: str) -> float:
    """Share of chars that are not letters, digits, or whitespace."""
    if not s:
        return 1.0
    bad = sum(1 for c in s if not (c.isalnum() or c.isspace()))
    return bad / len(s)


def validate_requirement_statement(statement: str) -> RequirementValidationResult:
    """
    Reject garbage / empty / useless lines with explicit reasons.

    Strict SRS (FLOWMIND_SRS_STRICT_VALIDATION=1): require shall|must|will|should
    (case-insensitive) as a weak proxy for IEEE-style imperative requirements.
    """
    reasons: List[str] = []
    codes: List[str] = []

    raw = statement if isinstance(statement, str) else ""
    s = raw.strip()
    if not s:
        return RequirementValidationResult(False, ["Empty or whitespace-only text."], ["EMPTY"])

    if len(s) < 12:
        return RequirementValidationResult(
            False,
            [f"Too short ({len(s)} characters); likely not a complete requirement."],
            ["TOO_SHORT"],
        )

    # Repeated single character / keyboard mashing
    if re.search(r"(.)\1{7,}", s):
        return RequirementValidationResult(
            False,
            ["Repeated characters detected; treated as garbage input."],
            ["REPEATED_CHARS"],
        )

    low = s.lower()
    noise_phrases = (
        "lorem ipsum",
        "none found",
        "no requirements",
        "n/a",
        "todo:",
        "tbd",
        "placeholder",
    )
    if any(p in low for p in noise_phrases) and len(s) < 80:
        return RequirementValidationResult(
            False,
            ["Matches placeholder / empty-result phrasing."],
            ["PLACEHOLDER"],
        )

    nar = _non_alnum_ratio(s)
    if nar > 0.42:
        return RequirementValidationResult(
            False,
            [f"Too many symbols or non-alphanumeric characters ({nar:.0%}); likely OCR or diagram noise."],
            ["HIGH_SYMBOL_RATIO"],
        )

    lr = _letter_ratio(s)
    if lr < 0.35:
        return RequirementValidationResult(
            False,
            [f"Too few letters ({lr:.0%} of characters); likely not natural-language requirement text."],
            ["LOW_LETTER_RATIO"],
        )

    words = [w for w in re.split(r"\s+", s) if w]
    if len(words) < 3:
        return RequirementValidationResult(
            False,
            [f"Too few words ({len(words)}); not enough content to treat as a requirement."],
            ["TOO_FEW_WORDS"],
        )

    if _strict_srs_enabled():
        if not re.search(r"\b(shall|must|will|should)\b", low):
            return RequirementValidationResult(
                False,
                [
                    "Strict SRS validation is on: statement must include "
                    "a modal verb (shall / must / will / should)."
                ],
                ["STRICT_NO_MODAL_VERB"],
            )

    return RequirementValidationResult(True, [], ["OK"])


def partition_valid_requirements(
    items: Optional[List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split structured requirement dicts into accepted vs rejected.
    Rejected entries include original fields plus reasons/codes.
    """
    if not items:
        return [], []
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        stmt = str(item.get("statement") or "").strip()
        vr = validate_requirement_statement(stmt)
        if not vr.accepted:
            row = dict(item)
            row["validation_ok"] = False
            row["validation_reasons"] = vr.reasons
            row["validation_codes"] = vr.codes
            rejected.append(row)
            continue
        row = dict(item)
        row["validation_ok"] = True
        row["validation_codes"] = [c for c in vr.codes if c != "OK"] or ["OK"]
        accepted.append(row)
    return accepted, rejected
