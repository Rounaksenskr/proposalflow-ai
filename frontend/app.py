import streamlit as st
import httpx

API_BASE_URL = "http://127.0.0.1:8000/api"

st.set_page_config(
    page_title="ProposalFlow AI — Review Console",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ ProposalFlow AI")
st.caption("Human-in-the-Loop Review Dashboard & Lead Ingestion")

# ---------------------------------------------------------
# Sidebar: Submit New Lead
# ---------------------------------------------------------
with st.sidebar:
    st.header("📥 Ingest New Lead")
    with st.form("lead_form", clear_on_submit=False):
        client_name = st.text_input("Client / Company Name", placeholder="Apex Logistics Group")
        website = st.text_input("Website URL (Optional)", placeholder="https://apexlogistics.example")
        budget = st.text_input("Budget", placeholder="$5,000")
        deadline = st.text_input("Deadline", placeholder="4 weeks")
        project_description = st.text_area(
            "Project Description (Min 10 chars)",
            placeholder="We need an automated dispatch routing dashboard using React and FastAPI.",
            height=120,
        )
        submit_btn = st.form_submit_button("Run Agent Pipeline", use_container_width=True)

    if submit_btn:
        if len(project_description.strip()) < 10:
            st.error("Project description must be at least 10 characters long.")
        elif not client_name.strip():
            st.error("Client name is required.")
        else:
            with st.spinner("Agent researching via Tavily, retrieving cases, and drafting proposal..."):
                payload = {
                    "client_name": client_name.strip(),
                    "website": website.strip() or None,
                    "budget": budget.strip() or None,
                    "deadline": deadline.strip() or None,
                    "project_description": project_description.strip(),
                }
                try:
                    resp = httpx.post(f"{API_BASE_URL}/leads/submit", json=payload, timeout=90.0)
                    if resp.status_code == 202:
                        data = resp.json()
                        st.session_state["active_thread_id"] = data["thread_id"]
                        st.success(f"Draft ready! Thread ID: {data['thread_id']}")
                    else:
                        st.error(f"API Error ({resp.status_code}): {resp.text}")
                except Exception as exc:
                    st.error(f"Could not connect to FastAPI server at port 8000: {exc}")

# ---------------------------------------------------------
# Main Panel: Inspect State & Human-in-the-Loop Sign-off
# ---------------------------------------------------------
thread_id_input = st.text_input(
    "Active Thread ID",
    value=st.session_state.get("active_thread_id", ""),
    placeholder="lead_xxxxxxxx",
    help="Enter the thread ID returned by the agent workflow.",
)

if thread_id_input.strip():
    tid = thread_id_input.strip()
    try:
        resp = httpx.get(f"{API_BASE_URL}/proposals/{tid}", timeout=10.0)
        if resp.status_code == 200:
            state = resp.json()
            proposal = state.get("proposal") or {}
            critic_logs = state.get("critic_logs") or []
            research = state.get("research") or {}
            is_paused = state.get("is_paused", False)
            final_status = state.get("final_status")

            # Status Banner
            if is_paused:
                st.warning("⏸️ **State: Paused at Human Review node (`interrupt`). Action required.**")
            else:
                st.success(f"✅ **State: Completed (`{final_status}`)**")

            col_main, col_sidebar = st.columns([3, 2])

            with col_main:
                st.subheader("📄 Proposal Draft")
                with st.expander("Executive Summary", expanded=True):
                    st.write(proposal.get("executive_summary", "No summary generated."))

                with st.expander("Solution Architecture", expanded=True):
                    st.write(proposal.get("solution_architecture", "No architecture provided."))

                m1, m2 = st.columns(2)
                with m1:
                    st.metric("Estimated Pricing", proposal.get("estimated_pricing", "N/A"))
                with m2:
                    st.metric("Estimated Timeline", proposal.get("project_timeline", "N/A"))

            with col_sidebar:
                st.subheader("🧐 Critic Reflection Log")
                if critic_logs:
                    latest = critic_logs[-1]
                    score = latest.get("score", 0)
                    st.metric("Adversarial Score", f"{score}/10")
                    st.markdown(f"**Passed**: `{latest.get('passed', False)}`")

                    revisions = latest.get("revisions_required", [])
                    if revisions:
                        st.markdown("**Required Revisions Flagged:**")
                        for rev in revisions:
                            st.write(f"- {rev}")
                else:
                    st.info("No critic logs recorded.")

                if research:
                    with st.expander("🔍 Tavily Market Reconnaissance", expanded=False):
                        st.markdown(f"**Industry:** {research.get('industry', 'N/A')}")
                        st.markdown(f"**Summary:** {research.get('company_summary', 'N/A')}")
                        sources = research.get("source_urls", [])
                        if sources:
                            st.markdown("**Sources:**")
                            for s in sources:
                                st.markdown(f"- [{s}]({s})")

            # Human-in-the-Loop Action Controls
            if is_paused:
                st.divider()
                st.subheader("✍️ Human Review Action")
                feedback = st.text_input("Reviewer Feedback / Revision Notes", value="Approved for delivery.")

                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("✅ Approve & Persist", use_container_width=True, type="primary"):
                        with st.spinner("Resuming graph execution..."):
                            act_resp = httpx.post(
                                f"{API_BASE_URL}/proposals/{tid}/review",
                                json={"approved": True, "feedback": feedback},
                                timeout=30.0,
                            )
                            if act_resp.status_code == 200:
                                st.success("Proposal approved and committed to database!")
                                st.rerun()
                            else:
                                st.error(f"Error ({act_resp.status_code}): {act_resp.text}")

                with btn_col2:
                    if st.button("❌ Reject & Discard", use_container_width=True):
                        with st.spinner("Terminating graph execution..."):
                            act_resp = httpx.post(
                                f"{API_BASE_URL}/proposals/{tid}/review",
                                json={"approved": False, "feedback": feedback},
                                timeout=30.0,
                            )
                            if act_resp.status_code == 200:
                                st.warning("Proposal rejected and discarded.")
                                st.rerun()
                            else:
                                st.error(f"Error ({act_resp.status_code}): {act_resp.text}")

        elif resp.status_code == 404:
            st.error(f"Thread '{tid}' not found in state checkpointer.")
        else:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
    except Exception as exc:
        st.error(f"Connection failed: {exc}")
else:
    st.info("Submit a lead from the sidebar or enter a Thread ID above to inspect.")