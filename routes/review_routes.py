"""Client review workflow routes."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import get_current_user, get_db
from database import Feature, ParsedFile, ReviewAssignment, ReviewFeedback, User
from rag_agent import get_agent

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


class InviteClientRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    file_id: int


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


def _req_title(feature: Feature) -> str:
    title = (getattr(feature, "title", None) or "").strip()
    if title:
        return title
    desc = (feature.description or "").strip()
    if not desc:
        return f"Requirement {feature.id}"
    first_line = desc.split("\n")[0].strip()
    if len(first_line) > 96:
        return first_line[:93] + "..."
    return first_line or f"Requirement {feature.id}"


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
        if latest_feedback:
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
            "feedback_date": latest_feedback.created_at.isoformat() if latest_feedback else None,
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

    learning_update = None
    try:
        owner_user_id = getattr(feature, "user_id", None) or assignment.manager_id
        agent = get_agent(user_id=owner_user_id)
        learning_update = agent.learn_from_feedback(
            feature_text=feature.description or "",
            category=feature.category or "features",
            action=action,
            title=_req_title(feature),
            comment=feedback.comment or "",
            file_id=file_id,
            req_id=payload.req_id,
        )
    except Exception as e:
        print(f"⚠️ Feedback learning update failed for req_id={payload.req_id}: {str(e)}")

    return {
        "feedback_id": feedback.id,
        "req_id": payload.req_id,
        "action": action,
        "review_status": feature.client_review_status,
        "client_comment": feedback.comment or "",
        "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
        "learning_update": learning_update,
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

    category = (payload.category or "functional").strip().lower()
    if category not in ("functional", "non-functional", "business", "system"):
        raise HTTPException(status_code=400, detail="Invalid category")

    priority = (payload.priority or "Medium").strip().capitalize()
    if priority not in ("High", "Medium", "Low"):
        raise HTTPException(status_code=400, detail="priority must be High, Medium, or Low")

    parsed_file = db.query(ParsedFile).filter(ParsedFile.id == file_id).first()
    if not parsed_file:
        raise HTTPException(status_code=404, detail="File not found")

    feature = Feature(
        user_id=current_user.id,
        project_id=getattr(parsed_file, "project_id", None),
        file_id=file_id,
        category=category,
        title=title,
        description=(payload.description or "").strip() or title,
        priority=priority,
        source="client",
        client_review_status="pending_manager_approval",
        status="pending",
        quality_score=0,
        feedback=None,
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
            if latest_feedback.comment:
                client_comments.append({
                    "feedback_id": latest_feedback.id,
                    "req_id": feature.id,
                    "title": _req_title(feature),
                    "action": latest_feedback.action,
                    "comment": latest_feedback.comment,
                    "resolved": bool(latest_feedback.resolved),
                    "created_at": latest_feedback.created_at.isoformat() if latest_feedback.created_at else None,
                })
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
            "category": (feature.category or "functional").lower(),
            "priority": feature.priority or "Medium",
            "source": feature.source or "system",
            "review_status": "pending",
            "feedback_id": latest_feedback.id if latest_feedback else None,
            "comment": latest_feedback.comment if latest_feedback else "",
            "resolved": bool(latest_feedback.resolved) if latest_feedback else False,
        }

        if latest_feedback:
            item["review_status"] = _action_to_status(latest_feedback.action)

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
    if source not in ("system", "client", "client_approved"):
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
