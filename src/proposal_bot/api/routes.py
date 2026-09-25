import uuid
import sqlite3
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from proposal_bot.graph import create_proposal_graph
from proposal_bot.state import LeadInput

router = APIRouter(prefix="/api", tags=["Proposals"])

# Persistent SQLite checkpointer for web requests
conn = sqlite3.connect("proposal_db/checkpoints.sqlite", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph_app = create_proposal_graph(checkpointer=checkpointer)


class HumanReviewPayload(BaseModel):
    approved: bool
    feedback: Optional[str] = "Approved via API"


@router.post("/leads/submit", status_code=status.HTTP_202_ACCEPTED)
def submit_lead(payload: LeadInput):
    """Submits a lead and executes the agent pipeline until human review is required."""
    thread_id = f"lead_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    lead_dict = payload.model_dump()
    lead_dict["thread_id"] = thread_id

    initial_state = {
        "lead": lead_dict,
        "research": None,
        "retrieved_cases": [],
        "proposal": None,
        "critic_logs": [],
        "retry_count": 0,
        "human_approved": None,
        "human_feedback": None,
        "final_status": "received",
    }

    # Execute graph until it hits interrupt() at human_review
    graph_app.invoke(initial_state, config=config)

    # Inspect the snapshot to verify it is waiting at the review step
    snapshot = graph_app.get_state(config)
    if not snapshot.next:
        raise HTTPException(
            status_code=500, detail="Graph completed unexpectedly without pausing for review."
        )

    current_proposal = snapshot.values.get("proposal")
    latest_critic = (
        snapshot.values.get("critic_logs")[-1]
        if snapshot.values.get("critic_logs")
        else None
    )

    return {
        "message": "Lead processed. Proposal ready for human approval.",
        "thread_id": thread_id,
        "status": "awaiting_approval",
        "proposal_draft": current_proposal,
        "critic_evaluation": latest_critic,
    }


@router.get("/proposals/{thread_id}")
def get_proposal_status(thread_id: str):
    """Retrieves current proposal draft and approval status for a given thread."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph_app.get_state(config)

    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Thread ID not found.")

    return {
        "thread_id": thread_id,
        "is_paused": bool(snapshot.next),
        "next_node": snapshot.next,
        "final_status": snapshot.values.get("final_status"),
        "proposal": snapshot.values.get("proposal"),
        "critic_logs": snapshot.values.get("critic_logs"),
    }


@router.post("/proposals/{thread_id}/review")
def review_proposal(thread_id: str, decision: HumanReviewPayload):
    """Submits human review decision and resumes graph execution to persist data."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph_app.get_state(config)

    if not snapshot.next:
        raise HTTPException(
            status_code=400, detail="Proposal is not currently awaiting review."
        )

    # Resume graph execution passing review parameters
    final_state = graph_app.invoke(
        Command(resume={"approved": decision.approved, "feedback": decision.feedback}),
        config=config,
    )

    return {
        "message": "Review submitted and proposal recorded.",
        "thread_id": thread_id,
        "final_status": final_state.get("final_status"),
        "human_approved": final_state.get("human_approved"),
    }