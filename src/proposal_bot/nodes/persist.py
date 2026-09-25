from proposal_bot.state import ProposalState
from proposal_bot.db.session import SessionLocal
from proposal_bot.db.models import Client, Lead, Proposal


def persist_node(state: ProposalState) -> dict:
    """Commits client, lead, research, proposal, and review status to PostgreSQL/SQLite."""
    lead_data = state.get("lead", {})
    client_name = lead_data.get("client_name", "Unknown Client")
    print(f"\n[Node: Persist] Writing approved records to application database for '{client_name}'...")

    db = SessionLocal()
    try:
        # 1. Upsert / Create Client
        client = db.query(Client).filter(Client.name == client_name).first()
        if not client:
            client = Client(name=client_name, website=lead_data.get("website"))
            db.add(client)
            db.flush()

        # 2. Record Lead
        lead_record = Lead(
            client_id=client.id,
            project_description=lead_data.get("project_description", ""),
            budget=lead_data.get("budget"),
            deadline=lead_data.get("deadline"),
            thread_id=state.get("lead", {}).get("thread_id", "manual_run"),
            status=state.get("final_status", "completed"),
        )
        db.add(lead_record)
        db.flush()

        # 3. Record Proposal Artifact
        retrieved_ids = [c.get("id") for c in state.get("retrieved_cases", []) if c.get("id")]
        proposal_record = Proposal(
            lead_id=lead_record.id,
            research_summary=state.get("research"),
            retrieved_case_ids=retrieved_ids,
            proposal_content=state.get("proposal", {}),
            critic_logs=state.get("critic_logs", []),
            iterations_count=state.get("retry_count", 1),
            human_approved=bool(state.get("human_approved", False)),
            human_notes=state.get("human_feedback"),
        )
        db.add(proposal_record)
        db.commit()
        print(f"[Node: Persist] Database commit successful. Proposal ID: {proposal_record.id}")
    except Exception as e:
        db.rollback()
        print(f"[Node: Persist] Failed to commit records to database: {e}")
    finally:
        db.close()

    return {"final_status": "persisted"}