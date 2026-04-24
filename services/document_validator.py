"""Document quality and SRS-validity checks used before extraction."""
import os
import re
from typing import List, Tuple

# Minimum SRS score accepted by the pre-model gate. Scores below this mean
# the text lacks enough SRS signals (modals, numbered requirements, tech vocab)
# to be worth feeding to the LLM/VLM pipeline.
_PRE_MODEL_MIN_SCORE = int(os.getenv("FLOWMIND_PRE_MODEL_MIN_SCORE", "25"))

# Below this number of non-whitespace characters, a document is treated as empty.
_EMPTY_MIN_CHARS = int(os.getenv("FLOWMIND_EMPTY_MIN_CHARS", "20"))
_EMPTY_MIN_WORDS = int(os.getenv("FLOWMIND_EMPTY_MIN_WORDS", "5"))

_IMAGE_ONLY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}


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
    
    # +10 points: common software engineering vocabulary
    tech_keywords = ["database", "server", "client", "api", "interface", "login", "auth", "security", 
                     "performance", "latency", "storage", "memory", "cpu", "cloud", "deployment", 
                     "testing", "validation", "verification"]
    if sum(1 for kw in tech_keywords if kw in lower) >= 5:
        score += 10
        reasons.append("Found common technical/SRS vocabulary (+10)")

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

    # -15 points: fewer than 30 words (reduced from 50 words/-30)
    if words < 30:
        score -= 15
        reasons.append(f"Very short content ({words} words < 30) (-15)")

    # -10 points: no sentence-ending periods
    if not re.search(r"\.", content):
        score -= 10
        reasons.append(
            "No sentence-ending periods found; "
            "text quality appears poor (-10)"
        )

    # Garbage check
    is_junk, junk_reason = is_garbage(content)
    # Reduce is_junk penalty to be more permissive
    if is_junk:
        score -= 15
        reasons.append("Contains patterns often seen in non-technical content.")

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
    
    # If very low score, reject
    if score < 10:
        is_rejected = True
        reject_reason = "Extremely low technical content detected."
    elif is_junk and score < 20:
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


def is_document_empty(text: str) -> Tuple[bool, str]:
    """
    Fast empty / near-empty detection used before any expensive analysis.
    Returns (is_empty, reason). Reason is empty string when not empty.
    """
    if text is None:
        return True, "Document has no extractable text content."
    # Strip whitespace and ASCII control characters
    cleaned = re.sub(r"[\s\x00-\x1f\x7f]+", "", text)
    if len(cleaned) == 0:
        return True, "Document has no extractable text content."
    if len(cleaned) < _EMPTY_MIN_CHARS:
        return True, (
            f"Document has almost no text content ("
            f"{len(cleaned)} non-whitespace chars)."
        )
    words = len(re.findall(r"\b[\w'-]+\b", text))
    if words < _EMPTY_MIN_WORDS:
        return True, (
            f"Document has too few words ({words}) to be a valid document."
        )
    return False, ""


def pre_model_gate(text: str, filename: str = "") -> Tuple[bool, dict]:
    """
    Rapid pre-model gate: reject empty and non-SRS documents quickly,
    BEFORE any LLM / VLM / embedding / heavy OCR work runs.

    Returns (should_reject, detail):
      - When should_reject is True, `detail` is shaped for HTTPException(detail=...)
        with keys: error, message, score, reasons, recommendation.
      - When should_reject is False, `detail` is the full SRS validation dict
        (same shape as validate_document_for_srs) so callers can keep using it
        for downstream logging / persistence.
    """
    # 1) Empty check first — cheapest and most common failure mode.
    is_empty, empty_reason = is_document_empty(text)
    if is_empty:
        return True, {
            "error": "DOCUMENT_EMPTY",
            "message": empty_reason,
            "score": 0,
            "reasons": [empty_reason],
            "recommendation": (
                "Upload a document that contains readable SRS-style text content."
            ),
        }

    ext = os.path.splitext(str(filename or ""))[1].lower()
    is_image_only = ext in _IMAGE_ONLY_EXTS

    v_res = validate_document_for_srs(text)

    # Image-only uploads (diagrams, UI mockups) often have short OCR text and
    # lack classic SRS modal keywords, but can still be valid SRS artifacts.
    # Only reject them if the underlying validator already flagged junk / garbage.
    if is_image_only:
        if v_res.get("is_rejected"):
            return True, {
                "error": "NON_SRS_DOCUMENT",
                "message": v_res.get("reject_reason")
                or "Image does not contain readable SRS-relevant content.",
                "score": v_res.get("srs_score"),
                "reasons": v_res.get("reasons"),
                "recommendation": v_res.get("recommendation"),
            }
        return False, v_res

    # 2) Text-bearing documents: use validator's built-in rejection...
    if v_res.get("is_rejected"):
        return True, {
            "error": "NON_SRS_DOCUMENT",
            "message": v_res.get("reject_reason")
            or "Document does not look like a Software Requirements Specification.",
            "score": v_res.get("srs_score"),
            "reasons": v_res.get("reasons"),
            "recommendation": v_res.get("recommendation"),
        }

    # 3) ... plus a stricter early-reject threshold so non-SRS docs that
    # squeak past the base validator are still stopped before the models run.
    score = int(v_res.get("srs_score") or 0)
    if score < _PRE_MODEL_MIN_SCORE:
        return True, {
            "error": "NON_SRS_DOCUMENT",
            "message": (
                "Document does not look like a Software Requirements Specification "
                f"(SRS score {score} below threshold {_PRE_MODEL_MIN_SCORE}). "
                "Please upload a requirements document."
            ),
            "score": score,
            "reasons": v_res.get("reasons"),
            "recommendation": v_res.get("recommendation"),
        }

    return False, v_res
