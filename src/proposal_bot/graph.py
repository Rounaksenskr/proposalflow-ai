from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from proposal_bot.state import ProposalState

# Day 2 Live Nodes
from proposal_bot.nodes.ingestion import ingestion_node
from proposal_bot.nodes.research import research_node
from proposal_bot.nodes.retrieval import retrieval_node

# Day 3 Live Nodes
from proposal_bot.nodes.generator import proposal_generator_node
from proposal_bot.nodes.critic import critic_node


# --- Human-in-the-Loop Review Node ---

def human_review_node(state: ProposalState) -> dict:
    """Suspends graph execution via interrupt() and waits for human approval."""
    proposal = state.get("proposal", {})
    print("\n" + "=" * 60)
    print("🚨 HUMAN-IN-THE-LOOP CHECKPOINT: PROPOSAL REQUIRES APPROVAL 🚨")
    print("=" * 60)
    print(f"Executive Summary: {proposal.get('executive_summary')}")
    print(f"Scope: {proposal.get('scope_of_work')}")
    print(f"Tech Stack: {proposal.get('recommended_tech_stack')}")
    print(f"Pricing: {proposal.get('estimated_pricing')}")
    print(f"Experience Cited: {proposal.get('relevant_experience')}")
    print("=" * 60)

    # Interrupt execution; serializes and yields payload to the caller
    human_response = interrupt({
        "task": "review_proposal",
        "proposal": proposal,
    })

    approved = human_response.get("approved", False)
    notes = human_response.get("feedback", "")

    print(f"\n[Node: Human Review] Decision received: Approved={approved}, Notes='{notes}'")

    return {
        "human_approved": approved,
        "human_feedback": notes,
        "final_status": "approved" if approved else "rejected",
    }


# --- Conditional Routing Logic ---

def route_critic_decision(state: ProposalState) -> str:
    latest_review = state["critic_logs"][-1]
    passed = latest_review.get("passed", False)
    retries = state.get("retry_count", 0)

    if passed:
        print("[Router: Decision] Critic PASSED -> Routing to Human Review.")
        return "human_review"

    if retries >= 2:
        print("[Router: Decision] Circuit Breaker hit (>= 2 retries) -> Escalating to Human Review.")
        return "human_review"

    print("[Router: Decision] Critic FAILED -> Routing back to Generator for self-correction.")
    return "generator"


# --- Graph Factory ---

def create_proposal_graph(
    checkpointer=None,
    custom_ingest=None,
    custom_research=None,
    custom_retrieval=None,
    custom_generator=None,
    custom_critic=None,
    custom_human=None,
):
    workflow = StateGraph(ProposalState)

    # Register all 6 pipeline nodes
    workflow.add_node("ingest", custom_ingest or ingestion_node)
    workflow.add_node("research", custom_research or research_node)
    workflow.add_node("retrieval", custom_retrieval or retrieval_node)
    workflow.add_node("generator", custom_generator or proposal_generator_node)
    workflow.add_node("critic", custom_critic or critic_node)
    workflow.add_node("human_review", custom_human or human_review_node)

    # Execution Flow: Ingest -> Research -> Retrieval -> Generator -> Critic
    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "research")
    workflow.add_edge("research", "retrieval")
    workflow.add_edge("retrieval", "generator")
    workflow.add_edge("generator", "critic")

    # Conditional Reflection Edge
    workflow.add_conditional_edges(
        "critic",
        route_critic_decision,
        {
            "generator": "generator",
            "human_review": "human_review",
        }
    )

    # Human review leads to terminal END
    workflow.add_edge("human_review", END)

    return workflow.compile(checkpointer=checkpointer)