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
    """Ensure the loop terminates cleanly after 2 retries if critic keeps failing."""

    def always_fail_critic(state):
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

    # Pass the failing critic directly into the graph factory
    app = create_proposal_graph(custom_critic=always_fail_critic)
    final_state = app.invoke(base_lead_state)

    assert final_state["retry_count"] == 2
    assert len(final_state["critic_logs"]) == 2
    assert final_state["critic_logs"][-1]["passed"] is False