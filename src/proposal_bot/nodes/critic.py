import json
import logging
from langchain_groq import ChatGroq

from proposal_bot.config import settings
from proposal_bot.state import ProposalState, CriticFeedback
from proposal_bot.prompts import CRITIC_SYSTEM_PROMPT, CRITIC_USER_PROMPT

logger = logging.getLogger(__name__)


def critic_node(state: ProposalState) -> dict:
    attempts = state.get("critic_attempts", state.get("retry_count", 0)) + 1
    revisions = state.get("revision_count", 0)
    print(f"[Node: Critic] Adversarial review in progress (Evaluation #{attempts}, Generator revisions: {revisions})...")

    lead = state.get("lead", {})
    retrieved = state.get("retrieved_cases", [])
    proposal = state.get("proposal", {})

    user_prompt = CRITIC_USER_PROMPT.format(
        lead_json=json.dumps(lead, indent=2),
        retrieved_cases_json=json.dumps(retrieved, indent=2),
        proposal_json=json.dumps(proposal, indent=2),
    )

    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=0.0,
    ).with_structured_output(CriticFeedback)

    try:
        feedback: CriticFeedback = llm.invoke([
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        feedback_dict = feedback.model_dump()
    except Exception as exc:
        logger.error("[Node: Critic] LLM evaluation error or schema validation failure: %s", exc)
        print(f"[Node: Critic] WARNING: Automated evaluation failed ({exc}). Applying fail-safe fallback.")
        feedback_dict = {
            "passed": False,
            "score": 1,
            "missing_requirements": ["Automated critique service encountered an invocation error."],
            "hallucinated_claims": [],
            "actionable_revisions": ["Escalate to human review due to critic failure."],
        }

    # Deterministic enforcement: passed requires both explicit pass AND score >= 8
    score = feedback_dict.get("score", 0)
    is_passed = bool(feedback_dict.get("passed", False)) and (score >= 8)
    feedback_dict["passed"] = is_passed

    print(f"[Node: Critic] Evaluation Result: Score={score}/10, Passed={is_passed}")
    if not is_passed:
        print(f"[Node: Critic] Revisions Required: {feedback_dict.get('actionable_revisions', [])}")

    return {
        "critic_logs": [feedback_dict],
        "critic_attempts": attempts,
        "retry_count": attempts,  # Backward compatibility
    }