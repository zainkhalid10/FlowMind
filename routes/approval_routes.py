"""
Feature Approval Routes
Handles feature approval/denial by clients
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from database import SessionLocal, Feature, ParsedFile
from auth import get_current_user, User
from datetime import datetime
import re

router = APIRouter()

@router.get("/approve")
async def serve_approve_page():
    """Serve the feature approval page - no auth required on page serve."""
    import os
    approve_path = os.path.join("static", "approve.html")
    if os.path.exists(approve_path):
        from fastapi.responses import HTMLResponse
        with open(approve_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content="<h1>Approve page not found</h1>", status_code=404)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class FeatureResponse(BaseModel):
    id: int
    category: str
    description: str
    status: str
    quality_score: int
    file_id: Optional[int]
    filename: Optional[str]
    
    class Config:
        from_attributes = True

class FeatureUpdate(BaseModel):
    status: str  # approved or denied
    feedback: Optional[str] = None  # Client feedback on the requirement

class BulkFeatureUpdate(BaseModel):
    feature_ids: List[int]
    status: str

@router.get("/api/features")
async def get_features(
    status: Optional[str] = None,
    category: Optional[str] = None,
    file_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all features for the current user with optional filters.
    When file_id is not specified, only returns features from the most recent run of each file."""
    query = db.query(Feature).filter(Feature.user_id == current_user.id)
    
    if status:
        query = query.filter(Feature.status == status)
    if category:
        query = query.filter(Feature.category == category)
    if file_id:
        # If specific file_id is provided, filter by it
        query = query.filter(Feature.file_id == file_id)
    else:
        # If no file_id specified, only show features from the most recent run of each file
        # Each run creates a new ParsedFile record with a unique auto-incrementing ID
        # Get the most recent ParsedFile.id for each unique filename
        # Use both max(id) and max(created_at) to ensure we get the absolute latest
        subquery = db.query(
            ParsedFile.filename,
            func.max(ParsedFile.id).label('latest_file_id'),
            func.max(ParsedFile.created_at).label('latest_created_at')
        ).filter(
            ParsedFile.user_id == current_user.id
        ).group_by(ParsedFile.filename).subquery()
        
        # Get the list of latest file IDs (these represent the current/most recent run for each file)
        latest_file_ids = [row[0] for row in db.query(subquery.c.latest_file_id).all()]
        
        if latest_file_ids:
            # Only show features from these most recent runs
            query = query.filter(Feature.file_id.in_(latest_file_ids))
        else:
            # No files found, return empty result
            from fastapi.responses import JSONResponse
            return JSONResponse(
                content={"features": [], "total": 0},
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
            )
    
    features = query.order_by(Feature.created_at.desc()).all()
    
    # Join with file info
    result = []
    for feature in features:
        file = db.query(ParsedFile).filter(ParsedFile.id == feature.file_id).first()
        result.append({
            "id": feature.id,
            "category": feature.category,
            "description": feature.description,
            "status": feature.status,
            "quality_score": feature.quality_score,
            "file_id": feature.file_id,
            "filename": file.filename if file else "Unknown",
            "feedback": feature.feedback or "",
            "created_at": feature.created_at.isoformat() if feature.created_at else None
        })
    
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"features": result, "total": len(result)},
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )

@router.get("/api/features/stats")
async def get_feature_stats(
    file_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get feature statistics for the current user, optionally filtered by file_id.
    When file_id is not specified, only counts features from the most recent run of each file."""
    from fastapi.responses import JSONResponse
    
    query = db.query(Feature).filter(Feature.user_id == current_user.id)
    
    if file_id:
        query = query.filter(Feature.file_id == file_id)
    else:
        # If no file_id specified, only count features from the most recent run of each file
        # Each run creates a new ParsedFile record with a unique auto-incrementing ID
        subquery = db.query(
            ParsedFile.filename,
            func.max(ParsedFile.id).label('latest_file_id')
        ).filter(
            ParsedFile.user_id == current_user.id
        ).group_by(ParsedFile.filename).subquery()
        
        # Get the list of latest file IDs (these represent the current/most recent run for each file)
        latest_file_ids = [row[0] for row in db.query(subquery.c.latest_file_id).all()]
        
        if latest_file_ids:
            # Only count features from these most recent runs
            query = query.filter(Feature.file_id.in_(latest_file_ids))
        else:
            # No files found, return zero stats
            return JSONResponse(
                content={
                    "total": 0,
                    "approved": 0,
                    "denied": 0,
                    "pending": 0
                },
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
            )
    
    total = query.count()
    approved = query.filter(Feature.status == "approved").count()
    denied = query.filter(Feature.status == "denied").count()
    pending = query.filter(Feature.status == "pending").count()
    
    return JSONResponse(
        content={
            "total": total,
            "approved": approved,
            "denied": denied,
            "pending": pending
        },
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )

@router.get("/api/documents")
async def get_user_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all documents for the current user that have features.
    Only returns the most recent run of each unique filename."""
    from fastapi.responses import JSONResponse
    
    # Get the most recent ParsedFile.id for each unique filename that has features
    subquery = db.query(
        ParsedFile.filename,
        func.max(ParsedFile.id).label('latest_file_id')
    ).join(Feature).filter(
        ParsedFile.user_id == current_user.id,
        Feature.user_id == current_user.id
    ).group_by(ParsedFile.filename).subquery()
    
    # Get the actual ParsedFile records for these latest file IDs
    latest_file_ids = [row[0] for row in db.query(subquery.c.latest_file_id).all()]
    
    if not latest_file_ids:
        return JSONResponse(
            content={"documents": []},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        )
    
    documents = db.query(ParsedFile).filter(
        ParsedFile.id.in_(latest_file_ids)
    ).order_by(ParsedFile.created_at.desc()).all()
    
    result = []
    for doc in documents:
        feature_count = db.query(Feature).filter(
            Feature.file_id == doc.id,
            Feature.user_id == current_user.id
        ).count()
        # Format the timestamp for display
        run_label = "Current Run"
        if doc.created_at:
            try:
                if isinstance(doc.created_at, str):
                    dt = datetime.fromisoformat(doc.created_at.replace('Z', '+00:00'))
                else:
                    dt = doc.created_at
                run_label = dt.strftime("%Y-%m-%d %H:%M")
            except:
                run_label = "Current Run"
        
        result.append({
            "id": doc.id,
            "filename": doc.filename,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "feature_count": feature_count,
            "run_label": run_label
        })
    
    return JSONResponse(
        content={"documents": result},
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )

@router.put("/api/features/{feature_id}")
async def update_feature_status(
    feature_id: int,
    update: FeatureUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update feature approval status and/or feedback."""
    feature = db.query(Feature).filter(
        Feature.id == feature_id,
        Feature.user_id == current_user.id
    ).first()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    if update.status and update.status not in ["approved", "denied", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    if update.status:
        feature.status = update.status
    if update.feedback is not None:
        feature.feedback = update.feedback
    db.commit()
    
    return {"success": True, "feature_id": feature_id, "status": feature.status, "feedback": feature.feedback or ""}

class FeedbackUpdate(BaseModel):
    feedback: str

@router.put("/api/features/{feature_id}/feedback")
async def update_feature_feedback(
    feature_id: int,
    update: FeedbackUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update feedback for a specific feature."""
    feature = db.query(Feature).filter(
        Feature.id == feature_id,
        Feature.user_id == current_user.id
    ).first()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    feature.feedback = update.feedback
    db.commit()
    
    return {"success": True, "feature_id": feature_id, "feedback": feature.feedback or ""}

@router.put("/api/features/bulk-update")
async def bulk_update_features(
    update: BulkFeatureUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk update feature statuses."""
    if update.status not in ["approved", "denied", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    # Update all specified features
    updated = db.query(Feature).filter(
        Feature.id.in_(update.feature_ids),
        Feature.user_id == current_user.id
    ).update({"status": update.status}, synchronize_session=False)
    
    db.commit()
    
    return {"success": True, "updated": updated, "status": update.status}

@router.delete("/api/features/{feature_id}")
async def delete_feature(
    feature_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a feature."""
    feature = db.query(Feature).filter(
        Feature.id == feature_id,
        Feature.user_id == current_user.id
    ).first()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    db.delete(feature)
    db.commit()
    
    return {"success": True, "feature_id": feature_id}

@router.delete("/api/features/cleanup/old")
async def cleanup_old_features(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete ALL features for the current user, but keep patterns and self-learning intact."""
    try:
        # Delete ALL features for the current user
        deleted_count = db.query(Feature).filter(
            Feature.user_id == current_user.id
        ).delete(synchronize_session=False)
        
        db.commit()
        
        # Note: Patterns and self-learning are stored in ChromaDB and agent memory,
        # not in the Feature table, so they remain intact
        
        return {
            "success": True,
            "deleted": deleted_count,
            "message": f"Deleted all {deleted_count} features. Patterns and self-learning remain intact."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error cleaning up features: {str(e)}")

@router.delete("/api/features/cleanup/all")
async def cleanup_all_features(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete ALL features for the current user. Use with caution!"""
    try:
        deleted_count = db.query(Feature).filter(
            Feature.user_id == current_user.id
        ).delete(synchronize_session=False)
        
        db.commit()
        
        return {
            "success": True,
            "deleted": deleted_count,
            "message": f"Deleted all {deleted_count} features for user"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting features: {str(e)}")

def parse_and_save_features(extracted_text: str, user_id: int, file_id: int, db: Session, image_summaries: list = None):
    """
    Parse extracted requirements text and save as individual features.
    Merges content from both text extraction and image summaries.
    Called after document processing.
    
    Args:
        extracted_text: Text extracted from document (from RAG agent)
        user_id: User ID
        file_id: ParsedFile ID
        db: Database session
        image_summaries: Optional list of image summaries to merge with text extraction
    """
    try:
        # Merge image summaries with extracted text if available
        merged_content = extracted_text
        
        if image_summaries and len(image_summaries) > 0:
            # Extract requirements from image summaries
            image_requirements = []
            requirement_patterns = [
                r'(?:The system|System|It|Application|Software|Platform).*?shall.*?\.',
                r'(?:Must|Should|Will|Can|May).*?\.',
                r'(?:Requirement|Feature|Function).*?:.*?\.',
            ]
            for img_summary in image_summaries:
                if isinstance(img_summary, dict):
                    # Extract from different possible keys
                    summary_text = img_summary.get('summary', '') or img_summary.get('interpretation', '') or img_summary.get('full_interpretation', '')
                    if summary_text:
                        # Look for requirement-like patterns in image summaries
                        # Extract sentences that look like requirements
                        for pattern in requirement_patterns:
                            matches = re.findall(pattern, summary_text, re.IGNORECASE)
                            image_requirements.extend(matches)
                elif isinstance(img_summary, str):
                    summary_text = img_summary
                    for pattern in requirement_patterns:
                        matches = re.findall(pattern, summary_text, re.IGNORECASE)
                        image_requirements.extend(matches)
            
            # Add image requirements to merged content
            if image_requirements:
                merged_content += "\n\n# Requirements from Images:\n"
                for req in image_requirements[:20]:  # Limit to 20 to avoid too much duplication
                    merged_content += f"- {req}\n"
                print(f"📸 Merged {len(image_requirements)} requirements from {len(image_summaries)} images")
        
        # Parse the merged content into features
        lines = merged_content.split('\n')
        current_category = None
        features_saved = 0
        seen_descriptions = set()  # Track to avoid duplicates
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if it's a category header
            if line.endswith(':') and '(' in line:
                # Extract category name (e.g., "Functional Requirements (5 items)")
                category_match = re.match(r'(.+?)\s*\(', line)
                if category_match:
                    category_raw = category_match.group(1).strip().rstrip(':')
                    # Normalize category name
                    if 'functional' in category_raw.lower() and 'non' not in category_raw.lower():
                        current_category = 'functional'
                    elif 'non-functional' in category_raw.lower():
                        current_category = 'non_functional'
                    elif 'user' in category_raw.lower():
                        current_category = 'user'
                    elif 'business' in category_raw.lower():
                        current_category = 'business'
                    else:
                        current_category = 'other'
                continue
            
            # Check if it's a feature line (starts with -, ✅, ⚠️, or ❌)
            if line.startswith('-') or line.startswith('✅') or line.startswith('⚠️') or line.startswith('❌'):
                # Extract quality score if present
                quality_score = 0
                description = line
                
                # Remove bullet point
                if line.startswith('-'):
                    description = line[1:].strip()
                
                # Extract quality indicator and score
                if '✅' in description or '⚠️' in description or '❌' in description:
                    # Remove indicator
                    description = re.sub(r'^[✅⚠️❌]\s*', '', description)
                    
                    # Extract score if present (format: (85) or similar)
                    score_match = re.match(r'\((\d+)\)\s*-?\s*(.+)', description)
                    if score_match:
                        quality_score = int(score_match.group(1))
                        description = score_match.group(2).strip()
                
                # Skip empty or placeholder descriptions
                if not description or description.lower() in ['(none)', 'none']:
                    continue
                
                # Normalize description for duplicate checking
                normalized_desc = re.sub(r'\s+', ' ', description.strip().lower())
                if normalized_desc in seen_descriptions:
                    continue  # Skip duplicates
                seen_descriptions.add(normalized_desc)
                
                # Save feature to database
                if current_category:
                    feature = Feature(
                        user_id=user_id,
                        file_id=file_id,
                        category=current_category,
                        description=description,
                        status='pending',
                        quality_score=quality_score
                    )
                    db.add(feature)
                    features_saved += 1
        
        db.commit()
        print(f"✅ Saved {features_saved} features for approval (merged from text + {len(image_summaries) if image_summaries else 0} images)")
        return features_saved
        
    except Exception as e:
        print(f"⚠️ Error parsing features: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 0

