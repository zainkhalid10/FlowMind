"""Project workflow routes: project scope, client approval gate, and task generation."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import can_user_access_project, get_current_user, get_db
from database import Feature, Project, ProjectMember, ProjectTask, User

router = APIRouter()


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    client_user_id: Optional[int] = None


class ProjectMemberRequest(BaseModel):
    user_id: int
    role_in_project: str  # client | project_manager | team_head | member


class TaskUpdateRequest(BaseModel):
    status: Optional[str] = None  # todo | in_progress | blocked | done
    daily_update: Optional[str] = None


@router.get("/api/projects")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List projects visible to current user."""
    if getattr(current_user, "role", None) == "manager":
        projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    else:
        projects = db.query(Project).filter(Project.created_by == current_user.id).all()
        member_rows = db.query(ProjectMember).filter(ProjectMember.user_id == current_user.id).all()
        for row in member_rows:
            p = db.query(Project).filter(Project.id == row.project_id).first()
            if p and p not in projects:
                projects.append(p)

    out = []
    for p in projects:
        out.append(
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "workflow_stage": p.workflow_stage,
                "created_by": p.created_by,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
        )
    return {"projects": out}


@router.post("/api/projects")
async def create_project(
    body: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a project. Manager only by policy."""
    if getattr(current_user, "role", None) != "manager":
        raise HTTPException(status_code=403, detail="Only manager can create projects")

    project = Project(
        name=body.name.strip(),
        description=(body.description or "").strip() or None,
        created_by=current_user.id,
        status="active",
        workflow_stage="requirements_extraction",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Add creator as explicit project manager membership
    db.add(ProjectMember(project_id=project.id, user_id=current_user.id, role_in_project="project_manager"))

    # Optional: add client user to approval flow
    if body.client_user_id:
        client = db.query(User).filter(User.id == body.client_user_id, User.is_active == 1).first()
        if client:
            db.add(ProjectMember(project_id=project.id, user_id=client.id, role_in_project="client"))

    db.commit()
    return {
        "id": project.id,
        "name": project.name,
        "status": project.status,
        "workflow_stage": project.workflow_stage,
    }


@router.post("/api/projects/{project_id}/members")
async def add_project_member(
    project_id: int,
    body: ProjectMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign user into a project role. Manager only."""
    if getattr(current_user, "role", None) != "manager":
        raise HTTPException(status_code=403, detail="Only manager can manage project members")

    _get_project_or_404(project_id, db)

    if body.role_in_project not in ("client", "project_manager", "team_head", "member"):
        raise HTTPException(status_code=400, detail="Invalid project role")

    user = db.query(User).filter(User.id == body.user_id, User.is_active == 1).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    row = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == body.user_id,
    ).first()
    if row:
        row.role_in_project = body.role_in_project
    else:
        db.add(ProjectMember(project_id=project_id, user_id=body.user_id, role_in_project=body.role_in_project))

    db.commit()
    return {"ok": True}


@router.get("/api/projects/{project_id}/overview")
async def project_overview(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Project-level summary across requirements and tasks."""
    if not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed")

    project = _get_project_or_404(project_id, db)
    f_query = db.query(Feature).filter(Feature.project_id == project_id)
    t_query = db.query(ProjectTask).filter(ProjectTask.project_id == project_id)

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "status": project.status,
            "workflow_stage": project.workflow_stage,
        },
        "requirements": {
            "total": f_query.count(),
            "approved": f_query.filter(Feature.status == "approved").count(),
            "denied": f_query.filter(Feature.status == "denied").count(),
            "pending": f_query.filter(Feature.status == "pending").count(),
        },
        "tasks": {
            "total": t_query.count(),
            "todo": t_query.filter(ProjectTask.status == "todo").count(),
            "in_progress": t_query.filter(ProjectTask.status == "in_progress").count(),
            "blocked": t_query.filter(ProjectTask.status == "blocked").count(),
            "done": t_query.filter(ProjectTask.status == "done").count(),
        },
    }


@router.post("/api/projects/{project_id}/client-approval/finalize")
async def finalize_client_approval(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move project from approval stage to execution planning after client/manager confirmation."""
    if not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed")

    project = _get_project_or_404(project_id, db)

    # Permission: manager OR explicit client member for this project
    is_manager = getattr(current_user, "role", None) == "manager"
    pm = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.id,
        ProjectMember.role_in_project == "client",
    ).first()
    if not is_manager and not pm:
        raise HTTPException(status_code=403, detail="Only project client or manager can finalize approval")

    pending = db.query(Feature).filter(Feature.project_id == project_id, Feature.status == "pending").count()
    if pending > 0:
        raise HTTPException(status_code=400, detail="Cannot finalize: pending requirements still exist")

    project.workflow_stage = "execution_planning"
    db.commit()
    return {"ok": True, "workflow_stage": project.workflow_stage}


@router.post("/api/projects/{project_id}/tasks/generate")
async def generate_tasks_from_approved_requirements(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate actionable tasks only from client-approved requirements."""
    if not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed")

    if getattr(current_user, "role", None) not in ("manager", "team_head"):
        raise HTTPException(status_code=403, detail="Only manager or team head can generate tasks")

    project = _get_project_or_404(project_id, db)
    if project.workflow_stage not in ("execution_planning", "execution"):
        raise HTTPException(status_code=400, detail="Tasks can be generated after approval finalization")

    approved = db.query(Feature).filter(
        Feature.project_id == project_id,
        Feature.status == "approved",
    ).all()

    created = 0
    for feat in approved:
        exists = db.query(ProjectTask).filter(ProjectTask.project_id == project_id, ProjectTask.feature_id == feat.id).first()
        if exists:
            continue
        title = f"Implement {feat.category or 'requirement'}"
        db.add(
            ProjectTask(
                project_id=project_id,
                feature_id=feat.id,
                title=title,
                description=feat.description,
                assigned_to_user_id=getattr(feat, "assigned_to_user_id", None),
                created_by=current_user.id,
                status="todo",
            )
        )
        created += 1

    project.workflow_stage = "execution"
    db.commit()
    return {"ok": True, "created_tasks": created, "workflow_stage": project.workflow_stage}


@router.get("/api/projects/{project_id}/tasks")
async def list_project_tasks(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List project tasks visible to a project participant."""
    if not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed")

    tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).order_by(ProjectTask.updated_at.desc()).all()
    out = []
    for t in tasks:
        out.append(
            {
                "id": t.id,
                "project_id": t.project_id,
                "feature_id": t.feature_id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "assigned_to_user_id": t.assigned_to_user_id,
                "created_by": t.created_by,
                "daily_update": t.daily_update,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
        )
    return {"tasks": out}


@router.patch("/api/tasks/{task_id}")
async def update_project_task(
    task_id: int,
    body: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Members can post daily updates on assigned tasks; heads/managers can update any task in visible projects."""
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not can_user_access_project(current_user, task.project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed")

    role = getattr(current_user, "role", None)
    is_owner = task.assigned_to_user_id == current_user.id
    if role not in ("manager", "team_head") and not is_owner:
        raise HTTPException(status_code=403, detail="Only assignee can update this task")

    if body.status is not None:
        if body.status not in ("todo", "in_progress", "blocked", "done"):
            raise HTTPException(status_code=400, detail="Invalid task status")
        task.status = body.status
    if body.daily_update is not None:
        task.daily_update = body.daily_update.strip()

    db.commit()
    return {"ok": True, "task_id": task.id, "status": task.status}
