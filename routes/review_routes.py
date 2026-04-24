"""Client review workflow routes."""
import asyncio
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
import requests
from sqlalchemy.orm import Session

from auth import get_current_user, get_db
from database import Feature, ParsedFile, ReviewAssignment, ReviewFeedback, SessionLocal, User
from rag_agent import get_agent
from services.export_service import auto_export_after_approval, remove_from_pending_export_queue

router = APIRouter()


class ReviewActionRequest(BaseModel):
    req_id: int
    action: str
    comment: Optional[str] = None


class AddRequirementRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    category: str
    priority: str = "Medium"


class SetPriorityRequest(BaseModel):
    req_id: int
    priority: str


class ResolveFeedbackRequest(BaseModel):
    resolved: bool = True
    manager_note: Optional[str] = None


class SubmitReviewRequest(BaseModel):
    summary_note: Optional[str] = None


class ManagerCreateRequirementRequest(BaseModel):
    file_id: int
    title: str
    description: Optional[str] = ""
    category: str = "functional"
    priority: str = "Medium"
    source: str = "client_approved"


class RequirementUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None


class InviteClientRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    file_id: int


class AiRefineRequest(BaseModel):
    """Client asks the AI to rewrite a requirement given their instructions."""
    instruction: str


def _ensure_client(user: User):
    if (getattr(user, "role", "") or "").lower() != "client":
        raise HTTPException(status_code=403, detail="Client role required")


def _ensure_manager(user: User):
    if (getattr(user, "role", "") or "").lower() != "manager":
        raise HTTPException(status_code=403, detail="Manager role required")


def _action_to_status(action: str) -> str:
    mapping = {
        "approve": "approved",
        "reject": "rejected",
        "request_modification": "modification_requested",
    }
    return mapping.get(action, "pending")


def is_meaningful_feedback(comment: str) -> bool:
    # Too short
    if len((comment or "").strip()) < 10:
        return False
    # All same character
    compact = (comment or "").replace(" ", "")
    if len(set(compact)) < 4:
        return False
    # No real words (check against common English words)
    words = (comment or "").lower().split()
    common = {
        "the", "system", "should", "must", "shall", "requirement", "change",
        "please", "need", "want", "add", "remove", "update", "incorrect",
        "wrong", "missing", "unclear", "improve", "fix", "this", "is", "not",
        "a", "an", "to", "of", "and", "or", "it", "be", "for", "with", "that",
    }
    real_words = sum(1 for w in words if w in common or len(w) > 3)
    if real_words < 2:
        return False
    return True


def _req_title(feature: Feature) -> str:
    title = (getattr(feature, "title", None) or "").strip()
    if title:
        return title
    desc = (feature.description or "").strip()
    if not desc:
        return f"Requirement {feature.id}"
    first_line = desc.split("\n")[0].strip()
    candidate = first_line.split(".")[0].strip()
    candidate = candidate.replace("The system shall", "").replace("The system must", "").strip()
    candidate = candidate.replace("The application shall", "").replace("The application must", "").strip()
    candidate = candidate.replace("System shall", "").replace("System must", "").strip()
    if not candidate:
        candidate = first_line
    if len(candidate) > 120:
        candidate = candidate[:117].rstrip() + "..."
    return candidate or f"Requirement {feature.id}"


def _normalize_feature_category(category: str) -> str:
    raw = (category or "").strip().lower().replace("_", "-")
    if raw in ("functional", "non-functional", "business", "system"):
        return raw
    return "functional"


def _priority_label(priority: str) -> str:
    raw = (priority or "").strip().lower()
    if raw == "high":
        return "High"
    if raw == "low":
        return "Low"
    return "Medium"


def _extract_revision_pair(manager_note: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    note = (manager_note or "").strip()
    if not note:
        return None, None
    before_marker = "AUTO_REVISION_BEFORE::"
    after_marker = "AUTO_REVISION_AFTER::"
    if before_marker not in note or after_marker not in note:
        return None, None
    try:
        before_part = note.split(before_marker, 1)[1].split(after_marker, 1)[0].strip()
        after_part = note.split(after_marker, 1)[1].strip()
        return (before_part or None), (after_part or None)
    except Exception:
        return None, None


def _rewrite_requirement_with_feedback(feature: Feature, feedback_comment: str) -> str:
    prompt = f"""
Original requirement: {feature.description or ""}
Client requested change: {feedback_comment or ""}
Rewrite this requirement incorporating the client feedback.
Keep SHALL/MUST language. Output only the rewritten requirement.
""".strip()

    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": os.getenv("FLOWMIND_OLLAMA_MODEL", "llama3:8b"), "prompt": prompt, "stream": False},
            timeout=8,
        )
        if resp.ok:
            text = (resp.json().get("response") or "").strip()
            if text:
                return text
    except Exception:
        pass

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.getenv("FLOWMIND_OPENROUTER_MODEL", "meta-llama/llama-3.1-70b-instruct"),
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=10,
            )
            if resp.ok:
                text = (((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
                if text:
                    return text
        except Exception:
            pass

    # Deterministic fallback: always incorporate the client comment.
    base = (feature.description or "").strip()
    if not base:
        base = (feature.title or "").strip() or f"Requirement {feature.id}"
    comment = (feedback_comment or "").strip()
    if " shall " in base.lower() or " must " in base.lower():
        if comment:
            return f"{base.rstrip('.')} The system SHALL incorporate this client-requested change: {comment}."
        return base
    if comment:
        return f"The system SHALL {base[0].lower() + base[1:] if base else 'be updated'} It SHALL incorporate this client-requested change: {comment}."
    return f"The system SHALL {base[0].lower() + base[1:] if base else 'be updated'}."


def process_feedback_automatically(feedback_id: int) -> dict:
    """Process feedback immediately and return the updated requirement snapshot."""
    db = SessionLocal()
    try:
        db_feedback = db.query(ReviewFeedback).filter(ReviewFeedback.id == feedback_id).first()
        if not db_feedback:
            return {"processed": False, "reason": "feedback_not_found"}
        feature = db.query(Feature).filter(Feature.id == db_feedback.req_id).first()
        if not feature:
            return {"processed": False, "reason": "requirement_not_found"}

        action = (db_feedback.action or "").strip().lower()
        owner_user_id = getattr(feature, "user_id", None) or db_feedback.client_id
        agent = get_agent(user_id=owner_user_id)
        auto_note = None

        if action == "approve":
            feature.client_review_status = "approved"
            feature.status = "approved"
            feature.manager_attention = 0
            feature.suggested_revision = None
            agent.learn_from_feedback(
                feature_text=feature.description or "",
                category=feature.category or "features",
                action="approve",
                title=_req_title(feature),
                comment=(db_feedback.comment or "").strip(),
                file_id=feature.file_id,
                req_id=feature.id,
            )
            # Reinforce positive example with a stronger second pass.
            agent.learn_from_feedback(
                feature_text=feature.description or "",
                category=feature.category or "features",
                action="approve",
                title=_req_title(feature),
                comment="positive_learning_boost",
                file_id=feature.file_id,
                req_id=feature.id,
            )
            auto_export_after_approval(db, feature)
            db_feedback.resolved = 1
            db_feedback.manager_note = "Auto-resolved by system after client approval"
            db_feedback.resolved_at = datetime.utcnow()
            auto_note = "Auto-approved and exported where integrations are connected"
            print("Auto-exported to Jira/Trello after client approval")

        elif action == "reject":
            feature.client_review_status = "rejected"
            feature.status = "denied"
            feature.manager_attention = 0
            db_feedback.resolved = 1
            db_feedback.manager_note = "Auto-resolved by system after client rejection"
            db_feedback.resolved_at = datetime.utcnow()
            remove_from_pending_export_queue(feature.id)
            agent.learn_from_feedback(
                feature_text=feature.description or "",
                category=feature.category or "features",
                action="reject",
                title=_req_title(feature),
                comment=(db_feedback.comment or "").strip(),
                file_id=feature.file_id,
                req_id=feature.id,
            )
            auto_note = "Auto-rejected and removed from export queue"
            print("Requirement rejected and removed from export queue")

        elif action == "request_modification":
            feature.client_review_status = "pending"
            feature.status = "pending"
            # Keep manager attention on modifications so the manager sees
            # exactly which requirements were iteratively changed.
            feature.manager_attention = 1
            previous_description = (feature.description or "").strip()
            rewritten = _rewrite_requirement_with_feedback(feature, db_feedback.comment or "")
            feature.suggested_revision = rewritten
            if rewritten:
                feature.description = rewritten
                feature.title = None
                feature.title = _req_title(feature)
            db_feedback.resolved = 1
            db_feedback.manager_note = (
                "Auto-resolved by system with AI revision and sent back to client\n"
                f"AUTO_REVISION_BEFORE::{previous_description}\n"
                f"AUTO_REVISION_AFTER::{feature.description or ''}"
            )
            db_feedback.resolved_at = datetime.utcnow()
            agent.learn_from_feedback(
                feature_text=feature.description or "",
                category=feature.category or "features",
                action="request_modification",
                title=_req_title(feature),
                comment=(db_feedback.comment or "").strip(),
                file_id=feature.file_id,
                req_id=feature.id,
            )
            auto_note = "Requirement auto-rewritten from client comment and re-queued for client review"
            print(f"Auto-revised requirement {feature.id} and queued for client re-review")

        feature.updated_at = datetime.utcnow()
        db.commit()
        return {
            "processed": True,
            "feedback_id": db_feedback.id,
            "action": action,
            "auto_note": auto_note,
            "requirement": {
                "req_id": feature.id,
                "title": _req_title(feature),
                "description": feature.description or "",
                "suggested_revision": getattr(feature, "suggested_revision", None),
                "category": (feature.category or "functional").lower(),
                "priority": feature.priority or "Medium",
                "review_status": feature.client_review_status or "pending",
                "manager_attention": bool(getattr(feature, "manager_attention", 0)),
                "feedback_resolved": bool(getattr(db_feedback, "resolved", 0)),
                "feedback_comment": db_feedback.comment or "",
            },
        }
    except Exception as e:
        db.rollback()
        print(f"⚠️ process_feedback_automatically failed for feedback_id={feedback_id}: {e}")
        return {"processed": False, "reason": "processing_error", "error": str(e)}
    finally:
        db.close()


def _latest_assignment_for_manager(db: Session, file_id: int, manager_id: int) -> Optional[ReviewAssignment]:
    assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.manager_id == manager_id,
    ).all()
    if not assignments:
        return None

    def _sort_key(row: ReviewAssignment):
        submitted = row.submitted_at or datetime.min
        created = row.created_at or datetime.min
        has_submitted = 1 if row.submitted_at else 0
        return (has_submitted, submitted, created)

    return max(assignments, key=_sort_key)


def _manager_can_access_feature(db: Session, manager_id: int, feature: Feature) -> bool:
    if not feature:
        return False
    if feature.user_id == manager_id:
        return True
    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == feature.file_id,
        ReviewAssignment.manager_id == manager_id,
    ).first()
    return assignment is not None


@router.get("/review/{file_id}")
async def get_review_requirements(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Client view: get requirements assigned for review."""
    _ensure_client(current_user)

    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.client_id == current_user.id,
    ).order_by(ReviewAssignment.created_at.desc()).first()

    if not assignment:
        raise HTTPException(status_code=403, detail="No review assignment for this document")

    features = db.query(Feature).filter(Feature.file_id == file_id).order_by(Feature.created_at.asc()).all()

    rows = []
    for f in features:
        latest_feedback = db.query(ReviewFeedback).filter(
            ReviewFeedback.file_id == file_id,
            ReviewFeedback.req_id == f.id,
            ReviewFeedback.client_id == current_user.id,
        ).order_by(ReviewFeedback.created_at.desc()).first()

        review_status = getattr(f, "client_review_status", None) or "pending"
        client_comment = (latest_feedback.comment if latest_feedback else "") or ""
        if latest_feedback and not bool(getattr(latest_feedback, "resolved", 0)):
            review_status = _action_to_status(latest_feedback.action)

        rows.append({
            "req_id": f.id,
            "category": (f.category or "functional").lower(),
            "title": _req_title(f),
            "description": f.description or "",
            "priority": getattr(f, "priority", None) or "Medium",
            "review_status": review_status,
            "client_comment": client_comment,
            "source": getattr(f, "source", None) or "system",
            "suggested_revision": getattr(f, "suggested_revision", None),
            "auto_resolved": bool(getattr(latest_feedback, "resolved", 0)) if latest_feedback else False,
            "feedback_date": latest_feedback.created_at.isoformat() if latest_feedback else None,
            "classification_reason": getattr(f, "classification_reason", None),
            "classification_method": getattr(f, "classification_method", None),
            "classification_confidence_label": getattr(f, "classification_confidence_label", None),
        })

    manager = db.query(User).filter(User.id == assignment.manager_id).first()
    file_row = db.query(ParsedFile).filter(ParsedFile.id == file_id).first()

    return {
        "file_id": file_id,
        "filename": file_row.filename if file_row else f"File {file_id}",
        "manager_name": (manager.username if manager else "Project Manager"),
        "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
        "submitted_at": assignment.submitted_at.isoformat() if assignment.submitted_at else None,
        "requirements": rows,
    }


@router.post("/review/{file_id}/action")
async def submit_review_action(
    file_id: int,
    payload: ReviewActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Client action on a requirement: approve, reject, request modification."""
    _ensure_client(current_user)

    action = (payload.action or "").strip().lower()
    if action not in ("approve", "reject", "request_modification"):
        raise HTTPException(status_code=400, detail="Invalid action")
    if action == "request_modification" and not (payload.comment or "").strip():
        raise HTTPException(status_code=400, detail="Comment is required for modification request")
    if (payload.comment or "").strip() and not is_meaningful_feedback((payload.comment or "").strip()):
        raise HTTPException(
            status_code=400,
            detail=(
                "Your comment does not appear to be meaningful feedback. "
                "Please describe the specific change you want made to this requirement."
            ),
        )

    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.client_id == current_user.id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="No review assignment for this document")

    feature = db.query(Feature).filter(Feature.id == payload.req_id, Feature.file_id == file_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Requirement not found")

    feedback = ReviewFeedback(
        file_id=file_id,
        req_id=payload.req_id,
        client_id=current_user.id,
        action=action,
        comment=(payload.comment or "").strip() or None,
    )
    db.add(feedback)

    feature.client_review_status = _action_to_status(action)
    if feedback.comment:
        feature.feedback = feedback.comment
    feature.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(feedback)
    auto_result = process_feedback_automatically(feedback.id)
    db.refresh(feature)

    return {
        "feedback_id": feedback.id,
        "req_id": payload.req_id,
        "action": action,
        "review_status": feature.client_review_status,
        "client_comment": feedback.comment or "",
        "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
        "learning_update": {"status": "processed"},
        "auto_processing": auto_result,
    }


@router.post("/review/{file_id}/set-priority")
async def set_requirement_priority(
    file_id: int,
    payload: SetPriorityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Client can suggest priority for a requirement in assigned file."""
    _ensure_client(current_user)

    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.client_id == current_user.id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="No review assignment for this document")

    normalized_priority = (payload.priority or "").strip().capitalize()
    if normalized_priority not in ("High", "Medium", "Low"):
        raise HTTPException(status_code=400, detail="priority must be High, Medium, or Low")

    feature = db.query(Feature).filter(Feature.id == payload.req_id, Feature.file_id == file_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Requirement not found")

    feature.priority = normalized_priority
    feature.updated_at = datetime.utcnow()
    db.commit()

    return {"req_id": feature.id, "priority": feature.priority}


@router.post("/review/{file_id}/add-requirement")
async def add_client_requirement(
    file_id: int,
    payload: AddRequirementRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Client can add a new requirement to assigned file."""
    _ensure_client(current_user)

    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.client_id == current_user.id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="No review assignment for this document")

    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")

    description = (payload.description or "").strip() or title
    agent = get_agent(user_id=assignment.manager_id or current_user.id)
    # Do not hard-block client-added requirements on strict NLP validation.
    # Keep intake smooth for demos/review workflows and classify anyway.
    is_valid = agent._is_valid_requirement(description, source="text")

    auto_category = _normalize_feature_category(agent._classify_requirement_improved(description))
    auto_priority = _priority_label(agent._infer_priority(description))

    parsed_file = db.query(ParsedFile).filter(ParsedFile.id == file_id).first()
    if not parsed_file:
        raise HTTPException(status_code=404, detail="File not found")

    feature = Feature(
        user_id=current_user.id,
        project_id=getattr(parsed_file, "project_id", None),
        file_id=file_id,
        category=auto_category,
        title=title,
        description=description,
        priority=auto_priority,
        source="client",
        client_review_status="pending_manager_approval",
        manager_attention=1,
        status="pending",
        quality_score=0,
        feedback=(
            "Client added requirement pending manager review"
            if is_valid
            else "Client added requirement captured (validation soft-failed); pending manager review"
        ),
    )
    db.add(feature)
    db.commit()
    db.refresh(feature)

    return {
        "req_id": feature.id,
        "title": feature.title,
        "description": feature.description,
        "category": feature.category,
        "priority": feature.priority,
        "review_status": feature.client_review_status,
        "source": feature.source,
        "manager_attention": bool(getattr(feature, "manager_attention", 0)),
    }


@router.post("/review/{file_id}/requirements/{req_id}/ai-refine")
async def ai_refine_requirement(
    file_id: int,
    req_id: int,
    payload: AiRefineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Client-only: use the LLM (Groq → Ollama fallback) to rewrite the
    requirement's description based on the client's modification prompt.
    Returns the suggested text WITHOUT persisting it — the client previews
    and submits it through the normal /review/{id}/action flow."""
    _ensure_client(current_user)

    instruction = (payload.instruction or "").strip()
    if len(instruction) < 10:
        raise HTTPException(
            status_code=400,
            detail="Please describe the change you want in a full sentence (at least 10 characters).",
        )

    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.client_id == current_user.id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="No review assignment for this document")

    feature = (
        db.query(Feature)
        .filter(Feature.id == req_id, Feature.file_id == file_id)
        .first()
    )
    if not feature:
        raise HTTPException(status_code=404, detail="Requirement not found")

    parsed_file = db.query(ParsedFile).filter(ParsedFile.id == file_id).first()
    doc_summary = (parsed_file.summary or "")[:600] if parsed_file else ""

    prompt = (
        "You are a senior requirements analyst. A client is asking for a rewrite of "
        "ONE software requirement. Preserve the original intent and category — only "
        "apply the change they requested.\n\n"
        f"Document context (first 600 chars):\n{doc_summary}\n\n"
        f"Original requirement (category={feature.category or 'functional'}, "
        f"priority={getattr(feature, 'priority', None) or 'Medium'}):\n"
        f"{feature.description or ''}\n\n"
        f"Client's modification request:\n{instruction}\n\n"
        "Rewrite the requirement in ONE concise sentence using an imperative "
        "modal verb (shall/must/should). Do not add explanations, preambles, "
        "bullet points, or headings. Output only the rewritten requirement.\n\n"
        "Rewritten requirement:"
    )

    agent = get_agent()
    refined = None
    # Prefer Groq via the agent helper — fastest + best quality.
    try:
        refined = agent._call_groq(prompt, timeout=30)
    except Exception:
        refined = None

    # Fall back to local Ollama if Groq is unreachable.
    if not refined:
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": agent._resolve_ollama_model(),
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=45,
            )
            if resp.ok:
                out = (resp.json().get("response") or "").strip()
                refined = out or None
        except Exception:
            refined = None

    if not refined:
        raise HTTPException(
            status_code=502,
            detail="AI service unavailable. Try typing your change directly into the comment instead.",
        )

    # Strip any leading label the LLM might add ("Rewritten requirement:" etc.)
    cleaned = refined.strip()
    for prefix in (
        "rewritten requirement:",
        "requirement:",
        "updated requirement:",
        "here is the rewritten requirement:",
    ):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    # Strip surrounding quotes
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()

    return {
        "req_id": req_id,
        "file_id": file_id,
        "original": feature.description or "",
        "refined": cleaned,
        "instruction": instruction,
    }


@router.post("/review/{file_id}/submit")
async def submit_review(
    file_id: int,
    payload: Optional[SubmitReviewRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Client submits review completion."""
    _ensure_client(current_user)

    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.client_id == current_user.id,
    ).order_by(ReviewAssignment.created_at.desc()).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="No review assignment for this document")

    assignment.submitted_at = datetime.utcnow()
    db.commit()

    return {
        "status": "submitted",
        "submitted_at": assignment.submitted_at.isoformat() if assignment.submitted_at else None,
    }


@router.get("/review/{file_id}/summary")
async def review_summary_for_manager(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager summary of client review for a specific document."""
    _ensure_manager(current_user)

    assignment = _latest_assignment_for_manager(db, file_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=404, detail="No client assignment for this file")

    features = db.query(Feature).filter(Feature.file_id == file_id).all()

    approved = 0
    rejected = 0
    modification_requested = 0
    pending = 0
    client_comments = []

    for feature in features:
        latest_feedback = db.query(ReviewFeedback).filter(
            ReviewFeedback.file_id == file_id,
            ReviewFeedback.req_id == feature.id,
            ReviewFeedback.client_id == assignment.client_id,
        ).order_by(ReviewFeedback.created_at.desc()).first()

        if latest_feedback:
            status_value = _action_to_status(latest_feedback.action)
        else:
            status_value = "pending"

        if status_value == "approved":
            approved += 1
        elif status_value == "rejected":
            rejected += 1
        elif status_value == "modification_requested":
            modification_requested += 1
        else:
            pending += 1

    # Build an explicit event feed of all client actions (not only latest per requirement)
    # so manager can always see which specific requirements were modified/approved/rejected.
    all_feedback_rows = db.query(ReviewFeedback).filter(
        ReviewFeedback.file_id == file_id,
        ReviewFeedback.client_id == assignment.client_id,
    ).order_by(ReviewFeedback.created_at.desc()).all()

    req_title_map = {f.id: _req_title(f) for f in features}
    for fb in all_feedback_rows:
        before_text, after_text = _extract_revision_pair(fb.manager_note)
        client_comments.append({
            "feedback_id": fb.id,
            "req_id": fb.req_id,
            "title": req_title_map.get(fb.req_id, f"Requirement {fb.req_id}"),
            "action": fb.action,
            "comment": fb.comment,
            "resolved": bool(fb.resolved),
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
            "before_text": before_text,
            "after_text": after_text,
        })

    return {
        "file_id": file_id,
        "total": len(features),
        "approved": approved,
        "rejected": rejected,
        "modification_requested": modification_requested,
        "pending": pending,
        "submitted": assignment.submitted_at is not None,
        "submitted_at": assignment.submitted_at.isoformat() if assignment.submitted_at else None,
        "client_id": assignment.client_id,
        "client_comments": client_comments,
    }


@router.put("/review/feedback/{feedback_id}/resolve")
async def resolve_feedback(
    feedback_id: int,
    payload: ResolveFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager resolves a client feedback entry."""
    _ensure_manager(current_user)

    feedback = db.query(ReviewFeedback).filter(ReviewFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == feedback.file_id,
        ReviewAssignment.client_id == feedback.client_id,
        ReviewAssignment.manager_id == current_user.id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="Not allowed to resolve this feedback")

    feedback.resolved = 1 if payload.resolved else 0
    feedback.manager_note = (payload.manager_note or "").strip() or None
    feedback.resolved_at = datetime.utcnow() if feedback.resolved else None
    db.commit()

    return {
        "feedback_id": feedback.id,
        "resolved": bool(feedback.resolved),
        "manager_note": feedback.manager_note or "",
        "resolved_at": feedback.resolved_at.isoformat() if feedback.resolved_at else None,
    }


@router.get("/review/{file_id}/manager-feedback")
async def get_manager_feedback_lists(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager list view for feedback tabs."""
    _ensure_manager(current_user)

    assignment = _latest_assignment_for_manager(db, file_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=404, detail="No client assignment for this file")

    features = db.query(Feature).filter(Feature.file_id == file_id).all()

    modification_requests = []
    rejected = []
    approved = []
    client_added = []
    auto_handled = []

    for feature in features:
        latest_feedback = db.query(ReviewFeedback).filter(
            ReviewFeedback.file_id == file_id,
            ReviewFeedback.req_id == feature.id,
            ReviewFeedback.client_id == assignment.client_id,
        ).order_by(ReviewFeedback.created_at.desc()).first()

        item = {
            "req_id": feature.id,
            "title": _req_title(feature),
            "description": feature.description or "",
            "suggested_revision": getattr(feature, "suggested_revision", None),
            "category": (feature.category or "functional").lower(),
            "priority": feature.priority or "Medium",
            "source": feature.source or "system",
            "review_status": "pending",
            "manager_attention": bool(getattr(feature, "manager_attention", 0)),
            "feedback_id": latest_feedback.id if latest_feedback else None,
            "comment": latest_feedback.comment if latest_feedback else "",
            "resolved": bool(latest_feedback.resolved) if latest_feedback else False,
            "resolved_at": latest_feedback.resolved_at.isoformat() if (latest_feedback and latest_feedback.resolved_at) else None,
            "manager_note": latest_feedback.manager_note if latest_feedback else "",
        }

        if latest_feedback:
            item["review_status"] = _action_to_status(latest_feedback.action)
            before_text, after_text = _extract_revision_pair(latest_feedback.manager_note)
            item["before_text"] = before_text
            item["after_text"] = after_text

        # Fully auto-handled feedback should move to audit-style tab.
        if (
            latest_feedback
            and bool(latest_feedback.resolved)
            and item["review_status"] == "rejected"
            and not bool(getattr(feature, "manager_attention", 0))
        ):
            auto_handled.append(item)
            continue

        if item["source"] == "client":
            client_added.append(item)
        if item["review_status"] == "modification_requested":
            modification_requests.append(item)
        elif item["review_status"] == "rejected":
            rejected.append(item)
        elif item["review_status"] == "approved":
            approved.append(item)

    return {
        "file_id": file_id,
        "modification_requests": modification_requests,
        "rejected": rejected,
        "client_added": client_added,
        "approved": approved,
        "auto_handled": auto_handled,
    }


@router.get("/api/assignments")
async def get_file_assignments(
    file_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get review assignments for a file - shows which clients are reviewing what."""
    _ensure_manager(current_user)

    if file_id is None:
        raise HTTPException(status_code=400, detail="file_id required")

    assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.manager_id == current_user.id,
    ).all()

    result = []
    for assign in assignments:
        client = db.query(User).filter(User.id == assign.client_id).first()
        result.append({
            "assignment_id": assign.id,
            "client_id": assign.client_id,
            "client_name": client.username if client else "Unknown",
            "client_email": client.email if client else "",
            "file_id": assign.file_id,
            "due_date": assign.due_date.isoformat() if assign.due_date else None,
            "submitted_at": assign.submitted_at.isoformat() if assign.submitted_at else None,
        })

    return result


@router.post("/api/bulk/remind-pending")
async def send_reminders_pending(
    file_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send reminder emails to clients with pending reviews."""
    _ensure_manager(current_user)

    if file_id is None:
        raise HTTPException(status_code=400, detail="file_id required")

    assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.manager_id == current_user.id,
        ReviewAssignment.submitted_at == None,
    ).all()

    count = 0
    for assign in assignments:
        client = db.query(User).filter(User.id == assign.client_id).first()
        if client and client.email:
            try:
                from utils.email_sender import send_email_async
                subject = "Reminder: Please review your requirements in FlowMind"
                body = f"Hi {client.username},\n\nThis is a friendly reminder to review your assigned requirements in FlowMind.\n\nPlease log in to complete your review.\n\nBest regards,\nFlowMind Team"
                asyncio.create_task(send_email_async(client.email, subject, body))
                count += 1
            except Exception:
                pass

    return {"count": count}


@router.post("/api/bulk/resend-invites")
async def resend_all_invites(
    file_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resend invitations to all assigned clients."""
    _ensure_manager(current_user)

    if file_id is None:
        raise HTTPException(status_code=400, detail="file_id required")

    assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.manager_id == current_user.id,
    ).all()

    count = 0
    for assign in assignments:
        client = db.query(User).filter(User.id == assign.client_id).first()
        if client and client.email:
            try:
                from utils.email_sender import send_email_async
                invite_link = f"http://localhost:8000/client-review?file_id={file_id}"
                subject = "You're invited to review requirements in FlowMind"
                body = f"Hi {client.username},\n\nYou have been invited to review requirements for a document in FlowMind.\n\nClick here to access the review: {invite_link}\n\nBest regards,\nFlowMind Team"
                asyncio.create_task(send_email_async(client.email, subject, body))
                count += 1
            except Exception:
                pass

    return {"count": count}


@router.post("/requirements")
async def manager_add_requirement(
    payload: ManagerCreateRequirementRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager-only requirement creation endpoint for accepting client-added requirements."""
    _ensure_manager(current_user)

    parsed_file = db.query(ParsedFile).filter(ParsedFile.id == payload.file_id).first()
    if not parsed_file:
        raise HTTPException(status_code=404, detail="File not found")

    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    category = (payload.category or "functional").strip().lower()
    if category not in ("functional", "non-functional", "business", "system"):
        raise HTTPException(status_code=400, detail="Invalid category")

    priority = (payload.priority or "Medium").strip().capitalize()
    if priority not in ("High", "Medium", "Low"):
        raise HTTPException(status_code=400, detail="priority must be High, Medium, or Low")

    source = (payload.source or "client_approved").strip().lower()
    if source not in ("system", "client", "client_approved", "image_analysis"):
        source = "client_approved"

    created = Feature(
        user_id=current_user.id,
        project_id=getattr(parsed_file, "project_id", None),
        file_id=payload.file_id,
        category=category,
        title=title,
        description=(payload.description or "").strip() or title,
        priority=priority,
        source=source,
        client_review_status="pending",
        status="pending",
        quality_score=0,
    )
    db.add(created)
    db.commit()
    db.refresh(created)

    return {
        "req_id": created.id,
        "title": created.title,
        "description": created.description,
        "category": created.category,
        "priority": created.priority,
        "source": created.source,
    }


@router.put("/requirements/{req_id}")
async def manager_update_requirement(
    req_id: int,
    payload: RequirementUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager edits requirement fields from feedback tabs."""
    _ensure_manager(current_user)

    feature = db.query(Feature).filter(Feature.id == req_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if not _manager_can_access_feature(db, current_user.id, feature):
        raise HTTPException(status_code=403, detail="Not allowed to edit this requirement")

    if payload.title is not None:
        title = (payload.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="title cannot be empty")
        feature.title = title

    if payload.description is not None:
        description = (payload.description or "").strip()
        if not description:
            raise HTTPException(status_code=400, detail="description cannot be empty")
        feature.description = description

    if payload.category is not None:
        category = _normalize_feature_category(payload.category)
        feature.category = category

    if payload.priority is not None:
        priority = _priority_label(payload.priority)
        feature.priority = priority

    feature.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(feature)

    return {
        "req_id": feature.id,
        "title": _req_title(feature),
        "description": feature.description or "",
        "category": feature.category or "functional",
        "priority": feature.priority or "Medium",
    }


@router.post("/requirements/{req_id}/keep")
async def manager_keep_requirement(
    req_id: int,
    feedback_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager keeps a previously rejected/flagged requirement."""
    _ensure_manager(current_user)

    feature = db.query(Feature).filter(Feature.id == req_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if not _manager_can_access_feature(db, current_user.id, feature):
        raise HTTPException(status_code=403, detail="Not allowed to update this requirement")

    feature.client_review_status = "approved"
    feature.status = "approved"
    feature.source = "client_approved" if (feature.source or "").lower() == "client" else feature.source
    feature.manager_attention = 0
    feature.updated_at = datetime.utcnow()

    if feedback_id:
        feedback = db.query(ReviewFeedback).filter(ReviewFeedback.id == feedback_id).first()
        if feedback:
            feedback.resolved = 1
            feedback.manager_note = "Manager kept requirement"
            feedback.resolved_at = datetime.utcnow()

    db.commit()
    return {"success": True, "req_id": req_id, "status": "approved"}


@router.post("/requirements/{req_id}/accept-client")
async def manager_accept_client_requirement(
    req_id: int,
    feedback_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager accepts a client-added requirement without duplicating it."""
    _ensure_manager(current_user)

    feature = db.query(Feature).filter(Feature.id == req_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if not _manager_can_access_feature(db, current_user.id, feature):
        raise HTTPException(status_code=403, detail="Not allowed to update this requirement")

    feature.source = "client_approved"
    feature.client_review_status = "approved"
    feature.status = "approved"
    feature.manager_attention = 0
    feature.updated_at = datetime.utcnow()

    if feedback_id:
        feedback = db.query(ReviewFeedback).filter(ReviewFeedback.id == feedback_id).first()
        if feedback:
            feedback.resolved = 1
            feedback.manager_note = "Client-added requirement accepted by manager"
            feedback.resolved_at = datetime.utcnow()

    db.commit()
    return {"success": True, "req_id": req_id, "source": "client_approved"}


@router.delete("/requirements/{req_id}")
async def manager_delete_requirement(
    req_id: int,
    feedback_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager removes a requirement from project scope."""
    _ensure_manager(current_user)

    feature = db.query(Feature).filter(Feature.id == req_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if not _manager_can_access_feature(db, current_user.id, feature):
        raise HTTPException(status_code=403, detail="Not allowed to delete this requirement")

    if feedback_id:
        feedback = db.query(ReviewFeedback).filter(ReviewFeedback.id == feedback_id).first()
        if feedback:
            feedback.resolved = 1
            feedback.manager_note = "Requirement removed by manager"
            feedback.resolved_at = datetime.utcnow()
    db.query(ReviewFeedback).filter(ReviewFeedback.req_id == req_id).delete(synchronize_session=False)
    db.delete(feature)
    db.commit()
    return {"success": True, "req_id": req_id, "deleted": True}
