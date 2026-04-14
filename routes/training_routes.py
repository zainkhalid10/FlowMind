"""Model training and learning status routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from database import SessionLocal, User
from auth import get_current_user, get_db
from fastapi.responses import HTMLResponse, FileResponse
import os
import asyncio
import time
import json
from pathlib import Path

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"


def _decode_user_from_token(token: Optional[str], credentials: Optional[HTTPAuthorizationCredentials], db: Session) -> User:
    """Authenticate user from query token or Authorization header."""
    from auth import SECRET_KEY, ALGORITHM
    from jose import JWTError, jwt

    auth_token = token or (credentials.credentials if credentials else None)
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
        user_id = int(user_id_str)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.is_active == 0:
        raise credentials_exception
    return user


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _count_scored_patterns(feedback_pattern_scores: dict) -> tuple[int, int]:
    """Count positively and negatively scored learned patterns across all groups."""
    promoted = 0
    demoted = 0

    if not isinstance(feedback_pattern_scores, dict):
        return promoted, demoted

    for group_data in feedback_pattern_scores.values():
        if not isinstance(group_data, dict):
            continue

        for bucket_name in ("keywords", "phrases", "patterns"):
            bucket = group_data.get(bucket_name, {})
            if not isinstance(bucket, dict):
                continue

            for stats in bucket.values():
                if not isinstance(stats, dict):
                    continue

                try:
                    score = float(stats.get("score", 0.0))
                except (TypeError, ValueError):
                    continue

                if score > 0:
                    promoted += 1
                elif score < 0:
                    demoted += 1

    return promoted, demoted


@router.get("/api/learning-maintenance-status")
async def get_learning_maintenance_status(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    """Return latest automated learning maintenance status for manager dashboards."""
    current_user = _decode_user_from_token(token, credentials, db)

    state_file = REPORTS_DIR / "learning_maintenance_state.json"
    state = _read_json_file(state_file)

    run_file = state.get("last_run_file")
    run_data = {}
    if run_file:
        run_path = Path(run_file)
        if not run_path.is_absolute():
            run_path = BASE_DIR / run_path
        run_data = _read_json_file(run_path)

    backfill = run_data.get("backfill", {}) if isinstance(run_data, dict) else {}
    actions = backfill.get("actions", {}) if isinstance(backfill, dict) else {}

    # Cumulative learning stats come from per-user learning state.
    learning_state_path = REPORTS_DIR / f"learning_state_user_{current_user.id}.json"
    learning_state = _read_json_file(learning_state_path)
    extraction_stats = learning_state.get("extraction_stats", {}) if isinstance(learning_state, dict) else {}
    action_totals = extraction_stats.get("feedback_action_counts", {}) if isinstance(extraction_stats, dict) else {}
    promoted_total, demoted_total = _count_scored_patterns(learning_state.get("feedback_pattern_scores", {}))

    return {
        "has_state": bool(state),
        "state_file": str(state_file),
        "last_run_utc": state.get("last_run_utc"),
        "last_run_file": state.get("last_run_file"),
        "last_report_file": state.get("last_report_file"),
        "last_current_baseline_file": state.get("last_current_baseline_file"),
        "last_feedback_id": state.get("last_feedback_id"),
        "processed_feedback_rows": backfill.get("processed_feedback_rows", 0),
        "promoted_patterns": backfill.get("promoted_patterns", 0),
        "demoted_patterns": backfill.get("demoted_patterns", 0),
        "updated_patterns": backfill.get("updated_patterns", 0),
        "actions": {
            "approve": actions.get("approve", 0),
            "reject": actions.get("reject", 0),
            "request_modification": actions.get("request_modification", 0),
        },
        "processed_feedback_total": extraction_stats.get("feedback_events", 0),
        "promoted_patterns_total": promoted_total,
        "demoted_patterns_total": demoted_total,
        "action_totals": {
            "approve": action_totals.get("approve", 0),
            "reject": action_totals.get("reject", 0),
            "request_modification": action_totals.get("request_modification", 0),
        },
        "n_feedback": run_data.get("n_feedback"),
        "backfill_limit": run_data.get("backfill_limit"),
    }


@router.get("/api/learning-maintenance-report/latest")
async def get_latest_learning_maintenance_report(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    """Download latest self-learning report file for authenticated users."""
    _ = _decode_user_from_token(token, credentials, db)
    state = _read_json_file(REPORTS_DIR / "learning_maintenance_state.json")
    report_file = state.get("last_report_file")
    if not report_file:
        raise HTTPException(status_code=404, detail="No maintenance report found")

    report_path = Path(report_file)
    if not report_path.is_absolute():
        report_path = BASE_DIR / report_path
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Maintenance report file not found")

    return FileResponse(path=str(report_path), media_type="application/json", filename=report_path.name)


@router.get("/training", response_class=HTMLResponse)
async def training_page():
    """Model training dashboard page."""
    # Return a simple training page
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Training - FlowMind</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .card {
            background: rgba(15, 23, 42, 0.86);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 18px 40px rgba(2, 6, 23, 0.42);
            border: 1px solid rgba(96, 165, 250, 0.18);
            backdrop-filter: blur(10px);
            color: #e2e8f0;
        }
        .card h1, .card h3, .card h5 {
            color: #f8fafc;
        }
        .stat-card {
            text-align: center;
            padding: 20px;
            background: rgba(2, 6, 23, 0.42);
            border-radius: 10px;
            margin: 10px;
            border: 1px solid rgba(96, 165, 250, 0.18);
        }
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 50%, #8b5cf6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stat-label {
            color: #94a3b8;
            margin-top: 10px;
        }
        .keyword-list {
            max-height: 400px;
            overflow-y: auto;
            background: rgba(2, 6, 23, 0.35);
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
        }
        .keyword-item {
            padding: 8px 12px;
            margin: 5px;
            background: rgba(15, 23, 42, 0.9);
            border-radius: 6px;
            display: inline-block;
            border: 1px solid rgba(96, 165, 250, 0.18);
            color: #e2e8f0;
        }
        .btn-primary {
            background: linear-gradient(135deg, #0891b2 0%, #2563eb 50%, #7c3aed 100%);
            border: none;
        }
        .text-primary {
            color: #06b6d4 !important;
        }
        .text-muted {
            color: #94a3b8 !important;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h1><i class="fas fa-graduation-cap text-primary"></i> Model Training Dashboard</h1>
                <div>
                    <a href="/extract" class="btn btn-primary me-2"><i class="fas fa-upload"></i> Extract</a>
                    <a href="/dashboard" class="btn btn-secondary me-2"><i class="fas fa-tachometer-alt"></i> Dashboard</a>
                    <a href="/" class="btn btn-outline-secondary"><i class="fas fa-home"></i> Home</a>
                </div>
            </div>
            
            <div id="loading" class="text-center py-5">
                <i class="fas fa-spinner fa-spin fa-3x text-primary"></i>
                <p class="mt-3">Loading training data...</p>
            </div>
            
            <div id="content" style="display: none;">
                <div class="row">
                    <div class="col-md-3">
                        <div class="stat-card">
                            <div class="stat-number" id="total-patterns">0</div>
                            <div class="stat-label">Total Patterns</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stat-card">
                            <div class="stat-number" id="total-keywords">0</div>
                            <div class="stat-label">Total Keywords</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stat-card">
                            <div class="stat-number" id="total-docs">0</div>
                            <div class="stat-label">Documents Processed</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stat-card">
                            <div class="stat-number" id="iterations">0</div>
                            <div class="stat-label">Learning Iterations</div>
                        </div>
                    </div>
                </div>
                
                <div class="card mt-4">
                    <h3><i class="fas fa-key"></i> Learned Keywords by Category</h3>
                    <div id="keywords-display"></div>
                </div>
                
                <div class="card mt-4">
                    <h3><i class="fas fa-project-diagram"></i> Learned Patterns</h3>
                    <div id="patterns-display"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        async function loadTrainingData() {
            try {
                const token = localStorage.getItem('access_token');
                if (!token) {
                    window.location.href = '/';
                    return;
                }
                
                const response = await fetch('/api/training-status', {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    displayTrainingData(data);
                } else {
                    document.getElementById('loading').innerHTML = 
                        '<div class="alert alert-danger">Failed to load training data</div>';
                }
            } catch (error) {
                console.error('Error loading training data:', error);
                document.getElementById('loading').innerHTML = 
                    '<div class="alert alert-danger">Error loading training data</div>';
            }
        }
        
        function displayTrainingData(data) {
            document.getElementById('total-patterns').textContent = data.total_learned_patterns || 0;
            document.getElementById('total-keywords').textContent = data.total_keywords || 0;
            document.getElementById('total-docs').textContent = data.total_documents_processed || 0;
            document.getElementById('iterations').textContent = data.learning_iterations || 0;
            
            // Display keywords by category
            const keywordsHtml = Object.entries(data.learned_keywords || {}).map(([category, keywords]) => {
                const keywordList = Array.isArray(keywords) ? keywords : Object.keys(keywords || {});
                return `
                    <div class="mb-4">
                        <h5>${category.charAt(0).toUpperCase() + category.slice(1)} (${keywordList.length})</h5>
                        <div class="keyword-list">
                            ${keywordList.slice(0, 100).map(k => 
                                `<span class="keyword-item">${k}</span>`
                            ).join('')}
                            ${keywordList.length > 100 ? `<p class="text-muted mt-2">... and ${keywordList.length - 100} more</p>` : ''}
                        </div>
                    </div>
                `;
            }).join('');
            document.getElementById('keywords-display').innerHTML = keywordsHtml || '<p class="text-muted">No keywords learned yet</p>';
            
            // Display patterns
            const patternsHtml = Object.entries(data.learned_patterns || {}).map(([category, patterns]) => {
                const patternList = Array.isArray(patterns) ? patterns : Object.keys(patterns || {});
                return `
                    <div class="mb-4">
                        <h5>${category.charAt(0).toUpperCase() + category.slice(1)} (${patternList.length})</h5>
                        <div class="keyword-list">
                            ${patternList.slice(0, 50).map(p => 
                                `<span class="keyword-item">${p}</span>`
                            ).join('')}
                            ${patternList.length > 50 ? `<p class="text-muted mt-2">... and ${patternList.length - 50} more</p>` : ''}
                        </div>
                    </div>
                `;
            }).join('');
            document.getElementById('patterns-display').innerHTML = patternsHtml || '<p class="text-muted">No patterns learned yet</p>';
            
            document.getElementById('loading').style.display = 'none';
            document.getElementById('content').style.display = 'block';
        }
        
        loadTrainingData();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


# Simple in-memory cache for training status (5 second TTL)
_training_status_cache = {}
_cache_ttl = 10  # seconds
_training_status_warmup = set()


def _default_training_status(message: str = "Training status is warming up"):
    return {
        "status": "warming_up",
        "message": message,
        "total_learned_patterns": 0,
        "total_keywords": 0,
        "total_phrases": 0,
        "total_patterns": 0,
        "total_learned_items": 0,
        "keywords_by_category": {},
        "patterns_by_category": {},
        "total_documents_processed": 0,
        "learning_iterations": 0,
        "learning_enabled": True,
        "learned_keywords": {},
        "learned_patterns": {},
        "learned_phrases": {},
        "extraction_stats": {},
        "last_learning_session": {}
    }


def _extract_training_result_from_agent(agent):
    """Build JSON response payload from an initialized agent."""
    stats = agent.extraction_stats if hasattr(agent, 'extraction_stats') else {}
    learned_patterns = agent.learned_patterns if hasattr(agent, 'learned_patterns') else {}
    print(f"📊 Stats: {len(learned_patterns)} pattern categories found")
    print(f"📊 Learned patterns type: {type(learned_patterns)}, keys: {list(learned_patterns.keys()) if isinstance(learned_patterns, dict) else 'N/A'}")

    total_patterns = 0
    total_keywords = 0
    total_phrases = 0
    keywords_by_category = {}
    patterns_by_category = {}
    phrases_by_category = {}

    for category, data in learned_patterns.items():
        if isinstance(data, dict):
            keywords = data.get('keywords', set())
            patterns = data.get('patterns', set())
            phrases = data.get('phrases', set())

            keywords_list = list(keywords) if isinstance(keywords, set) else (keywords if isinstance(keywords, list) else [])
            patterns_list = list(patterns) if isinstance(patterns, set) else (patterns if isinstance(patterns, list) else [])
            phrases_list = list(phrases) if isinstance(phrases, set) else (phrases if isinstance(phrases, list) else [])

            total_keywords += len(keywords_list)
            total_patterns += len(patterns_list)
            total_phrases += len(phrases_list)

            keywords_by_category[category] = keywords_list
            patterns_by_category[category] = patterns_list
            phrases_by_category[category] = phrases_list

    total_learned_items = total_keywords + total_patterns + total_phrases

    print(f"📊 Counted - Keywords: {total_keywords}, Patterns: {total_patterns}, Phrases: {total_phrases}, Total: {total_learned_items}")

    result = {
        "total_learned_patterns": total_learned_items,
        "total_patterns": total_patterns,
        "total_keywords": total_keywords,
        "total_phrases": total_phrases,
        "total_learned_items": total_learned_items,
        "total_documents_processed": stats.get("total_documents", 0),
        "learning_iterations": stats.get("learning_iterations", 0),
        "learning_enabled": getattr(agent, "enable_self_learning", False),
        "learned_keywords": keywords_by_category,
        "learned_patterns": patterns_by_category,
        "learned_phrases": phrases_by_category,
        "extraction_stats": stats,
        "last_learning_session": stats.get("last_learning_session", {})
    }

    print(f"📊 Returning result with total_learned_patterns: {result['total_learned_patterns']}, total_learned_items: {result['total_learned_items']}")
    return result


async def _warm_training_status_cache(cache_key: str, user_id_for_agent: int):
    """Warm agent-based training status in background so requests stay responsive."""
    try:
        from rag_agent import get_agent
        from utils.async_helpers import run_in_thread

        print(f"🔥 Warming training status in background for user_id={user_id_for_agent}")
        agent = await run_in_thread(get_agent, user_id=user_id_for_agent, timeout=30.0)
        result = _extract_training_result_from_agent(agent)
        _training_status_cache[cache_key] = (result, time.time())
        print(f"✅ Training status cache warmed for user_id={user_id_for_agent}")
    except Exception as e:
        print(f"⚠️ Background warmup failed for user_id={user_id_for_agent}: {e}")
    finally:
        _training_status_warmup.discard(cache_key)

@router.get("/api/training-status")
async def get_training_status(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Get model training status and learned patterns. Accepts token via Authorization header or query parameter.
    Results are cached for 5 seconds to reduce load."""
    import time
    user = _decode_user_from_token(token, credentials, db)
    user_id = user.id
    
    # Check cache first
    cache_key = f"user_{user_id}"
    current_time = time.time()
    if cache_key in _training_status_cache:
        cached_data, cache_time = _training_status_cache[cache_key]
        if current_time - cache_time < _cache_ttl:
            print(f"📊 Returning cached training status for user_id={user_id}")
            return cached_data
    
    # Extract user_id before slow operations to avoid holding DB session
    user_id_for_agent = user_id

    # On cache miss, avoid blocking the request path. Warm in background and return quickly.
    if cache_key not in _training_status_warmup:
        _training_status_warmup.add(cache_key)
        asyncio.create_task(_warm_training_status_cache(cache_key, user_id_for_agent))

    return _default_training_status("Training data is initializing in background. Please refresh shortly.")
    
    # Unreachable fallback kept for safety in case flow changes.
    return _default_training_status()

