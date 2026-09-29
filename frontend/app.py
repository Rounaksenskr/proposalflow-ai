import io
import re
from datetime import datetime
from xml.sax.saxutils import escape

import streamlit as st
import httpx
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

API_BASE_URL = "http://127.0.0.1:8000/api"


# ---------------------------------------------------------
# PDF Generation (ReportLab)
# ---------------------------------------------------------
def _pdf_clean(value):
    """Convert any value to safe plain text for ReportLab's built-in fonts."""
    if value is None:
        return ""
    text = str(value).replace("\\n", "\n").strip()
    # Built-in Helvetica has no glyph for the rupee sign; use a readable fallback.
    text = text.replace("\u20b9", "INR ")
    # Drop characters the built-in font cannot draw (e.g. emojis) instead of
    # letting them render as black boxes.
    return text.encode("cp1252", errors="ignore").decode("cp1252").strip()


def _pdf_markup(value):
    """Escape text for ReportLab Paragraph markup; supports **bold** and line breaks."""
    text = escape(_pdf_clean(value))
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return text.replace("\n", "<br/>")


def _pdf_as_list(value):
    """Normalize a field into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    elif isinstance(value, str):
        items = value.replace("\\n", "\n").split("\n")
    else:
        items = [value]
    cleaned = [_pdf_clean(item) for item in items]
    return [item for item in cleaned if item]


def generate_proposal_pdf(proposal, thread_id):
    """Build a PDF for the given proposal dict and return it as bytes."""
    proposal = proposal if isinstance(proposal, dict) else {}
    safe_thread_id = _pdf_clean(thread_id) or "N/A"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="Project Proposal",
        author="ProposalFlow AI",
    )

    base = getSampleStyleSheet()
    accent = colors.HexColor("#1F3A5F")

    title_style = ParagraphStyle(
        "ProposalTitle", parent=base["Title"], fontSize=22, leading=26,
        textColor=accent, alignment=0, spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "ProposalMeta", parent=base["Normal"], fontSize=9, leading=12,
        textColor=colors.grey, spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "ProposalHeading", parent=base["Heading2"], fontSize=13, leading=16,
        textColor=accent, spaceBefore=14, spaceAfter=6, keepWithNext=1,
    )
    body_style = ParagraphStyle(
        "ProposalBody", parent=base["Normal"], fontSize=10.5, leading=15,
        spaceAfter=4,
    )
    bullet_style = ParagraphStyle(
        "ProposalBullet", parent=body_style, leftIndent=14, bulletIndent=2,
    )
    price_style = ParagraphStyle(
        "ProposalPrice", parent=body_style, fontName="Helvetica-Bold",
        fontSize=13, leading=17, textColor=accent,
    )

    def add_bullets(story, items, empty_text):
        if not items:
            story.append(Paragraph(_pdf_markup(empty_text), body_style))
            return
        for item in items:
            story.append(Paragraph(_pdf_markup(item), bullet_style, bulletText="\u2022"))

    story = [
        Paragraph("Project Proposal", title_style),
        Paragraph(
            f"Thread ID: {_pdf_markup(safe_thread_id)} &nbsp;|&nbsp; "
            f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}",
            meta_style,
        ),
        HRFlowable(width="100%", thickness=1, color=accent, spaceAfter=4),
    ]

    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    summary = _pdf_clean(proposal.get("executive_summary")) or "No summary generated."
    story.append(Paragraph(_pdf_markup(summary), body_style))

    # Scope of Work
    story.append(Paragraph("Scope of Work", heading_style))
    add_bullets(story, _pdf_as_list(proposal.get("scope_of_work")), "No scope provided.")

    # Recommended Tech Stack
    story.append(Paragraph("Recommended Tech Stack", heading_style))
    stack_items = _pdf_as_list(proposal.get("recommended_tech_stack"))
    stack_text = ", ".join(stack_items) if stack_items else "N/A"
    story.append(Paragraph(_pdf_markup(stack_text), body_style))

    # Estimated Pricing
    story.append(Paragraph("Estimated Pricing", heading_style))
    pricing = _pdf_clean(proposal.get("estimated_pricing")) or "N/A"
    story.append(Paragraph(_pdf_markup(pricing), price_style))

    # Timeline
    story.append(Paragraph("Timeline", heading_style))
    timeline_lines = _pdf_as_list(proposal.get("timeline_and_phases"))
    if not timeline_lines:
        story.append(Paragraph("N/A", body_style))
    for line in timeline_lines:
        if line.startswith(("- ", "* ")):
            story.append(Paragraph(_pdf_markup(line[2:]), bullet_style, bulletText="\u2022"))
        else:
            story.append(Paragraph(_pdf_markup(line), body_style))

    story.append(Spacer(1, 6))

    def draw_footer(canvas, pdf_doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(20 * mm, 10 * mm, f"ProposalFlow AI  |  Thread {safe_thread_id}")
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {pdf_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()


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

                with st.expander("Scope of Work", expanded=True):
                    scope = proposal.get("scope_of_work", [])
                    if scope:
                        for item in scope:
                            st.write(f"- {item}")
                    else:
                        st.write("No scope provided.")

                with st.expander("Recommended Tech Stack", expanded=False):
                    stack = proposal.get("recommended_tech_stack", [])
                    st.write(", ".join(stack) if stack else "N/A")

                st.metric("Estimated Pricing", proposal.get("estimated_pricing", "N/A"))

                with st.expander("Timeline", expanded=True):
                    timeline = proposal.get("timeline_and_phases", "N/A")
                    normalized = timeline.replace("\\n", "\n") if isinstance(timeline, str) else str(timeline)
                    for line in normalized.split("\n"):
                        line = line.strip()
                        if line:
                            st.write(line)

                # Download Proposal as PDF
                pdf_bytes = None
                try:
                    pdf_bytes = generate_proposal_pdf(proposal, tid)
                except Exception as pdf_exc:
                    st.error(f"Could not generate PDF: {pdf_exc}")

                if pdf_bytes:
                    safe_tid = re.sub(r"[^A-Za-z0-9_-]", "_", tid)
                    st.download_button(
                        label="📥 Download Proposal as PDF",
                        data=pdf_bytes,
                        file_name=f"proposal_{safe_tid}.pdf",
                        mime="application/pdf",
                        key=f"download_pdf_{safe_tid}",
                        use_container_width=True,
                    )

            with col_sidebar:
                st.subheader("🧐 Critic Reflection Log")
                if critic_logs:
                    latest = critic_logs[-1]
                    score = latest.get("score", 0)
                    st.metric("Adversarial Score", f"{score}/10")
                    st.markdown(f"**Passed**: `{latest.get('passed', False)}`")

                    missing = latest.get("missing_requirements", [])
                    if missing:
                        st.markdown("**Missing Requirements:**")
                        for m in missing:
                            st.write(f"- {m}")

                    revisions = latest.get("actionable_revisions", [])
                    if revisions:
                        st.markdown("**Actionable Revisions:**")
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