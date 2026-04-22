"""Document quality and SRS-validity checks used before extraction."""
import re
from typing import List


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def is_garbage(text: str) -> tuple[bool, str]:
    """
    Check if text is likely gibberish or garbage.
    Returns (is_garbage, reason).
    """
    if not text or len(text.strip()) < 10:
        return True, "Content too short"

    # Repeated characters (e.g., "aaaaaaaaa")
    if re.search(r"(.)\1{10,}", text):
        return True, "High repetition of single characters detected"

    # Too many non-alphanumeric characters (excluding whitespace)
    total_chars = len(text)
    alnum_chars = len(re.findall(r"[a-zA-Z0-9\s]", text))
    symbol_ratio = (total_chars - alnum_chars) / total_chars
    if symbol_ratio > 0.4:
        return True, f"Too many symbols/noise ({symbol_ratio:.1%})"

    # Word distribution (junk words)
    words = text.lower().split()
    if len(words) > 0:
        noise_words = {"asdf", "hjkl", "qwerty", "zxcv"}
        noise_count = sum(1 for w in words if any(n in w for n in noise_words))
        if noise_count / len(words) > 0.2:
            return True, "Likely keyboard mashing / nonsensical words"

    return False, ""


def detect_thematic_mismatch(text: str) -> tuple[int, list[str]]:
    """
    Detect if the document is clearly about a non-technical theme.
    Returns (score_penalty, findings).
    """
    lower = text.lower()
    penalty = 0
    findings = []

    # Non-technical themes (negative markers)
    themes = {
        "lifestyle": (["recipe", "ingredients", "cooking", "fashion", "travel", "vlog"], 20),
        "entertainment": (["movie", "actor", "celebrity", "sports", "football", "gameplay"], 15),
        "nonsense": (["lorem ipsum", "dolor sit amet"], 30)
    }

    for theme, (keywords, weight) in themes.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits >= 3:
            penalty += weight
            findings.append(f"Detected non-technical theme: {theme} (-{weight})")

    return penalty, findings


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

    # +15 points: 3+ shall/must (lowered from 5)
    modal_hits = len(re.findall(r"\b(shall|must|should|will)\b", lower))
    if modal_hits >= 3:
        score += 15
        reasons.append(
            f"Found {modal_hits} requirement modals "
            "(shall/must/should/will) (+15)"
        )
    elif modal_hits >= 1:
        score += 5
        reasons.append(f"Found {modal_hits} requirement modal(s) (+5)")

    # +10 points: system/user/stakeholder terms (plural-resilient)
    if all(re.search(fr"\b{token}s?\b", lower) for token in ("system", "user", "stakeholder")):
        score += 10
        reasons.append("Found system/user/stakeholder perspective terms (+10)")

    # +15 points: numbered requirements patterns (increased from 10)
    if re.search(
        r"\b\d+\.\d+\b|\bFR[- ]\d+|\bNFR[- ]\d+|\bREQ[- ]\d+",
        content,
        re.IGNORECASE,
    ):
        score += 15
        reasons.append(
            "Found structured requirement IDs/numbering "
            "(1.1/FR-/NFR-/REQ-) (+15)"
        )

    # +10 points: scope or objective or introduction (any 2 of 3)
    found_intro = [t for t in ("scope", "objective", "introduction") if t in lower]
    if len(found_intro) >= 2:
        score += 10
        reasons.append(f"Found document structure markers ({', '.join(found_intro)}) (+10)")

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

    # Garbage check
    is_junk, junk_reason = is_garbage(content)
    if is_junk:
        score -= 50
        reasons.append(f"Garbage detection: {junk_reason} (-50)")

    # Thematic check
    theme_penalty, theme_findings = detect_thematic_mismatch(content)
    if theme_penalty > 0:
        score -= theme_penalty
        reasons.extend(theme_findings)

    # Clamp score to 0-100
    score = max(0, min(100, score))

    # Strict rejection logic
    is_rejected = False
    reject_reason = ""
    
    if score < 15:
        is_rejected = True
        reject_reason = "Document score too low to be a valid technical/SRS document."
    elif is_junk and score < 30:
        is_rejected = True
        reject_reason = "High likelihood of garbage/noise content."

    if score >= 70:
        confidence = "High"
        is_srs = True
        recommendation = "SRS document detected. Extraction confidence is high."
    elif score >= 40:
        confidence = "Medium"
        is_srs = True
        recommendation = "Partial SRS document. Some requirements may be missed."
    elif score >= 15:
        confidence = "Low"
        is_srs = False
        recommendation = "This may not be an SRS document. Review results carefully."
    else:
        confidence = "None"
        is_srs = False
        recommendation = (
            "This does not appear to be an SRS document. "
            "Rejection highly recommended."
        )

    if not reasons:
        reasons.append("No strong SRS markers were found.")

    return {
        "is_srs": is_srs,
        "is_rejected": is_rejected,
        "reject_reason": reject_reason,
        "confidence": confidence,
        "srs_score": score,
        "reasons": reasons,
        "recommendation": recommendation,
    }
