"""File upload and extraction routes"""
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session
from database import SessionLocal, ParsedFile, User
from auth import get_current_user, get_db, can_user_access_project
from services.document_service import analyze_document, analyze_with_agent
from services.progress_storage import create_progress_tracker, remove_progress_tracker
import asyncio
import os
import json
import time
from datetime import datetime, timedelta

router = APIRouter()
_DEBUG_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug-0e985e.log")

# Store results temporarily
_processing_results = {}

# File upload configuration
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB default
# Manager-only product decision: PPT/PPTX and plain text are no longer
# accepted. The allowed formats cover real SRS artefacts: PDF, Word docs
# (legacy + modern), and images (for screenshots / architecture diagrams).
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.gif', '.bmp'}

def validate_file_extension(filename: str) -> bool:
    """Validate file extension is allowed."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def validate_file_size(file_size: int) -> bool:
    """Validate file size is within limits."""
    return file_size <= MAX_FILE_SIZE


@router.post("/upload_client_doc")
async def upload_client_doc(
    file: UploadFile = File(...),
    project_id: int = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Basic text extraction only; returns JSON. Requires authentication."""
    # Validate file extension
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file to check size
    contents = await file.read()
    file_size = len(contents)
    
    # Validate file size
    if not validate_file_size(file_size):
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Reset file pointer for processing
    await file.seek(0)
    
    # Create progress tracker
    tracker_id, tracker = create_progress_tracker()
    tracker.start()

    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed to upload into this project")
    
    try:
        # Process document with progress tracking
        result = await analyze_document(
            file,
            current_user.id,
            db,
            progress_tracker_id=tracker_id,
            project_id=project_id,
        )
        # Add tracker ID to response
        result["progress_tracker_id"] = tracker_id

        # Resolve file_id so the frontend can deep-link into the requirements
        # view without a second /api/my-uploads round trip. Mirrors the
        # agent-upload flow below.
        try:
            if isinstance(result, dict) and not result.get("file_id"):
                view_id = result.get("view_id")
                row = None
                if view_id:
                    row = (
                        db.query(ParsedFile)
                        .filter(ParsedFile.view_id == view_id)
                        .order_by(ParsedFile.id.desc())
                        .first()
                    )
                if row is None:
                    cutoff = datetime.utcnow() - timedelta(minutes=10)
                    row = (
                        db.query(ParsedFile)
                        .filter(
                            ParsedFile.user_id == current_user.id,
                            ParsedFile.filename == file.filename,
                            ParsedFile.created_at >= cutoff,
                        )
                        .order_by(ParsedFile.created_at.desc())
                        .first()
                    )
                if row:
                    result["file_id"] = row.id
        except Exception:
            pass

        return result
    except Exception as e:
        remove_progress_tracker(tracker_id)
        raise


@router.post("/upload_agent_doc")
@router.post("/upload/agent_doc")
async def upload_agent_doc(
    file: UploadFile = File(...),
    project_id: int = Form(None),
    basic_extraction_text: str = Form(None),
    basic_extraction_full_text: str = Form(None),
    basic_extraction_image_summaries: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """JSON response for AI agent document analysis. Requires authentication.
    Optionally accepts Basic Extraction data to merge with AI analysis."""
    # Validate file extension
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file to check size
    contents = await file.read()
    file_size = len(contents)
    
    # Validate file size
    if not validate_file_size(file_size):
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Reset file pointer for processing
    await file.seek(0)
    
    # Parse Basic Extraction image summaries if provided
    basic_extraction_data = None
    if basic_extraction_text or basic_extraction_full_text or basic_extraction_image_summaries:
        import json
        image_summaries = []
        if basic_extraction_image_summaries:
            try:
                image_summaries = json.loads(basic_extraction_image_summaries)
            except:
                pass
        
        basic_extraction_data = {
            "extracted_text": basic_extraction_text or "",
            "full_text": basic_extraction_full_text or "",
            "image_summaries": image_summaries
        }
        print(f"✅ Received Basic Extraction data: {len(basic_extraction_text or '')} chars text, {len(image_summaries)} image summaries")
    
    # Create progress tracker
    tracker_id, tracker = create_progress_tracker()
    tracker.start()

    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed to upload into this project")
    
    # #region agent log
    try:
        f = open(_DEBUG_LOG, "a", encoding="utf-8"); f.write(json.dumps({"sessionId": "0e985e", "hypothesisId": "A", "location": "upload_routes.py:upload_agent_doc", "message": "upload_agent_doc before analyze_with_agent", "data": {"filename": file.filename}, "timestamp": int(time.time() * 1000)}) + "\n"); f.close()
    except Exception:
        pass
    # #endregion
    try:
        # Process document with progress tracking and Basic Extraction data
        result = await analyze_with_agent(
            file, 
            current_user.id, 
            db, 
            progress_tracker_id=tracker_id,
            basic_extraction_data=basic_extraction_data,
            project_id=project_id,
        )
        # #region agent log
        try:
            f = open(_DEBUG_LOG, "a", encoding="utf-8"); f.write(json.dumps({"sessionId": "0e985e", "hypothesisId": "C", "location": "upload_routes.py:upload_agent_doc", "message": "analyze_with_agent returned success", "data": {"filename": file.filename}, "timestamp": int(time.time() * 1000)}) + "\n"); f.close()
        except Exception:
            pass
        # #endregion
        # Add tracker ID to response
        result["progress_tracker_id"] = tracker_id
        try:
            view_id = result.get("view_id") if isinstance(result, dict) else None
            if view_id:
                row = db.query(ParsedFile).filter(ParsedFile.view_id == view_id).order_by(ParsedFile.id.desc()).first()
                if row:
                    result["file_id"] = row.id
            # Fallback: resolve latest matching file for this user when view_id lookup is late.
            if not result.get("file_id"):
                cutoff = datetime.utcnow() - timedelta(minutes=10)
                row = db.query(ParsedFile).filter(
                    ParsedFile.user_id == current_user.id,
                    ParsedFile.filename == file.filename,
                    ParsedFile.created_at >= cutoff,
                ).order_by(ParsedFile.created_at.desc()).first()
                if row:
                    result["file_id"] = row.id
        except Exception:
            pass
        return result
    except Exception:
        remove_progress_tracker(tracker_id)
        raise


@router.get("/api/progress/{tracker_id}")
async def get_progress(tracker_id: str):
    """Get progress for a specific tracker."""
    from services.progress_storage import get_progress_tracker
    
    tracker = get_progress_tracker(tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="Progress tracker not found")
    
    return tracker.get_progress()

