import os
import logging
from typing import Dict, Any, Optional

import httpx
from dotenv import load_dotenv, find_dotenv

# Load variables from the .env file in the current working directory (same place
# config.py looks) into os.environ.
# override=False -> real environment variables (shell, Docker, CI) always win.
load_dotenv(find_dotenv(usecwd=True), override=False)

logger = logging.getLogger(__name__)


def _get_crm_url() -> Optional[str]:
    """Read at call time so .env / late-set environment variables are honoured."""
    return os.getenv("CRM_API_URL") or None


def _get_crm_key() -> Optional[str]:
    return os.getenv("CRM_API_KEY") or None


def sync_proposal_to_crm(
    lead_data: Dict[str, Any],
    proposal_data: Optional[Dict[str, Any]],
    thread_id: str,
    status: str = "approved",
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """
    Syncs approved client and proposal deal records to an external CRM.
    Returns True if successfully synchronized or False if bypassed / failed.
    """
    target_url = api_url or _get_crm_url()
    token = api_key or _get_crm_key()

    if not target_url:
        logger.info("[CRM Sync] No CRM_API_URL configured. Skipping CRM synchronization.")
        return False

    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    lead_data = lead_data or {}
    client_name = lead_data.get("client_name", "Unknown Client")
    proposal = proposal_data or {}

    payload = {
        "deal_name": f"Project Proposal - {client_name}",
        "thread_id": thread_id,
        "client": {
            "name": client_name,
            "website": lead_data.get("website"),
        },
        "details": {
            "budget": lead_data.get("budget"),
            "deadline": lead_data.get("deadline"),
            "status": status,
            "executive_summary": proposal.get("executive_summary", ""),
            "estimated_pricing": proposal.get("estimated_pricing", ""),
        },
    }

    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.post(target_url, json=payload, headers=headers)
            if resp.is_success:
                logger.info("[CRM Sync] Successfully synced proposal record for thread %s", thread_id)
                return True
            else:
                logger.warning(
                    "[CRM Sync] CRM returned HTTP %s: %s",
                    resp.status_code,
                    resp.text,
                )
                return False
    except Exception as exc:
        logger.warning("[CRM Sync] Failed to sync to CRM (non-blocking): %s", exc)
        return False