"""Dashboard and user file management routes.

Legacy HTML page handlers that served static/*.html for each dashboard route
were removed when the React SPA took over rendering — the SPA catch-all in
flowmind.py handles `/dashboard`, `/upload`, `/requirements`, `/approve`,
`/settings`, `/export`, `/analytics`, `/members`, `/integrations`,
`/integration-log`, `/manager-feedback`, `/client-review`, and `/clients`.
Only JSON / data endpoints live in this module now.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from database import SessionLocal, ParsedFile, User, Team, Feature, IntegrationLog, ImageMeta, ReviewAssignment, ReviewFeedback, AgentChatHistory
from auth import get_current_user, get_db, get_visible_user_ids, can_user_access_project, SECRET_KEY, ALGORITHM
from jose import JWTError, jwt
import os

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_user_from_token(token: Optional[str] = None, credentials: Optional[HTTPAuthorizationCredentials] = None, db: Session = None) -> User:
    """Helper function to get user from token (query param or header)."""
    auth_token = None
    if token:
        auth_token = token
    elif credentials:
        auth_token = credentials.credentials
    
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(auth_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        # Convert string back to int (JWT requires sub to be string)
        user_id = int(user_id_str)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.is_active == 0:
        raise credentials_exception
    
    return user


@router.get("/api/my-uploads")
async def get_my_uploads(
    token: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Get all files uploaded by the current user. Accepts token via Authorization header or query parameter."""
    try:
        print(f"📂 Getting uploads for user...")
        current_user = _get_user_from_token(token, credentials, db)
        print(f"📂 User authenticated: {current_user.id}")
        if project_id is not None and not can_user_access_project(current_user, project_id, db):
            raise HTTPException(status_code=403, detail="Not allowed for this project")

        visible_ids = get_visible_user_ids(current_user, db)
        if not visible_ids:
            return {"uploads": []}
        uploads_query = db.query(ParsedFile).filter(
            ParsedFile.user_id.in_(visible_ids)
        )
        if project_id is not None:
            uploads_query = uploads_query.filter(ParsedFile.project_id == project_id)

        uploads = uploads_query.order_by(ParsedFile.created_at.desc()).all()
        print(f"📂 Found {len(uploads)} uploads")
        result = []
        for upload in uploads:
            user = db.query(User).filter(User.id == upload.user_id).first()
            result.append({
                "id": upload.id,
                "filename": upload.filename,
                "summary": upload.summary,
                "extracted_text": upload.extracted_text[:500] if upload.extracted_text else None,
                "detected_shapes": upload.detected_shapes or 0,
                "created_at": upload.created_at.isoformat() if upload.created_at else None,
                "view_id": upload.view_id,
                "user_id": upload.user_id,
                "username": user.username if user else None,
                "project_id": getattr(upload, "project_id", None),
            })
        
        print(f"✅ Returning {len(result)} uploads")
        return {"uploads": result}
    except HTTPException:
        # Auth errors and other deliberate HTTP responses must pass through
        # unchanged; wrapping them as 500 hides the real failure mode.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching uploads: {str(e)}")


@router.get("/api/agent-chat-history")
async def get_agent_chat_history(
    token: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    """Get persistent AI analysis history for the authenticated user."""
    current_user = _get_user_from_token(token, credentials, db)
    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed for this project")

    query = db.query(AgentChatHistory).filter(AgentChatHistory.user_id == current_user.id)
    if project_id is not None:
        query = query.filter(AgentChatHistory.project_id == project_id)

    rows = query.order_by(AgentChatHistory.created_at.desc()).limit(limit).all()
    history = []
    for row in rows:
        history.append({
            "id": row.id,
            "filename": row.filename,
            "user_message": row.user_message or "",
            "assistant_message": row.assistant_message or "",
            "view_id": row.view_id,
            "file_id": row.file_id,
            "project_id": row.project_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })

    return {"history": history}


@router.delete("/api/files/{file_id}")
async def delete_file(
    file_id: int,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    """Delete an uploaded file and linked extracted artifacts if allowed."""
    current_user = _get_user_from_token(token, credentials, db)
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        raise HTTPException(status_code=403, detail="Not allowed")

    row = db.query(ParsedFile).filter(
        ParsedFile.id == file_id,
        ParsedFile.user_id.in_(visible_ids),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    # Allow deletion by owner, manager, or team head.
    if current_user.id != row.user_id and current_user.role not in ("manager", "team_head"):
        raise HTTPException(status_code=403, detail="Not allowed to delete this file")

    # Remove review lifecycle records for this file so test/duplicate uploads can be cleaned.
    db.query(ReviewFeedback).filter(ReviewFeedback.file_id == row.id).delete(synchronize_session=False)
    db.query(ReviewAssignment).filter(ReviewAssignment.file_id == row.id).delete(synchronize_session=False)

    # Clean up linked image files from disk where possible.
    image_rows = db.query(ImageMeta).filter(ImageMeta.file_id == row.id).all()
    for img in image_rows:
        try:
            if img.image_path and os.path.exists(img.image_path):
                os.remove(img.image_path)
        except Exception:
            pass

    # Clean up extracted full text file if present.
    try:
        if row.full_text_path and os.path.exists(row.full_text_path):
            os.remove(row.full_text_path)
    except Exception:
        pass

    db.query(ImageMeta).filter(ImageMeta.file_id == row.id).delete(synchronize_session=False)
    db.query(Feature).filter(Feature.file_id == row.id).delete(synchronize_session=False)
    db.delete(row)
    db.commit()

    return {"status": "success", "deleted_file_id": file_id}


@router.get("/files")
async def get_files(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Part 2 compatibility endpoint for listing files."""
    current_user = _get_user_from_token(token, credentials, db)
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        return {"files": []}

    rows = db.query(ParsedFile).filter(ParsedFile.user_id.in_(visible_ids)).order_by(ParsedFile.created_at.desc()).all()
    files = []
    for row in rows:
        req_count = db.query(Feature).filter(Feature.file_id == row.id).count()
        has_summary = bool((row.summary or "").strip())
        status_val = "complete" if has_summary else "processing"
        exported_jira = False
        try:
            if row.view_id:
                exported_jira = db.query(IntegrationLog).filter(
                    IntegrationLog.platform == "jira",
                    IntegrationLog.source_id == row.view_id,
                ).count() > 0
        except Exception:
            exported_jira = False

        file_size = None
        try:
            if row.full_text_path and os.path.exists(row.full_text_path):
                file_size = os.path.getsize(row.full_text_path)
        except Exception:
            file_size = None

        files.append({
            "id": row.id,
            "filename": row.filename,
            "uploaded_at": row.created_at.isoformat() if row.created_at else None,
            "requirements_count": req_count,
            "status": status_val,
            "exported_to_jira": exported_jira,
            "file_size": file_size,
        })

    return {"files": files}


@router.get("/files/{file_id}")
async def get_file_by_id(
    file_id: int,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Part 2 compatibility endpoint for single file details."""
    current_user = _get_user_from_token(token, credentials, db)
    visible_ids = get_visible_user_ids(current_user, db)
    row = db.query(ParsedFile).filter(ParsedFile.id == file_id, ParsedFile.user_id.in_(visible_ids)).first()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    req_count = db.query(Feature).filter(Feature.file_id == row.id).count()
    file_size = None
    try:
        if row.full_text_path and os.path.exists(row.full_text_path):
            file_size = os.path.getsize(row.full_text_path)
    except Exception:
        file_size = None

    return {
        "id": row.id,
        "filename": row.filename,
        "uploaded_at": row.created_at.isoformat() if row.created_at else None,
        "requirements_count": req_count,
        "status": "complete" if (row.summary or "").strip() else "processing",
        "file_size": file_size,
    }


@router.get("/status/{file_id}")
async def get_processing_status(
    file_id: int,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Part 2 compatibility endpoint for processing status by file ID."""
    current_user = _get_user_from_token(token, credentials, db)
    visible_ids = get_visible_user_ids(current_user, db)
    row = db.query(ParsedFile).filter(ParsedFile.id == file_id, ParsedFile.user_id.in_(visible_ids)).first()
    if not row:
        return {"stage": "FAILED", "progress": 0, "stages_done": []}

    req_count = db.query(Feature).filter(Feature.file_id == row.id).count()
    # Existing pipeline writes record at completion; treat persisted record as complete.
    return {
        "stage": "COMPLETE",
        "progress": 100,
        "stages_done": ["UPLOADING", "PARSING", "TEXT_EXTRACTION", "IMAGE_DETECTION", "OCR_PROCESSING", "IMAGE_SUMMARIZATION", "FINALIZING"],
        "requirements_count": req_count,
    }


@router.post("/retry/{file_id}")
async def retry_processing(
    file_id: int,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Part 2 compatibility retry endpoint."""
    current_user = _get_user_from_token(token, credentials, db)
    visible_ids = get_visible_user_ids(current_user, db)
    row = db.query(ParsedFile).filter(ParsedFile.id == file_id, ParsedFile.user_id.in_(visible_ids)).first()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "queued", "file_id": file_id}


@router.get("/api/upload/{upload_id}")
async def get_upload_details(
    upload_id: int,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific upload. Accepts token via Authorization header or query parameter."""
    try:
        current_user = _get_user_from_token(token, credentials, db)
        visible_ids = get_visible_user_ids(current_user, db)
        if not visible_ids:
            raise HTTPException(status_code=404, detail="Upload not found")
        upload = db.query(ParsedFile).filter(
            ParsedFile.id == upload_id,
            ParsedFile.user_id.in_(visible_ids)
        ).first()
        if not upload:
            raise HTTPException(status_code=404, detail="Upload not found")
        
        # Build response - FastAPI will automatically close DB session after this returns
        return {
            "id": upload.id,
            "filename": upload.filename,
            "summary": upload.summary,
            "extracted_text": upload.extracted_text,
            "detected_shapes": upload.detected_shapes or 0,
            "created_at": upload.created_at.isoformat() if upload.created_at else None,
            "view_id": upload.view_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching upload: {str(e)}")


@router.get("/api/teams")
async def get_teams(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """List teams. Manager: all teams. Team head: only their team. Member: 403."""
    current_user = _get_user_from_token(token, credentials, db)
    role = getattr(current_user, "role", "member")
    if role == "manager":
        teams = db.query(Team).all()
        return {"teams": [{"id": t.id, "name": t.name, "description": t.description or ""} for t in teams]}
    if role == "team_head" and getattr(current_user, "team_id", None):
        t = db.query(Team).filter(Team.id == current_user.team_id).first()
        if t:
            return {"teams": [{"id": t.id, "name": t.name, "description": t.description or ""}]}
    raise HTTPException(status_code=403, detail="Not allowed to list teams")


@router.get("/api/teams/{team_id}/users")
async def get_team_users(
    team_id: int,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """List users in a team. Manager: any team. Team head: only their team."""
    current_user = _get_user_from_token(token, credentials, db)
    role = getattr(current_user, "role", "member")
    if role == "member":
        raise HTTPException(status_code=403, detail="Not allowed")
    if role == "team_head" and getattr(current_user, "team_id", None) != team_id:
        raise HTTPException(status_code=403, detail="Can only view your own team")
    users = db.query(User).filter(User.team_id == team_id, User.is_active == 1).all()
    return {"users": [{"id": u.id, "username": u.username, "email": u.email, "role": getattr(u, "role", "member")} for u in users]}


@router.get("/api/progress")
async def get_progress(
    token: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Progress summary. Manager: per-team counts. Team head: own team. Member: own counts."""
    current_user = _get_user_from_token(token, credentials, db)
    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed for this project")

    visible_ids = get_visible_user_ids(current_user, db)
    role = getattr(current_user, "role", "member")
    if not visible_ids:
        if role == "manager":
            return {"uploads": 0, "features": 0, "by_team": []}
        return {"uploads": 0, "features": 0}
    uploads_query = db.query(ParsedFile).filter(ParsedFile.user_id.in_(visible_ids))
    features_query = db.query(Feature).filter(Feature.user_id.in_(visible_ids))
    if project_id is not None:
        uploads_query = uploads_query.filter(ParsedFile.project_id == project_id)
        features_query = features_query.filter(Feature.project_id == project_id)

    uploads_count = uploads_query.count()
    features_count = features_query.count()
    if role == "manager":
        teams = db.query(Team).all()
        by_team = []
        for t in teams:
            member_ids = [u.id for u in db.query(User).filter(User.team_id == t.id, User.is_active == 1).all()]
            team_uploads = db.query(ParsedFile).filter(ParsedFile.user_id.in_(member_ids)) if member_ids else None
            team_features = db.query(Feature).filter(Feature.user_id.in_(member_ids)) if member_ids else None
            if project_id is not None and team_uploads is not None and team_features is not None:
                team_uploads = team_uploads.filter(ParsedFile.project_id == project_id)
                team_features = team_features.filter(Feature.project_id == project_id)
            u_count = team_uploads.count() if team_uploads is not None else 0
            f_count = team_features.count() if team_features is not None else 0
            by_team.append({"team_id": t.id, "team_name": t.name, "uploads": u_count, "features": f_count})
        return {"uploads": uploads_count, "features": features_count, "by_team": by_team}
    if role == "team_head" and getattr(current_user, "team_id", None):
        return {"uploads": uploads_count, "features": features_count, "team_id": current_user.team_id}
    return {"uploads": uploads_count, "features": features_count}


# --------------- Manager: Members & user assignment (team + role) ---------------
@router.get("/api/members")
async def get_members(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """List all users with team and role. Manager only."""
    current_user = _get_user_from_token(token, credentials, db)
    if getattr(current_user, "role", None) != "manager":
        raise HTTPException(status_code=403, detail="Manager only")
    users = db.query(User).filter(User.is_active == 1).all()
    teams = {t.id: t.name for t in db.query(Team).all()}
    return {
        "members": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": getattr(u, "role", "member"),
                "team_id": getattr(u, "team_id", None),
                "team_name": teams.get(u.team_id, "") if getattr(u, "team_id", None) else None,
            }
            for u in users
        ],
        "teams": [{"id": t.id, "name": t.name} for t in db.query(Team).all()],
    }


class UserUpdateBody(BaseModel):
    team_id: Optional[int] = None
    role: Optional[str] = None  # member | team_head (manager cannot set manager)


@router.patch("/api/users/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdateBody,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Update a user's team and/or role. Manager only. Cannot change own role or demote the last manager."""
    current_user = _get_user_from_token(token, credentials, db)
    if getattr(current_user, "role", None) != "manager":
        raise HTTPException(status_code=403, detail="Manager only")
    target = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    # Update team_id only when key was sent (so we can clear with null)
    try:
        sent = body.model_dump(exclude_unset=True)
    except Exception:
        sent = body.dict(exclude_unset=True) if hasattr(body, 'dict') else {}
    if "team_id" in sent:
        if sent["team_id"] is None or sent["team_id"] == 0:
            target.team_id = None
        elif sent["team_id"] and int(sent["team_id"]) > 0:
            team = db.query(Team).filter(Team.id == int(sent["team_id"])).first()
            if not team:
                raise HTTPException(status_code=400, detail="Team not found")
            target.team_id = team.id
    if body.role is not None:
        if body.role not in ("member", "team_head"):
            raise HTTPException(status_code=400, detail="Role must be member or team_head")
        if target.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        if getattr(target, "role", None) == "manager" and db.query(User).filter(User.role == "manager", User.is_active == 1).count() <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last manager")
        target.role = body.role
    db.commit()
    return {"ok": True, "user_id": user_id}


@router.get("/api/assignable-users")
async def get_assignable_users(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Users that the current user can assign features to. Manager: all. Team head: own team members."""
    current_user = _get_user_from_token(token, credentials, db)
    role = getattr(current_user, "role", "member")
    if role == "manager":
        users = db.query(User).filter(User.is_active == 1).all()
        return {"users": [{"id": u.id, "username": u.username or u.email} for u in users]}
    if role == "team_head" and getattr(current_user, "team_id", None):
        users = db.query(User).filter(User.team_id == current_user.team_id, User.is_active == 1).all()
        return {"users": [{"id": u.id, "username": u.username or u.email} for u in users]}
    return {"users": []}


# ==============================================================
#  Manager dashboard: aggregate stats for the home screen
# ==============================================================

@router.get("/api/manager/stats")
async def manager_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rich aggregate stats for the manager dashboard home page.

    Returns document counts, requirement counts broken down by status and
    category, integration export counts, recent-documents feed with
    per-doc status badges, and a 14-day activity sparkline.
    """
    from sqlalchemy import func

    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        return {
            "totals": {"documents": 0, "requirements": 0, "images": 0},
            "by_status": {},
            "by_category": {},
            "exports": {"jira": 0, "trello": 0, "csv": 0, "json": 0, "total": 0},
            "client_feedback": {
                "total": 0, "approved": 0, "rejected": 0,
                "modification_requested": 0, "pending": 0,
            },
            "recent_documents": [],
            "activity_14d": [],
        }

    # --- Totals --------------------------------------------------
    total_docs = (
        db.query(func.count(ParsedFile.id))
        .filter(ParsedFile.user_id.in_(visible_ids))
        .scalar() or 0
    )
    total_reqs = (
        db.query(func.count(Feature.id))
        .filter(Feature.user_id.in_(visible_ids))
        .scalar() or 0
    )
    total_images = (
        db.query(func.count(ImageMeta.id))
        .join(ParsedFile, ParsedFile.id == ImageMeta.file_id)
        .filter(ParsedFile.user_id.in_(visible_ids))
        .scalar() or 0
    )

    # --- Features by status & category ---------------------------
    by_status: dict[str, int] = {}
    for row in (
        db.query(Feature.status, func.count(Feature.id))
        .filter(Feature.user_id.in_(visible_ids))
        .group_by(Feature.status)
        .all()
    ):
        by_status[(row[0] or "pending")] = int(row[1])

    by_category: dict[str, int] = {}
    for row in (
        db.query(Feature.category, func.count(Feature.id))
        .filter(Feature.user_id.in_(visible_ids))
        .group_by(Feature.category)
        .all()
    ):
        by_category[(row[0] or "uncategorized").lower()] = int(row[1])

    # --- Integration exports -----------------------------------
    exports = {"jira": 0, "trello": 0, "csv": 0, "json": 0, "total": 0}
    for row in (
        db.query(IntegrationLog.platform, func.count(IntegrationLog.id))
        .filter(IntegrationLog.user_id.in_(visible_ids))
        .group_by(IntegrationLog.platform)
        .all()
    ):
        p = (row[0] or "").lower()
        if p in exports:
            exports[p] = int(row[1])
        exports["total"] += int(row[1])

    # --- Client feedback totals -------------------------------
    client_feedback = {
        "total": 0, "approved": 0, "rejected": 0,
        "modification_requested": 0, "pending": 0,
    }
    file_ids_visible = [
        fid for (fid,) in db.query(ParsedFile.id)
        .filter(ParsedFile.user_id.in_(visible_ids)).all()
    ]
    if file_ids_visible:
        for row in (
            db.query(ReviewFeedback.action, func.count(ReviewFeedback.id))
            .filter(ReviewFeedback.file_id.in_(file_ids_visible))
            .group_by(ReviewFeedback.action)
            .all()
        ):
            action = (row[0] or "").lower()
            key = {
                "approve": "approved",
                "reject": "rejected",
                "request_modification": "modification_requested",
            }.get(action, "pending")
            client_feedback[key] = client_feedback.get(key, 0) + int(row[1])
            client_feedback["total"] += int(row[1])

    # --- Recent documents with per-doc status -----------------
    recent_files = (
        db.query(ParsedFile)
        .filter(ParsedFile.user_id.in_(visible_ids))
        .order_by(ParsedFile.created_at.desc())
        .limit(10)
        .all()
    )
    recent_documents = []
    for pf in recent_files:
        feat_total = (
            db.query(func.count(Feature.id))
            .filter(Feature.file_id == pf.id)
            .scalar() or 0
        )
        feat_approved = (
            db.query(func.count(Feature.id))
            .filter(Feature.file_id == pf.id, Feature.status == "approved")
            .scalar() or 0
        )
        has_client_review = (
            db.query(func.count(ReviewAssignment.id))
            .filter(ReviewAssignment.file_id == pf.id)
            .scalar() or 0
        ) > 0

        # Derive a coarse status for the badge
        if feat_total == 0:
            status_label = "processing"
        elif has_client_review:
            submitted = (
                db.query(func.count(ReviewAssignment.id))
                .filter(
                    ReviewAssignment.file_id == pf.id,
                    ReviewAssignment.submitted_at.isnot(None),
                )
                .scalar() or 0
            )
            status_label = "client-submitted" if submitted else "in-review"
        elif feat_approved and feat_approved == feat_total:
            status_label = "complete"
        else:
            status_label = "pending"

        recent_documents.append({
            "id": pf.id,
            "filename": pf.filename,
            "created_at": pf.created_at.isoformat() if pf.created_at else None,
            "view_id": pf.view_id,
            "user_id": pf.user_id,
            "feature_count": int(feat_total),
            "approved_count": int(feat_approved),
            "status": status_label,
        })

    # --- 14-day activity (uploads per day) --------------------
    activity_14d = []
    today = datetime.utcnow().date()
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        count = (
            db.query(func.count(ParsedFile.id))
            .filter(
                ParsedFile.user_id.in_(visible_ids),
                func.date(ParsedFile.created_at) == day,
            )
            .scalar() or 0
        )
        activity_14d.append({"date": day.isoformat(), "uploads": int(count)})

    return {
        "totals": {
            "documents": int(total_docs),
            "requirements": int(total_reqs),
            "images": int(total_images),
        },
        "by_status": by_status,
        "by_category": by_category,
        "exports": exports,
        "client_feedback": client_feedback,
        "recent_documents": recent_documents,
        "activity_14d": activity_14d,
    }
