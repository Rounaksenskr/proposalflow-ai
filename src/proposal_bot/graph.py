import logging
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from proposal_bot.state import ProposalState
from proposal_bot.nodes.ingestion import ingestion_node
from proposal_bot.nodes.research import research_node
from proposal_bot.nodes.retrieval import retrieval_node
from proposal_bot.nodes.generator import proposal_generator_node
from proposal_bot.nodes.critic import critic_node
from proposal_bot.nodes.persist import persist_node
from proposal_bot.integrations.notifications import (
    send_review_needed_notification,
    send_final_status_notification,
)

logger = logging.getLogger(__name__)


# --- Human-in-the-Loop Review Node ---

def human_review_node(state: ProposalState) -> dict:
    proposal = state.get("proposal", {})
    lead = state.get("lead", {})
    thread_id = lead.get("thread_id", "unknown_thread")
    critic_logs = state.get("critic_logs", [])
    latest_critic = critic_logs[-1] if critic_logs else None

    # Outbound webhook alert before pausing (non-blocking)
    send_review_needed_notification(
        thread_id=thread_id,
        lead=lead,
        proposal=proposal,
        critic_log=latest_critic,
    )

    human_response = interrupt({
        "task": "review_proposal",
        "proposal": proposal,
    })

    if not isinstance(human_response, dict):
        human_response = {"approved": False, "feedback": "Malformed resume payload"}

    approved = bool(human_response.get("approved", False))
    notes = human_response.get("feedback", "")
    status = "approved" if approved else "rejected"

    print(f"\n[Node: Human Review] Decision applied: status='{status}', notes='{notes}'")

    if not approved:
        # Alert if rejected (approved branch is handled after persistence)
        send_final_status_notification(
            thread_id=thread_id,
            client_name=lead.get("client_name", "Unknown Client"),
            status="rejected",
        )

    return {
        "human_approved": approved,
        "human_feedback": notes,
        "final_status": status,
    }


# --- Routing Logic ---

def route_critic_decision(state: ProposalState) -> str:
    critic_logs = state.get("critic_logs", [])
    if not critic_logs:
        return "generator"

    latest_review = critic_logs[-1]
    passed = latest_review.get("passed", False)
    score = latest_review.get("score", 0)
    revisions = state.get("revision_count", 0)

    if passed and score >= 8:
        print(f"[Router: Critic] PASSED (Score={score}/10) -> Routing to Human Review.")
        return "human_review"

    if revisions >= 2:
        print(f"[Router: Critic] Circuit Breaker tripped ({revisions} revisions) -> Escalating to Human Review.")
        return "human_review"

    print(f"[Router: Critic] FAILED (Score={score}/10, Revisions={revisions}) -> Routing to Generator for revision {revisions + 1}.")
    return "generator"


def route_human_decision(state: ProposalState) -> str:
    """Routes to persistence on approval, or ends on rejection."""
    approved = state.get("human_approved", False)
    if approved:
        print("[Router: Human Decision] Proposal APPROVED -> Proceeding to persistence.")
        return "persist"

    print("[Router: Human Decision] Proposal REJECTED -> Terminating workflow without persistence.")
    return END


# --- Graph Factory ---

def create_proposal_graph(
    checkpointer=None,
    custom_ingest=None,
    custom_research=None,
    custom_retrieval=None,
    custom_generator=None,
    custom_critic=None,
    custom_human=None,
    custom_persist=None,
):
    workflow = StateGraph(ProposalState)

    workflow.add_node("ingest", custom_ingest or ingestion_node)
    workflow.add_node("research", custom_research or research_node)
    workflow.add_node("retrieval", custom_retrieval or retrieval_node)
    workflow.add_node("generator", custom_generator or proposal_generator_node)
    workflow.add_node("critic", custom_critic or critic_node)
    workflow.add_node("human_review", custom_human or human_review_node)
    workflow.add_node("persist", custom_persist or persist_node)

    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "research")
    workflow.add_edge("research", "retrieval")
    workflow.add_edge("retrieval", "generator")
    workflow.add_edge("generator", "critic")

    workflow.add_conditional_edges(
        "critic",
        route_critic_decision,
        {
            "generator": "generator",
            "human_review": "human_review",
        }
    )

    workflow.add_conditional_edges(
        "human_review",
        route_human_decision,
        {
            "persist": "persist",
            END: END,
        }
    )

    workflow.add_edge("persist", END)

    return workflow.compile(checkpointer=checkpointer)