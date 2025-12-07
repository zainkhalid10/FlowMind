"""Model training and learning status routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from database import SessionLocal, User
from auth import get_current_user, get_db
from fastapi.responses import HTMLResponse
import os

router = APIRouter()


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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .card {
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .stat-card {
            text-align: center;
            padding: 20px;
            background: #f8fafc;
            border-radius: 10px;
            margin: 10px;
        }
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            color: #667eea;
        }
        .stat-label {
            color: #64748b;
            margin-top: 10px;
        }
        .keyword-list {
            max-height: 400px;
            overflow-y: auto;
            background: #f8fafc;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
        }
        .keyword-item {
            padding: 8px 12px;
            margin: 5px;
            background: white;
            border-radius: 6px;
            display: inline-block;
            border: 1px solid #e2e8f0;
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
                    window.location.href = '/login';
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
_cache_ttl = 5  # seconds

@router.get("/api/training-status")
async def get_training_status(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Get model training status and learned patterns. Accepts token via Authorization header or query parameter.
    Results are cached for 5 seconds to reduce load."""
    from auth import SECRET_KEY, ALGORITHM
    from jose import JWTError, jwt
    import time
    
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
    if user is None or user.is_active == 0:
        raise credentials_exception
    
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
    
    try:
        # Import here to avoid issues
        from rag_agent import get_agent
        from utils.async_helpers import run_in_thread
        import asyncio
        
        print(f"📊 Getting training status for user_id={user_id_for_agent}...")
        
        # Get user-specific agent to show user's learning data
        # Use async helper with timeout to avoid blocking
        # Note: DB session will be closed by FastAPI dependency system after this function returns
        try:
            agent = await run_in_thread(get_agent, user_id=user_id_for_agent, timeout=30.0)
            print(f"✅ Agent retrieved for user_id={user_id}")
        except asyncio.TimeoutError:
            # Return cached or default data if agent initialization times out
            print(f"⚠️ Agent initialization timed out for user_id={user_id}, returning cached/default data")
            return {
                "status": "partial",
                "message": "Training status partially loaded (agent initialization timed out)",
                "total_learned_patterns": 0,
                "total_keywords": 0,
                "total_phrases": 0,
                "total_patterns": 0,
                "keywords_by_category": {},
                "patterns_by_category": {},
                "total_documents_processed": 0,
                "learning_enabled": True
            }
        
        # Get learning statistics
        stats = agent.extraction_stats if hasattr(agent, 'extraction_stats') else {}
        learned_patterns = agent.learned_patterns if hasattr(agent, 'learned_patterns') else {}
        print(f"📊 Stats: {len(learned_patterns)} pattern categories found")
        
        # Count total patterns and keywords
        total_patterns = 0
        total_keywords = 0
        keywords_by_category = {}
        patterns_by_category = {}
        
        for category, data in learned_patterns.items():
            if isinstance(data, dict):
                keywords = data.get('keywords', set())
                patterns = data.get('patterns', set())
                
                keywords_list = list(keywords) if isinstance(keywords, set) else keywords
                patterns_list = list(patterns) if isinstance(patterns, set) else patterns
                
                total_keywords += len(keywords_list)
                total_patterns += len(patterns_list)
                
                keywords_by_category[category] = keywords_list
                patterns_by_category[category] = patterns_list
        
        result = {
            "total_learned_patterns": total_patterns,
            "total_keywords": total_keywords,
            "total_documents_processed": stats.get("total_documents", 0),
            "learning_iterations": stats.get("learning_iterations", 0),
            "learned_keywords": keywords_by_category,
            "learned_patterns": patterns_by_category,
            "extraction_stats": stats
        }
        
        # Cache the result
        _training_status_cache[cache_key] = (result, current_time)
        
        return result
    except Exception as e:
        import traceback
        print(f"Error getting training status: {traceback.format_exc()}")
        # FastAPI will automatically close DB session via dependency system
        return {
            "total_learned_patterns": 0,
            "total_keywords": 0,
            "total_documents_processed": 0,
            "learning_iterations": 0,
            "learned_keywords": {},
            "learned_patterns": {},
            "extraction_stats": {}
        }

