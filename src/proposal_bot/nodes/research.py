from typing import Any, Dict
from tavily import TavilyClient
from langchain_groq import ChatGroq

from proposal_bot.config import settings
from proposal_bot.state import ProposalState, ResearchArtifact
from proposal_bot.prompts import RESEARCH_SYSTEM_PROMPT, RESEARCH_USER_PROMPT


def research_node(state: ProposalState) -> dict:
    """Researches prospective client via Tavily and extracts structured business intelligence."""
    lead = state.get("lead", {})
    client_name = lead.get("client_name", "")
    website = lead.get("website", "")
    description = lead.get("project_description", "")

    print(f"[Node: Research] Conducting live market research on '{client_name}'...")

    # 1. Search via Tavily
    search_content = ""
    source_urls = []
    
    try:
        tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
        query = f"{client_name} company business overview technology products"
        search_res = tavily.search(query=query, max_results=3)
        
        snippets = []
        for r in search_res.get("results", []):
            snippets.append(f"Title: {r.get('title')}\nSnippet: {r.get('content')}\nURL: {r.get('url')}")
            source_urls.append(r.get("url"))
        search_content = "\n\n".join(snippets)
    except Exception as e:
        print(f"[Node: Research] Tavily search failed or skipped: {e}")
        search_content = f"No live search results available. Base info: {client_name} ({website})"

    # 2. Extract structured intelligence with LLM
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=0.1
    ).with_structured_output(ResearchArtifact)

    formatted_user_prompt = RESEARCH_USER_PROMPT.format(
        client_name=client_name,
        client_website=website or "Not provided",
        project_description=description,
        search_results=search_content or "No external context found."
    )

    try:
        artifact: ResearchArtifact = llm.invoke([
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": formatted_user_prompt}
        ])
        
        # Merge URLs discovered if LLM missed any
        if not artifact.source_urls and source_urls:
            artifact.source_urls = source_urls

        return {"research": artifact.model_dump()}
    except Exception as e:
        print(f"[Node: Research] Structured extraction error: {e}. Falling back to default.")
        fallback = ResearchArtifact(
            company_summary=f"{client_name} operates in standard industry domains.",
            industry="Technology & Services",
            pain_points=["Manual workflow inefficiencies"],
            identified_tech=[],
            source_urls=source_urls
        )
        return {"research": fallback.model_dump()}