"""Document analysis service - wraps internal functions"""
# Import will be done at runtime to avoid circular imports
from fastapi import UploadFile
from sqlalchemy.orm import Session
from typing import Optional


async def analyze_document(
    file: UploadFile,
    user_id: int,
    db: Session,
    progress_tracker_id: Optional[str] = None,
    project_id: Optional[int] = None,
):
    """Analyze document and save with user_id."""
    # Import here to avoid circular import
    from flowmind import _analyze_document_internal
    return await _analyze_document_internal(
        file,
        user_id=user_id,
        db_session=db,
        progress_tracker_id=progress_tracker_id,
        project_id=project_id,
    )


async def analyze_with_agent(
    file: UploadFile,
    user_id: int,
    db: Session,
    progress_tracker_id: Optional[str] = None,
    basic_extraction_data: Optional[dict] = None,
    project_id: Optional[int] = None,
):
    """Analyze document with AI agent and save with user_id.
    Optionally merges Basic Extraction data for improved results."""
    # Import here to avoid circular import
    from flowmind import _analyze_with_agent_internal
    return await _analyze_with_agent_internal(
        file,
        user_id=user_id,
        db_session=db,
        progress_tracker_id=progress_tracker_id,
        basic_extraction_data=basic_extraction_data,
        project_id=project_id,
    )

