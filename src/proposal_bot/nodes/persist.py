import logging
from sqlalchemy.exc import IntegrityError
from proposal_bot.state import ProposalState
from proposal_bot.db.session import SessionLocal
from proposal_bot.db.models import Client, Lead, Proposal
from proposal_bot.integrations.crm import sync_proposal_to_crm
from proposal_bot.integrations.notifications import send_final_status_notification

logger = logging.getLogger(__name__)


def persist_node(state: ProposalState) -> dict:
    """Commits records to database, syncs with CRM, and dispatches final alerts."""
    lead_data = state.get("lead", {})
    client_name = lead_data.get("client_name", "Unknown Client")
    thread_id = lead_data.get("thread_id", "manual_run")
    proposal_content = state.get("proposal", {})
    print(f"\n[Node: Persist] Writing records to application database for '{client_name}' (Thread: {thread_id})...")

    db = SessionLocal()
    try:
        # 1. Idempotent Upsert for Client
        client = db.query(Client).filter(Client.name == client_name).first()
        if not client:
            try:
                client = Client(name=client_name, website=lead_data.get("website"))
                db.add(client)
                db.flush()
            except IntegrityError:
                db.rollback()
                client = db.query(Client).filter(Client.name == client_name).first()
                if not client:
                    raise RuntimeError(f"Could not resolve client record for '{client_name}'")

        # 2. Idempotent Upsert for Lead
        lead_record = db.query(Lead).filter(Lead.thread_id == thread_id).first()
        if not lead_record:
            lead_record = Lead(
                client_id=client.id,
                project_description=lead_data.get("project_description", ""),
                budget=lead_data.get("budget"),
                deadline=lead_data.get("deadline"),
                thread_id=thread_id,
                status=state.get("final_status", "approved"),
            )
            db.add(lead_record)
            db.flush()
        else:
            lead_record.status = state.get("final_status", "approved")
            lead_record.budget = lead_data.get("budget") or lead_record.budget
            lead_record.deadline = lead_data.get("deadline") or lead_record.deadline

        # 3. Idempotent Upsert for Proposal Artifact
        retrieved_ids = [c.get("id") for c in state.get("retrieved_cases", []) if c.get("id")]
        revisions = state.get("revision_count", 0)
        is_approved = bool(state.get("human_approved", False))

        proposal_record = db.query(Proposal).filter(Proposal.lead_id == lead_record.id).first()
        if not proposal_record:
            proposal_record = Proposal(
                lead_id=lead_record.id,
                research_summary=state.get("research"),
                retrieved_case_ids=retrieved_ids,
                proposal_content=proposal_content,
                critic_logs=state.get("critic_logs", []),
                iterations_count=revisions + 1,
                human_approved=is_approved,
                human_notes=state.get("human_feedback"),
            )
            db.add(proposal_record)
        else:
            proposal_record.research_summary = state.get("research")
            proposal_record.retrieved_case_ids = retrieved_ids
            proposal_record.proposal_content = proposal_content
            proposal_record.critic_logs = state.get("critic_logs", [])
            proposal_record.iterations_count = revisions + 1
            proposal_record.human_approved = is_approved
            proposal_record.human_notes = state.get("human_feedback")

        db.commit()
        print(f"[Node: Persist] Database commit successful. Proposal ID: {proposal_record.id}")

        # Outbound Integrations (safely isolated)
        sync_proposal_to_crm(
            lead_data=lead_data,
            proposal_data=proposal_content,
            thread_id=thread_id,
            status="approved",
        )
        send_final_status_notification(
            thread_id=thread_id,
            client_name=client_name,
            status="approved",
        )

        return {"final_status": "persisted"}

    except Exception as exc:
        db.rollback()
        logger.exception("[Node: Persist] Failed to commit records to database: %s", exc)
        print(f"[Node: Persist] ERROR: Database transaction failed ({exc}). Rolled back.")
        return {"final_status": "persist_failed"}
    finally:
        db.close()