"""
Feature Approval Routes
Handles feature approval/denial by clients
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import SessionLocal, Feature, ParsedFile
from auth import get_current_user, User
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

class BulkFeatureUpdate(BaseModel):
    feature_ids: List[int]
    status: str

@router.get("/api/features")
async def get_features(
    status: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all features for the current user with optional filters."""
    query = db.query(Feature).filter(Feature.user_id == current_user.id)
    
    if status:
        query = query.filter(Feature.status == status)
    if category:
        query = query.filter(Feature.category == category)
    
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
            "created_at": feature.created_at.isoformat() if feature.created_at else None
        })
    
    return {"features": result, "total": len(result)}

@router.get("/api/features/stats")
async def get_feature_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get feature statistics for the current user."""
    total = db.query(Feature).filter(Feature.user_id == current_user.id).count()
    approved = db.query(Feature).filter(
        Feature.user_id == current_user.id,
        Feature.status == "approved"
    ).count()
    denied = db.query(Feature).filter(
        Feature.user_id == current_user.id,
        Feature.status == "denied"
    ).count()
    pending = db.query(Feature).filter(
        Feature.user_id == current_user.id,
        Feature.status == "pending"
    ).count()
    
    return {
        "total": total,
        "approved": approved,
        "denied": denied,
        "pending": pending
    }

@router.put("/api/features/{feature_id}")
async def update_feature_status(
    feature_id: int,
    update: FeatureUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update feature approval status."""
    feature = db.query(Feature).filter(
        Feature.id == feature_id,
        Feature.user_id == current_user.id
    ).first()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    if update.status not in ["approved", "denied", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    feature.status = update.status
    db.commit()
    
    return {"success": True, "feature_id": feature_id, "status": update.status}

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

def parse_and_save_features(extracted_text: str, user_id: int, file_id: int, db: Session):
    """
    Parse extracted requirements text and save as individual features.
    Called after document processing.
    """
    try:
        # Parse the formatted text into features
        lines = extracted_text.split('\n')
        current_category = None
        features_saved = 0
        
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
        print(f"✅ Saved {features_saved} features for approval")
        return features_saved
        
    except Exception as e:
        print(f"⚠️ Error parsing features: {e}")
        db.rollback()
        return 0

