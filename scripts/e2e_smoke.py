"""End-to-end smoke test: manager + client roles through the live backend.

Usage:  python scripts/e2e_smoke.py [BASE_URL]

Signs up a fresh manager, invites a new client, exercises every page-level
API endpoint under each role, and verifies role-based access control.
Exits non-zero on the first failure.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
TIMEOUT = 180  # generous: first request wakes up the RAG agent


# ---------- pretty-printed assertions ------------------------------------

passed = 0
failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    mark = "PASS" if ok else "FAIL"
    tail = f"  {detail}" if detail else ""
    print(f"  [{mark}] {label}{tail}")
    if ok:
        passed += 1
    else:
        failed += 1


def must(label: str, got: int, expected: int | set[int], body: Any = "") -> None:
    expected_set = expected if isinstance(expected, set) else {expected}
    ok = got in expected_set
    detail = f"got {got}"
    if not ok and body:
        detail += f"  body={str(body)[:180]}"
    check(label, ok, detail)


# ---------- http helpers --------------------------------------------------


def jget(path: str, token: str | None = None, **params: Any) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{BASE}{path}", headers=headers, params=params, timeout=TIMEOUT)


def jpost(path: str, body: dict, token: str | None = None) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(
        f"{BASE}{path}", headers=headers, data=json.dumps(body), timeout=TIMEOUT
    )


def upload(path: str, token: str, filename: str, content: bytes) -> requests.Response:
    return requests.post(
        f"{BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, content, "text/plain")},
        timeout=TIMEOUT,
    )


def section(title: str) -> None:
    bar = "=" * max(60, len(title) + 4)
    print(f"\n{bar}\n  {title}\n{bar}")


# ---------- 1. SPA shell reachable ---------------------------------------

section("SPA pages (all should return the React shell, 200)")
SPA_ROUTES = [
    "/", "/login", "/dashboard", "/upload", "/requirements", "/approve",
    "/analytics", "/export", "/settings", "/members", "/clients",
    "/integrations", "/integration-log", "/manager-feedback", "/client-review",
]
for p in SPA_ROUTES:
    r = requests.get(f"{BASE}{p}", timeout=TIMEOUT)
    ok = r.status_code == 200 and "id=\"root\"" in r.text
    check(f"GET {p}", ok, f"{r.status_code}")

# ---------- 2. Manager signup + login ------------------------------------

section("Manager signup & login")
ts = int(time.time())
mgr_email = f"mgr_{ts}@example.com"
mgr_password = "ManagerPass123!"

r = jpost("/api/signup", {"email": mgr_email, "password": mgr_password, "name": "Smoke Manager"})
must(f"POST /api/signup  {mgr_email}", r.status_code, 200, r.text)
mgr_token = r.json().get("access_token")
mgr_id = r.json().get("user", {}).get("id")
check("manager token present", bool(mgr_token))
check("role == manager", r.json().get("role") == "manager", r.json().get("role", ""))

r = jpost("/api/login", {"email": mgr_email, "password": mgr_password})
must("POST /api/login  (manager)", r.status_code, 200, r.text)
mgr_token = r.json()["access_token"]

r = jget("/api/me", mgr_token)
must("GET  /api/me  (manager)", r.status_code, 200)
check("me.email matches", r.json().get("email") == mgr_email)

# ---------- 3. Manager-only read endpoints -------------------------------

section("Manager reads each page-level endpoint")
for path in [
    "/api/my-uploads",
    "/api/features",
    "/api/features/stats",
    "/api/members",
    "/api/manager/clients",
    "/api/integration/config",
    "/api/integration/log",
    "/api/teams",
    "/api/assignable-users",
]:
    r = jget(path, mgr_token)
    must(f"GET  {path}", r.status_code, 200)

# ---------- 4. Pre-model gate rejects empty & non-SRS --------------------

section("Pre-model gate on upload (DOCUMENT_EMPTY / NON_SRS_DOCUMENT)")

# Build real .docx files in-memory — .txt is no longer an accepted format.
import docx as _docx
import io as _io


def _docx_bytes(body_lines):
    doc = _docx.Document()
    for line in body_lines:
        doc.add_paragraph(line)
    buf = _io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


r = upload("/upload_client_doc", mgr_token, "empty.docx", _docx_bytes([]))
must("POST /upload_client_doc  empty.docx", r.status_code, 400, r.text)
try:
    detail = r.json().get("detail") or {}
    check("empty rejection has error=DOCUMENT_EMPTY",
          detail.get("error") == "DOCUMENT_EMPTY",
          json.dumps(detail)[:160])
except Exception:
    check("empty rejection JSON parse", False, r.text[:160])

r = upload(
    "/upload_client_doc", mgr_token, "recipe.docx",
    _docx_bytes(["Add salt and pepper. Mix ingredients in a bowl and bake for 30 minutes."]),
)
must("POST /upload_client_doc  recipe.docx", r.status_code, 400, r.text)
try:
    detail = r.json().get("detail") or {}
    check("non-SRS rejection has error=NON_SRS_DOCUMENT",
          detail.get("error") == "NON_SRS_DOCUMENT",
          json.dumps(detail)[:160])
except Exception:
    check("non-SRS rejection JSON parse", False, r.text[:160])

# ---------- 5. Valid SRS upload -----------------------------------------

section("Valid SRS upload reaches analyzer")
srs_text = """\
1. Introduction
1.1 Scope
The system shall allow users to sign up, log in, and manage projects.

Functional Requirements:
FR-1: The system must authenticate users via email and password.
FR-2: The system shall store passwords using bcrypt hashing.
FR-3: Users shall be able to upload Software Requirements documents.

Non-Functional Requirements:
NFR-1: The API must respond within 200 ms for authenticated requests.
NFR-2: The system shall support 1000 concurrent users.
NFR-3: The service must be available 99.5% of the time.

Stakeholders include end users, administrators, and auditors.
The system interfaces with Jira and Trello via REST APIs.
"""
r = upload(
    "/upload_client_doc",
    mgr_token,
    f"srs_{ts}.docx",
    _docx_bytes(srs_text.strip().splitlines()),
)
# 200 on success; anything in the 4xx/5xx range is a backend failure.
must(
    f"POST /upload_client_doc  srs_{ts}.docx",
    r.status_code,
    {200, 201},
    r.text[:200],
)
file_id = None
if r.status_code in (200, 201):
    try:
        body = r.json()
        file_id = body.get("file_id")
        view_id = body.get("view_id")
        check("srs upload returned file_id or view_id", bool(file_id or view_id),
              f"file_id={file_id} view_id={view_id}")
    except Exception:
        check("srs upload JSON parse", False, r.text[:160])

# If file_id wasn't returned inline, resolve it from /api/my-uploads.
if not file_id:
    r = jget("/api/my-uploads", mgr_token)
    if r.status_code == 200:
        uploads_list = r.json().get("uploads") or []
        if uploads_list:
            file_id = uploads_list[0]["id"]
            check("resolved file_id from /api/my-uploads", True, f"file_id={file_id}")

# ---------- 6. Invite a client ------------------------------------------

section("Manager invites a client")
client_email = f"client_{ts}@example.com"
invite_body = {"email": client_email, "name": "Smoke Client"}
if file_id:
    invite_body["file_id"] = file_id

r = jpost("/api/manager/invite-client", invite_body, mgr_token)
must("POST /api/manager/invite-client", r.status_code, 200, r.text)
client_temp_pw = None
if r.status_code == 200:
    client_temp_pw = r.json().get("temp_password")
    check("invite returned temp_password", bool(client_temp_pw))

# ---------- 7. Client login + client view ------------------------------

section("Client login + role-scoped view")
client_token = None
if client_temp_pw:
    r = jpost("/api/login", {"email": client_email, "password": client_temp_pw})
    must("POST /api/login  (client)", r.status_code, 200, r.text)
    if r.status_code == 200:
        client_token = r.json()["access_token"]
        check("role == client", r.json().get("role") == "client", r.json().get("role", ""))

    if client_token and file_id:
        r = jget(f"/review/{file_id}", client_token)
        must(f"GET  /review/{file_id}  (client)", r.status_code, 200, r.text[:200])

# ---------- 8. Role gating ----------------------------------------------

section("Role-based access control")
# Manager must NOT be able to use the client review endpoint.
if file_id:
    r = jget(f"/review/{file_id}", mgr_token)
    must(f"GET  /review/{file_id}  (manager -> forbidden)",
         r.status_code, {403, 400}, r.text[:160])

# Client must NOT be able to see manager-only endpoints.
if client_token:
    for path in ("/api/members", "/api/manager/clients", "/api/integration/log"):
        r = jget(path, client_token)
        must(f"GET  {path}  (client -> forbidden)",
             r.status_code, {403, 401}, r.text[:160])

# ---------- 9. No-auth on protected endpoints ---------------------------

section("Unauthenticated access is blocked")
for path in ("/api/features", "/api/members", "/api/my-uploads"):
    r = requests.get(f"{BASE}{path}", timeout=TIMEOUT)
    must(f"GET  {path}  (no token)", r.status_code, {401, 403}, r.text[:120])

# ---------- 10. Legacy redirect + dead paths ---------------------------

section("Legacy compatibility")
r = requests.get(f"{BASE}/login.html?invite_token=x", allow_redirects=False, timeout=TIMEOUT)
must("GET  /login.html?invite_token=x  -> 301", r.status_code, 301)
check(
    "redirect preserves query",
    r.headers.get("location", "").endswith("/login?invite_token=x"),
    r.headers.get("location", ""),
)

for p in ("/static/analytics.html", "/static/css/style.css"):
    r = requests.get(f"{BASE}{p}", timeout=TIMEOUT)
    must(f"GET  {p}  -> 404", r.status_code, 404)

# ---------- summary -----------------------------------------------------

print()
bar = "=" * 60
print(bar)
print(f"  RESULT: {passed} passed, {failed} failed")
print(bar)
sys.exit(0 if failed == 0 else 1)
