"""Node for validating and normalizing raw inbound client leads."""
from proposal_bot.state import ProposalState, LeadInput


def ingestion_node(state: ProposalState) -> dict:
    """Validates the incoming lead payload and initializes workflow state."""
    raw_lead = state.get("lead", {})
    print(f"[Node: Ingest] Validating inbound payload for '{raw_lead.get('client_name', 'Unknown')}'...")

    # Validate against Pydantic contract
    validated_lead = LeadInput(**raw_lead)

    return {
        "lead": validated_lead.model_dump(),
        "final_status": "in_progress",
    }