from proposal_bot.graph import create_proposal_graph


def run_pipeline():
    print("========================================")
    print("ProposalFlow AI — Testing Core Graph Flow")
    print("========================================\n")

    app = create_proposal_graph()

    initial_state = {
        "lead": {
            "client_name": "Apex Logistics Group",
            "website": "https://apexlogistics.example",
            "project_description": "Need a real-time dispatch dashboard with React & FastAPI.",
            "budget": "$4,000",
            "deadline": "4 weeks"
        },
        "research": None,
        "retrieved_cases": [],
        "proposal": None,
        "critic_logs": [],
        "retry_count": 0,
        "human_approved": None,
        "human_feedback": None,
        "final_status": "pending"
    }

    final_state = app.invoke(initial_state)

    print("\n========================================")
    print("Workflow Execution Complete")
    print("========================================")
    print(f"Total Iterations: {final_state['retry_count']}")
    print(f"Critic Evaluation History: {len(final_state['critic_logs'])} entries logged")
    print(f"Final Critic Score: {final_state['critic_logs'][-1]['score']}/10")
    print(f"Latest Summary: {final_state['proposal']['executive_summary']}")


if __name__ == "__main__":
    run_pipeline()