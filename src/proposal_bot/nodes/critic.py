import json
from langchain_groq import ChatGroq

from proposal_bot.config import settings
from proposal_bot.state import ProposalState, CriticFeedback
from proposal_bot.prompts import CRITIC_SYSTEM_PROMPT, CRITIC_USER_PROMPT


def critic_node(state: ProposalState) -> dict:
    retries = state.get("retry_count", 0)
    print(f"[Node: Critic] Adversarial review in progress (Retry count so far: {retries})...")

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

    feedback: CriticFeedback = llm.invoke([
        {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])

    print(f"[Node: Critic] Evaluation Result: Score={feedback.score}/10, Passed={feedback.passed}")
    if not feedback.passed:
        print(f"[Node: Critic] Revisions Required: {feedback.actionable_revisions}")

    return {
        "critic_logs": [feedback.model_dump()],
        "retry_count": retries + 1,
    }