"""Authentication routes"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from urllib.parse import quote
import os
import secrets
from pathlib import Path
from jose import jwt, JWTError
from dotenv import load_dotenv
from database import SessionLocal, User, Team, ParsedFile, ReviewAssignment
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, get_db, SECRET_KEY, ALGORITHM
)
from utils.email_sender import send_invite_email_async, send_confirmation_email_to_manager_async

router = APIRouter()


class SignupRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    username: Optional[str] = None
    password: str
    role: Optional[str] = "manager"


class LoginRequest(BaseModel):
    email: str
    password: str
    role: Optional[str] = None  # Optional compatibility field


class InviteClientRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    file_id: Optional[int] = None
    due_date: Optional[str] = None


def _get_assigned_file_id(db: Session, user_id: int) -> Optional[int]:
    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.client_id == user_id
    ).order_by(ReviewAssignment.created_at.desc()).first()
    return assignment.file_id if assignment else None


def _build_client_invite_token(client_id: int, file_id: int, email: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(client_id),
        "role": "client",
        "email": email,
        "assigned_file_id": file_id,
        "type": "client_invite",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _resolve_app_base_url() -> str:
    configured = os.getenv("APP_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return "http://127.0.0.1:8000"


@router.post("/api/signup")
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Simple user registration - no verification required."""
    try:
        # Public signup is manager-only by product decision.
        selected_role = "manager"

        requested_name = (request.name or request.username or "").strip()
        base_username = requested_name if requested_name else request.email.split("@")[0]
        normalized = "".join(ch for ch in base_username.lower().replace(" ", "_") if ch.isalnum() or ch == "_")
        username_candidate = normalized or request.email.split("@")[0]

        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.email == request.email)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        username = username_candidate
        suffix = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{username_candidate}{suffix}"
            suffix += 1
        
        # Validate password length
        if len(request.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long"
            )
        
        # Create new user immediately with the selected role.
        hashed_password = get_password_hash(request.password)
        default_team = db.query(Team).first()
        assigned_team_id = default_team.id if default_team and selected_role in ("team_head", "member") else None
        new_user = User(
            email=request.email,
            username=username,
            hashed_password=hashed_password,
            role=selected_role,
            team_id=assigned_team_id
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        role = getattr(new_user, "role", "member") or "member"
        team_id = getattr(new_user, "team_id", None)
        access_token = create_access_token(data={"sub": new_user.id, "role": role, "team_id": team_id})
        team_name = default_team.name if team_id and default_team else None
        return {
            "status": "success",
            "message": "Account created successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "role": role,
            "name": new_user.username,
            "assigned_file_id": _get_assigned_file_id(db, new_user.id),
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
                "role": role,
                "team_id": team_id,
                "team_name": team_name,
                "avatar_url": getattr(new_user, "oauth_profile_picture", None),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        error_trace = traceback.format_exc()
        print(f"Signup error: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating account: {str(e)}"
        )


@router.post("/auth/public/signup")
async def public_signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Public signup alias to avoid collisions with legacy endpoints."""
    return await signup(request, db)


@router.post("/auth/signup")
async def auth_signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Auth namespace signup alias."""
    return await signup(request, db)


@router.post("/api/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Simple user login."""
    try:
        # Find user by email
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if user.is_active == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        role = getattr(user, "role", "member") or "member"
        role_sel = (request.role or "").strip().lower()
        if role_sel and role_sel not in ("manager", "client"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role selected")
        if role_sel and role_sel != role.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This account is a {role.replace('_', ' ').title()}. Please select '{role.replace('_', ' ').title()}' or use the correct account."
            )
        team_id = getattr(user, "team_id", None)
        access_token = create_access_token(data={"sub": user.id, "role": role, "team_id": team_id})
        team_name = (getattr(user, "team", None) and getattr(user.team, "name", None)) or None
        return {
            "status": "success",
            "message": "Login successful",
            "access_token": access_token,
            "token_type": "bearer",
            "role": role,
            "name": user.username,
            "assigned_file_id": _get_assigned_file_id(db, user.id),
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": role,
                "team_id": team_id,
                "team_name": team_name,
                "avatar_url": getattr(user, "oauth_profile_picture", None),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during login: {str(e)}"
        )


@router.post("/auth/public/login")
async def public_login(request: LoginRequest, db: Session = Depends(get_db)):
    """Public login alias to avoid collisions with legacy endpoints."""
    return await login(request, db)


@router.post("/auth/login")
async def auth_login(request: LoginRequest, db: Session = Depends(get_db)):
    """Auth namespace login alias."""
    return await login(request, db)


@router.get("/auth/client-invite/resolve")
async def resolve_client_invite(token: str, db: Session = Depends(get_db)):
    """Resolve a client invite token to prefill a client-only login flow."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired invite link")

    if (payload.get("type") or "") != "client_invite":
        raise HTTPException(status_code=400, detail="Invalid invite token type")

    try:
        client_id = int(payload.get("sub"))
        file_id = int(payload.get("assigned_file_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Malformed invite token")

    email = (payload.get("email") or "").strip().lower()
    user = db.query(User).filter(User.id == client_id).first()
    if not user or (user.role or "").lower() != "client":
        raise HTTPException(status_code=404, detail="Client account not found")
    if email and (user.email or "").strip().lower() != email:
        raise HTTPException(status_code=400, detail="Invite link does not match account")

    assignment = db.query(ReviewAssignment).filter(
        ReviewAssignment.file_id == file_id,
        ReviewAssignment.client_id == user.id,
    ).order_by(ReviewAssignment.created_at.desc()).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Review assignment not found for this invite")

    return {
        "email": user.email,
        "name": user.username,
        "role": "client",
        "assigned_file_id": assignment.file_id,
    }


@router.post("/api/manager/invite-client")
async def invite_client(
    request: InviteClientRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manager creates a client account and receives a temporary password to share manually."""
    if (getattr(current_user, "role", "") or "").lower() != "manager":
        raise HTTPException(status_code=403, detail="Manager only")

    parsed_file = None
    if request.file_id is not None:
        parsed_file = db.query(ParsedFile).filter(ParsedFile.id == request.file_id).first()
        if not parsed_file:
            raise HTTPException(status_code=404, detail="File not found")

    existing = db.query(User).filter(User.email == request.email).first()
    if existing and (getattr(existing, "role", "") or "").lower() != "client":
        raise HTTPException(status_code=400, detail="Email already registered as non-client account")

    temporary_password = secrets.token_urlsafe(10)
    created_new_client = False

    if existing:
        client_user = existing
        client_user.hashed_password = get_password_hash(temporary_password)
        client_user.role = "client"
        client_user.is_active = 1
    else:
        base_name = (request.name or request.email.split("@")[0]).strip()
        normalized = "".join(ch for ch in base_name.lower().replace(" ", "_") if ch.isalnum() or ch == "_")
        username_candidate = normalized or request.email.split("@")[0]
        username = username_candidate
        suffix = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{username_candidate}{suffix}"
            suffix += 1

        client_user = User(
            email=request.email,
            username=username,
            hashed_password=get_password_hash(temporary_password),
            role="client",
            team_id=None,
        )
        db.add(client_user)
        created_new_client = True

    db.commit()
    db.refresh(client_user)

    due_date = None
    if request.due_date:
        try:
            due_date = datetime.fromisoformat(request.due_date)
        except ValueError:
            due_date = None

    email_warning = None
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path)
    mail_email = os.getenv("MAIL_EMAIL", "").strip()
    mail_password = os.getenv("MAIL_PASSWORD", "").strip()
    can_send_email = bool(mail_email and mail_password and len(mail_password) == 16)
    if not can_send_email:
        email_warning = (
            "Email delivery not configured correctly. "
            "Gmail app password must be 16 characters."
        )

    if parsed_file:
        assignment = db.query(ReviewAssignment).filter(
            ReviewAssignment.file_id == parsed_file.id,
            ReviewAssignment.client_id == client_user.id,
        ).order_by(ReviewAssignment.created_at.desc()).first()

        if assignment:
            assignment.manager_id = current_user.id
            assignment.due_date = due_date
            assignment.submitted_at = None
            assignment.temp_password = temporary_password
        else:
            assignment = ReviewAssignment(
                file_id=parsed_file.id,
                manager_id=current_user.id,
                client_id=client_user.id,
                temp_password=temporary_password,
                due_date=due_date,
            )
            db.add(assignment)
        db.commit()

        invite_token = _build_client_invite_token(client_user.id, parsed_file.id, client_user.email)
        invite_link = f"{_resolve_app_base_url()}/login.html?invite_token={quote(invite_token)}"

        # Send invitation emails only when SMTP config appears valid.
        deadline_str = due_date.isoformat() if due_date else ""
        if can_send_email:
            send_invite_email_async(
                to_email=client_user.email,
                to_name=request.name or client_user.username,
                manager_name=current_user.username,
                filename=parsed_file.filename,
                deadline=deadline_str,
                temp_password=temporary_password,
                login_link=invite_link,
            )

            send_confirmation_email_to_manager_async(
                manager_email=current_user.email,
                manager_name=current_user.username,
                client_email=client_user.email,
                client_name=request.name or client_user.username,
                filename=parsed_file.filename,
                deadline=deadline_str,
                temp_password=temporary_password,
            )
    else:
        # No file attached — the client is still being invited, so the
        # email still goes out. The login link is generic (no invite token)
        # because there's no assigned document yet.
        invite_link = f"{_resolve_app_base_url()}/login.html"

        if can_send_email:
            send_invite_email_async(
                to_email=client_user.email,
                to_name=request.name or client_user.username,
                manager_name=current_user.username,
                filename="(your manager will attach a document soon)",
                deadline=request.due_date or "",
                temp_password=temporary_password,
                login_link=invite_link,
            )
            send_confirmation_email_to_manager_async(
                manager_email=current_user.email,
                manager_name=current_user.username,
                client_email=client_user.email,
                client_name=request.name or client_user.username,
                filename="(No specific document)",
                deadline="",
                temp_password=temporary_password,
            )

    return {
        "status": "success",
        "message": "Client account created successfully" if created_new_client else "Client account updated successfully",
        "email_warning": email_warning,
        "email_delivery_enabled": can_send_email,
        "client": {
            "id": client_user.id,
            "email": client_user.email,
            "username": client_user.username,
            "role": client_user.role,
        },
        "client_id": client_user.id,
        "temp_password": temporary_password,
        "temporary_password": temporary_password,
        "assigned_file_id": parsed_file.id if parsed_file else None,
        "invite_link": invite_link,
    }


@router.post("/auth/invite-client")
async def invite_client_auth_alias(
    request: InviteClientRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Alias endpoint for client invitation workflow requested by Part 4."""
    return await invite_client(request, current_user, db)


@router.get("/api/me")
async def get_current_user_info(
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Get current user information. Accepts token via Authorization header or query parameter."""
    from auth import SECRET_KEY, ALGORITHM
    from jose import JWTError, jwt
    
    # Try to get token from query parameter first, then from header
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
    if user is None:
        raise credentials_exception
    
    if user.is_active == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    role = getattr(user, "role", "member") or "member"
    team_id = getattr(user, "team_id", None)
    team_name = user.team.name if (getattr(user, "team", None) and user.team) else None
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": role,
        "team_id": team_id,
        "team_name": team_name,
        "avatar_url": getattr(user, "oauth_profile_picture", None),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/api/manager/clients")
async def get_manager_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all clients created by the current manager with their project details."""
    if (getattr(current_user, "role", "") or "").lower() != "manager":
        raise HTTPException(status_code=403, detail="Manager only")
    
    # Get all review assignments where this user is the manager
    assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.manager_id == current_user.id
    ).order_by(ReviewAssignment.created_at.desc()).all()
    
    clients_data = []
    seen_client_file_pairs = set()
    
    for assignment in assignments:
        client_user = db.query(User).filter(User.id == assignment.client_id).first()
        pair_key = (assignment.client_id, assignment.file_id)
        if not client_user or pair_key in seen_client_file_pairs:
            continue

        seen_client_file_pairs.add(pair_key)
        
        # Get the file name if available
        filename = "(No specific document)"
        if assignment.file_id:
            file_record = db.query(ParsedFile).filter(ParsedFile.id == assignment.file_id).first()
            if file_record:
                filename = file_record.filename
        
        # Get temp password from review assignment if available
        temp_password = getattr(assignment, "temp_password", None) or "N/A"
        invite_link = None
        if assignment.file_id:
            invite_token = _build_client_invite_token(client_user.id, assignment.file_id, client_user.email)
            invite_link = f"{_resolve_app_base_url()}/login.html?invite_token={quote(invite_token)}"
        else:
            invite_link = f"{_resolve_app_base_url()}/login.html"
        
        clients_data.append({
            "assignment_id": assignment.id,
            "client_id": client_user.id,
            "client_email": client_user.email,
            "client_name": client_user.username,
            "temp_password": temp_password,
            "invite_link": invite_link,
            "created_at": client_user.created_at.isoformat() if client_user.created_at else None,
            "file_id": assignment.file_id,
            "filename": filename,
            "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
            "submitted_at": assignment.submitted_at.isoformat() if assignment.submitted_at else None,
        })
    
    return {
        "status": "success",
        "clients": clients_data,
        "total": len(clients_data)
    }

