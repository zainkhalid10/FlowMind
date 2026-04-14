"""
Feature Approval Routes
Handles feature approval/denial by clients
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from pathlib import Path
from database import SessionLocal, Feature, ParsedFile, ImageMeta, User
from auth import get_current_user, get_visible_user_ids, can_user_access_project, User
from datetime import datetime
import re

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

router = APIRouter()
VISUAL_EXPLANATION_CACHE: Dict[str, Dict[str, Any]] = {}


class VisualExplainRequest(BaseModel):
    image_id: Optional[str] = None
    image_url: Optional[str] = None
    ocr_text: Optional[str] = None

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
    status: Optional[str] = None  # approved, denied, or pending
    feedback: Optional[str] = None  # Client feedback on the requirement
    assigned_to_user_id: Optional[int] = None  # Team head/manager assigns to a member

class BulkFeatureUpdate(BaseModel):
    feature_ids: List[int]
    status: str

@router.get("/api/features")
async def get_features(
    status: Optional[str] = None,
    category: Optional[str] = None,
    file_id: Optional[int] = None,
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get features for users the current user can see (self, team, or all for manager)."""
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        from fastapi.responses import JSONResponse
        return JSONResponse(content={"features": [], "total": 0}, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed for this project")

    query = db.query(Feature).filter(Feature.user_id.in_(visible_ids))
    if project_id is not None:
        query = query.filter(Feature.project_id == project_id)
    if status:
        query = query.filter(Feature.status == status)
    if category:
        query = query.filter(Feature.category == category)
    if file_id:
        query = query.filter(Feature.file_id == file_id)
    else:
        parsed_query = db.query(
            ParsedFile.filename,
            ParsedFile.user_id,
            func.max(ParsedFile.id).label('latest_file_id'),
            func.max(ParsedFile.created_at).label('latest_created_at')
        ).filter(
            ParsedFile.user_id.in_(visible_ids)
        )
        if project_id is not None:
            parsed_query = parsed_query.filter(ParsedFile.project_id == project_id)

        subquery = parsed_query.group_by(ParsedFile.filename, ParsedFile.user_id).subquery()
        
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
    
    result = []
    for feature in features:
        file = db.query(ParsedFile).filter(ParsedFile.id == feature.file_id).first()
        uploader = db.query(User).filter(User.id == feature.user_id).first()
        assignee = db.query(User).filter(User.id == feature.assigned_to_user_id).first() if getattr(feature, "assigned_to_user_id", None) else None
        result.append({
            "id": feature.id,
            "category": feature.category,
            "description": feature.description,
            "status": feature.status,
            "quality_score": feature.quality_score,
            "file_id": feature.file_id,
            "filename": file.filename if file else "Unknown",
            "feedback": feature.feedback or "",
            "created_at": feature.created_at.isoformat() if feature.created_at else None,
            "user_id": feature.user_id,
            "username": uploader.username if uploader else None,
            "assigned_to_user_id": getattr(feature, "assigned_to_user_id", None),
            "assigned_to_username": assignee.username if assignee else None,
        })
    
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"features": result, "total": len(result)},
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )

@router.get("/api/features/stats")
async def get_feature_stats(
    file_id: Optional[int] = None,
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get feature statistics for users the current user can see."""
    from fastapi.responses import JSONResponse
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        return JSONResponse(content={"total": 0, "approved": 0, "denied": 0, "pending": 0}, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed for this project")

    query = db.query(Feature).filter(Feature.user_id.in_(visible_ids))
    if project_id is not None:
        query = query.filter(Feature.project_id == project_id)
    if file_id:
        query = query.filter(Feature.file_id == file_id)
    else:
        parsed_query = db.query(
            ParsedFile.filename,
            ParsedFile.user_id,
            func.max(ParsedFile.id).label('latest_file_id')
        ).filter(
            ParsedFile.user_id.in_(visible_ids)
        )
        if project_id is not None:
            parsed_query = parsed_query.filter(ParsedFile.project_id == project_id)

        subquery = parsed_query.group_by(ParsedFile.filename, ParsedFile.user_id).subquery()
        
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
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all documents for the current visible users that have features.
    Only returns the most recent run of each unique filename."""
    from fastapi.responses import JSONResponse
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        return JSONResponse(
            content={"documents": []},
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        )

    if project_id is not None and not can_user_access_project(current_user, project_id, db):
        raise HTTPException(status_code=403, detail="Not allowed for this project")
    
    # Get the most recent ParsedFile.id for each unique filename that has features
    parsed_query = db.query(
        ParsedFile.filename,
        ParsedFile.user_id,
        func.max(ParsedFile.id).label('latest_file_id')
    ).join(Feature).filter(
        ParsedFile.user_id.in_(visible_ids),
        Feature.user_id.in_(visible_ids)
    )
    if project_id is not None:
        parsed_query = parsed_query.filter(Feature.project_id == project_id)

    subquery = parsed_query.group_by(ParsedFile.filename, ParsedFile.user_id).subquery()
    
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
            Feature.user_id.in_(visible_ids)
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
            "run_label": run_label,
            "project_id": getattr(doc, "project_id", None),
            "user_id": doc.user_id,
        })
    
    return JSONResponse(
        content={"documents": result},
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )


@router.get("/api/files/{file_id}/visual-analysis")
async def get_file_visual_analysis(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return image/pattern insights for a specific uploaded file."""
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        raise HTTPException(status_code=403, detail="Not allowed")

    parsed_file = db.query(ParsedFile).filter(
        ParsedFile.id == file_id,
        ParsedFile.user_id.in_(visible_ids)
    ).first()
    if not parsed_file:
        raise HTTPException(status_code=404, detail="File not found")

    image_rows = db.query(ImageMeta).filter(ImageMeta.file_id == file_id).order_by(ImageMeta.page_number.asc(), ImageMeta.id.asc()).all()

    def _fallback_upload_images(filename: Optional[str]) -> List[dict]:
        name = (filename or "").strip()
        if not name:
            return []

        uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
        if not uploads_dir.exists():
            return []

        pattern = name + "_IMG-*.png"
        matches = sorted(uploads_dir.glob(pattern))
        out = []
        for idx, path in enumerate(matches, start=1):
            page_match = re.search(r"_IMG-[^-]+-(\d+)-\d+$", path.stem)
            page_number = int(page_match.group(1)) if page_match else None
            out.append({
                "id": f"fallback-{idx}",
                "page_number": page_number,
                "image_url": f"/uploads/{path.name}",
                "ocr_text": "",
                "agent_note": "Visual detected from uploaded document (OCR summary unavailable for this image).",
            })
        return out

    def _pdf_page_previews(filename: Optional[str], max_pages: int = 50) -> List[dict]:
        if fitz is None:
            return []

        name = (filename or "").strip()
        if not name:
            return []

        uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
        pdf_path = uploads_dir / name
        if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
            return []

        previews = []
        doc = None
        try:
            doc = fitz.open(str(pdf_path))
            total = min(len(doc), max_pages)
            for i in range(total):
                page_no = i + 1
                # Use versioned preview names to refresh older cached black previews.
                out_name = f"{name}_VIS2-{page_no}.png"
                out_path = uploads_dir / out_name

                # Generate once, then reuse cached preview file.
                if not out_path.exists():
                    page = doc[i]
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2.0, 2.0),
                        colorspace=fitz.csRGB,
                        alpha=False,
                        annots=False,
                    )
                    pix.save(str(out_path))

                ocr_text = ""
                if pytesseract is not None and Image is not None:
                    try:
                        with Image.open(out_path) as im:
                            ocr_text = (pytesseract.image_to_string(im) or "").strip()
                    except Exception:
                        ocr_text = ""

                if ocr_text:
                    agent_note = _agent_note(ocr_text)
                else:
                    agent_note = "Page visual preview generated. OCR text was not confidently readable on this page."

                previews.append({
                    "id": f"page-preview-{page_no}",
                    "page_number": page_no,
                    "image_url": f"/uploads/{out_name}",
                    "ocr_text": ocr_text,
                    "agent_note": agent_note,
                })
        except Exception:
            return []
        finally:
            if doc is not None:
                doc.close()

        return previews

    def _to_upload_url(image_path: Optional[str]) -> Optional[str]:
        if not image_path:
            return None
        name = Path(str(image_path)).name
        return f"/uploads/{name}" if name else None

    def _agent_note(ocr_text: Optional[str]) -> str:
        text = (ocr_text or "").strip()
        if not text:
            return "No OCR text extracted from this image."
        first_line = text.splitlines()[0].strip()
        if len(first_line) > 220:
            return first_line[:217] + "..."
        return first_line

    images = []
    for row in image_rows:
        images.append({
            "id": row.id,
            "page_number": row.page_number,
            "image_url": _to_upload_url(row.image_path),
            "ocr_text": row.ocr_text or "",
            "agent_note": _agent_note(row.ocr_text),
        })

    if not images:
        images = _fallback_upload_images(parsed_file.filename)
    if not images:
        images = _pdf_page_previews(parsed_file.filename)

    detected_patterns = int(parsed_file.detected_shapes or 0)
    if not detected_patterns and images:
        detected_patterns = len(images)

    return {
        "file_id": parsed_file.id,
        "filename": parsed_file.filename,
        "detected_patterns": detected_patterns,
        "images_detected": len(images),
        "images": images,
    }


@router.post("/api/files/{file_id}/visual-analysis/explain")
async def explain_file_visual_item(
    file_id: int,
    payload: VisualExplainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate richer AI explanation for one image/pattern item on demand."""
    visible_ids = get_visible_user_ids(current_user, db)
    if not visible_ids:
        raise HTTPException(status_code=403, detail="Not allowed")

    parsed_file = db.query(ParsedFile).filter(
        ParsedFile.id == file_id,
        ParsedFile.user_id.in_(visible_ids)
    ).first()
    if not parsed_file:
        raise HTTPException(status_code=404, detail="File not found")

    uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
    image_path: Optional[Path] = None
    fallback_ocr = (payload.ocr_text or "").strip()

    # Primary resolution path: DB image id linked to this file.
    if payload.image_id:
        try:
            image_id_int = int(str(payload.image_id))
            row = db.query(ImageMeta).filter(
                ImageMeta.id == image_id_int,
                ImageMeta.file_id == file_id
            ).first()
            if row and row.image_path:
                candidate = Path(row.image_path)
                if candidate.exists():
                    image_path = candidate
                if not fallback_ocr:
                    fallback_ocr = (row.ocr_text or "").strip()
        except (TypeError, ValueError):
            pass

    # Secondary resolution path: image URL from /uploads.
    if image_path is None and payload.image_url:
        image_name = Path(str(payload.image_url)).name
        if image_name:
            candidate = uploads_dir / image_name
            if candidate.exists():
                image_path = candidate

    if image_path is None:
        raise HTTPException(status_code=404, detail="Image not found for explanation")

    cache_key = f"{file_id}:{image_path.name}"
    if cache_key in VISUAL_EXPLANATION_CACHE:
        return VISUAL_EXPLANATION_CACHE[cache_key]

    explanation_text = ""
    extracted_requirements: List[str] = []
    components: List[str] = []
    relationships: List[str] = []
    process_steps: List[str] = []

    try:
        from services.image_service import comprehensive_image_interpretation

        context = (
            f"Document: {parsed_file.filename}. Explain what this visual means in terms of system behavior, "
            f"workflow, actors, inputs/outputs, and requirement implications."
        )
        result = comprehensive_image_interpretation(str(image_path), context)

        explanation_text = str(result.get("full_interpretation") or "").strip()
        extracted_requirements = [str(x).strip() for x in (result.get("requirements") or []) if str(x).strip()]
        components = [str(x).strip() for x in (result.get("components") or []) if str(x).strip()]
        relationships = [str(x).strip() for x in (result.get("relationships") or []) if str(x).strip()]
        process_steps = [str(x).strip() for x in (result.get("process_steps") or []) if str(x).strip()]
    except Exception:
        explanation_text = ""

    if not explanation_text:
        if fallback_ocr:
            short_ocr = re.sub(r'\s+', ' ', fallback_ocr).strip()
            if len(short_ocr) > 420:
                short_ocr = short_ocr[:417] + "..."
            explanation_text = (
                "AI interpretation is limited for this visual, so this is OCR-based context. "
                "It likely represents structural elements, labels, or process hints.\n\n"
                f"OCR summary: {short_ocr}"
            )
        else:
            explanation_text = (
                "AI could not confidently interpret this image. Try a clearer/high-resolution diagram "
                "or enable VLM (FLOWMIND_USE_VLM=true) for stronger visual semantics."
            )

    response = {
        "status": "success",
        "file_id": file_id,
        "image_name": image_path.name,
        "explanation": explanation_text,
        "extracted_requirements": extracted_requirements[:8],
        "components": components[:10],
        "relationships": relationships[:8],
        "process_steps": process_steps[:10],
        "learning_hint": "Approve/reject a few extracted requirements from this document to improve future ranking and filtering.",
    }
    VISUAL_EXPLANATION_CACHE[cache_key] = response
    return response

@router.put("/api/features/{feature_id}")
async def update_feature_status(
    feature_id: int,
    update: FeatureUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update feature approval status and/or feedback. Allowed for owner or visible users (team head/manager)."""
    visible_ids = get_visible_user_ids(current_user, db)
    feature = db.query(Feature).filter(
        Feature.id == feature_id,
        Feature.user_id.in_(visible_ids)
    ).first()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    if update.status and update.status not in ["approved", "denied", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    if update.status:
        feature.status = update.status
    if update.feedback is not None:
        feature.feedback = update.feedback
    # Team head / manager can assign feature to a team member (must be in visible users)
    if update.assigned_to_user_id is not None:
        if getattr(current_user, "role", None) not in ("manager", "team_head"):
            raise HTTPException(status_code=403, detail="Only manager or team head can assign features")
        if update.assigned_to_user_id == 0:
            feature.assigned_to_user_id = None
        else:
            target_user = db.query(User).filter(User.id == update.assigned_to_user_id, User.is_active == 1).first()
            if not target_user or target_user.id not in visible_ids:
                raise HTTPException(status_code=400, detail="Invalid assignee or not in your team")
            feature.assigned_to_user_id = target_user.id
    db.commit()
    
    return {"success": True, "feature_id": feature_id, "status": feature.status, "feedback": feature.feedback or "", "assigned_to_user_id": getattr(feature, "assigned_to_user_id", None)}

class FeedbackUpdate(BaseModel):
    feedback: str

@router.put("/api/features/{feature_id}/feedback")
async def update_feature_feedback(
    feature_id: int,
    update: FeedbackUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update feedback for a specific feature. Allowed for owner or visible users."""
    visible_ids = get_visible_user_ids(current_user, db)
    feature = db.query(Feature).filter(
        Feature.id == feature_id,
        Feature.user_id.in_(visible_ids)
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
    """Bulk update feature statuses. Allowed for visible users' features."""
    if update.status not in ["approved", "denied", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    visible_ids = get_visible_user_ids(current_user, db)
    updated = db.query(Feature).filter(
        Feature.id.in_(update.feature_ids),
        Feature.user_id.in_(visible_ids)
    ).update({"status": update.status}, synchronize_session=False)
    
    db.commit()
    
    return {"success": True, "updated": updated, "status": update.status}

@router.delete("/api/features/{feature_id}")
async def delete_feature(
    feature_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a feature. Allowed for owner or visible users."""
    visible_ids = get_visible_user_ids(current_user, db)
    feature = db.query(Feature).filter(
        Feature.id == feature_id,
        Feature.user_id.in_(visible_ids)
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

def parse_and_save_features(
    extracted_text: str,
    user_id: int,
    file_id: int,
    db: Session,
    image_summaries: list = None,
    structured_requirements: Optional[List[Dict[str, Any]]] = None,
    project_id: Optional[int] = None,
):
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
        def clean_description(text: str) -> str:
            s = str(text or "").strip()
            if not s:
                return ""
            s = re.sub(r'^[✅⚠️❌]\s*', '', s)
            s = re.sub(r'^REQ-\d+\s*[·:-]?\s*', '', s, flags=re.IGNORECASE)
            s = re.sub(r'\+\w+\([^)]*\)', ' ', s)
            s = re.sub(r'\s+', ' ', s).strip(' -:;,.')
            return s

        def looks_like_requirement(text: str) -> bool:
            s = clean_description(text)
            if not s:
                return False
            lower = s.lower()

            if len(s) < 20 or len(s) > 260:
                return False

            symbol_count = len(re.findall(r'[+\\|><{}\[\]_=]', s))
            if symbol_count > max(6, int(len(s) * 0.08)):
                return False

            blacklist = [
                'post /upload_agent_doc', 'frontend (ui)', 'dashboard view', 'test objective',
                'pass/fail', 'actual result', 'vector store', 'metrics updated'
            ]
            if any(b in lower for b in blacklist):
                return False

            has_modal = bool(re.search(r'\b(shall|must|should|will|needs to|is required to|has to)\b', lower))
            has_action = bool(re.search(r'\b(provide|support|allow|enable|store|process|extract|classify|display|integrate|validate|secure)\b', lower))
            has_subject = bool(re.search(r'\b(system|application|platform|user|client|dashboard|api|module)\b', lower))
            return (has_modal and (has_action or has_subject)) or (has_action and has_subject)

        # JSON-first path: save strict structured requirements when available.
        if structured_requirements and isinstance(structured_requirements, list):
            features_saved = 0
            seen_descriptions = set()

            for req in structured_requirements:
                if not isinstance(req, dict):
                    continue

                description = clean_description(req.get("statement") or "")
                if not description or description.lower() in ["(none)", "none"]:
                    continue

                if not looks_like_requirement(description):
                    continue

                normalized_desc = re.sub(r'\s+', ' ', description.lower())
                if normalized_desc in seen_descriptions:
                    continue
                seen_descriptions.add(normalized_desc)

                raw_category = str(req.get("category") or "other").strip().lower()
                if raw_category in ["functional", "non_functional", "user", "business", "system", "features", "other"]:
                    category = raw_category
                else:
                    if "non" in raw_category and "functional" in raw_category:
                        category = "non_functional"
                    elif "functional" in raw_category:
                        category = "functional"
                    elif "user" in raw_category or "story" in raw_category:
                        category = "user"
                    elif "business" in raw_category:
                        category = "business"
                    elif "system" in raw_category:
                        category = "system"
                    elif "feature" in raw_category:
                        category = "features"
                    else:
                        category = "other"

                confidence = req.get("confidence")
                quality_score = 0
                try:
                    if confidence is not None:
                        quality_score = max(0, min(100, int(float(confidence) * 100)))
                except (TypeError, ValueError):
                    quality_score = 0

                feature = Feature(
                    user_id=user_id,
                    project_id=project_id,
                    file_id=file_id,
                    category=category,
                    description=description,
                    status='pending',
                    quality_score=quality_score,
                )
                db.add(feature)
                features_saved += 1

            db.commit()
            print(f"✅ Saved {features_saved} features from structured requirements JSON")
            return features_saved

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
                        project_id=project_id,
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

