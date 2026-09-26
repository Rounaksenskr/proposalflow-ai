import httpx
from unittest.mock import patch, MagicMock
from proposal_bot.integrations.notifications import (
    send_review_needed_notification,
    send_final_status_notification,
)
from proposal_bot.integrations.crm import sync_proposal_to_crm


def test_notifications_skipped_when_no_url():
    """Verify notification gracefully bypasses when webhook URL is not configured."""
    result = send_review_needed_notification(
        thread_id="test_thread_01",
        lead={"client_name": "Test Co"},
        proposal={"executive_summary": "Summary"},
        webhook_url=None,
    )
    assert result is False


def test_notifications_dispatch_success():
    """Verify formatted review alert succeeds when webhook returns 200."""
    mock_resp = MagicMock()
    mock_resp.is_success = True

    with patch.object(httpx.Client, "post", return_value=mock_resp) as mock_post:
        result = send_review_needed_notification(
            thread_id="test_thread_02",
            lead={"client_name": "Acme Corp", "budget": "$5,000", "deadline": "2 weeks"},
            proposal={"executive_summary": "Detailed technical proposal."},
            critic_log={"score": 9},
            webhook_url="https://hooks.slack.com/services/mock/webhook",
        )
        assert result is True
        assert mock_post.called
        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json", {})
        assert "Acme Corp" in payload["text"]
        assert len(payload["blocks"]) >= 3


def test_notifications_graceful_on_network_error():
    """Verify network timeouts or request exceptions do not raise unhandled errors."""
    with patch.object(httpx.Client, "post", side_effect=httpx.ConnectTimeout("Timeout")):
        result = send_review_needed_notification(
            thread_id="test_thread_03",
            lead={"client_name": "Acme Corp"},
            proposal={"executive_summary": "Summary"},
            webhook_url="https://hooks.slack.com/services/mock/webhook",
        )
        assert result is False


def test_crm_sync_skipped_when_no_url():
    """Verify CRM sync quietly bypasses when no CRM_API_URL is configured."""
    result = sync_proposal_to_crm(
        lead_data={"client_name": "Client A"},
        proposal_data={"executive_summary": "Summary"},
        thread_id="test_crm_01",
        api_url=None,
    )
    assert result is False


def test_crm_sync_success():
    """Verify CRM sync maps deal fields and sends authorized POST request."""
    mock_resp = MagicMock()
    mock_resp.is_success = True

    with patch.object(httpx.Client, "post", return_value=mock_resp) as mock_post:
        result = sync_proposal_to_crm(
            lead_data={
                "client_name": "Global Logistics",
                "website": "https://globallogistics.example",
                "budget": "$15,000",
                "deadline": "6 weeks",
            },
            proposal_data={
                "executive_summary": "Logistics optimization suite.",
                "estimated_pricing": "$15,000 fixed price",
            },
            thread_id="test_crm_02",
            status="approved",
            api_url="https://api.crm.example.com/v1/deals",
            api_key="mock_secret_key",
        )
        assert result is True
        assert mock_post.called

        headers = mock_post.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer mock_secret_key"

        payload = mock_post.call_args.kwargs.get("json", {})
        assert payload["deal_name"] == "Project Proposal - Global Logistics"
        assert payload["details"]["status"] == "approved"


def test_crm_sync_error_handling():
    """Verify CRM sync does not crash callers on server 500 error."""
    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        result = sync_proposal_to_crm(
            lead_data={"client_name": "Client Error"},
            proposal_data={},
            thread_id="test_crm_03",
            api_url="https://api.crm.example.com/v1/deals",
        )
        assert result is False