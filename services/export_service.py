"""Requirement export service for Jira/Trello and automation hooks."""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import requests
from sqlalchemy.orm import Session

from database import Feature, IntegrationConfig, IntegrationLog

# Lightweight in-memory queue to track pending exports during runtime.
PENDING_EXPORT_QUEUE = set()


def _load_platform_config(db: Session, platform: str) -> Dict[str, str]:
    rows = db.query(IntegrationConfig).filter(IntegrationConfig.platform == platform).all()
    return {str(row.key_name): str(row.value or "") for row in rows}


def _cfg_value(config: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (config.get(key) or "").strip()
        if value:
            return value
    return ""


def jira_is_connected(config: Dict[str, str]) -> bool:
    return all(
        [
            _cfg_value(config, "jira_url", "url"),
            _cfg_value(config, "jira_project_key", "project_key"),
            _cfg_value(config, "jira_email", "email"),
            _cfg_value(config, "jira_token", "api_token"),
        ]
    )


def trello_is_connected(config: Dict[str, str]) -> bool:
    return all(
        [
            _cfg_value(config, "trello_key", "api_key"),
            _cfg_value(config, "trello_token", "token"),
            _cfg_value(config, "trello_board_id", "list_id"),
        ]
    )


def _integration_log(
    db: Session,
    platform: str,
    source: str,
    source_id: Optional[str],
    success: bool,
    message: str,
    details: Optional[str] = None,
):
    row = IntegrationLog(
        user_id=None,
        platform=platform,
        source=source,
        source_id=source_id,
        items_count=1,
        success_count=1 if success else 0,
        message=message,
        details=details,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()


def push_to_jira(requirement: Feature, config: Dict[str, str]) -> Dict[str, object]:
    jira_url = _cfg_value(config, "jira_url", "url")
    jira_email = _cfg_value(config, "jira_email", "email")
    jira_token = _cfg_value(config, "jira_token", "api_token")
    jira_project_key = _cfg_value(config, "jira_project_key", "project_key")
    issue_type = _cfg_value(config, "jira_issue_type", "issue_type") or "Story"
    if not all([jira_url, jira_email, jira_token, jira_project_key]):
        return {"success": False, "error": "Jira config incomplete"}

    url = f"{jira_url.rstrip('/')}/rest/api/3/issue"
    token = b64encode(f"{jira_email}:{jira_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }
    priority_map = {"high": "High", "medium": "Medium", "low": "Low"}
    payload = {
        "fields": {
            "project": {"key": jira_project_key},
            "summary": (requirement.title or requirement.description or f"Requirement {requirement.id}")[:255],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": requirement.description or "",
                            }
                        ],
                    }
                ],
            },
            "issuetype": {"name": issue_type},
            "priority": {"name": priority_map.get(str(requirement.priority or "").lower(), "Medium")},
            "labels": [str(requirement.category or "functional"), "FlowMind"],
        }
    }
    response = requests.post(url, json=payload, headers=headers, timeout=12)
    if response.status_code == 201:
        issue_key = response.json().get("key")
        return {"success": True, "issue_key": issue_key}
    return {"success": False, "error": response.text}


def push_to_trello(requirement: Feature, config: Dict[str, str]) -> Dict[str, object]:
    trello_key = _cfg_value(config, "trello_key", "api_key")
    trello_token = _cfg_value(config, "trello_token", "token")
    if not all([trello_key, trello_token]):
        return {"success": False, "error": "Trello config incomplete"}

    category_list_map = {
        "functional": _cfg_value(config, "trello_functional_list_id"),
        "non-functional": _cfg_value(config, "trello_nonfunctional_list_id"),
        "non_functional": _cfg_value(config, "trello_nonfunctional_list_id"),
        "business": _cfg_value(config, "trello_business_list_id"),
        "system": _cfg_value(config, "trello_system_list_id"),
    }
    fallback_list = _cfg_value(config, "trello_board_id", "list_id")
    list_id = category_list_map.get(str(requirement.category or "").strip().lower()) or fallback_list
    if not list_id:
        return {"success": False, "error": "Trello list/board config missing"}

    url = "https://api.trello.com/1/cards"
    params = {
        "key": trello_key,
        "token": trello_token,
        "idList": list_id,
        "name": (requirement.title or requirement.description or f"Requirement {requirement.id}")[:255],
        "desc": (
            f"{requirement.description or ''}\n\n"
            f"Priority: {requirement.priority or 'Medium'}\n"
            "Source: FlowMind"
        ),
        "pos": "bottom",
    }
    response = requests.post(url, params=params, timeout=12)
    if response.status_code == 200:
        card_id = response.json().get("id")
        return {"success": True, "card_id": card_id}
    return {"success": False, "error": response.text}


def _approved_requirements(
    db: Session,
    file_id: int,
    visible_user_ids: Optional[Sequence[int]] = None,
) -> List[Feature]:
    q = db.query(Feature).filter(
        Feature.file_id == file_id,
        Feature.client_review_status == "approved",
    )
    if visible_user_ids:
        q = q.filter(Feature.user_id.in_(visible_user_ids))
    return q.order_by(Feature.created_at.asc()).all()


def _get_requirement(
    db: Session,
    req_id: int,
    visible_user_ids: Optional[Sequence[int]] = None,
) -> Optional[Feature]:
    q = db.query(Feature).filter(Feature.id == req_id)
    if visible_user_ids:
        q = q.filter(Feature.user_id.in_(visible_user_ids))
    return q.first()


def remove_from_pending_export_queue(req_id: int):
    PENDING_EXPORT_QUEUE.discard(int(req_id))


def push_all_approved_to_jira(
    db: Session,
    file_id: int,
    visible_user_ids: Optional[Sequence[int]] = None,
) -> Dict[str, object]:
    config = _load_platform_config(db, "jira")
    if not jira_is_connected(config):
        return {"success": False, "message": "Jira is not connected", "results": []}

    reqs = _approved_requirements(db, file_id, visible_user_ids)
    results = [push_to_jira(req, config) | {"req_id": req.id} for req in reqs]
    ok = sum(1 for r in results if r.get("success"))
    return {"success": ok > 0, "message": f"Exported {ok}/{len(reqs)} approved requirements to Jira", "results": results}


def push_all_approved_to_trello(
    db: Session,
    file_id: int,
    visible_user_ids: Optional[Sequence[int]] = None,
) -> Dict[str, object]:
    config = _load_platform_config(db, "trello")
    if not trello_is_connected(config):
        return {"success": False, "message": "Trello is not connected", "results": []}

    reqs = _approved_requirements(db, file_id, visible_user_ids)
    results = [push_to_trello(req, config) | {"req_id": req.id} for req in reqs]
    ok = sum(1 for r in results if r.get("success"))
    return {"success": ok > 0, "message": f"Exported {ok}/{len(reqs)} approved requirements to Trello", "results": results}


def push_single_to_jira(
    db: Session,
    req_id: int,
    visible_user_ids: Optional[Sequence[int]] = None,
) -> Dict[str, object]:
    req = _get_requirement(db, req_id, visible_user_ids)
    if not req:
        return {"success": False, "error": "Requirement not found"}
    result = push_to_jira(req, _load_platform_config(db, "jira"))
    return {"req_id": req.id, **result}


def push_single_to_trello(
    db: Session,
    req_id: int,
    visible_user_ids: Optional[Sequence[int]] = None,
) -> Dict[str, object]:
    req = _get_requirement(db, req_id, visible_user_ids)
    if not req:
        return {"success": False, "error": "Requirement not found"}
    result = push_to_trello(req, _load_platform_config(db, "trello"))
    return {"req_id": req.id, **result}


def auto_export_after_approval(db: Session, requirement: Feature) -> Dict[str, object]:
    """Auto-export one approved requirement to connected platforms."""
    results: Dict[str, object] = {"jira": None, "trello": None}
    jira_cfg = _load_platform_config(db, "jira")
    trello_cfg = _load_platform_config(db, "trello")

    if jira_is_connected(jira_cfg):
        jira_result = push_to_jira(requirement, jira_cfg)
        results["jira"] = jira_result
        _integration_log(
            db,
            platform="jira",
            source="approved",
            source_id=str(requirement.id),
            success=bool(jira_result.get("success")),
            message="Auto-exported to Jira after client approval",
            details=str(jira_result),
        )

    if trello_is_connected(trello_cfg):
        trello_result = push_to_trello(requirement, trello_cfg)
        results["trello"] = trello_result
        _integration_log(
            db,
            platform="trello",
            source="approved",
            source_id=str(requirement.id),
            success=bool(trello_result.get("success")),
            message="Auto-exported to Trello after client approval",
            details=str(trello_result),
        )

    return results
