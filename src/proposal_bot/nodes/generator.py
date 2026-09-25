import json
from langchain_groq import ChatGroq

from proposal_bot.config import settings
from proposal_bot.state import ProposalState, ProposalDraft
from proposal_bot.prompts import (
    PROPOSAL_GENERATOR_SYSTEM_PROMPT,
    PROPOSAL_GENERATOR_USER_PROMPT,
)


def proposal_generator_node(state: ProposalState) -> dict:
    attempt = state.get("retry_count", 0) + 1
    print(f"\n[Node: Generator] Synthesizing proposal draft (Iteration #{attempt})...")

    lead = state.get("lead", {})
    research = state.get("research", {}) or {}
    retrieved = state.get("retrieved_cases", [])

    # Format retrieved case studies
    cases_text = ""
    for idx, c in enumerate(retrieved, start=1):
        cases_text += (
            f"Case #{idx}: {c.get('title')} ({c.get('industry')})\n"
            f"Tech Stack: {', '.join(c.get('technologies', []))}\n"
            f"Summary: {c.get('summary')}\n\n"
        )
    if not cases_text:
        cases_text = "No internal case studies found. Ground strictly on standard best practices."

    # Format previous critique if available
    critique_text = "First iteration. No prior critiques."
    if state.get("critic_logs"):
        latest = state["critic_logs"][-1]
        critique_text = (
            f"Previous Score: {latest.get('score')}/10\n"
            f"Required Revisions:\n"
            + "\n".join(f"- {rev}" for rev in latest.get("actionable_revisions", []))
        )

    user_prompt = PROPOSAL_GENERATOR_USER_PROMPT.format(
        client_name=lead.get("client_name", "Prospective Client"),
        website=lead.get("website", "N/A"),
        project_description=lead.get("project_description", ""),
        budget=lead.get("budget", "Flexible / TBD"),
        deadline=lead.get("deadline", "Flexible / TBD"),
        industry=research.get("industry", "Technology"),
        company_summary=research.get("company_summary", "N/A"),
        pain_points=", ".join(research.get("pain_points", [])) or "N/A",
        identified_tech=", ".join(research.get("identified_tech", [])) or "N/A",
        retrieved_cases=cases_text.strip(),
        critic_feedback=critique_text,
    )

    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=0.2,
    ).with_structured_output(ProposalDraft)

    proposal: ProposalDraft = llm.invoke([
        {"role": "system", "content": PROPOSAL_GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])

    return {"proposal": proposal.model_dump()}