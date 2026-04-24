"""Google OAuth routes for FlowMind.

Flow:
    1. Browser hits /auth/google/init — we mint a CSRF nonce, set it in an
       HttpOnly cookie, and redirect to Google's consent screen with the
       nonce embedded in the `state` parameter.
    2. Google redirects back to /auth/google/callback with an authorization
       code and the original `state`. We compare the state nonce against the
       cookie, exchange the code, verify Google's ID token, and either
       create or look up the FlowMind user.
    3. We mint a FlowMind JWT and redirect to /auth/google/complete with the
       session payload in the URL fragment (so it is never sent back to the
       server or logged). A small React page pulls it out of the fragment,
       stores it via AuthContext, and routes by role.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

import google.auth.transport.requests
import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from auth import create_access_token, get_db, get_password_hash
from database import ReviewAssignment, Team, User

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# Name of the short-lived CSRF cookie that pins the OAuth state to this browser.
_STATE_COOKIE = "flowmind_oauth_state"
# Cookie lifetime. Just long enough for the user to complete consent.
_STATE_TTL_SECONDS = 10 * 60


def _b64url_encode(raw: bytes | str) -> str:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _build_state(nonce: str, role: str, redirect_tab: str) -> str:
    payload = {"n": nonce, "r": role, "t": redirect_tab, "ts": int(time.time())}
    return _b64url_encode(json.dumps(payload, separators=(",", ":")))


def _parse_state(state: str) -> dict[str, Any]:
    if not state:
        return {}
    padded = state + "=" * (-len(state) % 4)
    try:
        data = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        return json.loads(data)
    except Exception:
        return {}


def _oauth_error_page(title: str, message: str, hint: str = "") -> HTMLResponse:
    """Render a minimal, non-leaking error page for failed OAuth flows."""
    hint_block = (
        f"<p class='hint'>{hint}</p>" if hint else ""
    )
    html = f"""\
<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
         margin: 0; background: #f1f5f9; color: #0f172a; min-height: 100vh;
         display: grid; place-items: center; padding: 24px; }}
  .card {{ max-width: 480px; width: 100%; background: #fff; border: 1px solid #e2e8f0;
          border-radius: 14px; padding: 28px; box-shadow: 0 10px 32px rgba(15,23,42,0.06); }}
  h1 {{ margin: 0 0 8px; font-size: 1.15rem; }}
  p {{ margin: 0 0 8px; color: #475569; line-height: 1.5; font-size: 0.92rem; }}
  .hint {{ color: #94a3b8; font-size: 0.82rem; }}
  a.back {{ display: inline-flex; align-items: center; gap: 6px; margin-top: 16px;
            background: #2c4ff2; color: #fff; text-decoration: none;
            padding: 9px 14px; border-radius: 10px; font-weight: 600; font-size: 0.88rem; }}
  a.back:hover {{ background: #263cd1; }}
</style>
</head><body>
  <div class="card">
    <h1>{title}</h1>
    <p>{message}</p>
    {hint_block}
    <a class="back" href="/login">Back to sign in</a>
  </div>
</body></html>"""
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)


def _redirect_to_spa_complete(payload: dict[str, Any]) -> RedirectResponse:
    """Hand the session off to the React app via a URL fragment so the token
    is never transmitted back to the server or written to access logs.
    """
    encoded = quote(
        json.dumps(payload, separators=(",", ":")),
        safe="",
    )
    return RedirectResponse(
        url=f"/oauth/complete#data={encoded}", status_code=302
    )


@router.get("/auth/google/init")
async def google_oauth_init(
    role: str = Query("manager", pattern="^(manager|client)$"),
    redirect_tab: str = Query("login"),
):
    """Start the Google OAuth flow. Sets a one-shot CSRF cookie and bounces
    the browser to Google's consent screen."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return _oauth_error_page(
            "Google Sign-In Not Configured",
            "Google OAuth is available in the app, but the server is missing "
            "Google client credentials.",
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env, then restart FlowMind.",
        )

    nonce = secrets.token_urlsafe(32)
    state = _build_state(nonce=nonce, role=role, redirect_tab=redirect_tab)

    auth_params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    redirect_url = f"{GOOGLE_AUTH_URL}?{urlencode(auth_params)}"

    response = RedirectResponse(url=redirect_url, status_code=302)
    # SameSite=Lax lets the cookie survive the top-level cross-site redirect
    # Google performs when returning to /auth/google/callback.
    response.set_cookie(
        key=_STATE_COOKIE,
        value=nonce,
        max_age=_STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=GOOGLE_REDIRECT_URI.startswith("https://"),
        path="/auth/google",
    )
    return response


@router.get("/auth/google/callback")
async def google_oauth_callback(
    request: Request,
    code: str | None = Query(None),
    state: str = Query(""),
    error: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Validate state, redeem the code, issue a JWT, and bounce the browser
    back to the React app via `/auth/google/complete`."""
    if error:
        return _oauth_error_page(
            "Google Sign-In Cancelled",
            f"Google returned an authentication error ({error}).",
            "Please try again, or sign in with your email and password.",
        )

    if not code:
        return _oauth_error_page(
            "Google Sign-In Failed",
            "No authorization code was returned by Google.",
        )

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return _oauth_error_page(
            "Google Sign-In Not Configured",
            "Google OAuth credentials are missing on the server.",
        )

    # --- CSRF check: state nonce must match the cookie we set at /init ---
    state_data = _parse_state(state)
    expected_nonce = state_data.get("n")
    cookie_nonce = request.cookies.get(_STATE_COOKIE)
    if (
        not expected_nonce
        or not cookie_nonce
        or not secrets.compare_digest(str(expected_nonce), str(cookie_nonce))
    ):
        resp = _oauth_error_page(
            "Google Sign-In Rejected",
            "The sign-in session could not be verified.",
            "This usually happens if you reloaded the Google page, used an old link, "
            "or started the flow in another tab. Please try again.",
        )
        resp.delete_cookie(_STATE_COOKIE, path="/auth/google")
        return resp

    role = state_data.get("r") or "manager"
    if role not in ("manager", "client"):
        role = "manager"

    try:
        # --- Redeem the authorization code for Google tokens ---
        token_response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI,
            },
            timeout=20,
        )
        token_response.raise_for_status()
        tokens = token_response.json()

        id_token_str = tokens.get("id_token")
        if not id_token_str:
            raise ValueError("No id_token in Google response")

        try:
            id_info = id_token.verify_oauth2_token(
                id_token_str,
                google.auth.transport.requests.Request(),
                GOOGLE_CLIENT_ID,
            )
        except ValueError:
            access_token_google = tokens.get("access_token")
            userinfo_response = requests.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token_google}"},
                timeout=15,
            )
            userinfo_response.raise_for_status()
            id_info = userinfo_response.json()

        google_id = id_info.get("sub")
        email = id_info.get("email")
        picture_url = id_info.get("picture")
        display_name = id_info.get("name") or (email.split("@")[0] if email else "")

        if not google_id or not email:
            raise ValueError("Missing required fields from Google OAuth response")

        # --- Find or create the FlowMind user ---
        user = db.query(User).filter(User.google_id == google_id).first()
        if not user:
            email_user = db.query(User).filter(User.email == email).first()
            if email_user:
                email_user.google_id = google_id
                email_user.oauth_provider = "google"
                email_user.oauth_profile_picture = picture_url
                email_user.oauth_verified_at = datetime.utcnow()
                db.commit()
                db.refresh(email_user)
                user = email_user
            else:
                base_username = (
                    "".join(
                        ch
                        for ch in (display_name or email.split("@")[0]).lower().replace(" ", "_")
                        if ch.isalnum() or ch == "_"
                    )
                    or email.split("@")[0]
                )
                username = base_username
                suffix = 1
                while db.query(User).filter(User.username == username).first():
                    username = f"{base_username}{suffix}"
                    suffix += 1

                # We never use this hash — OAuth users have no password login.
                oauth_placeholder_password = get_password_hash(secrets.token_urlsafe(48))

                user = User(
                    email=email,
                    username=username,
                    hashed_password=oauth_placeholder_password,
                    role=role,
                    team_id=None,
                    google_id=google_id,
                    oauth_provider="google",
                    oauth_profile_picture=picture_url,
                    oauth_verified_at=datetime.utcnow(),
                )
                db.add(user)
                db.commit()
                db.refresh(user)

        # --- Mint a FlowMind JWT and build the session payload ---
        resolved_role = getattr(user, "role", "member") or "member"
        team_id = getattr(user, "team_id", None)
        access_token = create_access_token(
            data={"sub": user.id, "role": resolved_role, "team_id": team_id}
        )

        assignment = (
            db.query(ReviewAssignment)
            .filter(ReviewAssignment.client_id == user.id)
            .order_by(ReviewAssignment.created_at.desc())
            .first()
        )
        assigned_file_id = assignment.file_id if assignment else None

        team_name = (
            (getattr(user, "team", None) and getattr(user.team, "name", None)) or None
        )

        session_payload = {
            "access_token": access_token,
            "token_type": "bearer",
            "role": resolved_role,
            "assigned_file_id": assigned_file_id,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": resolved_role,
                "team_id": team_id,
                "team_name": team_name,
                "avatar_url": getattr(user, "oauth_profile_picture", None),
            },
        }

        response = _redirect_to_spa_complete(session_payload)
        response.delete_cookie(_STATE_COOKIE, path="/auth/google")
        return response

    except requests.RequestException as exc:
        return _oauth_error_page(
            "Google Sign-In Failed",
            "FlowMind could not exchange the Google authorization code.",
            f"Technical detail: {exc}",
        )
    except Exception as exc:
        import traceback

        print(f"Google OAuth callback error: {traceback.format_exc()}")
        return _oauth_error_page(
            "Google Sign-In Failed",
            "Unexpected error while completing Google authentication.",
            f"Technical detail: {exc}",
        )


@router.post("/auth/google/verify-token")
async def verify_google_token(token: str, db: Session = Depends(get_db)):
    """Verify a Google ID token directly. Handy for clients that use
    Google's JS SDK instead of the redirect flow."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured.",
        )
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google.auth.transport.requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        return {
            "valid": True,
            "google_id": id_info.get("sub"),
            "email": id_info.get("email"),
            "name": id_info.get("name"),
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token"
        )
