import logging
from typing import Any, Dict, List
from tavily import TavilyClient
from langchain_groq import ChatGroq

from proposal_bot.config import settings
from proposal_bot.state import ProposalState, ResearchArtifact
from proposal_bot.prompts import RESEARCH_SYSTEM_PROMPT, RESEARCH_USER_PROMPT

logger = logging.getLogger(__name__)


def build_tavily_query(client_name: str, website: str, description: str) -> str:
    """Builds a high-precision search query using domain or keywords."""
    clean_domain = (
        website.replace("https://", "").replace("http://", "").strip("/")
        if website
        else ""
    )
    
    if clean_domain and "example.com" not in clean_domain:
        return f"site:{clean_domain} OR \"{client_name}\" business products services"
    
    # Extract core keywords from project description (first 60 chars) for specificity
    core_context = description[:60].replace("\n", " ").strip()
    return f"\"{client_name}\" {core_context} company overview services"


def research_node(state: ProposalState) -> dict:
    """Researches prospective client via Tavily and extracts structured business intelligence."""
    lead = state.get("lead", {})
    client_name = lead.get("client_name", "Unknown Client")
    website = lead.get("website", "")
    description = lead.get("project_description", "")

    print(f"\n[Node: Research] Conducting live market research on '{client_name}'...")

    search_content = ""
    source_urls: List[str] = []

    # 1. Query Tavily if API key is present
    if settings.TAVILY_API_KEY and settings.TAVILY_API_KEY.strip():
        try:
            tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
            query = build_tavily_query(client_name, website, description)
            
            search_res = tavily.search(query=query, max_results=4, search_depth="basic")

            snippets = []
            for r in search_res.get("results", []):
                content = r.get("content", "").strip()
                title = r.get("title", "").strip()
                url = r.get("url")
                if content:
                    snippets.append(f"Title: {title}\nSnippet: {content}\nURL: {url}")
                if url and url not in source_urls:
                    source_urls.append(url)

            search_content = "\n\n".join(snippets)
            print(f"[Node: Research] Tavily returned {len(snippets)} snippets for {client_name}.")
        except Exception as e:
            logger.warning("[Node: Research] Tavily search failed: %s", e)
            print(f"[Node: Research] Tavily search bypassed/failed: {e}")
            search_content = f"No live search results available. Base info: {client_name} ({website})"
    else:
        print("[Node: Research] TAVILY_API_KEY not configured. Bypassing live web lookup.")
        search_content = f"No live search results available. Base info: {client_name} ({website})"

    # 2. Extract structured intelligence with LLM
    try:
        llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            temperature=0.1,
        ).with_structured_output(ResearchArtifact)

        formatted_user_prompt = RESEARCH_USER_PROMPT.format(
            client_name=client_name,
            client_website=website or "Not provided",
            project_description=description,
            search_results=search_content or "No external context found.",
        )

        artifact: ResearchArtifact = llm.invoke([
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": formatted_user_prompt},
        ])

        # Merge discovered source URLs if LLM did not extract them
        if not artifact.source_urls and source_urls:
            artifact.source_urls = source_urls

        return {"research": artifact.model_dump()}

    except Exception as e:
        logger.error("[Node: Research] LLM extraction error: %s. Using default artifact.", e)
        fallback = ResearchArtifact(
            company_summary=f"{client_name} operates in the specified industry domain.",
            industry="Technology & Services",
            pain_points=["Manual workflow inefficiencies and modernization needs"],
            identified_tech=[],
            source_urls=source_urls,
        )
        return {"research": fallback.model_dump()}