import pytest
from proposal_bot.graph import create_proposal_graph


@pytest.fixture
def base_lead_state():
    return {
        "lead": {
            "client_name": "Test Logistics",
            "project_description": "A logistics dashboard needing automated dispatch."
        },
        "research": None,
        "retrieved_cases": [],
        "proposal": None,
        "critic_logs": [],
        "retry_count": 0,
        "human_approved": None,
        "human_feedback": None,
        "final_status": "pending"
    }


def test_graph_terminates_on_max_retries(base_lead_state):
    """Ensure the loop terminates cleanly after 2 retries when critic consistently fails."""

    def mock_failing_critic(state):
        retries = state.get("retry_count", 0)
        return {
            "critic_logs": [{
                "passed": False,
                "score": 4,
                "missing_requirements": ["Incomplete scope"],
                "hallucinated_claims": [],
                "actionable_revisions": ["Revise scope completely"]
            }],
            "retry_count": retries + 1
        }

    # Pass mock research and retrieval so external network calls are avoided during testing
    def mock_research(state):
        return {"research": {"company_summary": "Test Co", "industry": "Logistics"}}

    def mock_retrieval(state):
        return {"retrieved_cases": [{"title": "Past Project 1", "id": "proj-001"}]}

    app = create_proposal_graph(
        custom_research=mock_research,
        custom_retrieval=mock_retrieval,
        custom_critic=mock_failing_critic,
    )

    final_state = app.invoke(base_lead_state)

    assert final_state["retry_count"] == 2
    assert len(final_state["critic_logs"]) == 2
    assert final_state["critic_logs"][-1]["passed"] is False