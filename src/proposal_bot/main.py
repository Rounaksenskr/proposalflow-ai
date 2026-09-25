import sqlite3
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from proposal_bot.graph import create_proposal_graph


def run_pipeline():
    print("========================================")
    print("ProposalFlow AI — Day 3 End-to-End Run")
    print("========================================\n")

    # 1. Ensure database directory exists and set up SQLite checkpointer
    Path("proposal_db").mkdir(exist_ok=True)
    conn = sqlite3.connect("proposal_db/checkpoints.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # 2. Compile graph with checkpointer
    app = create_proposal_graph(checkpointer=checkpointer)

    # 3. Define unique thread id for this execution run
    thread_id = "lead_run_001"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "lead": {
            "client_name": "Apex Logistics Group",
            "website": "https://apexlogistics.example",
            "project_description": "We need a real-time dispatch operations dashboard with React and FastAPI, integrated with driver authentication.",
            "budget": "$4,500",
            "deadline": "5 weeks",
        },
        "research": None,
        "retrieved_cases": [],
        "proposal": None,
        "critic_logs": [],
        "retry_count": 0,
        "human_approved": None,
        "human_feedback": None,
        "final_status": "pending",
    }

    print(f"Starting execution for Thread: {thread_id}...\n")

    # 4. First execution: runs until human_review interrupt
    app.invoke(initial_state, config=config)

    # 5. Check snapshot to verify graph paused at interrupt
    snapshot = app.get_state(config)
    if snapshot.next:
        print("\n[State Snapshot] Graph suspended execution at node:", snapshot.next)
        
        # Interactive CLI prompt simulating human reviewer
        user_input = input("\nApprove this proposal? (y/n): ").strip().lower()
        is_approved = user_input == "y"
        notes = "Approved via CLI review" if is_approved else "Scope needs adjustment"

        print(f"\nResuming execution with decision: Approved={is_approved}...")

        # 6. Resume execution passing human decision to the interrupt
        final_state = app.invoke(
            Command(resume={"approved": is_approved, "feedback": notes}),
            config=config,
        )

        print("\n========================================")
        print("Workflow Completed Successfully")
        print("========================================")
        print(f"Final Status: {final_state.get('final_status')}")
        print(f"Human Approved: {final_state.get('human_approved')}")
        print(f"Total Iterations: {final_state.get('retry_count')}")
        if final_state.get("critic_logs"):
            print(f"Final Critic Score: {final_state['critic_logs'][-1].get('score')}/10")
    else:
        print("\nWorkflow completed without triggering interrupt.")


if __name__ == "__main__":
    run_pipeline()