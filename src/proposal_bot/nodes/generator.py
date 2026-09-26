import json
import logging
from langchain_groq import ChatGroq

from proposal_bot.config import settings
from proposal_bot.state import ProposalState, ProposalDraft
from proposal_bot.prompts import (
    PROPOSAL_GENERATOR_SYSTEM_PROMPT,
    PROPOSAL_GENERATOR_USER_PROMPT,
)

logger = logging.getLogger(__name__)


def proposal_generator_node(state: ProposalState) -> dict:
    critic_logs = state.get("critic_logs", [])
    current_revisions = state.get("revision_count", 0)

    # If critic logs exist, this invocation is a revision
    if critic_logs:
        current_revisions += 1
        print(f"\n[Node: Generator] Revising proposal draft (Revision #{current_revisions})...")
    else:
        print("\n[Node: Generator] Synthesizing initial proposal draft...")

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

    # Format previous critique safely
    critique_text = "First iteration. No prior critiques."
    if critic_logs:
        latest = critic_logs[-1]
        critique_text = (
            f"Previous Score: {latest.get('score', 0)}/10\n"
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

    try:
        proposal: ProposalDraft = llm.invoke([
            {"role": "system", "content": PROPOSAL_GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        proposal_dict = proposal.model_dump()
    except Exception as exc:
        logger.error("[Node: Generator] LLM generation or validation failed: %s", exc)
        print(f"[Node: Generator] WARNING: Proposal synthesis failed ({exc}). Using fallback draft.")
        proposal_dict = {
            "executive_summary": f"Draft proposal for {lead.get('client_name', 'Client')}. Automated synthesis encountered a temporary model issue.",
            "scope_of_work": ["Requirements analysis", "Implementation architecture", "Final delivery"],
            "recommended_tech_stack": ["Python", "FastAPI"],
            "timeline_and_phases": "Phase 1: Discovery (1 week), Phase 2: Implementation (3 weeks)",
            "estimated_pricing": lead.get("budget", "To be finalized upon technical discovery"),
            "relevant_experience": "Experience with modern scalable cloud integrations.",
        }

    return {
        "proposal": proposal_dict,
        "revision_count": current_revisions,
    }