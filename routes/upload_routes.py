"""File upload and extraction routes"""
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import SessionLocal, ParsedFile, User
from auth import get_current_user, get_db
from services.document_service import analyze_document, analyze_with_agent
from services.progress_storage import create_progress_tracker, remove_progress_tracker
import asyncio
import os

router = APIRouter()

# Store results temporarily
_processing_results = {}

# File upload configuration
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB default
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.txt', '.png', '.jpg', '.jpeg', '.gif', '.bmp'}

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
    
    try:
        # Process document with progress tracking
        result = await analyze_document(file, current_user.id, db, progress_tracker_id=tracker_id)
        # Add tracker ID to response
        result["progress_tracker_id"] = tracker_id
        return result
    except Exception as e:
        remove_progress_tracker(tracker_id)
        raise


@router.post("/upload_agent_doc")
async def upload_agent_doc(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """JSON response for AI agent document analysis. Requires authentication."""
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
    
    try:
        # Process document with progress tracking
        result = await analyze_with_agent(file, current_user.id, db, progress_tracker_id=tracker_id)
        # Add tracker ID to response
        result["progress_tracker_id"] = tracker_id
        return result
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("Analyze_with_agent error:", tb)
        remove_progress_tracker(tracker_id)
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@router.get("/api/progress/{tracker_id}")
async def get_progress(tracker_id: str):
    """Get progress for a specific tracker."""
    from services.progress_storage import get_progress_tracker
    
    tracker = get_progress_tracker(tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="Progress tracker not found")
    
    return tracker.get_progress()

