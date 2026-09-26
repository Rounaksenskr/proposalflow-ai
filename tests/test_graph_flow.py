import pytest
from proposal_bot.graph import create_proposal_graph
from proposal_bot.state import ProposalState


@pytest.fixture
def base_lead_state() -> ProposalState:
    return {
        "lead": {
            "client_name": "Test Logistics",
            "project_description": "A logistics dashboard needing automated dispatch.",
            "website": "https://testlogistics.example.com",
            "budget": "$10,000",
            "deadline": "4 weeks",
        },
        "research": None,
        "retrieved_cases": [],
        "proposal": None,
        "critic_logs": [],
        "critic_attempts": 0,
        "revision_count": 0,
        "retry_count": 0,
        "human_approved": None,
        "human_feedback": None,
        "final_status": "received",
    }


def test_graph_terminates_on_max_retries(base_lead_state):
    """Ensure the loop terminates cleanly after 2 retries when critic consistently fails."""

    def mock_failing_critic(state):
        attempts = state.get("critic_attempts", state.get("retry_count", 0)) + 1
        return {
            "critic_logs": [
                {
                    "passed": False,
                    "score": 4,
                    "missing_requirements": ["Incomplete scope"],
                    "hallucinated_claims": [],
                    "actionable_revisions": ["Revise scope completely"],
                }
            ],
            "critic_attempts": attempts,
            "retry_count": attempts,
        }

    # Pass mock research, retrieval, and human review to avoid external network calls & pauses
    def mock_research(state):
        return {"research": {"company_summary": "Test Co", "industry": "Logistics"}}

    def mock_retrieval(state):
        return {"retrieved_cases": [{"title": "Past Project 1", "id": "proj-001"}]}

    def mock_human_review(state):
        return {
            "human_approved": False,
            "human_feedback": "Auto-rejected by circuit breaker test mock",
            "final_status": "rejected",
        }

    app = create_proposal_graph(
        custom_research=mock_research,
        custom_retrieval=mock_retrieval,
        custom_critic=mock_failing_critic,
        custom_human=mock_human_review,
    )

    final_state = app.invoke(base_lead_state)

    # 1. Generator performs an initial draft + exactly 2 revisions = 2 revisions
    assert final_state["revision_count"] == 2

    # 2. Critic evaluates 3 times (initial draft + revision 1 + revision 2)
    assert final_state["critic_attempts"] == 3
    assert final_state["retry_count"] == 3
    assert len(final_state["critic_logs"]) == 3

    # 3. Post-escalation routing verification
    assert final_state["final_status"] == "rejected"