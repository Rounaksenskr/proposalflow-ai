from langgraph.graph import StateGraph, START, END
from proposal_bot.state import ProposalState


# --- Mock Node Handlers ---

def ingestion_node(state: ProposalState) -> dict:
    print("[Node: Ingest] Validating lead input...")
    lead = state.get("lead", {})
    if not lead.get("client_name") or not lead.get("project_description"):
        raise ValueError("Lead missing required client_name or project_description.")
    return {"final_status": "in_progress"}


def research_node(state: ProposalState) -> dict:
    client_name = state["lead"].get("client_name", "Unknown")
    print(f"[Node: Research] Generating mock intelligence profile for '{client_name}'...")
    mock_research = {
        "company_summary": f"{client_name} specializes in logistics and freight tracking.",
        "industry": "Supply Chain & Logistics",
        "pain_points": ["Manual spreadsheet updates", "Lack of real-time shipment alerts"],
        "identified_tech": ["PostgreSQL", "Legacy Excel"],
        "source_urls": ["https://example.com/company"]
    }
    return {"research": mock_research}


def proposal_generator_node(state: ProposalState) -> dict:
    attempt = state.get("retry_count", 0) + 1
    print(f"[Node: Generator] Synthesizing proposal draft (Iteration #{attempt})...")
    
    # Read latest critic feedback if retrying
    critique_context = ""
    if state.get("critic_logs"):
        latest = state["critic_logs"][-1]
        critique_context = f" Addressing feedback: {latest.get('actionable_revisions')}"

    mock_proposal = {
        "executive_summary": f"Custom logistics management platform.{critique_context}",
        "scope_of_work": [
            "Architecture & Database Schema Design",
            "FastAPI REST Endpoints",
            "Interactive Dashboard Frontend"
        ],
        "recommended_tech_stack": ["FastAPI", "React", "PostgreSQL", "Docker"],
        "timeline_and_phases": "4 weeks across two 2-week sprints",
        "estimated_pricing": state["lead"].get("budget") or "$3,500",
        "relevant_experience": "Built real-time tracking engine for Regional Freight Corp."
    }
    return {"proposal": mock_proposal}


def critic_node(state: ProposalState) -> dict:
    retries = state.get("retry_count", 0)
    print(f"[Node: Critic] Evaluating proposal draft against requirements (Retry Count: {retries})...")

    # Simulate failure on iteration 0, pass on iteration 1
    if retries == 0:
        feedback = {
            "passed": False,
            "score": 6,
            "missing_requirements": ["Authentication specifics omitted."],
            "hallucinated_claims": [],
            "actionable_revisions": ["Explicitly mention JWT auth and role-based access control."]
        }
    else:
        feedback = {
            "passed": True,
            "score": 9,
            "missing_requirements": [],
            "hallucinated_claims": [],
            "actionable_revisions": []
        }

    return {
        "critic_logs": [feedback],
        "retry_count": retries + 1
    }


# --- Conditional Routing Logic ---

def route_critic_decision(state: ProposalState) -> str:
    latest_review = state["critic_logs"][-1]
    passed = latest_review.get("passed", False)
    retries = state.get("retry_count", 0)

    if passed:
        print("[Router: Decision] Critic PASSED -> Reached acceptance criteria.")
        return "approved"

    if retries >= 2:
        print("[Router: Decision] Retry limit hit (>= 2) -> Breaking loop.")
        return "max_retries_exceeded"

    print("[Router: Decision] Critic FAILED -> Routing back to Generator for self-correction.")
    return "regenerate"


# --- Graph Construction ---

def create_proposal_graph():
    workflow = StateGraph(ProposalState)

    workflow.add_node("ingest", ingestion_node)
    workflow.add_node("research", research_node)
    workflow.add_node("generator", proposal_generator_node)
    workflow.add_node("critic", critic_node)

    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "research")
    workflow.add_edge("research", "generator")
    workflow.add_edge("generator", "critic")

    workflow.add_conditional_edges(
        "critic",
        route_critic_decision,
        {
            "regenerate": "generator",
            "approved": END,
            "max_retries_exceeded": END,
        }
    )

    return workflow.compile()