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


def _get_webhook_url() -> Optional[str]:
    """Read at call time so .env / late-set environment variables are honoured."""
    return os.getenv("NOTIFICATIONS_WEBHOOK_URL") or os.getenv("SLACK_WEBHOOK_URL") or None


def send_review_needed_notification(
    thread_id: str,
    lead: Dict[str, Any],
    proposal: Optional[Dict[str, Any]],
    critic_log: Optional[Dict[str, Any]] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Sends a formatted notification to a webhook endpoint alerting reviewers
    that a proposal is paused and waiting for human sign-off.
    """
    target_url = webhook_url or _get_webhook_url()
    if not target_url:
        logger.info("[Notifications] No webhook URL configured. Skipping review alert.")
        return False

    lead = lead or {}
    client_name = lead.get("client_name", "Unknown Client")
    budget = lead.get("budget", "N/A")
    summary = proposal.get("executive_summary", "No summary provided.") if proposal else "Draft unavailable."
    score = critic_log.get("score", "N/A") if critic_log else "N/A"
    score_text = f"{score}/10" if isinstance(score, (int, float)) else str(score)

    # Only add an ellipsis when the summary was actually truncated.
    summary_preview = summary[:300] + ("..." if len(summary) > 300 else "")

    # Standard Slack Block Kit payload (also renders cleanly on Slack-compatible webhooks)
    payload = {
        "text": f"🚨 Human Approval Required for {client_name} (Thread: `{thread_id}`)",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 ProposalFlow: Review Required",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Client:*\n{client_name}"},
                    {"type": "mrkdwn", "text": f"*Thread ID:*\n`{thread_id}`"},
                    {"type": "mrkdwn", "text": f"*Budget:*\n{budget}"},
                    {"type": "mrkdwn", "text": f"*Critic Score:*\n{score_text}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Executive Summary:*\n>{summary_preview}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Resume via `POST /api/proposals/{thread_id}/review` with `{{\"approved\": true}}`",
                    }
                ],
            },
        ],
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(target_url, json=payload)
            if resp.is_success:
                logger.info("[Notifications] Review alert successfully dispatched for thread %s", thread_id)
                return True
            else:
                logger.warning(
                    "[Notifications] Webhook returned HTTP %s: %s",
                    resp.status_code,
                    resp.text,
                )
                return False
    except Exception as exc:
        logger.warning("[Notifications] Failed to send webhook alert (non-blocking): %s", exc)
        return False


def send_final_status_notification(
    thread_id: str,
    client_name: str,
    status: str,
    webhook_url: Optional[str] = None,
) -> bool:
    """Dispatches a notification when a proposal has finalized (approved or rejected)."""
    target_url = webhook_url or _get_webhook_url()
    if not target_url:
        logger.info("[Notifications] No webhook URL configured. Skipping final status alert.")
        return False

    emoji = "✅" if status in ("approved", "persisted") else "❌"
    payload = {
        "text": f"{emoji} Proposal for *{client_name}* finished with status: `{status}` (Thread: `{thread_id}`)"
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(target_url, json=payload)
            if resp.is_success:
                return True
            logger.warning(
                "[Notifications] Webhook returned HTTP %s: %s",
                resp.status_code,
                resp.text,
            )
            return False
    except Exception as exc:
        logger.warning("[Notifications] Failed to send final status alert: %s", exc)
        return False