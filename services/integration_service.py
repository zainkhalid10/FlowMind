"""Integration service for Trello and Jira - exports requirements as tasks."""
import os
import re
import csv
import io
import json
import requests
from typing import List, Dict, Any, Optional, Tuple


def parse_requirements_from_response(response_text: str) -> List[Dict[str, str]]:
    """
    Parse the requirements response text into structured list of {category, description}.
    Handles formats like:
      Functional Requirements:
      - item 1
      - item 2
      Non-Functional Requirements:
      - item 1
    """
    requirements = []
    current_category = "Other"
    lines = (response_text or "").split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Section heading (ends with colon, no leading bullet)
        if line.endswith(":") and not line.startswith("-") and not line.startswith(("✅", "⚠️", "❌")):
            # Clean category name (remove parenthetical counts like "Functional Requirements (47 items)")
            category = re.sub(r"\s*\([^)]*\)\s*$", "", line.rstrip(":")).strip()
            if category.lower() != "(none)":
                current_category = category
            continue

        # Bullet item: - text or ✅/⚠️/❌ text
        if line.startswith("- ") or line.startswith("✅") or line.startswith("⚠️") or line.startswith("❌"):
            text = line[2:].strip() if line.startswith("- ") else re.sub(r"^[✅⚠️❌]\s*", "", line).strip()
        else:
            # Regular line under current section
            text = line

        if not text or text.lower() == "(none)":
            continue

        requirements.append({
            "category": current_category,
            "description": text
        })

    return requirements


def export_as_json(requirements: List[Dict[str, str]], filename: str, summary: str) -> str:
    """Export requirements as JSON string."""
    data = {
        "source_file": filename,
        "summary": summary,
        "total_count": len(requirements),
        "requirements": requirements
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def export_as_csv(requirements: List[Dict[str, str]]) -> str:
    """Export requirements as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Category", "Description"])
    for r in requirements:
        writer.writerow([r["category"], r["description"]])
    return output.getvalue()


def push_to_trello(
    requirements: List[Dict[str, str]],
    list_id: str,
    api_key: str,
    token: str,
    source_filename: str = ""
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Push requirements as Trello cards to the specified list.
    Returns (success, message, results).
    """
    if not list_id or not api_key or not token:
        return False, "Missing Trello credentials (list_id, api_key, token). Add to .env: TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_LIST_ID", []

    base_url = "https://api.trello.com/1"
    results = []
    created = 0
    errors = []

    for req in requirements:
        name = (req["description"][:16380] + "...") if len(req["description"]) > 16380 else req["description"]
        desc = f"**Category:** {req['category']}\n\n**Source:** {source_filename}\n\n---\n\n{req['description']}"

        params = {
            "name": name[:16384],  # Trello card name limit
            "desc": desc[:16384],  # Trello desc limit
            "idList": list_id,
            "key": api_key,
            "token": token
        }

        try:
            resp = requests.post(f"{base_url}/cards", params=params, timeout=15)
            if resp.status_code in (200, 201):
                data = resp.json()
                results.append({"category": req["category"], "name": name[:80], "url": data.get("url", ""), "created": True})
                created += 1
            else:
                err_msg = resp.text[:200] if resp.text else resp.reason
                errors.append(f"{req['category']}: {err_msg}")
                results.append({"category": req["category"], "name": name[:80], "error": err_msg, "created": False})
        except Exception as e:
            errors.append(str(e))
            results.append({"category": req["category"], "name": name[:80], "error": str(e), "created": False})

    if created == len(requirements):
        return True, f"Successfully created {created} cards on Trello", results
    elif created > 0:
        return True, f"Created {created}/{len(requirements)} cards. Errors: {'; '.join(errors[:3])}", results
    else:
        return False, f"Failed to create cards: {'; '.join(errors[:3])}", results


def push_to_jira(
    requirements: List[Dict[str, str]],
    jira_url: str,
    project_key: str,
    email: str,
    api_token: str,
    issue_type: str = "Task",
    source_filename: str = ""
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Push requirements as Jira issues.
    Returns (success, message, results).
    """
    if not all([jira_url, project_key, email, api_token]):
        return False, "Missing Jira credentials. Add to .env: JIRA_URL, JIRA_PROJECT_KEY, JIRA_EMAIL, JIRA_API_TOKEN", []

    base_url = jira_url.rstrip("/")
    endpoint = f"{base_url}/rest/api/2/issue"
    auth = (email, api_token)
    headers = {"Content-Type": "application/json"}
    results = []
    created = 0
    errors = []

    for req in requirements:
        summary = req["description"][:255]  # Jira summary limit
        description = f"*Category:* {req['category']}\n\n*Source:* {source_filename}\n\n---\n\n{req['description']}"

        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type}
            }
        }

        try:
            resp = requests.post(endpoint, json=payload, auth=auth, headers=headers, timeout=15)
            if resp.status_code in (200, 201):
                data = resp.json()
                key = data.get("key", "")
                results.append({"category": req["category"], "summary": summary[:80], "key": key, "created": True})
                created += 1
            else:
                err_msg = resp.text[:200] if resp.text else resp.reason
                errors.append(f"{req['category']}: {err_msg}")
                results.append({"category": req["category"], "summary": summary[:80], "error": err_msg, "created": False})
        except Exception as e:
            errors.append(str(e))
            results.append({"category": req["category"], "summary": summary[:80], "error": str(e), "created": False})

    if created == len(requirements):
        return True, f"Successfully created {created} issues in Jira", results
    elif created > 0:
        return True, f"Created {created}/{len(requirements)} issues. Errors: {'; '.join(errors[:3])}", results
    else:
        return False, f"Failed to create issues: {'; '.join(errors[:3])}", results
