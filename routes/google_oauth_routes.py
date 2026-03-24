"""Google OAuth routes for FlowMind"""
import os
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime
from urllib.parse import urlencode
import json
import google.auth.transport.requests
from google.oauth2 import id_token
import requests

from database import User, Team, ReviewAssignment
from auth import create_access_token, get_db, get_password_hash

router = APIRouter()


def _oauth_error_page(title: str, message: str, hint: str = "") -> HTMLResponse:
    """Render a user-friendly OAuth error page for browser flows."""
    hint_block = f"<p style='color:#94a3b8;font-size:0.95rem;margin-top:8px'>{hint}</p>" if hint else ""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{title}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                background: radial-gradient(circle at 85% 5%, rgba(14, 165, 233, 0.25), transparent 35%), #020617;
                color: #e2e8f0;
                padding: 20px;
            }}
            .card {{
                width: min(560px, 100%);
                border: 1px solid rgba(148, 163, 184, 0.24);
                border-radius: 14px;
                background: rgba(15, 23, 42, 0.9);
                padding: 24px;
                box-shadow: 0 24px 60px rgba(2, 6, 23, 0.45);
            }}
            h1 {{ margin: 0 0 10px; font-size: 1.2rem; }}
            p {{ margin: 0; line-height: 1.55; color: #cbd5e1; }}
            a {{
                display: inline-block;
                margin-top: 16px;
                text-decoration: none;
                color: #020617;
                background: #38bdf8;
                padding: 10px 14px;
                border-radius: 10px;
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>{title}</h1>
            <p>{message}</p>
            {hint_block}
            <a href="/">Back to Sign In</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@router.get("/auth/google/init")
async def google_oauth_init(role: str = Query("manager", pattern="^(manager|client)$"), redirect_tab: str = Query("login")):
    """
    Initiates Google OAuth flow by redirecting to Google's authorization endpoint.
    
    Args:
        role: User role for signup. Public signup uses manager.
        redirect_tab: Whether user is on 'login' or 'signup' tab (for post-auth redirect logic).
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return _oauth_error_page(
            "Google Sign-In Not Configured",
            "Google OAuth is available in the app, but the server is missing Google client credentials.",
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env, then restart FlowMind."
        )
    
    # Build OAuth URL with parameters
    scope = "openid email profile"
    auth_params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        # Store role and tab in state for retrieval after callback
        "state": f"{role}|{redirect_tab}"
    }
    
    # Build query string safely (encodes scope and redirect URI correctly)
    query_string = urlencode(auth_params)
    redirect_url = f"{GOOGLE_AUTH_URL}?{query_string}"
    
    return RedirectResponse(url=redirect_url)


@router.get("/auth/google/callback", response_class=HTMLResponse)
async def google_oauth_callback(code: str = Query(...), state: str = Query("manager|login"), error: str = Query(None), db: Session = Depends(get_db)):
    """
    Handles Google OAuth callback. Exchanges authorization code for tokens and creates/logs in user.
    
    Args:
        code: Authorization code from Google
        state: State parameter containing role|redirect_tab
        error: Error parameter if authorization failed
    """
    if error:
        return _oauth_error_page(
            "Google Sign-In Cancelled",
            f"Google returned an authentication error: {error}.",
            "Please try again, or use email/password sign in."
        )
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return _oauth_error_page(
            "Google Sign-In Not Configured",
            "Google OAuth credentials are missing on the server.",
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env and restart FlowMind."
        )
    
    try:
        # Parse state to get role and redirect tab
        state_parts = state.split("|")
        role = state_parts[0] if len(state_parts) > 0 else "manager"
        redirect_tab = state_parts[1] if len(state_parts) > 1 else "login"
        
        # Validate role
        if role not in ("manager", "client"):
            role = "manager"
        
        # Exchange authorization code for access token
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT_URI
        }
        
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        token_response.raise_for_status()
        tokens = token_response.json()
        
        # Verify and decode the ID token
        id_token_str = tokens.get("id_token")
        if not id_token_str:
            raise ValueError("No id_token in response")
        
        # Verify the ID token
        try:
            id_info = id_token.verify_oauth2_token(
                id_token_str,
                google.auth.transport.requests.Request(),
                GOOGLE_CLIENT_ID
            )
        except ValueError:
            # If verification fails, try fetching user info with access token instead
            access_token = tokens.get("access_token")
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
            userinfo_response.raise_for_status()
            id_info = userinfo_response.json()
        
        # Extract user information from Google response
        google_id = id_info.get("sub")
        email = id_info.get("email")
        picture_url = id_info.get("picture")
        
        if not google_id or not email:
            raise ValueError("Missing required fields from Google OAuth response")
        
        # Check if user with this Google ID already exists
        existing_user = db.query(User).filter(User.google_id == google_id).first()
        
        if existing_user:
            # User already signed up with Google - log them in
            user = existing_user
        else:
            # Check if a user with this email already exists
            email_user = db.query(User).filter(User.email == email).first()
            
            if email_user:
                # Email exists but not linked to Google - link it
                email_user.google_id = google_id
                email_user.oauth_provider = "google"
                email_user.oauth_profile_picture = picture_url
                email_user.oauth_verified_at = datetime.utcnow()
                db.commit()
                db.refresh(email_user)
                user = email_user
            else:
                # New user - create account with Google credentials
                # For new OAuth users, no password is required
                try:
                    # Generate a unique username from email
                    base_username = email.split("@")[0]
                    username = base_username
                    counter = 1
                    while db.query(User).filter(User.username == username).first():
                        username = f"{base_username}{counter}"
                        counter += 1
                    
                    # Create new user with OAuth credentials
                    default_team = db.query(Team).first()
                    assigned_team_id = None
                    oauth_placeholder_password = get_password_hash(secrets.token_urlsafe(48))
                    
                    new_user = User(
                        email=email,
                        username=username,
                        # Keep a non-usable random hash to support legacy DBs where hashed_password is NOT NULL.
                        hashed_password=oauth_placeholder_password,
                        role=role,
                        team_id=assigned_team_id,
                        google_id=google_id,
                        oauth_provider="google",
                        oauth_profile_picture=picture_url,
                        oauth_verified_at=datetime.utcnow()
                    )
                    db.add(new_user)
                    db.commit()
                    db.refresh(new_user)
                    user = new_user
                except Exception as e:
                    db.rollback()
                    raise ValueError(f"Failed to create user: {str(e)}")
        
        # Generate JWT token for FlowMind
        role = getattr(user, "role", "member") or "member"
        team_id = getattr(user, "team_id", None)
        access_token = create_access_token(data={"sub": user.id, "role": role, "team_id": team_id})
        assignment = db.query(ReviewAssignment).filter(ReviewAssignment.client_id == user.id).order_by(ReviewAssignment.created_at.desc()).first()
        assigned_file_id = assignment.file_id if assignment else None
        redirect_target = "/client-review" if role == "client" else "/dashboard"
        
        # Return HTML that stores auth data using existing app keys
        user_payload = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": role,
            "team_id": team_id,
            "team_name": (getattr(user, "team", None) and getattr(user.team, "name", None)) or None
        }
        user_payload_json = json.dumps(user_payload)

        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Signing in...</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background: #020617;
                    color: #e2e8f0;
                }}
                .container {{
                    text-align: center;
                }}
                .spinner {{
                    border: 3px solid rgba(56, 189, 248, 0.2);
                    border-top: 3px solid #38bdf8;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px;
                }}
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="spinner"></div>
                <p>Signing in with Google...</p>
            </div>
            <script>
                // Store token and user info and redirect
                localStorage.setItem('access_token', '{access_token}');
                localStorage.setItem('fm_token', '{access_token}');
                localStorage.setItem('fm_role', '{role}');
                localStorage.setItem('fm_name', {json.dumps(user.username)});
                {f"localStorage.setItem('fm_assigned_file', '{assigned_file_id}');" if assigned_file_id else "localStorage.removeItem('fm_assigned_file');"}
                localStorage.setItem('user', JSON.stringify({user_payload_json}));
                
                // Redirect by role
                window.location.href = '{redirect_target}';
            </script>
        </body>
        </html>
        """)
        
    except requests.RequestException as e:
        return _oauth_error_page(
            "Google Sign-In Failed",
            "FlowMind could not exchange the Google authorization code.",
            f"Technical detail: {str(e)}"
        )
    except Exception as e:
        import traceback
        print(f"Google OAuth callback error: {traceback.format_exc()}")
        return _oauth_error_page(
            "Google Sign-In Failed",
            "Unexpected error while completing Google authentication.",
            f"Technical detail: {str(e)}"
        )


@router.post("/auth/google/verify-token")
async def verify_google_token(token: str, db: Session = Depends(get_db)):
    """
    Endpoint to verify a Google ID token (useful for client-side verification).
    Can be called from frontend to validate tokens.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured."
        )
    
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google.auth.transport.requests.Request(),
            GOOGLE_CLIENT_ID
        )
        return {
            "valid": True,
            "google_id": id_info.get("sub"),
            "email": id_info.get("email"),
            "name": id_info.get("name")
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
