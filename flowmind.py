from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import pytesseract
from database import SessionLocal, ParsedFile, ImageMeta, User, init_db
from rag_agent import get_agent
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, get_db, get_current_user_optional
)

from PIL import Image
from pypdf import PdfReader
import docx
import pptx
import os
import uuid
import html
import hashlib
import cv2
import json
import subprocess
import shutil
import base64
import requests
import asyncio
import warnings
import logging
from dotenv import load_dotenv

# Suppress harmless warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pypdf")
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
warnings.filterwarnings("ignore", message=".*ARC4.*")
warnings.filterwarnings("ignore", message=".*_register_pytree_node.*")
warnings.filterwarnings("ignore", message=".*CoreMLExecutionProvider.*")
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

# Suppress ChromaDB telemetry errors
logging.getLogger("chromadb").setLevel(logging.ERROR)
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

# -------------------- OCR Summary Helpers --------------------
def _summarize_image_ocr(ocr_text: str, context: str = "") -> str:
    """Legacy function - now uses enhanced service."""
    from services.image_service import enhanced_ocr_summarize
    return enhanced_ocr_summarize(ocr_text, context)

# -------------------- SETUP --------------------
# Tesseract path - platform-aware configuration
import platform
tesseract_path = os.getenv("TESSERACT_CMD")
if not tesseract_path:
    if platform.system() == "Darwin":  # macOS
        tesseract_path = "/opt/homebrew/bin/tesseract"
    elif platform.system() == "Windows":
        tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    # Linux usually has it in PATH, so leave as None

if tesseract_path and os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
elif not tesseract_path:
    # Try to find tesseract in PATH
    tesseract_cmd = shutil.which("tesseract")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

load_dotenv()  # load env from .env so reload keeps VLM settings

# CORS configuration
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FlowMind")
init_db()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from routes import auth_routes, upload_routes, dashboard_routes, training_routes, approval_routes
from routes.approval_routes import parse_and_save_features

app.include_router(auth_routes.router)
app.include_router(upload_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(training_routes.router)
app.include_router(approval_routes.router)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Favicon endpoint
@app.get("/favicon.ico")
async def favicon():
    """Return empty favicon to prevent 404 errors."""
    from fastapi.responses import Response
    return Response(content="", media_type="image/x-icon")

# Serve static uploaded files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

REQUIREMENTS_VIEWS = {}

# Load persistent views from file
VIEWS_FILE = "requirements_views.json"

def load_views():
    """Load views from persistent storage."""
    global REQUIREMENTS_VIEWS
    try:
        if os.path.exists(VIEWS_FILE):
            with open(VIEWS_FILE, "r", encoding="utf-8") as f:
                REQUIREMENTS_VIEWS = json.load(f)
                print(f"📚 Loaded {len(REQUIREMENTS_VIEWS)} persisted views")
    except Exception as e:
        print(f"⚠️ Failed to load views: {str(e)}")
        REQUIREMENTS_VIEWS = {}

def save_views():
    """Save views to persistent storage."""
    try:
        with open(VIEWS_FILE, "w", encoding="utf-8") as f:
            json.dump(REQUIREMENTS_VIEWS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save views: {str(e)}")

# Load views on startup
load_views()

# -------------------- AUTHENTICATION ENDPOINTS --------------------
class SignupRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/signup")
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Simple user registration - no verification required."""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.email == request.email) | (User.username == request.username)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or username already registered"
            )
        
        # Validate password length
        if len(request.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long"
            )
        
        # No maximum length limit - using pbkdf2_sha256 which has no 72-byte restriction
        
        # Create new user immediately
        hashed_password = get_password_hash(request.password)
        new_user = User(
            email=request.email,
            username=request.username,
            hashed_password=hashed_password
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Create access token
        access_token = create_access_token(data={"sub": new_user.id})
        
        return {
            "status": "success",
            "message": "Account created successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        error_trace = traceback.format_exc()
        print(f"Signup error: {error_trace}")  # Debug logging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating account: {str(e)}"
        )

@app.post("/api/login")
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
        
        # Create access token
        access_token = create_access_token(data={"sub": user.id})
        
        return {
            "status": "success",
            "message": "Login successful",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during login: {str(e)}"
        )

# /api/me endpoint is now in routes/auth_routes.py

@app.post("/api/logout")
async def logout():
    """Logout endpoint (client-side token removal)."""
    return {"status": "success", "message": "Logged out successfully"}

# -------------------- VLM (Vision-Language Model) Helpers --------------------
def _get_env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}

def _vlm_summarize(image_path: str, context: str) -> str:
    """Enhanced function - uses comprehensive image interpretation."""
    from services.image_service import comprehensive_image_interpretation
    
    try:
        # Use comprehensive interpretation for much better results
        result = comprehensive_image_interpretation(image_path, context)
        return result['full_interpretation']
    except Exception as e:
        print(f"⚠️  Comprehensive interpretation failed, falling back: {e}")
        # Fallback to basic
        from services.image_service import enhanced_vlm_summarize
        image_type = "unknown"
        context_lower = context.lower() if context else ""
        if any(word in context_lower for word in ["diagram", "architecture", "component"]):
            image_type = "diagram"
        elif any(word in context_lower for word in ["chart", "graph", "plot", "data"]):
            image_type = "chart"
        elif any(word in context_lower for word in ["workflow", "process", "state", "transition"]):
            image_type = "workflow"
        return enhanced_vlm_summarize(image_path, context, image_type)

# ==============================================================
# MAIN ANALYZE FUNCTION
# ==============================================================

async def _analyze_document_internal(file: UploadFile, user_id: int = None, db_session = None, progress_tracker_id: str = None):
    """Internal function: Extracts text, images, and OCR from any uploaded document."""
    from services.progress_service import ProcessingStage
    from services.progress_storage import get_progress_tracker
    
    print(f"📄 Starting document analysis: {file.filename}")
    print(f"👤 User ID: {user_id}")
    
    tracker = None
    if progress_tracker_id:
        tracker = get_progress_tracker(progress_tracker_id)
        if tracker:
            tracker.set_stage(ProcessingStage.UPLOADING)
            progress = tracker.get_progress()
            print(f"📊 [{progress['progress']}%] {progress['message']}")
    
    print(f"⬆️ Uploading file: {file.filename}")
    filepath = os.path.join(UPLOAD_DIR, file.filename)
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
        file_size = len(content)
        print(f"✅ File uploaded successfully ({file_size:,} bytes)")
    
    if tracker:
        tracker.set_stage(ProcessingStage.PARSING)
        progress = tracker.get_progress()
        print(f"📊 [{progress['progress']}%] {progress['message']}")

    text_output = ""
    image_count = 0
    image_metadata = []  # (image_id, image_path, page_number, ocr_text)
    image_positions = []  # list of dicts: {image_id, page, char_offset, context_before}

    def gen_image_id(fname: str, page_num: int, idx: int) -> str:
        base = f"{fname}|{page_num}|{idx}"
        h = hashlib.md5(base.encode()).hexdigest()[:10]
        return f"IMG-{h}-{page_num}-{idx}"

    # ----------- PDF PARSING (Chunked) -----------
    if file.filename.endswith(".pdf"):
        print(f"📄 Detected PDF file, initializing PDF reader...")
        reader = PdfReader(filepath)
        total_pages = len(reader.pages)
        chunk_size = 10

        print(f"📘 Document has {total_pages} pages. Starting text extraction...")
        
        if tracker:
            tracker.set_stage(ProcessingStage.PARSING, total_pages=total_pages, current_page=0)
            progress = tracker.get_progress()
            print(f"📊 [{progress['progress']}%] {progress['message']}")

        page_end_offsets = {}
        for start in range(0, total_pages, chunk_size):
            end = min(start + chunk_size, total_pages)
            print(f"🔹 Processing pages {start + 1}–{end} of {total_pages}...")

            for page_index in range(start, end):
                page = reader.pages[page_index]
                page_text = page.extract_text() or ""
                text_output += page_text + "\n"
                page_end_offsets[page_index + 1] = len(text_output)

                if tracker:
                    tracker.set_stage(ProcessingStage.PARSING, total_pages=total_pages, current_page=page_index + 1)
                    if (page_index + 1) % 5 == 0 or page_index + 1 == total_pages:  # Log every 5 pages
                        progress = tracker.get_progress()
                        print(f"📊 [{progress['progress']}%] Currently working on page {page_index + 1}/{total_pages}")

            print(f"✅ Finished pages {start + 1}–{end} of {total_pages}.")
        print(f"✅ Completed all {total_pages} pages. Extracted {len(text_output):,} characters.")
        
        if tracker:
            tracker.set_stage(ProcessingStage.TEXT_EXTRACTION)

        # Extract images using pypdf Page.images if available
        print(f"🖼️ Starting image detection and extraction...")
        if tracker:
            tracker.set_stage(ProcessingStage.IMAGE_DETECTION)
            progress = tracker.get_progress()
            print(f"📊 [{progress['progress']}%] {progress['message']}")
        
        try:
            from io import BytesIO
            detected_images = 0
            for page_num, page in enumerate(reader.pages, start=1):
                try:
                    imgs = getattr(page, "images", []) or []
                except Exception:
                    imgs = []
                for img_idx, img in enumerate(imgs, start=1):
                    try:
                        data = getattr(img, "data", None)
                        if not data:
                            continue
                        image_count += 1
                        image_id = gen_image_id(file.filename, page_num, img_idx)
                        out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}.png")
                        try:
                            im = Image.open(BytesIO(data))
                            im.save(out_path, format="PNG")
                            ocr_text = pytesseract.image_to_string(im)
                        except Exception:
                            # If PIL cannot decode, just dump bytes and skip OCR
                            with open(out_path, "wb") as fimg:
                                fimg.write(data)
                            ocr_text = ""
                        image_metadata.append((image_id, out_path, page_num, ocr_text))
                        detected_images += 1
                        # Compute a simple position for context: end of that page's text
                        pos = page_end_offsets.get(page_num, len(text_output))
                        context_before = text_output[max(0, pos - 300):pos]
                        image_positions.append({
                            "image_id": image_id,
                            "page": page_num,
                            "char_offset": pos,
                            "context_before": context_before
                        })
                        
                        # Update progress for OCR
                        if tracker:
                            tracker.set_stage(ProcessingStage.OCR_PROCESSING, total_images=detected_images, current_image=detected_images)
                            progress = tracker.get_progress()
                            print(f"📊 [{progress['progress']}%] Processing OCR for image {detected_images} (page {page_num})")
                        
                        # Try VLM summary
                        if tracker:
                            tracker.set_stage(ProcessingStage.IMAGE_SUMMARIZATION, total_images=detected_images, current_image=detected_images)
                        vlm_sum = _vlm_summarize(out_path, context_before)
                        if vlm_sum:
                            print(f"✅ Generated summary for image {detected_images} on page {page_num}")
                        if vlm_sum:
                            text_output += f"\n[IMAGE_SUMMARY {image_id}]\n{vlm_sum}\n"
                        if (ocr_text or "").strip():
                            text_output += f"\n[IMAGE {image_id}]\nOCR: {(ocr_text or '').strip()}\n"
                    except Exception:
                        continue
        except Exception:
            pass

    # ----------- DOC (legacy) PARSING via LibreOffice conversion -----------
    elif file.filename.endswith(".doc"):
        # Convert .doc to .docx using LibreOffice if available
        soffice_path_candidates = [
            shutil.which("soffice"),
            "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        ]
        soffice = next((p for p in soffice_path_candidates if p and os.path.exists(p)), None)
        if not soffice:
            text_output = "Unsupported file format (.doc) and LibreOffice not found for conversion."
        else:
            try:
                subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", UPLOAD_DIR, filepath], check=True)
                converted = os.path.join(UPLOAD_DIR, os.path.splitext(file.filename)[0] + ".docx")
                d = docx.Document(converted)
                for para in d.paragraphs:
                    text_output += para.text + "\n"
                # Extract images from converted DOCX
                img_idx = 0
                for rel in d.part.rels.values():
                    if "image" in rel.reltype and getattr(rel, "target_part", None):
                        try:
                            img_idx += 1
                            image_count += 1
                            blob = rel.target_part.blob
                            page_num = 1
                            image_id = gen_image_id(file.filename, page_num, img_idx)
                            ext = ".png"
                            out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}{ext}")
                            with open(out_path, "wb") as imf:
                                imf.write(blob)
                            try:
                                img = Image.open(out_path)
                                ocr_text = pytesseract.image_to_string(img)
                            except Exception:
                                ocr_text = ""
                            image_metadata.append((image_id, out_path, page_num, ocr_text))
                            pos = len(text_output)
                            context_before = text_output[max(0, pos - 300):pos]
                            image_positions.append({
                                "image_id": image_id,
                                "page": page_num,
                                "char_offset": pos,
                                "context_before": context_before
                            })
                            vlm_sum = _vlm_summarize(out_path, context_before)
                            if vlm_sum:
                                text_output += f"\n[IMAGE_SUMMARY {image_id}]\n{vlm_sum}\n"
                            if ocr_text.strip():
                                text_output += f"\n[IMAGE {image_id}]\nOCR: {ocr_text.strip()}\n"
                        except Exception:
                            pass
            except Exception as e:
                text_output = f"Conversion error for .doc: {e}"

    # ----------- DOCX PARSING -----------
    elif file.filename.endswith(".docx"):
        d = docx.Document(filepath)
        for para in d.paragraphs:
            text_output += para.text + "\n"
        # Extract images from DOCX
        img_idx = 0
        for rel in d.part.rels.values():
            if "image" in rel.reltype and getattr(rel, "target_part", None):
                try:
                    img_idx += 1
                    image_count += 1
                    blob = rel.target_part.blob
                    page_num = 1
                    image_id = gen_image_id(file.filename, page_num, img_idx)
                    ext = ".png"
                    out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}{ext}")
                    with open(out_path, "wb") as imf:
                        imf.write(blob)
                    # OCR
                    try:
                        img = Image.open(out_path)
                        ocr_text = pytesseract.image_to_string(img)
                    except Exception:
                        ocr_text = ""
                    image_metadata.append((image_id, out_path, page_num, ocr_text))
                    # Inject lightweight context for agent
                    if ocr_text.strip():
                        text_output += f"\n[IMAGE {image_id}]\nOCR: {ocr_text.strip()}\n"
                except Exception:
                    pass

    # ----------- PPT (legacy) PARSING via LibreOffice conversion -----------
    elif file.filename.endswith(".ppt"):
        soffice_path_candidates = [
            shutil.which("soffice"),
            "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        ]
        soffice = next((p for p in soffice_path_candidates if p and os.path.exists(p)), None)
        if not soffice:
            text_output = "Unsupported file format (.ppt) and LibreOffice not found for conversion."
        else:
            try:
                subprocess.run([soffice, "--headless", "--convert-to", "pptx", "--outdir", UPLOAD_DIR, filepath], check=True)
                converted = os.path.join(UPLOAD_DIR, os.path.splitext(file.filename)[0] + ".pptx")
                prs = pptx.Presentation(converted)
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            text_output += shape.text + "\n"
                        if getattr(shape, "shape_type", None) == 13 and hasattr(shape, "image"):
                            try:
                                image_count += 1
                                image_id = gen_image_id(file.filename, 1, image_count)
                                ext = ".png"
                                out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}{ext}")
                                with open(out_path, "wb") as imf:
                                    imf.write(shape.image.blob)
                                try:
                                    img = Image.open(out_path)
                                    ocr_text = pytesseract.image_to_string(img)
                                except Exception:
                                    ocr_text = ""
                                image_metadata.append((image_id, out_path, 1, ocr_text))
                                pos = len(text_output)
                                context_before = text_output[max(0, pos - 300):pos]
                                image_positions.append({
                                    "image_id": image_id,
                                    "page": 1,
                                    "char_offset": pos,
                                    "context_before": context_before
                                })
                                vlm_sum = _vlm_summarize(out_path, context_before)
                                if vlm_sum:
                                    text_output += f"\n[IMAGE_SUMMARY {image_id}]\n{vlm_sum}\n"
                                if ocr_text.strip():
                                    text_output += f"\n[IMAGE {image_id}]\nOCR: {ocr_text.strip()}\n"
                            except Exception:
                                pass
            except Exception as e:
                text_output = f"Conversion error for .ppt: {e}"

    # ----------- PPTX PARSING -----------
    elif file.filename.endswith(".pptx"):
        prs = pptx.Presentation(filepath)
        # Extract text and images from PPTX
        for slide_idx, slide in enumerate(prs.slides, start=1):
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text_output += shape.text + "\n"
                # 13 == MSO_SHAPE_TYPE.PICTURE
                if getattr(shape, "shape_type", None) == 13 and hasattr(shape, "image"):
                    try:
                        image_count += 1
                        image_id = gen_image_id(file.filename, slide_idx, image_count)
                        ext = ".png"
                        out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}{ext}")
                        with open(out_path, "wb") as imf:
                            imf.write(shape.image.blob)
                        try:
                            img = Image.open(out_path)
                            ocr_text = pytesseract.image_to_string(img)
                        except Exception:
                            ocr_text = ""
                        image_metadata.append((image_id, out_path, slide_idx, ocr_text))
                        pos = len(text_output)
                        context_before = text_output[max(0, pos - 300):pos]
                        image_positions.append({
                            "image_id": image_id,
                            "page": slide_idx,
                            "char_offset": pos,
                            "context_before": context_before
                        })
                        vlm_sum = _vlm_summarize(out_path, context_before)
                        if vlm_sum:
                            text_output += f"\n[IMAGE_SUMMARY {image_id}]\n{vlm_sum}\n"
                        if ocr_text.strip():
                            text_output += f"\n[IMAGE {image_id}]\nOCR: {ocr_text.strip()}\n"
                    except Exception:
                        pass

    # ----------- IMAGE PARSING -----------
    elif file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        if tracker:
            tracker.set_stage(ProcessingStage.IMAGE_DETECTION)
        image_count = 1
        img = Image.open(filepath)
        if tracker:
            tracker.set_stage(ProcessingStage.OCR_PROCESSING, total_images=1, current_image=1)
        text_output = pytesseract.image_to_string(img)
        image_id = gen_image_id(file.filename, 1, 1)
        image_metadata.append((image_id, filepath, 1, text_output))
        if text_output.strip():
            text_output += f"\n[IMAGE {image_id}]\nOCR: {text_output.strip()}\n"

    # ----------- TEXT FILE PARSING -----------
    elif file.filename.lower().endswith(".txt"):
        if tracker:
            tracker.set_stage(ProcessingStage.TEXT_EXTRACTION)
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text_output = f.read()

    else:
        text_output = "Unsupported file format."

    # ----------- SAVE FULL TEXT FILE -----------
    # Sanitize text before writing to avoid surrogate encoding issues
    sanitized_text = (text_output or "").encode("utf-8", "ignore").decode("utf-8", "ignore")
    text_file_path = os.path.join(UPLOAD_DIR, f"{file.filename}_full.txt")
    with open(text_file_path, "w", encoding="utf-8") as tf:
        tf.write(sanitized_text)

    if tracker:
        tracker.set_stage(ProcessingStage.FINALIZING)
        progress = tracker.get_progress()
        print(f"📊 [{progress['progress']}%] {progress['message']}")

    summary = f"Extracted {len(text_output.split())} words and {image_count} image(s)."
    print(f"✅ Document analysis complete: {summary}")
    
    if tracker:
        tracker.complete()
        final_progress = tracker.get_progress()
        print(f"📊 [{final_progress['progress']}%] {final_progress['message']}")

    # ----------- SAVE TO DATABASE -----------
    try:
        if db_session is None:
            db = SessionLocal()
            should_close = True
        else:
            db = db_session
            should_close = False
        
        record = ParsedFile(
            filename=file.filename,
            extracted_text=sanitized_text[:400],
            detected_shapes=image_count,
            summary=summary,
            full_text_path=text_file_path,
            user_id=user_id  # Link to user
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # Save image metadata
        for image_id, image_path, page_num, ocr_text in image_metadata:
            img_meta = ImageMeta(
                file_id=record.id,
                image_path=image_path,
                page_number=page_num,
                ocr_text=ocr_text
            )
            db.add(img_meta)

        db.commit()
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        # Ensure session is always closed
        if should_close and db_session is None:
            try:
                db.close()
            except Exception:
                pass

    # Build quick lookup for contextual summaries
    ctx_by_id = {pos.get("image_id"): (pos.get("context_before") or "") for pos in image_positions}

    return {
        "filename": file.filename,
        "summary": summary,
        "full_text_file": text_file_path,
        "images_detected": image_count,
        "image_metadata_saved": len(image_metadata),
        "images": [
            {"image_id": iid, "path": path, "page": pg, "ocr": (ocr or "").strip(),
             "summary": (_vlm_summarize(path, ctx_by_id.get(iid, "")) or _summarize_image_ocr(ocr or "", context=ctx_by_id.get(iid, "")))}
            for (iid, path, pg, ocr) in image_metadata
        ],
        "image_positions": image_positions
    }


# -------------------- AUTHENTICATION PAGES --------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Clean login page with Bootstrap - NO VERIFICATION CODE."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - FlowMind</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .auth-card {
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            width: 100%;
            max-width: 450px;
            animation: slideUp 0.5s ease-out;
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .auth-header {
            text-align: center;
            margin-bottom: 2.5rem;
        }
        .auth-header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }
        .auth-header p {
            color: #64748b;
            font-size: 1rem;
        }
        .form-label {
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }
        .form-control {
            padding: 0.875rem 1rem;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        .form-control:focus {
            border-color: #2563eb;
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
        }
        .btn-primary {
            width: 100%;
            padding: 0.875rem;
            border-radius: 12px;
            font-weight: 600;
            font-size: 1rem;
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            border: none;
            transition: all 0.3s ease;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(37, 99, 235, 0.3);
        }
        .alert {
            border-radius: 12px;
            border: none;
            margin-bottom: 1.5rem;
        }
        .auth-footer {
            text-align: center;
            margin-top: 2rem;
            color: #64748b;
        }
        .auth-footer a {
            color: #2563eb;
            text-decoration: none;
            font-weight: 500;
        }
        .auth-footer a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="auth-card">
        <div class="auth-header">
            <h1><i class="fas fa-sign-in-alt text-primary"></i> Login</h1>
            <p>Welcome back to FlowMind</p>
        </div>
        
        <div id="alertContainer"></div>
        
        <form id="loginForm">
            <div class="mb-3">
                <label for="email" class="form-label">Email Address</label>
                <input type="email" class="form-control" id="email" name="email" required autocomplete="email" placeholder="Enter your email">
            </div>
            
            <div class="mb-4">
                <label for="password" class="form-label">Password</label>
                <input type="password" class="form-control" id="password" name="password" required autocomplete="current-password" placeholder="Enter your password">
            </div>
            
            <button type="submit" class="btn btn-primary" id="submitBtn">
                <i class="fas fa-sign-in-alt"></i> Login
            </button>
        </form>
        
        <div class="auth-footer">
            <p class="mb-2">Don't have an account? <a href="/signup">Sign up</a></p>
            <a href="/"><i class="fas fa-arrow-left"></i> Back to Home</a>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const form = document.getElementById('loginForm');
        const alertContainer = document.getElementById('alertContainer');
        const submitBtn = document.getElementById('submitBtn');
        
        function showAlert(message, type = 'danger') {
            alertContainer.innerHTML = `
                <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                    <i class="fas fa-${type === 'danger' ? 'exclamation-circle' : 'check-circle'}"></i> ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            alertContainer.innerHTML = '';
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Logging in...';
            
            const formData = {
                email: document.getElementById('email').value,
                password: document.getElementById('password').value
            };
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    localStorage.setItem('access_token', data.access_token);
                    localStorage.setItem('user', JSON.stringify(data.user));
                    showAlert('Login successful! Redirecting...', 'success');
                    setTimeout(() => window.location.href = '/extract', 1000);
                } else {
                    showAlert(data.detail || 'Login failed. Please try again.');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
                }
            } catch (error) {
                showAlert('Network error. Please check your connection and try again.');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
            }
        });
    </script>
</body>
</html>
    """

@app.get("/signup", response_class=HTMLResponse)
async def signup_page():
    """Clean signup page with Bootstrap - NO VERIFICATION CODE."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up - FlowMind</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .auth-card {
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            width: 100%;
            max-width: 450px;
            animation: slideUp 0.5s ease-out;
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .auth-header {
            text-align: center;
            margin-bottom: 2.5rem;
        }
        .auth-header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }
        .auth-header p {
            color: #64748b;
            font-size: 1rem;
        }
        .form-label {
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }
        .form-control {
            padding: 0.875rem 1rem;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        .form-control:focus {
            border-color: #2563eb;
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
        }
        .btn-primary {
            width: 100%;
            padding: 0.875rem;
            border-radius: 12px;
            font-weight: 600;
            font-size: 1rem;
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            border: none;
            transition: all 0.3s ease;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(37, 99, 235, 0.3);
        }
        .alert {
            border-radius: 12px;
            border: none;
            margin-bottom: 1.5rem;
        }
        .auth-footer {
            text-align: center;
            margin-top: 2rem;
            color: #64748b;
        }
        .auth-footer a {
            color: #2563eb;
            text-decoration: none;
            font-weight: 500;
        }
        .auth-footer a:hover {
            text-decoration: underline;
        }
        .password-hint {
            font-size: 0.875rem;
            color: #64748b;
            margin-top: 0.25rem;
        }
    </style>
</head>
<body>
    <div class="auth-card">
        <div class="auth-header">
            <h1><i class="fas fa-user-plus text-primary"></i> Sign Up</h1>
            <p>Create your FlowMind account</p>
        </div>
        
        <div id="alertContainer"></div>
        
        <form id="signupForm">
            <div class="mb-3">
                <label for="email" class="form-label">Email Address</label>
                <input type="email" class="form-control" id="email" name="email" required autocomplete="email" placeholder="Enter your email">
            </div>
            
            <div class="mb-3">
                <label for="username" class="form-label">Username</label>
                <input type="text" class="form-control" id="username" name="username" required autocomplete="username" placeholder="Choose a username">
            </div>
            
            <div class="mb-4">
                <label for="password" class="form-label">Password</label>
                <input type="password" class="form-control" id="password" name="password" required autocomplete="new-password" minlength="6" placeholder="Create a password">
                <div class="password-hint">Must be at least 6 characters long</div>
            </div>
            
            <button type="submit" class="btn btn-primary" id="submitBtn">
                <i class="fas fa-user-plus"></i> Create Account
            </button>
        </form>
        
        <div class="auth-footer">
            <p class="mb-2">Already have an account? <a href="/login">Login</a></p>
            <a href="/"><i class="fas fa-arrow-left"></i> Back to Home</a>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const form = document.getElementById('signupForm');
        const alertContainer = document.getElementById('alertContainer');
        const submitBtn = document.getElementById('submitBtn');
        
        function showAlert(message, type = 'danger') {
            alertContainer.innerHTML = `
                <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                    <i class="fas fa-${type === 'danger' ? 'exclamation-circle' : 'check-circle'}"></i> ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            alertContainer.innerHTML = '';
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating account...';
            
            const formData = {
                email: document.getElementById('email').value,
                username: document.getElementById('username').value,
                password: document.getElementById('password').value
            };
            
            try {
                const response = await fetch('/api/signup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    localStorage.setItem('access_token', data.access_token);
                    localStorage.setItem('user', JSON.stringify(data.user));
                    showAlert('Account created successfully! Redirecting...', 'success');
                    setTimeout(() => window.location.href = '/extract', 1000);
                } else {
                    showAlert(data.detail || 'Signup failed. Please try again.');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
                }
            } catch (error) {
                showAlert('Network error. Please check your connection and try again.');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
            }
        });
    </script>
</body>
</html>
    """

@app.get("/about", response_class=HTMLResponse)
async def about_page():
    """About Us page."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>About Us - FlowMind</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {
                --primary-color: #2563eb;
                --text-primary: #1e293b;
                --text-secondary: #64748b;
                --border: #e2e8f0;
                --radius: 12px;
            }
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 2rem;
            }
            .container {
                max-width: 900px;
                margin: 0 auto;
                background: white;
                border-radius: var(--radius);
                padding: 3rem;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            }
            .header {
                text-align: center;
                margin-bottom: 3rem;
            }
            .header h1 {
                font-size: 2.5rem;
                font-weight: 700;
                color: var(--text-primary);
                margin-bottom: 1rem;
            }
            .header p {
                color: var(--text-secondary);
                font-size: 1.1rem;
            }
            .content {
                line-height: 1.8;
                color: var(--text-primary);
            }
            .content h2 {
                font-size: 1.5rem;
                font-weight: 600;
                margin-top: 2rem;
                margin-bottom: 1rem;
                color: var(--primary-color);
            }
            .content p {
                margin-bottom: 1rem;
                color: var(--text-secondary);
            }
            .content ul {
                margin-left: 2rem;
                margin-bottom: 1rem;
                color: var(--text-secondary);
            }
            .content li {
                margin-bottom: 0.5rem;
            }
            .back-link {
                display: inline-block;
                margin-top: 2rem;
                color: var(--primary-color);
                text-decoration: none;
                font-weight: 500;
            }
            .back-link:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1><i class="fas fa-info-circle"></i> About FlowMind</h1>
                <p>Intelligent Document Analysis Platform</p>
            </div>
            <div class="content">
                <h2>What is FlowMind?</h2>
                <p>
                    FlowMind is an advanced document analysis platform that leverages artificial intelligence 
                    and machine learning to extract, analyze, and understand complex requirements from various 
                    document formats. Our platform helps organizations streamline their document processing 
                    workflows and gain valuable insights from their documents.
                </p>
                
                <h2>Key Features</h2>
                <ul>
                    <li><strong>Multi-Format Support:</strong> Process PDFs, Word documents, PowerPoint presentations, images, and text files</li>
                    <li><strong>Intelligent Extraction:</strong> Advanced OCR and text extraction capabilities</li>
                    <li><strong>Requirements Analysis:</strong> Automatically identify and extract requirements from documents</li>
                    <li><strong>RAG-Powered:</strong> Retrieval-Augmented Generation for accurate document understanding</li>
                    <li><strong>Visual Analysis:</strong> Extract and analyze images, diagrams, and visual elements</li>
                    <li><strong>Self-Learning System:</strong> Continuously improves extraction accuracy over time</li>
                </ul>
                
                <h2>Our Mission</h2>
                <p>
                    At FlowMind, we believe that document analysis should be intelligent, efficient, and accessible. 
                    Our mission is to empower organizations with cutting-edge AI technology that transforms how they 
                    process and understand their documents.
                </p>
                
                <h2>Technology Stack</h2>
                <p>
                    FlowMind is built using state-of-the-art technologies including FastAPI, LangChain, ChromaDB, 
                    and advanced machine learning models for natural language processing and computer vision.
                </p>
                
                <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> Back to Home</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMind – Intelligent Document Analysis</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {
                --primary-color: #2563eb;
                --primary-dark: #1d4ed8;
                --secondary-color: #64748b;
                --success-color: #10b981;
                --warning-color: #f59e0b;
                --error-color: #ef4444;
                --background: #f8fafc;
                --surface: #ffffff;
                --surface-elevated: #ffffff;
                --text-primary: #1e293b;
                --text-secondary: #64748b;
                --text-muted: #94a3b8;
                --border: #e2e8f0;
                --border-light: #f1f5f9;
                --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
                --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                --radius: 12px;
                --radius-sm: 8px;
                --radius-lg: 16px;
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: var(--text-primary);
                line-height: 1.6;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }

            .header {
                text-align: center;
                margin-bottom: 3rem;
                animation: fadeInDown 0.8s ease-out;
            }

            .header h1 {
                font-size: 3rem;
                font-weight: 700;
                color: white;
                margin-bottom: 0.5rem;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }

            .header p {
                font-size: 1.2rem;
                color: rgba(255, 255, 255, 0.9);
                font-weight: 300;
            }

            .main-content {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 2rem;
                margin-bottom: 2rem;
            }

            .card {
                background: var(--surface);
                border-radius: var(--radius-lg);
                padding: 2rem;
                box-shadow: var(--shadow-xl);
                border: 1px solid var(--border-light);
                transition: all 0.3s ease;
                animation: fadeInUp 0.8s ease-out;
            }

            .card:hover {
                transform: translateY(-4px);
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            }

            .card:nth-child(2) {
                animation-delay: 0.2s;
            }

            .card-header {
                display: flex;
                align-items: center;
                margin-bottom: 1.5rem;
            }

            .card-icon {
                width: 48px;
                height: 48px;
                border-radius: var(--radius);
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 1rem;
                font-size: 1.5rem;
                color: white;
            }

            .card-icon.basic {
                background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
            }

            .card-icon.agent {
                background: linear-gradient(135deg, var(--success-color), #059669);
            }

            .card-title {
                font-size: 1.5rem;
                font-weight: 600;
                color: var(--text-primary);
            }

            .card-subtitle {
                font-size: 0.9rem;
                color: var(--text-secondary);
                margin-top: 0.25rem;
            }

            .form-group {
                margin-bottom: 1.5rem;
            }

            .file-input-wrapper {
                position: relative;
                display: inline-block;
                width: 100%;
            }

            .file-input {
                position: absolute;
                opacity: 0;
                width: 100%;
                height: 100%;
                cursor: pointer;
            }

            .file-input-label {
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 1.5rem;
                border: 2px dashed var(--border);
                border-radius: var(--radius);
                background: var(--background);
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: 500;
                color: var(--text-secondary);
            }

            .file-input-label:hover {
                border-color: var(--primary-color);
                background: rgba(37, 99, 235, 0.05);
                color: var(--primary-color);
            }

            .file-input-label i {
                margin-right: 0.5rem;
                font-size: 1.2rem;
            }

            .btn {
                background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
                color: white;
                border: none;
                padding: 0.875rem 1.5rem;
                border-radius: var(--radius);
                font-weight: 500;
                font-size: 1rem;
                cursor: pointer;
                transition: all 0.3s ease;
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                box-shadow: var(--shadow);
            }

            .btn:hover {
                transform: translateY(-2px);
                box-shadow: var(--shadow-lg);
            }

            .btn:active {
                transform: translateY(0);
            }

            .btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }

            .progress-container {
                margin-top: 1rem;
                display: none;
            }

            .progress-bar {
                width: 100%;
                height: 8px;
                background: var(--border-light);
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 0.5rem;
            }

            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, var(--primary-color), var(--success-color));
                width: 0%;
                transition: width 0.3s ease;
                border-radius: 4px;
            }

            .progress-text {
                font-size: 0.875rem;
                color: var(--text-secondary);
                text-align: center;
            }

            .output-container {
                margin-top: 1.5rem;
                background: #0f172a;
                border-radius: var(--radius);
                padding: 1.5rem;
                color: #e2e8f0;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                font-size: 0.875rem;
                line-height: 1.5;
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid #1e293b;
            }

            .output-container::-webkit-scrollbar {
                width: 6px;
            }

            .output-container::-webkit-scrollbar-track {
                background: #1e293b;
                border-radius: 3px;
            }

            .output-container::-webkit-scrollbar-thumb {
                background: #475569;
                border-radius: 3px;
            }

            .output-container::-webkit-scrollbar-thumb:hover {
                background: #64748b;
            }

            .view-link {
                margin-top: 1rem;
                text-align: center;
            }

            .view-link a {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background: linear-gradient(135deg, var(--success-color), #059669);
                color: white;
                text-decoration: none;
                padding: 0.75rem 1.5rem;
                border-radius: var(--radius);
                font-weight: 500;
                transition: all 0.3s ease;
                box-shadow: var(--shadow);
            }

            .view-link a:hover {
                transform: translateY(-2px);
                box-shadow: var(--shadow-lg);
            }

            .navigation {
                background: var(--surface);
                border-radius: var(--radius-lg);
                padding: 1.5rem;
                box-shadow: var(--shadow-lg);
                animation: fadeInUp 0.8s ease-out 0.4s both;
            }

            .nav-links {
                display: flex;
                justify-content: center;
                gap: 2rem;
                flex-wrap: wrap;
            }

            .nav-link {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                color: var(--text-primary);
                text-decoration: none;
                font-weight: 500;
                padding: 0.75rem 1.5rem;
                border-radius: var(--radius);
                transition: all 0.3s ease;
                background: var(--background);
            }

            .nav-link:hover {
                background: var(--primary-color);
                color: white;
                transform: translateY(-2px);
                box-shadow: var(--shadow);
            }

            .nav-link i {
                font-size: 1.1rem;
            }

            .status-indicator {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem 1rem;
                border-radius: var(--radius-sm);
                font-size: 0.875rem;
                font-weight: 500;
                margin-left: 1rem;
            }

            .status-indicator.success {
                background: rgba(16, 185, 129, 0.1);
                color: var(--success-color);
            }

            .status-indicator.error {
                background: rgba(239, 68, 68, 0.1);
                color: var(--error-color);
            }

            .status-indicator.warning {
                background: rgba(245, 158, 11, 0.1);
                color: var(--warning-color);
            }

            @keyframes fadeInDown {
                from {
                    opacity: 0;
                    transform: translateY(-30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @keyframes pulse {
                0%, 100% {
                    opacity: 1;
                }
                50% {
                    opacity: 0.5;
                }
            }

            .loading {
                animation: pulse 1.5s ease-in-out infinite;
            }

            /* Learning Status Modal */
            .modal {
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                overflow: auto;
                background-color: rgba(0, 0, 0, 0.5);
                animation: fadeIn 0.3s;
            }

            .modal-content {
                background-color: var(--surface);
                margin: 5% auto;
                padding: 0;
                border-radius: var(--radius-lg);
                width: 90%;
                max-width: 800px;
                box-shadow: var(--shadow-xl);
                animation: slideDown 0.3s;
            }

            .modal-header {
                padding: 1.5rem 2rem;
                border-bottom: 2px solid var(--border-light);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .modal-header h2 {
                margin: 0;
                color: var(--text-primary);
                font-size: 1.5rem;
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }

            .modal-close {
                background: none;
                border: none;
                font-size: 2rem;
                color: var(--text-secondary);
                cursor: pointer;
                padding: 0;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 4px;
                transition: all 0.2s;
            }

            .modal-close:hover {
                background: var(--background);
                color: var(--text-primary);
            }

            .modal-body {
                padding: 2rem;
                max-height: 70vh;
                overflow-y: auto;
            }

            .stat-card {
                background: var(--background);
                border: 1px solid var(--border-light);
                border-radius: var(--radius);
                padding: 1.5rem;
                margin-bottom: 1rem;
            }

            .stat-label {
                font-size: 0.875rem;
                color: var(--text-secondary);
                margin-bottom: 0.5rem;
                font-weight: 500;
            }

            .stat-value {
                font-size: 2rem;
                font-weight: 700;
                color: var(--primary-color);
            }

            .progress-bar-container {
                background: var(--border-light);
                border-radius: 8px;
                height: 20px;
                overflow: hidden;
                margin-top: 0.5rem;
            }

            .progress-bar-fill {
                height: 100%;
                background: linear-gradient(90deg, var(--primary-color), var(--success-color));
                transition: width 0.3s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 0.75rem;
                font-weight: 600;
            }

            .pattern-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
                margin-top: 1rem;
            }

            .pattern-item {
                background: white;
                border: 1px solid var(--border-light);
                border-radius: var(--radius-sm);
                padding: 1rem;
                text-align: center;
            }

            .pattern-item .label {
                font-size: 0.875rem;
                color: var(--text-secondary);
                margin-bottom: 0.5rem;
            }

            .pattern-item .value {
                font-size: 1.5rem;
                font-weight: 700;
                color: var(--primary-color);
            }

            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            @keyframes slideDown {
                from {
                    opacity: 0;
                    transform: translateY(-30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @media (max-width: 768px) {
                .main-content {
                    grid-template-columns: 1fr;
                }
                
                .header h1 {
                    font-size: 2rem;
                }
                
                .nav-links {
                    flex-direction: column;
                    align-items: center;
                }
                
                .container {
                    padding: 1rem;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Auth Navigation Bar -->
            <div id="auth-nav" style="background: var(--surface); border-radius: var(--radius-lg); padding: 1rem 2rem; margin-bottom: 2rem; box-shadow: var(--shadow-lg); display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; gap: 1rem; align-items: center;">
                    <a href="/about" style="color: var(--text-primary); text-decoration: none; font-weight: 500;">
                        <i class="fas fa-info-circle"></i> About Us
                    </a>
                </div>
                <div id="auth-buttons" style="display: flex; gap: 1rem;">
                    <a href="/login" class="btn" style="text-decoration: none; padding: 0.5rem 1rem; font-size: 0.9rem;">
                        <i class="fas fa-sign-in-alt"></i> Login
                    </a>
                    <a href="/signup" class="btn" style="text-decoration: none; padding: 0.5rem 1rem; font-size: 0.9rem; background: linear-gradient(135deg, var(--success-color), #059669);">
                        <i class="fas fa-user-plus"></i> Sign Up
                    </a>
                </div>
                <div id="user-info" style="display: none; align-items: center; gap: 1rem;">
                    <span id="username-display" style="color: var(--text-primary); font-weight: 500;"></span>
                    <button onclick="logout()" class="btn" style="padding: 0.5rem 1rem; font-size: 0.9rem; background: linear-gradient(135deg, var(--error-color), #dc2626);">
                        <i class="fas fa-sign-out-alt"></i> Logout
                    </button>
                </div>
            </div>

            <div class="header">
                <h1><i class="fas fa-brain"></i> FlowMind</h1>
                <p>Intelligent Document Analysis & Requirements Extraction</p>
            </div>

            <!-- Login Required Message -->
            <div id="login-required" style="display: none; background: var(--surface); border-radius: var(--radius-lg); padding: 3rem; text-align: center; box-shadow: var(--shadow-xl); margin-bottom: 2rem;">
                <i class="fas fa-lock" style="font-size: 3rem; color: var(--primary-color); margin-bottom: 1rem;"></i>
                <h2 style="color: var(--text-primary); margin-bottom: 1rem;">Authentication Required</h2>
                <p style="color: var(--text-secondary); margin-bottom: 2rem;">Please login or sign up to access FlowMind features</p>
                <div style="display: flex; gap: 1rem; justify-content: center;">
                    <a href="/login" class="btn" style="text-decoration: none;">
                        <i class="fas fa-sign-in-alt"></i> Login
                    </a>
                    <a href="/signup" class="btn" style="text-decoration: none; background: linear-gradient(135deg, var(--success-color), #059669);">
                        <i class="fas fa-user-plus"></i> Sign Up
                    </a>
                </div>
            </div>

            <div class="main-content" id="main-content">
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon basic">
                            <i class="fas fa-file-text"></i>
                        </div>
                        <div>
                            <div class="card-title">Basic Extraction</div>
                            <div class="card-subtitle">Quick text and image extraction</div>
                        </div>
                    </div>
                    
                    <form id="form-basic">
                        <div class="form-group">
                            <div class="file-input-wrapper">
                                <input type="file" id="basic-file" class="file-input" accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.png,.jpg,.jpeg" required>
                                <label for="basic-file" class="file-input-label">
                                    <i class="fas fa-cloud-upload-alt"></i>
                                    Choose file to analyze
                                </label>
                            </div>
                        </div>
                        
                        <button type="submit" class="btn">
                            <i class="fas fa-play"></i>
                            Extract Content
                        </button>
                        
                        <div class="progress-container" id="basic-progress">
                            <div class="progress-bar">
                                <div class="progress-fill" id="basic-progress-bar"></div>
                            </div>
                            <div class="progress-text" id="basic-progress-text">Preparing...</div>
                        </div>
                        
                        <div class="output-container" id="basic-output">
                            <div style="color: var(--text-muted); text-align: center; padding: 2rem;">
                                <i class="fas fa-arrow-up" style="font-size: 2rem; margin-bottom: 1rem; opacity: 0.5;"></i>
                                <div>Upload a file to see extracted content here</div>
                            </div>
                        </div>
                    </form>
                </div>

                <div class="card">
                    <div class="card-header">
                        <div class="card-icon agent">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div>
                            <div class="card-title">AI Agent Analysis</div>
                            <div class="card-subtitle">Advanced RAG-powered requirements extraction</div>
                        </div>
                    </div>
                    
                    <form id="form-agent">
                        <div class="form-group">
                            <div class="file-input-wrapper">
                                <input type="file" id="agent-file" class="file-input" accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.png,.jpg,.jpeg" required>
                                <label for="agent-file" class="file-input-label">
                                    <i class="fas fa-cloud-upload-alt"></i>
                                    Choose file for AI analysis
                                </label>
                            </div>
                        </div>
                        
                        <button type="submit" class="btn">
                            <i class="fas fa-magic"></i>
                            Analyze with AI
                        </button>
                        
                        <div class="progress-container" id="agent-progress">
                            <div class="progress-bar">
                                <div class="progress-fill" id="agent-progress-bar"></div>
                            </div>
                            <div class="progress-text" id="agent-progress-text">Uploading...</div>
                        </div>
                        
                        <div class="output-container" id="agent-output">
                            <div style="color: var(--text-muted); text-align: center; padding: 2rem;">
                                <i class="fas fa-arrow-up" style="font-size: 2rem; margin-bottom: 1rem; opacity: 0.5;"></i>
                                <div>Upload a file to see AI analysis results here</div>
                            </div>
                        </div>
                        
                        <div class="view-link" id="agent-view-link"></div>
                    </form>
                </div>
            </div>

            <div class="navigation">
                <div class="nav-links">
                    <a href="/records" target="_blank" class="nav-link">
                        <i class="fas fa-database"></i>
                        View Records
                    </a>
                    <a href="/agent_status" target="_blank" class="nav-link">
                        <i class="fas fa-heartbeat"></i>
                        Agent Status
                    </a>
                    <button id="learning-status-btn" class="nav-link" style="cursor: pointer; border: none; font-family: inherit;">
                        <i class="fas fa-brain"></i>
                        Learning Progress
                    </button>
                    <a href="/docs" target="_blank" class="nav-link">
                        <i class="fas fa-book"></i>
                        API Documentation
                    </a>
                </div>
            </div>

            <!-- Learning Status Modal -->
            <div id="learningModal" class="modal" style="display: none;">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2><i class="fas fa-brain"></i> Learning Progress</h2>
                        <button id="close-learning-modal" class="modal-close">&times;</button>
                    </div>
                    <div class="modal-body" id="learningContent">
                        <div style="text-align: center; padding: 2rem;">
                            <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: var(--primary-color);"></i>
                            <div style="margin-top: 1rem;">Loading learning status...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Authentication check
            function checkAuth() {
                const token = localStorage.getItem('access_token');
                const userStr = localStorage.getItem('user');
                const authButtons = document.getElementById('auth-buttons');
                const userInfo = document.getElementById('user-info');
                const usernameDisplay = document.getElementById('username-display');
                const mainContent = document.getElementById('main-content');
                const loginRequired = document.getElementById('login-required');
                const navigation = document.querySelector('.navigation');

                if (token && userStr) {
                    try {
                        const user = JSON.parse(userStr);
                        // User is logged in - redirect to extract page
                        window.location.href = '/extract';
                        return;
                    } catch (e) {
                        // Invalid user data, clear and show login
                        localStorage.removeItem('access_token');
                        localStorage.removeItem('user');
                        showLoginRequired();
                    }
                } else {
                    showLoginRequired();
                }
            }

            function showLoginRequired() {
                const authButtons = document.getElementById('auth-buttons');
                const userInfo = document.getElementById('user-info');
                const mainContent = document.getElementById('main-content');
                const loginRequired = document.getElementById('login-required');
                const navigation = document.querySelector('.navigation');

                authButtons.style.display = 'flex';
                userInfo.style.display = 'none';
                mainContent.style.display = 'none';
                loginRequired.style.display = 'block';
                if (navigation) navigation.style.display = 'none';
            }

            function logout() {
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                window.location.href = '/';
            }

            // Helper function to get auth headers
            function getAuthHeaders() {
                const token = localStorage.getItem('access_token');
                if (!token) {
                    console.warn('No access token found in localStorage');
                    return {};
                }
                // When using FormData, don't set Content-Type - browser will set it with boundary
                // But we can still set Authorization header
                return { 'Authorization': `Bearer ${token}` };
            }

            // Check auth on page load
            document.addEventListener('DOMContentLoaded', function() {
                checkAuth();
            });

            // Enhanced file input handling
            function setupFileInput(inputId, labelSelector) {
                const input = document.getElementById(inputId);
                const label = document.querySelector(labelSelector);
                
                input.addEventListener('change', function() {
                    if (this.files.length > 0) {
                        const fileName = this.files[0].name;
                        label.innerHTML = `<i class="fas fa-file"></i> ${fileName}`;
                        label.style.borderColor = 'var(--success-color)';
                        label.style.background = 'rgba(16, 185, 129, 0.05)';
                        label.style.color = 'var(--success-color)';
                    }
                });
            }

            setupFileInput('basic-file', 'label[for="basic-file"]');
            setupFileInput('agent-file', 'label[for="agent-file"]');

            // Enhanced progress animation
            function animateProgress(progressId, textId, stages) {
                const progressContainer = document.getElementById(progressId);
                const progressBar = document.getElementById(progressId + '-bar');
                const progressText = document.getElementById(textId);
                
                progressContainer.style.display = 'block';
                
                let currentStage = 0;
                let progress = 0;
                
                const interval = setInterval(() => {
                    progress += Math.random() * 15 + 5; // Random increment between 5-20
                    
                    if (progress >= 100) {
                        progress = 100;
                        clearInterval(interval);
                    }
                    
                    progressBar.style.width = progress + '%';
                    
                    // Update stage based on progress
                    const stageProgress = Math.floor((progress / 100) * stages.length);
                    if (stageProgress !== currentStage && stageProgress < stages.length) {
                        currentStage = stageProgress;
                        progressText.textContent = stages[currentStage];
                    }
                }, 200);
                
                return interval;
            }

            // Enhanced form submission
            async function postForm(url, fileInput, outputId) {
                const fileEl = document.getElementById(fileInput);
                const outEl = document.getElementById(outputId);
                if (!fileEl || !outEl) {
                    console.error('Form elements not found');
                    return;
                }
                
                const submitBtn = fileEl.closest('form')?.querySelector('button[type="submit"]');
                if (!submitBtn) {
                    console.error('Submit button not found');
                    return;
                }
                
                if (!fileEl.files || !fileEl.files[0]) {
                    showError(outEl, 'Please select a file first.');
                    return;
                }

                // Check authentication
                const token = localStorage.getItem('access_token');
                if (!token) {
                    showError(outEl, 'Please login to upload files. <a href="/login" style="color: var(--primary-color);">Login here</a>');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = isAgent ? '<i class="fas fa-magic"></i> Analyze with AI' : '<i class="fas fa-play"></i> Extract Content';
                    return;
                }

                // Update UI state
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                outEl.innerHTML = '<div class="loading"><i class="fas fa-cog fa-spin"></i> Processing your document...</div>';

                const fd = new FormData();
                fd.append('file', fileEl.files[0]);
                
                const isAgent = (fileInput === 'agent-file');
                const stages = isAgent
                    ? ['Uploading...', 'Extracting text...', 'Processing images...', 'Running AI analysis...', 'Generating insights...']
                    : ['Uploading...', 'Extracting content...', 'Processing images...', 'Finalizing...'];
                
                let progressInterval = null;
                try {
                    progressInterval = animateProgress(
                        isAgent ? 'agent-progress' : 'basic-progress',
                        isAgent ? 'agent-progress-text' : 'basic-progress-text',
                        stages
                    );
                } catch (e) {
                    console.warn('Progress animation failed:', e);
                }

                try {
                    const headers = getAuthHeaders();
                    // Debug: Log token presence
                    const token = localStorage.getItem('access_token');
                    console.log('Token present:', !!token);
                    console.log('Headers being sent:', headers);
                    
                    if (!token) {
                        showError(outEl, 'Authentication token not found. Please <a href="/login" style="color: var(--primary-color);">login again</a>.');
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = isAgent ? '<i class="fas fa-magic"></i> Analyze with AI' : '<i class="fas fa-play"></i> Extract Content';
                        return;
                    }
                    
                    const res = await fetch(url, { 
                        method: 'POST', 
                        body: fd,
                        headers: headers
                    });
                    const text = await res.text();
                    
                    if (progressInterval) {
                        clearInterval(progressInterval);
                    }
                    
                    if (res.ok) {
                        try {
                            const data = JSON.parse(text);
                            displayResults(outEl, data, isAgent);
                            
                            if (data && data.view_id) {
                                const linkDiv = document.getElementById('agent-view-link');
                                if (linkDiv) {
                                    linkDiv.innerHTML = `
                                        <a href="/view_requirements/${data.view_id}" target="_blank">
                                            <i class="fas fa-external-link-alt"></i>
                                            View Formatted Results
                                        </a>
                                    `;
                                }
                            }
                        } catch(e) {
                            console.error('JSON parse error:', e);
                            showError(outEl, 'Invalid response format: ' + text.substring(0, 200));
                        }
                    } else {
                        // Handle specific error cases
                        if (res.status === 401) {
                            // Clear invalid token and redirect to login
                            localStorage.removeItem('access_token');
                            localStorage.removeItem('user');
                            showError(outEl, 'Your session has expired or authentication failed. Please <a href="/login" style="color: var(--primary-color); font-weight: bold;">login again</a> to continue.');
                            // Redirect to login after a short delay
                            setTimeout(() => {
                                window.location.href = '/login';
                            }, 3000);
                    } else {
                        showError(outEl, `Error ${res.status}: ${text.substring(0, 500)}`);
                        }
                    }
                } catch (e) {
                    if (progressInterval) {
                        clearInterval(progressInterval);
                    }
                    console.error('Network error:', e);
                    showError(outEl, 'Network error: ' + (e.message || 'Unknown error'));
                } finally {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = isAgent 
                            ? '<i class="fas fa-magic"></i> Analyze with AI'
                            : '<i class="fas fa-play"></i> Extract Content';
                    }
                }
            }

            function displayResults(container, data, isAgent) {
                let html = '<div style="color: var(--success-color); margin-bottom: 1rem;"><i class="fas fa-check-circle"></i> Analysis Complete</div>';
                
                if (isAgent) {
                    html += formatAgentResults(data);
                } else {
                    html += formatBasicResults(data);
                }
                
                container.innerHTML = html;
            }

            function formatBasicResults(data) {
                let html = '<div style="margin-bottom: 1rem;">';
                html += `<div><strong>File:</strong> ${data.filename || 'Unknown'}</div>`;
                html += `<div><strong>Summary:</strong> ${data.summary || 'No summary available'}</div>`;
                html += `<div><strong>Images detected:</strong> ${data.images_detected || 0}</div>`;
                html += '</div>';
                
                if (data.images && data.images.length > 0) {
                    html += '<div style="margin-top: 1rem;"><strong>Images:</strong></div>';
                    data.images.forEach((img, index) => {
                        html += `<div style="margin: 0.5rem 0; padding: 0.5rem; background: rgba(255,255,255,0.05); border-radius: 4px;">`;
                        html += `<div><strong>Image ${index + 1}</strong> (Page ${img.page})</div>`;
                        if (img.ocr) {
                            html += `<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">OCR: ${img.ocr.substring(0, 100)}${img.ocr.length > 100 ? '...' : ''}</div>`;
                        }
                        html += '</div>';
                    });
                }
                
                return html;
            }

            function formatAgentResults(data) {
                let html = '<div style="margin-bottom: 1rem;">';
                html += `<div><strong>File:</strong> ${data.filename || 'Unknown'}</div>`;
                html += `<div><strong>Extraction:</strong> ${data.extraction_summary || 'No summary available'}</div>`;
                html += '</div>';
                
                if (data.agent_processing) {
                    html += '<div style="margin-bottom: 1rem;">';
                    html += '<div><strong>Agent Processing:</strong></div>';
                    html += `<div style="margin-left: 1rem; color: var(--text-muted);">${data.agent_processing.message || 'Processing completed'}</div>`;
                    html += '</div>';
                }
                
                if (data.requirements_extraction && data.requirements_extraction.response) {
                    html += '<div style="margin-bottom: 1rem;">';
                    html += '<div><strong>Requirements Extracted:</strong></div>';
                    html += `<div style="margin-left: 1rem; white-space: pre-wrap;">${data.requirements_extraction.response}</div>`;
                    html += '</div>';
                }
                
                return html;
            }

            function showError(container, message) {
                container.innerHTML = `
                    <div style="color: var(--error-color); text-align: center; padding: 1rem;">
                        <i class="fas fa-exclamation-triangle"></i>
                        <div style="margin-top: 0.5rem;">${message}</div>
                    </div>
                `;
            }

            // Form event listeners
            document.getElementById('form-basic').addEventListener('submit', function(ev){
                ev.preventDefault();
                postForm('/upload_client_doc', 'basic-file', 'basic-output');
            });

            document.getElementById('form-agent').addEventListener('submit', function(ev){
                ev.preventDefault();
                postForm('/upload_agent_doc', 'agent-file', 'agent-output');
            });

            // Add some interactive effects
            document.querySelectorAll('.card').forEach(card => {
                card.addEventListener('mouseenter', function() {
                    this.style.transform = 'translateY(-8px)';
                });
                
                card.addEventListener('mouseleave', function() {
                    this.style.transform = 'translateY(0)';
                });
            });

            // Learning Status Functions
            async function showLearningStatus() {
                const modal = document.getElementById('learningModal');
                const content = document.getElementById('learningContent');
                
                modal.style.display = 'block';
                content.innerHTML = `
                    <div style="text-align: center; padding: 2rem;">
                        <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: var(--primary-color);"></i>
                        <div style="margin-top: 1rem;">Loading learning status...</div>
                    </div>
                `;
                
                try {
                    const response = await fetch('/learning-status');
                    const data = await response.json();
                    displayLearningStatus(data);
                } catch (error) {
                    content.innerHTML = `
                        <div style="color: var(--error-color); text-align: center; padding: 2rem;">
                            <i class="fas fa-exclamation-triangle"></i>
                            <div style="margin-top: 1rem;">Error loading learning status: ${error.message}</div>
                        </div>
                    `;
                }
            }

            function displayLearningStatus(data) {
                const content = document.getElementById('learningContent');
                
                if (data.error) {
                    content.innerHTML = `
                        <div style="color: var(--error-color); text-align: center; padding: 2rem;">
                            <i class="fas fa-exclamation-triangle"></i>
                            <div style="margin-top: 1rem;">${data.error}</div>
                        </div>
                    `;
                    return;
                }
                
                const totalPatterns = data.total_learned_patterns || 0;
                const iterations = data.learning_iterations || 0;
                const documents = data.total_documents_processed || 0;
                const successRate = (data.success_rate || 0) * 100;
                const learningEnabled = data.learning_enabled ? 'Enabled' : 'Disabled';
                
                let html = `
                    <div class="stat-card">
                        <div class="stat-label">Learning Status</div>
                        <div class="stat-value" style="font-size: 1.5rem;">${learningEnabled}</div>
                    </div>
                    
                    <div class="pattern-grid">
                        <div class="stat-card">
                            <div class="stat-label">Total Patterns Learned</div>
                            <div class="stat-value">${totalPatterns.toLocaleString()}</div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-label">Learning Iterations</div>
                            <div class="stat-value">${iterations.toLocaleString()}</div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-label">Documents Processed</div>
                            <div class="stat-value">${documents.toLocaleString()}</div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-label">Success Rate</div>
                            <div class="stat-value" style="font-size: 1.5rem;">${successRate.toFixed(1)}%</div>
                            <div class="progress-bar-container" style="margin-top: 0.5rem;">
                                <div class="progress-bar-fill" style="width: ${successRate}%;">${successRate.toFixed(0)}%</div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Patterns by Category
                if (data.patterns_by_category) {
                    html += `
                        <div style="margin-top: 2rem;">
                            <h3 style="margin-bottom: 1rem; color: var(--text-primary);">
                                <i class="fas fa-layer-group"></i> Patterns by Category
                            </h3>
                            <div class="pattern-grid">
                    `;
                    
                    for (const [category, patterns] of Object.entries(data.patterns_by_category)) {
                        const total = (patterns.keywords || 0) + (patterns.phrases || 0) + (patterns.patterns || 0);
                        html += `
                            <div class="pattern-item">
                                <div class="label">${category.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase())}</div>
                                <div class="value">${total}</div>
                                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">
                                    K: ${patterns.keywords || 0} | P: ${patterns.phrases || 0} | Pt: ${patterns.patterns || 0}
                                </div>
                            </div>
                        `;
                    }
                    
                    html += `
                            </div>
                        </div>
                    `;
                }
                
                // Method Success Rates
                if (data.method_success_rates && Object.keys(data.method_success_rates).length > 0) {
                    html += `
                        <div style="margin-top: 2rem;">
                            <h3 style="margin-bottom: 1rem; color: var(--text-primary);">
                                <i class="fas fa-chart-line"></i> Method Performance
                            </h3>
                    `;
                    
                    for (const [method, rate] of Object.entries(data.method_success_rates)) {
                        const ratePercent = rate * 100;
                        html += `
                            <div class="stat-card">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                    <div class="stat-label" style="margin: 0;">${method.charAt(0).toUpperCase() + method.slice(1)}</div>
                                    <div style="font-weight: 600; color: var(--primary-color);">${ratePercent.toFixed(1)}%</div>
                                </div>
                                <div class="progress-bar-container">
                                    <div class="progress-bar-fill" style="width: ${ratePercent}%;">${ratePercent.toFixed(0)}%</div>
                                </div>
                            </div>
                        `;
                    }
                    
                    html += `</div>`;
                }
                
                // Last Learning Session
                if (data.last_learning_session) {
                    const session = data.last_learning_session;
                    html += `
                        <div style="margin-top: 2rem;">
                            <h3 style="margin-bottom: 1rem; color: var(--text-primary);">
                                <i class="fas fa-clock"></i> Last Learning Session
                            </h3>
                            <div class="stat-card">
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem;">
                                    <div>
                                        <div class="stat-label">Keywords</div>
                                        <div class="stat-value" style="font-size: 1.25rem;">${session.keywords || 0}</div>
                                    </div>
                                    <div>
                                        <div class="stat-label">Phrases</div>
                                        <div class="stat-value" style="font-size: 1.25rem;">${session.phrases || 0}</div>
                                    </div>
                                    <div>
                                        <div class="stat-label">Patterns</div>
                                        <div class="stat-value" style="font-size: 1.25rem;">${session.patterns || 0}</div>
                                    </div>
                                    <div>
                                        <div class="stat-label">Total</div>
                                        <div class="stat-value" style="font-size: 1.25rem;">${session.total || 0}</div>
                                    </div>
                                </div>
                                ${session.filename ? `<div style="margin-top: 1rem; font-size: 0.875rem; color: var(--text-secondary);">File: ${session.filename}</div>` : ''}
                            </div>
                        </div>
                    `;
                }
                
                content.innerHTML = html;
            }

            function closeLearningModal() {
                document.getElementById('learningModal').style.display = 'none';
            }

            // Event listeners for learning status
            document.addEventListener('DOMContentLoaded', function() {
                const learningBtn = document.getElementById('learning-status-btn');
                const closeBtn = document.getElementById('close-learning-modal');
                const modal = document.getElementById('learningModal');
                
                if (learningBtn) {
                    learningBtn.addEventListener('click', function() {
                        showLearningStatus().catch(function(error) {
                            console.error('Error showing learning status:', error);
                            const content = document.getElementById('learningContent');
                            if (content) {
                                content.innerHTML = `
                                    <div style="color: var(--error-color); text-align: center; padding: 2rem;">
                                        <i class="fas fa-exclamation-triangle"></i>
                                        <div style="margin-top: 1rem;">Error loading learning status. Please try again.</div>
                                    </div>
                                `;
                            }
                        });
                    });
                }
                
                if (closeBtn) {
                    closeBtn.addEventListener('click', closeLearningModal);
                }
                
                // Close modal when clicking outside
                if (modal) {
                    modal.addEventListener('click', function(event) {
                        if (event.target === modal) {
                            closeLearningModal();
                        }
                    });
                }
            });
            
            // Global error handler for unhandled promises
            window.addEventListener('unhandledrejection', function(event) {
                console.error('Unhandled promise rejection:', event.reason);
                // Prevent the error from appearing in console
                event.preventDefault();
            });
        </script>
    </body>
    </html>
    """


# NOTE: Upload endpoints moved to routes/upload_routes.py to avoid duplicate route definitions
# The routes are included via app.include_router(upload_router) below


# ==============================================================
# LEARNING SYSTEM ENDPOINTS
# ==============================================================

@app.get("/learning-status")
async def get_learning_status():
    """Get the current learning status and statistics."""
    try:
        agent = get_agent()
        if hasattr(agent, 'get_learning_status'):
            status = agent.get_learning_status()
            return status
        else:
            return {"error": "Learning system not available"}
    except Exception as e:
        return {"error": f"Failed to get learning status: {str(e)}"}

# ==============================================================
# RECORDS DASHBOARD
# ==============================================================

@app.get("/records", response_class=HTMLResponse)
def get_records(current_user: User = Depends(get_current_user)):
    """Displays all analyzed file summaries. Requires authentication."""
    db = SessionLocal()
    records = db.query(ParsedFile).all()
    db.close()

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FlowMind Records</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {
                --primary-color: #2563eb;
                --primary-dark: #1d4ed8;
                --secondary-color: #64748b;
                --success-color: #10b981;
                --warning-color: #f59e0b;
                --error-color: #ef4444;
                --background: #f8fafc;
                --surface: #ffffff;
                --surface-elevated: #ffffff;
                --text-primary: #1e293b;
                --text-secondary: #64748b;
                --text-muted: #94a3b8;
                --border: #e2e8f0;
                --border-light: #f1f5f9;
                --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
                --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                --radius: 12px;
                --radius-sm: 8px;
                --radius-lg: 16px;
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: var(--text-primary);
                line-height: 1.6;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }

            .header {
                text-align: center;
                margin-bottom: 3rem;
                animation: fadeInDown 0.8s ease-out;
            }

            .header h1 {
                font-size: 3rem;
                font-weight: 700;
                color: white;
                margin-bottom: 0.5rem;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }

            .header p {
                font-size: 1.2rem;
                color: rgba(255, 255, 255, 0.9);
                font-weight: 300;
            }

            .back-btn {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background: var(--surface);
                color: var(--text-primary);
                text-decoration: none;
                padding: 0.75rem 1.5rem;
                border-radius: var(--radius);
                font-weight: 500;
                transition: all 0.3s ease;
                box-shadow: var(--shadow);
                margin-bottom: 2rem;
                animation: fadeInUp 0.8s ease-out;
            }

            .back-btn:hover {
                background: var(--primary-color);
                color: white;
                transform: translateY(-2px);
                box-shadow: var(--shadow-lg);
            }

            .records-card {
                background: var(--surface);
                border-radius: var(--radius-lg);
                padding: 2rem;
                box-shadow: var(--shadow-xl);
                border: 1px solid var(--border-light);
                animation: fadeInUp 0.8s ease-out 0.2s both;
            }

            .records-header {
                display: flex;
                align-items: center;
                margin-bottom: 2rem;
            }

            .records-icon {
                width: 48px;
                height: 48px;
                border-radius: var(--radius);
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 1rem;
                font-size: 1.5rem;
                color: white;
                background: linear-gradient(135deg, var(--success-color), #059669);
            }

            .records-title {
                font-size: 1.5rem;
                font-weight: 600;
                color: var(--text-primary);
            }

            .records-subtitle {
                font-size: 0.9rem;
                color: var(--text-secondary);
                margin-top: 0.25rem;
            }

            .records-table {
                width: 100%;
                border-collapse: collapse;
                background: var(--surface);
                border-radius: var(--radius);
                overflow: hidden;
                box-shadow: var(--shadow);
            }

            .records-table th {
                background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
                color: white;
                padding: 1rem;
                text-align: left;
                font-weight: 600;
                font-size: 0.9rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .records-table td {
                padding: 1rem;
                border-bottom: 1px solid var(--border-light);
                color: var(--text-primary);
            }

            .records-table tr:hover {
                background: var(--background);
                transform: scale(1.01);
                transition: all 0.2s ease;
            }

            .records-table tr:last-child td {
                border-bottom: none;
            }

            .file-link {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background: var(--primary-color);
                color: white;
                text-decoration: none;
                padding: 0.5rem 1rem;
                border-radius: var(--radius-sm);
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.3s ease;
            }

            .file-link:hover {
                background: var(--primary-dark);
                transform: translateY(-1px);
                box-shadow: var(--shadow);
            }

            .file-icon {
                width: 32px;
                height: 32px;
                border-radius: var(--radius-sm);
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 0.75rem;
                font-size: 1rem;
                color: white;
                background: linear-gradient(135deg, var(--secondary-color), #475569);
            }

            .file-name {
                font-weight: 500;
                color: var(--text-primary);
            }

            .file-meta {
                font-size: 0.875rem;
                color: var(--text-secondary);
                margin-top: 0.25rem;
            }

            .stats-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.25rem;
                background: rgba(16, 185, 129, 0.1);
                color: var(--success-color);
                padding: 0.25rem 0.75rem;
                border-radius: var(--radius-sm);
                font-size: 0.8rem;
                font-weight: 500;
            }

            .empty-state {
                text-align: center;
                padding: 3rem;
                color: var(--text-secondary);
            }

            .empty-state i {
                font-size: 3rem;
                margin-bottom: 1rem;
                opacity: 0.5;
            }

            @keyframes fadeInDown {
                from {
                    opacity: 0;
                    transform: translateY(-30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @media (max-width: 768px) {
                .container {
                    padding: 1rem;
                }
                
                .header h1 {
                    font-size: 2rem;
                }
                
                .records-table {
                    font-size: 0.875rem;
                }
                
                .records-table th,
                .records-table td {
                    padding: 0.75rem 0.5rem;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1><i class="fas fa-database"></i> FlowMind Records</h1>
                <p>All analyzed documents and their extracted content</p>
            </div>

            <a href="/" class="back-btn">
                <i class="fas fa-arrow-left"></i>
                Back to FlowMind
            </a>

            <div class="records-card">
                <div class="records-header">
                    <div class="records-icon">
                        <i class="fas fa-folder-open"></i>
                    </div>
                    <div>
                        <div class="records-title">Processed Documents</div>
                        <div class="records-subtitle">Total: """ + str(len(records)) + """ files analyzed</div>
                    </div>
                </div>
    """

    if records:
        html += """
                <table class="records-table">
                    <thead>
                        <tr>
                            <th><i class="fas fa-hashtag"></i> ID</th>
                            <th><i class="fas fa-file"></i> Filename</th>
                            <th><i class="fas fa-images"></i> Images</th>
                            <th><i class="fas fa-info-circle"></i> Summary</th>
                            <th><i class="fas fa-external-link-alt"></i> Actions</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        for r in records:
            text_link = r.full_text_path.replace("\\", "/") if r.full_text_path else "#"
            file_icon = "fas fa-file-pdf" if r.filename.lower().endswith('.pdf') else \
                       "fas fa-file-word" if r.filename.lower().endswith(('.doc', '.docx')) else \
                       "fas fa-file-powerpoint" if r.filename.lower().endswith(('.ppt', '.pptx')) else \
                       "fas fa-file-image" if r.filename.lower().endswith(('.png', '.jpg', '.jpeg')) else \
                       "fas fa-file-alt"
            
            html += f"""
                        <tr>
                            <td>
                                <div class="stats-badge">
                                    <i class="fas fa-hashtag"></i>
                                    {r.id}
                                </div>
                            </td>
                            <td>
                                <div class="file-icon">
                                    <i class="{file_icon}"></i>
                                </div>
                                <div>
                                    <div class="file-name">{r.filename}</div>
                                    <div class="file-meta">Processed document</div>
                                </div>
                            </td>
                            <td>
                                <div class="stats-badge">
                                    <i class="fas fa-images"></i>
                                    {r.detected_shapes}
                                </div>
                            </td>
                            <td>
                                <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">
                                    {r.summary}
                                </div>
                            </td>
                            <td>
                                <a href='/{text_link}' target='_blank' class="file-link">
                                    <i class="fas fa-external-link-alt"></i>
                                    View Text
                                </a>
                            </td>
                        </tr>
            """

        html += """
                    </tbody>
                </table>
        """
    else:
        html += """
                <div class="empty-state">
                    <i class="fas fa-folder-open"></i>
                    <h3>No documents processed yet</h3>
                    <p>Upload your first document to see it appear here</p>
                </div>
        """

    html += """
            </div>
        </div>
    </body>
    </html>
    """
    return html


# ==============================================================
# RAG AGENT ENDPOINTS
# ==============================================================

@app.post("/analyze_with_agent")
async def _analyze_with_agent_internal(
    file: UploadFile,
    user_id: int = None,
    db_session = None,
    progress_tracker_id: str = None
):
    """Internal function: Extract text from document and process with RAG agent for requirements extraction."""
    from services.progress_service import ProcessingStage
    from services.progress_storage import get_progress_tracker
    
    tracker = None
    if progress_tracker_id:
        tracker = get_progress_tracker(progress_tracker_id)
        if tracker:
            # Tracker should already be in UPLOADING stage from start()
            pass
    
    try:
        # First, extract text using existing functionality
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        if tracker:
            tracker.set_stage(ProcessingStage.UPLOADING)
            progress = tracker.get_progress()
            print(f"📊 Progress: {progress['progress']}% - {progress['message']}")
        
        with open(filepath, "wb") as f:
            f.write(await file.read())
        
        if tracker:
            tracker.set_stage(ProcessingStage.PARSING)
            progress = tracker.get_progress()
            print(f"📊 Progress: {progress['progress']}% - {progress['message']}")

        text_output = ""
        image_count = 0
        detected_images = 0  # Initialize counter for detected images
        image_metadata = []  # (image_id, image_path, page_number, ocr_text)

        def gen_image_id(fname: str, page_num: int, idx: int) -> str:
            base = f"{fname}|{page_num}|{idx}"
            h = hashlib.md5(base.encode()).hexdigest()[:10]
            return f"IMG-{h}-{page_num}-{idx}"

        # Extract text based on file type
        if file.filename.endswith(".pdf"):
            print(f"📄 Detected PDF file, initializing PDF reader...")
            reader = PdfReader(filepath)
            total_pages = len(reader.pages)
            chunk_size = 10
            page_end_offsets = {}

            print(f"📘 Document has {total_pages} pages. Starting text extraction...")
            
            if tracker:
                tracker.set_stage(ProcessingStage.PARSING, total_pages=total_pages, current_page=0)
                progress = tracker.get_progress()
                print(f"📊 [{progress['progress']}%] {progress['message']}")

            for start in range(0, total_pages, chunk_size):
                end = min(start + chunk_size, total_pages)
                print(f"🔹 Processing pages {start + 1}–{end} of {total_pages}...")

                for page_index in range(start, end):
                    page = reader.pages[page_index]
                    page_text = page.extract_text() or ""
                    text_output += page_text + "\n"
                    page_end_offsets[page_index + 1] = len(text_output)

                    if tracker:
                        tracker.set_stage(ProcessingStage.PARSING, total_pages=total_pages, current_page=page_index + 1)
                        if (page_index + 1) % 5 == 0 or page_index + 1 == total_pages:  # Log every 5 pages
                            progress = tracker.get_progress()
                            print(f"📊 [{progress['progress']}%] Currently working on page {page_index + 1}/{total_pages}")

                print(f"✅ Finished pages {start + 1}–{end} of {total_pages}.")
            print(f"✅ Completed all {total_pages} pages. Extracted {len(text_output):,} characters.")

            # Extract images using pypdf Page.images if available
            try:
                from io import BytesIO
                for page_num, page in enumerate(reader.pages, start=1):
                    try:
                        imgs = getattr(page, "images", []) or []
                    except Exception:
                        imgs = []
                    for img_idx, img in enumerate(imgs, start=1):
                        try:
                            data = getattr(img, "data", None)
                            if not data:
                                continue
                            image_count += 1
                            image_id = gen_image_id(file.filename, page_num, img_idx)
                            out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}.png")
                            try:
                                im = Image.open(BytesIO(data))
                                im.save(out_path, format="PNG")
                                ocr_text = pytesseract.image_to_string(im)
                            except Exception:
                                with open(out_path, "wb") as fimg:
                                    fimg.write(data)
                                ocr_text = ""
                            image_metadata.append((image_id, out_path, page_num, ocr_text))
                            detected_images += 1
                            pos = page_end_offsets.get(page_num, len(text_output))
                            context_before = text_output[max(0, pos - 300):pos]
                            
                            # Update progress for OCR
                            if tracker:
                                tracker.set_stage(ProcessingStage.OCR_PROCESSING, total_images=detected_images, current_image=detected_images)
                            
                            # Update progress for summarization
                            if tracker:
                                tracker.set_stage(ProcessingStage.IMAGE_SUMMARIZATION, total_images=detected_images, current_image=detected_images)
                            
            # Append marker after context to help later viewing
                            if (ocr_text or "").strip():
                                text_output += f"\n[IMAGE {image_id}]\nOCR: {(ocr_text or '').strip()}\n"
                        except Exception:
                            continue
            except Exception:
                pass

        elif file.filename.endswith(".doc"):
            soffice_path_candidates = [
                shutil.which("soffice"),
                "/Applications/LibreOffice.app/Contents/MacOS/soffice"
            ]
            soffice = next((p for p in soffice_path_candidates if p and os.path.exists(p)), None)
            if not soffice:
                text_output = "Unsupported file format (.doc) and LibreOffice not found for conversion."
            else:
                try:
                    subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", UPLOAD_DIR, filepath], check=True)
                    converted = os.path.join(UPLOAD_DIR, os.path.splitext(file.filename)[0] + ".docx")
                    d = docx.Document(converted)
                    for para in d.paragraphs:
                        text_output += para.text + "\n"
                    # Extract images from converted DOCX
                    img_idx = 0
                    for rel in d.part.rels.values():
                        if "image" in rel.reltype and getattr(rel, "target_part", None):
                            try:
                                img_idx += 1
                                image_count += 1
                                blob = rel.target_part.blob
                                page_num = 1
                                image_id = gen_image_id(file.filename, page_num, img_idx)
                                ext = ".png"
                                out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}{ext}")
                                with open(out_path, "wb") as imf:
                                    imf.write(blob)
                                try:
                                    img = Image.open(out_path)
                                    ocr_text = pytesseract.image_to_string(img)
                                except Exception:
                                    ocr_text = ""
                                image_metadata.append((image_id, out_path, page_num, ocr_text))
                                if ocr_text.strip():
                                    text_output += f"\n[IMAGE {image_id}]\nOCR: {ocr_text.strip()}\n"
                            except Exception:
                                pass
                except Exception as e:
                    text_output = f"Conversion error for .doc: {e}"

        elif file.filename.endswith(".docx"):
            d = docx.Document(filepath)
            for para in d.paragraphs:
                text_output += para.text + "\n"
            # Extract images from DOCX
            img_idx = 0
            for rel in d.part.rels.values():
                if "image" in rel.reltype and getattr(rel, "target_part", None):
                    try:
                        img_idx += 1
                        image_count += 1
                        blob = rel.target_part.blob
                        page_num = 1
                        image_id = gen_image_id(file.filename, page_num, img_idx)
                        ext = ".png"
                        out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}{ext}")
                        with open(out_path, "wb") as imf:
                            imf.write(blob)
                        try:
                            img = Image.open(out_path)
                            ocr_text = pytesseract.image_to_string(img)
                        except Exception:
                            ocr_text = ""
                        image_metadata.append((image_id, out_path, page_num, ocr_text))
                        if ocr_text.strip():
                            text_output += f"\n[IMAGE {image_id}]\nOCR: {ocr_text.strip()}\n"
                    except Exception:
                        pass

        elif file.filename.endswith(".ppt"):
            soffice_path_candidates = [
                shutil.which("soffice"),
                "/Applications/LibreOffice.app/Contents/MacOS/soffice"
            ]
            soffice = next((p for p in soffice_path_candidates if p and os.path.exists(p)), None)
            if not soffice:
                text_output = "Unsupported file format (.ppt) and LibreOffice not found for conversion."
            else:
                try:
                    subprocess.run([soffice, "--headless", "--convert-to", "pptx", "--outdir", UPLOAD_DIR, filepath], check=True)
                    converted = os.path.join(UPLOAD_DIR, os.path.splitext(file.filename)[0] + ".pptx")
                    prs = pptx.Presentation(converted)
                    for slide in prs.slides:
                        for shape in slide.shapes:
                            if hasattr(shape, "text"):
                                text_output += shape.text + "\n"
                            if getattr(shape, "shape_type", None) == 13 and hasattr(shape, "image"):
                                try:
                                    image_count += 1
                                    image_id = gen_image_id(file.filename, 1, image_count)
                                    ext = ".png"
                                    out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}{ext}")
                                    with open(out_path, "wb") as imf:
                                        imf.write(shape.image.blob)
                                    try:
                                        img = Image.open(out_path)
                                        ocr_text = pytesseract.image_to_string(img)
                                    except Exception:
                                        ocr_text = ""
                                    image_metadata.append((image_id, out_path, 1, ocr_text))
                                    if ocr_text.strip():
                                        text_output += f"\n[IMAGE {image_id}]\nOCR: {ocr_text.strip()}\n"
                                except Exception:
                                    pass
                except Exception as e:
                    text_output = f"Conversion error for .ppt: {e}"

        elif file.filename.endswith(".pptx"):
            prs = pptx.Presentation(filepath)
            for slide_idx, slide in enumerate(prs.slides, start=1):
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_output += shape.text + "\n"
                    if getattr(shape, "shape_type", None) == 13 and hasattr(shape, "image"):
                        try:
                            image_count += 1
                            image_id = gen_image_id(file.filename, slide_idx, image_count)
                            ext = ".png"
                            out_path = os.path.join(UPLOAD_DIR, f"{file.filename}_{image_id}{ext}")
                            with open(out_path, "wb") as imf:
                                imf.write(shape.image.blob)
                            try:
                                img = Image.open(out_path)
                                ocr_text = pytesseract.image_to_string(img)
                            except Exception:
                                ocr_text = ""
                            image_metadata.append((image_id, out_path, slide_idx, ocr_text))
                            if ocr_text.strip():
                                text_output += f"\n[IMAGE {image_id}]\nOCR: {ocr_text.strip()}\n"
                        except Exception:
                            pass

        elif file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            if tracker:
                tracker.set_stage(ProcessingStage.IMAGE_DETECTION)
            image_count = 1
            img = Image.open(filepath)
            if tracker:
                tracker.set_stage(ProcessingStage.OCR_PROCESSING, total_images=1, current_image=1)
            text_output = pytesseract.image_to_string(img)
            image_id = gen_image_id(file.filename, 1, 1)
            image_metadata.append((image_id, filepath, 1, text_output))
            if tracker:
                tracker.set_stage(ProcessingStage.IMAGE_SUMMARIZATION, total_images=1, current_image=1)
            if text_output.strip():
                text_output += f"\n[IMAGE {image_id}]\nOCR: {text_output.strip()}\n"

        elif file.filename.lower().endswith(".txt"):
            # Handle text files
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text_output = f.read()

        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # Save full text file
        sanitized_text = (text_output or "").encode("utf-8", "ignore").decode("utf-8", "ignore")
        text_file_path = os.path.join(UPLOAD_DIR, f"{file.filename}_full.txt")
        with open(text_file_path, "w", encoding="utf-8") as tf:
            tf.write(sanitized_text)

        # Process with RAG agent - use async helpers to avoid blocking
        # Get user-specific agent for user-specific learning
        if tracker:
            tracker.set_stage(ProcessingStage.FINALIZING)  # AI Processing stage
            progress = tracker.get_progress()
            print(f"📊 Progress: {progress['progress']}% - {progress['message']}")
        
        print(f"🤖 Initializing AI agent for user_id={user_id}...")
        
        # Import async helpers
        from utils.async_helpers import run_in_thread
        
        # Get agent in thread pool to avoid blocking (with timeout)
        try:
            agent = await run_in_thread(get_agent, user_id=user_id, timeout=60.0)
            print("✅ AI agent initialized, processing document...")
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Agent initialization timed out. Please try again."
            )
        except Exception as e:
            print(f"❌ Error initializing agent: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize AI agent: {str(e)}"
            )
        
        if tracker:
            # Update progress: Document processing
            tracker.set_stage(ProcessingStage.FINALIZING)
            progress = tracker.get_progress()
            print(f"📊 Progress: {progress['progress']}% - Processing document with AI agent...")
        
        # Process document in thread pool with timeout
        try:
            agent_result = await run_in_thread(
                agent.process_document,
                text_output,
                file.filename,
                timeout=240.0  # 4 minutes for document processing (increased for large documents)
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Document processing timed out. The document may be too large or complex."
            )
        except Exception as e:
            print(f"❌ Error processing document: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing document: {str(e)}"
            )
        
        if agent_result.get("status") != "success":
            msg = agent_result.get("message") or "Agent failed to process document"
            raise HTTPException(status_code=500, detail=msg)

        # Extract requirements using the agent
        if tracker:
            tracker.set_stage(ProcessingStage.FINALIZING)  # Requirements extraction
            progress = tracker.get_progress()
            print(f"📊 Progress: {progress['progress']}% - Extracting requirements...")
        
        # Extract requirements in thread pool with timeout
        try:
            requirements_result = await run_in_thread(
                agent.extract_requirements,
                timeout=300.0  # 5 minutes for requirements extraction (increased for large documents)
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Requirements extraction timed out. Please try again with a smaller document."
            )
        except Exception as e:
            print(f"❌ Error extracting requirements: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error extracting requirements: {str(e)}"
            )
        
        if tracker:
            tracker.complete()
            print(f"✅ Processing complete: {tracker.get_progress()['progress']}%")
        
        # Debug logging
        print(f"🔍 Requirements result status: {requirements_result.get('status')}")
        print(f"🔍 Requirements result keys: {list(requirements_result.keys())}")
        if requirements_result.get("message"):
            print(f"🔍 Error message: {requirements_result.get('message')}")
        
        if requirements_result.get("status") != "success":
            error_msg = requirements_result.get("message") or "Requirement extraction failed"
            print(f"❌ Extraction failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

        # Save to database - ensure session is closed promptly
        try:
            if db_session is None:
                db = SessionLocal()
                should_close = True
            else:
                db = db_session
                should_close = False
            
            record = ParsedFile(
                filename=file.filename,
                extracted_text=sanitized_text[:400],
                detected_shapes=image_count,
                summary=f"Processed with RAG agent. {agent_result['message']}",
                full_text_path=text_file_path,
                user_id=user_id  # Link to user
            )
            db.add(record)
            db.commit()
            db.refresh(record)

            # Save image metadata
            for image_id, image_path, page_num, ocr_text in image_metadata:
                img_meta = ImageMeta(
                    file_id=record.id,
                    image_path=image_path,
                    page_number=page_num,
                    ocr_text=ocr_text
                )
                db.add(img_meta)

            # Generate view_id and save to database
            view_id = str(uuid.uuid4())
            record.view_id = view_id
            db.commit()
        except Exception as e:
            print(f"❌ Database error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        finally:
            # Ensure session is always closed
            if should_close and db_session is None:
                try:
                    db.close()
                except Exception:
                    pass

        # Build quick lookup of context for images within this request is not tracked separately here,
        # so pass empty context for now; summarized meanings rely on OCR wording for agent runs
        
        # Parse and save features for approval
        try:
            extracted_response = requirements_result.get("response", "")
            features_count = parse_and_save_features(extracted_response, user_id, record.id, db)
            print(f"📋 Saved {features_count} features for user approval")
        except Exception as e:
            print(f"⚠️ Failed to save features: {e}")
        
        # Save to REQUIREMENTS_VIEWS for backward compatibility
        REQUIREMENTS_VIEWS[view_id] = {
                    "filename": file.filename,
                    "summary": f"Extracted {len(text_output.split())} words and {image_count} image(s)",
                    "response": requirements_result.get("response", ""),
                    "images": [
                        {"image_id": iid, "path": path, "page": pg, "ocr": (ocr or "").strip(),
                 "summary": (_vlm_summarize(path, (ocr or "")) or _summarize_image_ocr(ocr or "", context=(ocr or "")))}
                        for (iid, path, pg, ocr) in image_metadata
                    ]
        }
        save_views()  # Save to persistent storage
        
        return {
            "filename": file.filename,
            "extraction_summary": f"Extracted {len(text_output.split())} words and {image_count} image(s)",
            "agent_processing": agent_result,
            "requirements_extraction": requirements_result,
            "view_id": view_id,
            "full_text_file": text_file_path,
            "images_detected": image_count,
            "image_metadata_saved": len(image_metadata)
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("Analyze_with_agent error:", tb)
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e) or 'See server logs'}")


@app.post("/extract_requirements")
async def extract_requirements(query: str = None):
    """Extract requirements from already processed documents."""
    try:
        agent = get_agent()
        result = agent.extract_requirements(query)
        
        if result["status"] != "success":
            raise HTTPException(status_code=500, detail=result["message"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting requirements: {str(e)}")


@app.get("/get_document_summary")
async def get_document_summary():
    """Get a summary of all processed documents."""
    try:
        agent = get_agent()
        result = agent.get_document_summary()
        
        if result["status"] != "success":
            raise HTTPException(status_code=500, detail=result["message"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating summary: {str(e)}")


@app.post("/search_requirements")
async def search_requirements(requirement_type: str):
    """Search for specific types of requirements."""
    try:
        agent = get_agent()
        result = agent.search_specific_requirements(requirement_type)
        
        if result["status"] != "success":
            raise HTTPException(status_code=500, detail=result["message"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching requirements: {str(e)}")


@app.get("/agent_status")
async def get_agent_status():
    """Get the status of the RAG agent."""
    try:
        agent = get_agent()
        return {
            "status": "active",
            "model": getattr(agent, "model_name", "heuristic"),
            "vectorstore_initialized": agent.vectorstore is not None,
            "collection_name": agent.collection_name,
            "tools_available": len(agent.tools)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/agent_status_page")
async def agent_status_page():
    return {"message": "Use GET /agent_status for JSON status."}


# =============================
# Formatted Requirements Viewer
# =============================

@app.get("/view_requirements/{view_id}", response_class=HTMLResponse)
async def view_requirements(view_id: str):
    # Reload views in case file was updated
    load_views()
    data = REQUIREMENTS_VIEWS.get(view_id)
    if not data:
        raise HTTPException(status_code=404, detail="View not found or expired")

    def esc(s: str) -> str:
        return html.escape(s or "")

    filename = esc(data.get("filename", ""))
    summary = esc(data.get("summary", ""))
    response_text = data.get("response", "")
    images = data.get("images") or []
    
    # Convert to HTML: create collapsible dropdown sections
    import re
    sections = []
    current_section = None
    current_items = []
    lines = response_text.split("\n")
    
    for line in lines:
        line = esc(line.strip())
        if not line:
            continue
        
        # Check if this is a section heading (ends with colon and no bullet)
        if line.endswith(":") and not line.startswith("-"):
            # Save previous section
            if current_section and current_items:
                sections.append((current_section, current_items))
            
            # Start new section
            current_section = line.rstrip(":")
            current_items = []
        # Check if this is a bullet point
        elif line.startswith("- ") and current_section:
            requirement_text = line[2:].strip()
            if requirement_text.lower() != "(none)":
                current_items.append(requirement_text)
        # Regular line (add to current section if exists)
        elif current_section and line.lower() != "(none)":
            current_items.append(line)
    
    # Save last section
    if current_section and current_items:
        sections.append((current_section, current_items))
    
    # Build collapsible HTML
    safe_html = ""
    section_counter = 0
    for section_name, items in sections:
        section_id = f"section_{section_counter}"
        section_counter += 1
        item_count = len(items)
        
        safe_html += f'''
        <div class="dropdown-section">
            <button class="dropdown-toggle" data-section-id="{section_id}">
                <span class="dropdown-icon" id="icon_{section_id}">▼</span>
                <span class="dropdown-title">{section_name}</span>
                <span class="dropdown-count">({item_count})</span>
            </button>
            <div class="dropdown-content" id="{section_id}" style="display: none;">
                <ul class="simple-list">
        '''
        
        for item in items:
            safe_html += f'<li class="simple-item">{item}</li>'
        
        safe_html += '''
                </ul>
            </div>
        </div>
        '''
    
    safe = safe_html if safe_html else '<div class="no-content">No requirements found.</div>'
    
    # Build images section HTML
    items = []
    for img in images:
        image_id = esc(str(img.get("image_id", "")))
        page = esc(str(img.get("page", "?")))
        path = esc((img.get("path", "") or "").replace("\\", "/"))
        ocr = esc((img.get("ocr") or "").strip()[:1500])
        raw_summary = (img.get("summary") or "").strip()
        summary = esc(raw_summary)
        if summary:
            # Format summary with line breaks
            summary_html = "<br>".join(esc(line) for line in summary.splitlines())
        else:
            summary_html = ""
        # Build a brief interpretation sentence from the first bullet/line
        interp_src = raw_summary.splitlines()
        first_line = next((ln for ln in interp_src if ln.strip()), "")
        if first_line.startswith(("- ", "• ")):
            first_line = first_line[2:].strip()
        interpretation = f"This image indicates/defines: {first_line}" if first_line else ""
        interpretation_html = esc(interpretation)
        
        items.append(f"""
            <div class="image-card">
                <div class="image-header">
                    <div class="image-icon">
                        <i class="fas fa-image"></i>
                    </div>
                    <div class="image-info">
                        <div class="image-title">{image_id}</div>
                        <div class="image-meta">Page {page}</div>
                    </div>
                    <a href="/{path}" target="_blank" class="image-link">
                        <i class="fas fa-external-link-alt"></i>
                        View Image
                    </a>
                </div>
                
                <div class="image-content">
                    <div class="content-section">
                        <div class="section-label">
                            <i class="fas fa-eye"></i>
                            OCR Text
                        </div>
                        <div class="ocr-text">{ocr}</div>
                    </div>
                    
                    <div class="content-section">
                        <div class="section-label">
                            <i class="fas fa-brain"></i>
                            AI Summary
                        </div>
                        <div class="summary-text">{summary_html}</div>
                    </div>
                    
                    <div class="content-section">
                        <div class="section-label">
                            <i class="fas fa-lightbulb"></i>
                            Interpretation
                        </div>
                        <div class="interpretation-text">{interpretation_html}</div>
                    </div>
                </div>
            </div>
        """)
    
    images_html = "".join(items)

    html_doc = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Requirements Analysis – {filename}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {{
                --primary-color: #2563eb;
                --primary-dark: #1d4ed8;
                --secondary-color: #64748b;
                --success-color: #10b981;
                --warning-color: #f59e0b;
                --error-color: #ef4444;
                --background: #f8fafc;
                --surface: #ffffff;
                --surface-elevated: #ffffff;
                --text-primary: #1e293b;
                --text-secondary: #64748b;
                --text-muted: #94a3b8;
                --border: #e2e8f0;
                --border-light: #f1f5f9;
                --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
                --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                --radius: 12px;
                --radius-sm: 8px;
                --radius-lg: 16px;
            }}

            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: 'Georgia', 'Times New Roman', serif;
                background: #f5f5f5;
                min-height: 100vh;
                color: #333;
                line-height: 1.6;
            }}

            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }}

            .header {{
                text-align: center;
                margin-bottom: 2rem;
                padding: 2rem 0;
                background: #fff;
                border-bottom: 3px solid #2563eb;
            }}

            .header h1 {{
                font-size: 2rem;
                font-weight: 600;
                color: #1e293b;
                margin-bottom: 0.5rem;
            }}

            .header p {{
                font-size: 1rem;
                color: #64748b;
            }}

            .back-btn {{
                display: inline-block;
                background: #2563eb;
                color: white;
                text-decoration: none;
                padding: 0.75rem 1.5rem;
                border-radius: 4px;
                font-weight: 500;
                margin-bottom: 2rem;
                border: none;
                cursor: pointer;
            }}

            .back-btn:hover {{
                background: #1d4ed8;
            }}

            .card {{
                background: #ffffff;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 1.5rem;
                margin-bottom: 2rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}

            .card-header {{
                display: flex;
                align-items: center;
                margin-bottom: 1rem;
                padding-bottom: 1rem;
                border-bottom: 2px solid #e2e8f0;
            }}

            .card-icon {{
                width: 40px;
                height: 40px;
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 1rem;
                font-size: 1.2rem;
                color: white;
                background: #2563eb;
            }}

            .card-title {{
                font-size: 1.25rem;
                font-weight: 600;
                color: #1e293b;
            }}

            .card-subtitle {{
                font-size: 0.9rem;
                color: #64748b;
                margin-top: 0.25rem;
            }}

            .requirements-content {{
                background: #ffffff;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 0;
            }}
            
            /* Dropdown Sections */
            .dropdown-section {{
                border-bottom: 1px solid #e2e8f0;
            }}
            
            .dropdown-section:last-child {{
                border-bottom: none;
            }}
            
            .dropdown-toggle {{
                width: 100%;
                text-align: left;
                background: #f8fafc;
                border: none;
                padding: 1rem 1.5rem;
                cursor: pointer;
                font-size: 1.1rem;
                font-weight: 600;
                color: #1e293b;
                display: flex;
                align-items: center;
                gap: 0.75rem;
                transition: background 0.2s;
            }}
            
            .dropdown-toggle:hover {{
                background: #f1f5f9;
            }}
            
            .dropdown-icon {{
                font-size: 0.75rem;
                transition: transform 0.3s;
                color: #2563eb;
                transform: rotate(-90deg);
            }}
            
            .dropdown-icon.rotated {{
                transform: rotate(0deg);
            }}
            
            .dropdown-title {{
                flex: 1;
            }}
            
            .dropdown-count {{
                color: #64748b;
                font-weight: 400;
                font-size: 0.9rem;
            }}
            
            .dropdown-content {{
                padding: 1rem 1.5rem;
                background: #ffffff;
                border-top: 1px solid #e2e8f0;
            }}
            
            .simple-list {{
                list-style: none;
                padding: 0;
                margin: 0;
            }}
            
            .simple-item {{
                padding: 0.75rem 0;
                border-bottom: 1px solid #f1f5f9;
                color: #333;
                line-height: 1.6;
            }}
            
            .simple-item:last-child {{
                border-bottom: none;
            }}
            
            .simple-item::before {{
                content: "•";
                color: #2563eb;
                font-weight: bold;
                display: inline-block;
                width: 1em;
                margin-right: 0.5rem;
            }}
            
            .no-content {{
                padding: 2rem;
                text-align: center;
                color: #64748b;
            }}

            .image-card {{
                background: #ffffff;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}

            .image-header {{
                display: flex;
                align-items: center;
                margin-bottom: 1rem;
            }}

            .image-icon {{
                width: 40px;
                height: 40px;
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 1rem;
                font-size: 1.2rem;
                color: white;
                background: #2563eb;
            }}

            .image-info {{
                flex: 1;
            }}

            .image-title {{
                font-weight: 600;
                color: var(--text-primary);
                font-size: 1.1rem;
            }}

            .image-meta {{
                font-size: 0.875rem;
                color: var(--text-secondary);
                margin-top: 0.25rem;
            }}

            .image-link {{
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background: var(--primary-color);
                color: white;
                text-decoration: none;
                padding: 0.5rem 1rem;
                border-radius: var(--radius-sm);
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.3s ease;
            }}

            .image-link:hover {{
                background: var(--primary-dark);
                transform: translateY(-1px);
            }}

            .image-content {{
                display: grid;
                gap: 1rem;
            }}

            .content-section {{
                background: #f8fafc;
                border-radius: 4px;
                padding: 1rem;
                border: 1px solid #e2e8f0;
                margin-bottom: 1rem;
            }}
            
            .content-section:last-child {{
                margin-bottom: 0;
            }}

            .section-label {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-weight: 600;
                color: var(--text-primary);
                margin-bottom: 0.75rem;
                font-size: 0.9rem;
            }}

            .section-label i {{
                color: var(--primary-color);
            }}

            .ocr-text {{
                background: #f8fafc;
                color: #333;
                padding: 1rem;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 0.9rem;
                line-height: 1.6;
                max-height: 200px;
                overflow-y: auto;
                border: 1px solid #e2e8f0;
            }}

            .summary-text {{
                color: var(--text-primary);
                line-height: 1.6;
            }}

            .interpretation-text {{
                color: var(--text-secondary);
                font-style: italic;
                line-height: 1.6;
            }}

            @keyframes fadeInDown {{
                from {{
                    opacity: 0;
                    transform: translateY(-30px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}

            @keyframes fadeInUp {{
                from {{
                    opacity: 0;
                    transform: translateY(30px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}

            @media (max-width: 768px) {{
                .container {{
                    padding: 1rem;
                }}
                
                .header h1 {{
                    font-size: 1.5rem;
                }}
                
                .image-header {{
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 1rem;
                }}
                
                .image-link {{
                    align-self: flex-end;
                }}
            }}
        </style>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                // Add click handlers to all dropdown toggles
                document.querySelectorAll('.dropdown-toggle').forEach(function(button) {{
                    button.addEventListener('click', function() {{
                        const sectionId = this.getAttribute('data-section-id');
                        const content = document.getElementById(sectionId);
                        const icon = document.getElementById('icon_' + sectionId);
                        
                        if (content && icon) {{
                            if (content.style.display === 'none') {{
                                content.style.display = 'block';
                                icon.classList.add('rotated');
                            }} else {{
                                content.style.display = 'none';
                                icon.classList.remove('rotated');
                            }}
                        }}
                    }});
                }});
            }});
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1><i class="fas fa-file-alt"></i> Requirements Analysis</h1>
                <p>Detailed extraction results for {filename}</p>
            </div>

            <a href="/" class="back-btn">
                <i class="fas fa-arrow-left"></i>
                Back to FlowMind
            </a>

            <div class="card">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-file-alt"></i>
                    </div>
                    <div>
                        <div class="card-title">Document Analysis</div>
                        <div class="card-subtitle">{summary}</div>
                    </div>
                </div>
                
                <div class="requirements-content">{safe}</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-images"></i>
                    </div>
                    <div>
                        <div class="card-title">Image Analysis</div>
                        <div class="card-subtitle">OCR and AI-powered image insights</div>
                    </div>
                </div>
                
                <div class="image-content">
                    {images_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_doc)
