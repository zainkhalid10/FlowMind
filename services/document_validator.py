"""Document quality and SRS-validity checks used before extraction."""
import re
from typing import List


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def validate_document_for_srs(text: str) -> dict:
    """
    Returns:
    {
      is_srs: True/False,
      confidence: High/Medium/Low/None,
      srs_score: 0-100,
      reasons: [list of findings],
      recommendation: human readable message
    }
    """
    content = text or ""
    lower = content.lower()
    reasons: List[str] = []
    score = 0

    # +20 points: functional/non-functional headings
    if (
        "functional requirements" in lower
        or "non-functional requirements" in lower
    ):
        score += 20
        reasons.append(
            "Found SRS section marker: "
            "functional/non-functional requirements (+20)"
        )

    # +15 points: 5+ shall/must
    modal_hits = len(re.findall(r"\b(shall|must)\b", lower))
    if modal_hits >= 5:
        score += 15
        reasons.append(
            f"Found {modal_hits} requirement modals "
            "(shall/must) (+15)"
        )

    # +10 points: system/user/stakeholder terms
    if all(token in lower for token in ("system", "user", "stakeholder")):
        score += 10
        reasons.append("Found system/user/stakeholder perspective terms (+10)")

    # +10 points: numbered requirements patterns
    if re.search(
        r"\b\d+\.\d+\b|\bFR-\d+|\bNFR-\d+|\bREQ-\d+",
        content,
        re.IGNORECASE,
    ):
        score += 10
        reasons.append(
            "Found structured requirement IDs/numbering "
            "(1.1/FR-/NFR-/REQ-) (+10)"
        )

    # +10 points: scope/objective/introduction
    if all(token in lower for token in ("scope", "objective", "introduction")):
        score += 10
        reasons.append("Found scope/objective/introduction sections (+10)")

    words = _word_count(content)

    # +5 points: length over 500 words
    if words > 500:
        score += 5
        reasons.append(f"Document length is {words} words (>500) (+5)")

    # -20 points: mostly references/citations patterns
    citation_hits = len(re.findall(r"\[\d+\]|\bet\s+al\.|\bdoi:\b", lower))
    if citation_hits >= 5:
        score -= 20
        reasons.append(
            "High citation/reference density detected "
            "([n], et al., doi:) (-20)"
        )

    # -30 points: fewer than 50 words
    if words < 50:
        score -= 30
        reasons.append(f"Very short content ({words} words < 50) (-30)")

    # -20 points: no sentence-ending periods
    if not re.search(r"\.", content):
        score -= 20
        reasons.append(
            "No sentence-ending periods found; "
            "text quality appears poor (-20)"
        )

    # Clamp score to 0-100
    score = max(0, min(100, score))

    if score >= 70:
        confidence = "High"
        is_srs = True
        recommendation = "SRS document detected. Extraction confidence is high."
    elif score >= 40:
        confidence = "Medium"
        is_srs = True
        recommendation = "Partial SRS document. Some requirements may be missed."
    elif score >= 10:
        confidence = "Low"
        is_srs = False
        recommendation = "This may not be an SRS document. Review results carefully."
    else:
        confidence = "None"
        is_srs = False
        recommendation = (
            "This does not appear to be an SRS document. "
            "Very few or no requirements expected."
        )

    if not reasons:
        reasons.append("No strong SRS markers were found.")

    return {
        "is_srs": is_srs,
        "confidence": confidence,
        "srs_score": score,
        "reasons": reasons,
        "recommendation": recommendation,
    }
