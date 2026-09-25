from proposal_bot.state import ProposalState
from proposal_bot.rag.hybrid_retriever import HybridRetriever

# Module-level singleton to avoid reloading embeddings on every graph invoke
_retriever_instance: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever(
            docs_dir="data/knowledge_base",
            persist_dir="proposal_db/chroma"
        )
    return _retriever_instance


def retrieval_node(state: ProposalState) -> dict:
    """Retrieves top matching historical portfolio projects via hybrid search."""
    lead = state.get("lead", {})
    research = state.get("research", {}) or {}
    
    desc = lead.get("project_description", "")
    industry = research.get("industry", "")
    
    # Formulate rich query combining client brief and industry context
    query = f"{desc} {industry}".strip()
    print(f"[Node: Retrieval] Performing Hybrid RAG (BM25 + Chroma) for query: '{query[:60]}...'")

    retriever = get_retriever()
    cases = retriever.retrieve(query=query, top_k=2)

    print(f"[Node: Retrieval] Found {len(cases)} relevant historical case studies.")
    return {"retrieved_cases": cases}