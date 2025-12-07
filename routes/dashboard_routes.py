"""Dashboard and user file management routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from database import SessionLocal, ParsedFile, User
from auth import get_current_user, get_db, SECRET_KEY, ALGORITHM
from jose import JWTError, jwt
from fastapi.responses import HTMLResponse
import os

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """Dashboard page showing user's uploaded files."""
    dashboard_path = os.path.join("static", "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


@router.get("/extract", response_class=HTMLResponse)
async def extract_page():
    """Extract page for uploading and analyzing documents."""
    extract_path = os.path.join("static", "extract.html")
    if os.path.exists(extract_path):
        with open(extract_path, "r") as f:
            return HTMLResponse(content=f.read())
    # Fallback to embedded extract page if static file doesn't exist
    return HTMLResponse(content="<h1>Extract page not found</h1>", status_code=404)


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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Get all files uploaded by the current user. Accepts token via Authorization header or query parameter."""
    try:
        print(f"📂 Getting uploads for user...")
        current_user = _get_user_from_token(token, credentials, db)
        print(f"📂 User authenticated: {current_user.id}")
        
        # Execute query and get results immediately
        uploads = db.query(ParsedFile).filter(
            ParsedFile.user_id == current_user.id
        ).order_by(ParsedFile.created_at.desc()).all()
        print(f"📂 Found {len(uploads)} uploads")
        
        # Build result list while DB session is still open
        # FastAPI will automatically close the session after this function returns
        result = []
        for upload in uploads:
            result.append({
                "id": upload.id,
                "filename": upload.filename,
                "summary": upload.summary,
                "extracted_text": upload.extracted_text[:500] if upload.extracted_text else None,  # Preview
                "detected_shapes": upload.detected_shapes or 0,
                "created_at": upload.created_at.isoformat() if upload.created_at else None,
                "view_id": upload.view_id
            })
        
        print(f"✅ Returning {len(result)} uploads")
        return {"uploads": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching uploads: {str(e)}")


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
        upload = db.query(ParsedFile).filter(
            ParsedFile.id == upload_id,
            ParsedFile.user_id == current_user.id
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

