import uuid
import sqlite3
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from proposal_bot.graph import create_proposal_graph
from proposal_bot.api.schemas import (
    LeadSubmitRequest,
    HumanReviewRequest,
    LeadSubmitResponse,
    ProposalStatusResponse,
    ProposalReviewResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Proposals"])

# Prepare directory & configure SQLite checkpointer with WAL mode for concurrency
Path("proposal_db").mkdir(exist_ok=True)
conn = sqlite3.connect("proposal_db/checkpoints.sqlite", check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA busy_timeout=5000;")
checkpointer = SqliteSaver(conn)

graph_app = create_proposal_graph(checkpointer=checkpointer)


@router.post("/leads/submit", response_model=LeadSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_lead(payload: LeadSubmitRequest):
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
        "critic_attempts": 0,
        "revision_count": 0,
        "retry_count": 0,
        "human_approved": None,
        "human_feedback": None,
        "final_status": "received",
    }

    try:
        # Execute graph until it hits interrupt() at human_review
        graph_app.invoke(initial_state, config=config)
    except Exception as exc:
        logger.error("[API: Submit] Pipeline failed on thread %s: %s", thread_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Pipeline processing failed.", "thread_id": thread_id, "error": str(exc)},
        )

    # Inspect snapshot to verify it is waiting at the review step
    snapshot = graph_app.get_state(config)
    if not snapshot.next:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Graph completed unexpectedly without pausing for review.", "thread_id": thread_id},
        )

    current_proposal = snapshot.values.get("proposal")
    critic_logs = snapshot.values.get("critic_logs", [])
    latest_critic = critic_logs[-1] if critic_logs else None

    return {
        "message": "Lead processed. Proposal ready for human approval.",
        "thread_id": thread_id,
        "status": "awaiting_approval",
        "proposal_draft": current_proposal,
        "critic_evaluation": latest_critic,
    }


@router.get("/proposals/{thread_id}", response_model=ProposalStatusResponse)
def get_proposal_status(thread_id: str):
    """Retrieves current proposal draft and approval status for a given thread."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph_app.get_state(config)

    if not snapshot or not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )

    return {
        "thread_id": thread_id,
        "is_paused": bool(snapshot.next),
        "next_node": list(snapshot.next),
        "final_status": snapshot.values.get("final_status"),
        "proposal": snapshot.values.get("proposal"),
        "critic_logs": snapshot.values.get("critic_logs"),
        "human_approved": snapshot.values.get("human_approved"),
    }


@router.post("/proposals/{thread_id}/review", response_model=ProposalReviewResponse)
def review_proposal(thread_id: str, decision: HumanReviewRequest):
    """Submits human review decision and resumes graph execution to persist data."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph_app.get_state(config)

    if not snapshot or not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )

    # Guard: verify graph is actively awaiting review
    if "human_review" not in snapshot.next:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Proposal is not currently awaiting review. Current next state: {list(snapshot.next)}",
        )

    try:
        final_state = graph_app.invoke(
            Command(resume={"approved": decision.approved, "feedback": decision.feedback}),
            config=config,
        )
    except Exception as exc:
        logger.error("[API: Review] Resumption failed on thread %s: %s", thread_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to resume proposal workflow.", "thread_id": thread_id, "error": str(exc)},
        )

    approved = final_state.get("human_approved", decision.approved)
    return {
        "message": "Proposal approved and persisted." if approved else "Proposal rejected and discarded.",
        "thread_id": thread_id,
        "final_status": final_state.get("final_status"),
        "human_approved": approved,
    }