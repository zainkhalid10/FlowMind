"""Integration routes: Export (CSV/JSON), push to Trello/Jira, config, and log."""
import os
import json
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response, JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database import SessionLocal, IntegrationConfig, IntegrationLog, User, Feature
from auth import get_db, get_current_user_optional, get_current_user, get_visible_user_ids, can_user_access_project

from services.integration_service import (
    parse_requirements_from_response,
    export_as_json,
    export_as_csv,
    push_to_trello,
    push_to_jira,
)

router = APIRouter()
VIEWS_FILE = "requirements_views.json"


def get_views():
    """Load views from persistent storage."""
    if os.path.exists(VIEWS_FILE):
        with open(VIEWS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_integration_config(db: Session, platform: str) -> dict:
    """Load stored config for platform (trello | jira) as key -> value."""
    rows = db.query(IntegrationConfig).filter(IntegrationConfig.platform == platform).all()
    return {r.key_name: r.value for r in rows}


def _log_integration(db: Session, user_id: Optional[int], platform: str, source: str, source_id: Optional[str],
                     items_count: int, success_count: int, message: str, results: list):
    """Write one row to integration_log (D2)."""
    try:
        details = json.dumps(results, ensure_ascii=False) if results else None
        log = IntegrationLog(
            user_id=user_id,
            platform=platform,
            source=source,
            source_id=source_id,
            items_count=items_count,
            success_count=success_count,
            message=message,
            details=details,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Integration log write failed: {e}")


@router.get("/api/export/{view_id}/json")
async def export_requirements_json(view_id: str):
    """Export requirements as JSON file download."""
    views = get_views()
    data = views.get(view_id)
    if not data:
        raise HTTPException(status_code=404, detail="View not found or expired")

    requirements = parse_requirements_from_response(data.get("response", ""))
    filename = data.get("filename", "requirements").rsplit(".", 1)[0]
    json_str = export_as_json(requirements, filename, data.get("summary", ""))

    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}_requirements.json"'}
    )


@router.get("/api/export/{view_id}/csv")
async def export_requirements_csv(view_id: str):
    """Export requirements as CSV file download."""
    views = get_views()
    data = views.get(view_id)
    if not data:
        raise HTTPException(status_code=404, detail="View not found or expired")

    requirements = parse_requirements_from_response(data.get("response", ""))
    filename = data.get("filename", "requirements").rsplit(".", 1)[0]
    csv_str = export_as_csv(requirements)

    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}_requirements.csv"'}
    )


class TrelloPushRequest(BaseModel):
    list_id: Optional[str] = None
    api_key: Optional[str] = None
    token: Optional[str] = None


@router.post("/api/integration/trello/{view_id}")
async def push_requirements_to_trello(
    view_id: str,
    body: Optional[TrelloPushRequest] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Push extracted requirements to Trello as cards."""
    views = get_views()
    data = views.get(view_id)
    if not data:
        raise HTTPException(status_code=404, detail="View not found or expired")

    requirements = parse_requirements_from_response(data.get("response", ""))
    if not requirements:
        return JSONResponse({"success": False, "message": "No requirements to export", "results": []})

    cfg = get_integration_config(db, "trello")
    list_id = (body.list_id if body else None) or cfg.get("list_id") or os.getenv("TRELLO_LIST_ID")
    api_key = (body.api_key if body else None) or cfg.get("api_key") or os.getenv("TRELLO_API_KEY")
    token = (body.token if body else None) or cfg.get("token") or os.getenv("TRELLO_TOKEN")

    success, message, results = push_to_trello(
        requirements,
        list_id=list_id or "",
        api_key=api_key or "",
        token=token or "",
        source_filename=data.get("filename", "")
    )

    success_count = sum(1 for r in results if r.get("created"))
    _log_integration(
        db, getattr(current_user, "id", None) if current_user else None,
        "trello", "view", view_id, len(requirements), success_count, message, results
    )

    return JSONResponse({"success": success, "message": message, "results": results})


class JiraPushRequest(BaseModel):
    url: Optional[str] = None
    project_key: Optional[str] = None
    email: Optional[str] = None
    api_token: Optional[str] = None
    issue_type: Optional[str] = "Task"


@router.post("/api/integration/jira/{view_id}")
async def push_requirements_to_jira(
    view_id: str,
    body: Optional[JiraPushRequest] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Push extracted requirements to Jira as issues."""
    views = get_views()
    data = views.get(view_id)
    if not data:
        raise HTTPException(status_code=404, detail="View not found or expired")

    requirements = parse_requirements_from_response(data.get("response", ""))
    if not requirements:
        return JSONResponse({"success": False, "message": "No requirements to export", "results": []})

    cfg = get_integration_config(db, "jira")
    jira_url = (body.url if body else None) or cfg.get("url") or os.getenv("JIRA_URL")
    project_key = (body.project_key if body else None) or cfg.get("project_key") or os.getenv("JIRA_PROJECT_KEY")
    email = (body.email if body else None) or cfg.get("email") or os.getenv("JIRA_EMAIL")
    api_token = (body.api_token if body else None) or cfg.get("api_token") or os.getenv("JIRA_API_TOKEN")
    issue_type = (body.issue_type if body else "Task") or cfg.get("issue_type") or "Task"

    success, message, results = push_to_jira(
        requirements,
        jira_url=jira_url or "",
        project_key=project_key or "",
        email=email or "",
        api_token=api_token or "",
        issue_type=issue_type,
        source_filename=data.get("filename", "")
    )

    success_count = sum(1 for r in results if r.get("created"))
    _log_integration(
        db, getattr(current_user, "id", None) if current_user else None,
        "jira", "view", view_id, len(requirements), success_count, message, results
    )

    return JSONResponse({"success": success, "message": message, "results": results})


# --------------- Integration config (manager only) and log (D2) ---------------
def _require_manager(current_user: User = Depends(get_current_user)):
    if getattr(current_user, "role", None) != "manager":
        raise HTTPException(status_code=403, detail="Manager only")
    return current_user


@router.get("/api/integration/config")
async def get_integration_config_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_manager),
):
    """Get stored Trello and Jira config (manager only)."""
    trello = get_integration_config(db, "trello")
    jira = get_integration_config(db, "jira")
    return {"trello": trello, "jira": jira}


class IntegrationConfigUpdate(BaseModel):
    platform: str  # trello | jira
    config: dict   # key -> value


@router.put("/api/integration/config")
async def update_integration_config(
    body: IntegrationConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_manager),
):
    """Save Trello or Jira config (manager only)."""
    if body.platform not in ("trello", "jira"):
        raise HTTPException(status_code=400, detail="platform must be trello or jira")
    for key_name, value in (body.config or {}).items():
        row = db.query(IntegrationConfig).filter(
            IntegrationConfig.platform == body.platform,
            IntegrationConfig.key_name == key_name,
        ).first()
        if row:
            row.value = value if value is not None else ""
        else:
            db.add(IntegrationConfig(platform=body.platform, key_name=key_name, value=value or ""))
    db.commit()
    return {"ok": True}


@router.get("/api/integration/log")
async def get_integration_log(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_manager),
):
    """List integration log entries (D2), newest first (manager only)."""
    rows = db.query(IntegrationLog).order_by(IntegrationLog.created_at.desc()).limit(limit).all()
    out = []
    for r in rows:
        user = db.query(User).filter(User.id == r.user_id).first() if r.user_id else None
        out.append({
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "user_id": r.user_id,
            "username": user.username if user else None,
            "platform": r.platform,
            "source": r.source,
            "source_id": r.source_id,
            "items_count": r.items_count,
            "success_count": r.success_count,
            "message": r.message,
            "details": r.details,
        })
    return {"entries": out}


# --------------- Push approved features (from Approve page) ---------------
@router.post("/api/integration/trello/approved")
async def push_approved_to_trello(
    file_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Push approved features to Trello (manager/team head/member: own visible features)."""
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        return JSONResponse({"success": False, "message": "No visible features", "results": []})

    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed for this project")

    query = db.query(Feature).filter(Feature.user_id.in_(visible_ids), Feature.status == "approved")
    if file_id is not None:
        query = query.filter(Feature.file_id == file_id)
    if project_id is not None:
        query = query.filter(Feature.project_id == project_id)
    features = query.all()
    requirements = [{"category": f.category or "Other", "description": f.description or ""} for f in features]
    if not requirements:
        return JSONResponse({"success": False, "message": "No approved features to export", "results": []})
    cfg = get_integration_config(db, "trello")
    list_id = cfg.get("list_id") or os.getenv("TRELLO_LIST_ID")
    api_key = cfg.get("api_key") or os.getenv("TRELLO_API_KEY")
    token = cfg.get("token") or os.getenv("TRELLO_TOKEN")
    success, message, results = push_to_trello(
        requirements, list_id=list_id or "", api_key=api_key or "", token=token or "", source_filename="approved"
    )
    success_count = sum(1 for r in results if r.get("created"))
    _log_integration(
        db, current_user.id, "trello", "approved", None, len(requirements), success_count, message, results
    )
    return JSONResponse({"success": success, "message": message, "results": results})


@router.post("/api/integration/jira/approved")
async def push_approved_to_jira(
    file_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Push approved features to Jira."""
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        return JSONResponse({"success": False, "message": "No visible features", "results": []})

    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed for this project")

    query = db.query(Feature).filter(Feature.user_id.in_(visible_ids), Feature.status == "approved")
    if file_id is not None:
        query = query.filter(Feature.file_id == file_id)
    if project_id is not None:
        query = query.filter(Feature.project_id == project_id)
    features = query.all()
    requirements = [{"category": f.category or "Other", "description": f.description or ""} for f in features]
    if not requirements:
        return JSONResponse({"success": False, "message": "No approved features to export", "results": []})
    cfg = get_integration_config(db, "jira")
    jira_url = cfg.get("url") or os.getenv("JIRA_URL")
    project_key = cfg.get("project_key") or os.getenv("JIRA_PROJECT_KEY")
    email = cfg.get("email") or os.getenv("JIRA_EMAIL")
    api_token = cfg.get("api_token") or os.getenv("JIRA_API_TOKEN")
    issue_type = cfg.get("issue_type") or "Task"
    success, message, results = push_to_jira(
        requirements, jira_url=jira_url or "", project_key=project_key or "", email=email or "",
        api_token=api_token or "", issue_type=issue_type, source_filename="approved"
    )
    success_count = sum(1 for r in results if r.get("created"))
    _log_integration(
        db, current_user.id, "jira", "approved", None, len(requirements), success_count, message, results
    )
    return JSONResponse({"success": success, "message": message, "results": results})
