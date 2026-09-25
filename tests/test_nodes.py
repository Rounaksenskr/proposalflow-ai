import pytest
from proposal_bot.state import ProposalDraft, CriticFeedback


def test_proposal_draft_schema_validation():
    """Verify ProposalDraft validates required fields and types."""
    valid_data = {
        "executive_summary": "High-impact dispatch platform for freight management.",
        "scope_of_work": ["Design Schema", "Build Endpoints", "Frontend UI"],
        "recommended_tech_stack": ["FastAPI", "React", "PostgreSQL"],
        "timeline_and_phases": "4 weeks across 2 milestones",
        "estimated_pricing": "$4,500",
        "relevant_experience": "Delivered similar project for FleetCo."
    }

    draft = ProposalDraft(**valid_data)
    assert draft.executive_summary.startswith("High-impact")
    assert len(draft.scope_of_work) == 3
    assert "FastAPI" in draft.recommended_tech_stack


def test_critic_feedback_score_constraints():
    """Verify CriticFeedback enforces score boundaries (1-10)."""
    valid_feedback = {
        "passed": True,
        "score": 9,
        "missing_requirements": [],
        "hallucinated_claims": [],
        "actionable_revisions": []
    }
    feedback = CriticFeedback(**valid_feedback)
    assert feedback.passed is True
    assert feedback.score == 9

    # Assert out-of-bound scores raise ValidationError
    with pytest.raises(Exception):
        CriticFeedback(
            passed=False,
            score=15,  # Invalid: gt 10
            missing_requirements=[],
            hallucinated_claims=[],
            actionable_revisions=[]
        )