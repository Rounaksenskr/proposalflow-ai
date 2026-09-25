import pytest
from proposal_bot.rag.hybrid_retriever import HybridRetriever


@pytest.fixture(scope="module")
def retriever():
    return HybridRetriever(
        docs_dir="data/knowledge_base",
        persist_dir="proposal_db/test_chroma"
    )


def test_retrieval_returns_logistics_for_dispatch_query(retriever):
    query = "We need an operations dispatch dashboard built with React and FastAPI."
    results = retriever.retrieve(query=query, top_k=2)

    assert len(results) == 2
    top_case = results[0]

    # Verify proj-001 (logistics dashboard) is ranked #1
    assert top_case["id"] == "proj-001"
    assert "FastAPI" in top_case["technologies"]
    assert "React" in top_case["technologies"]


def test_retrieval_returns_ecommerce_for_shopify_query(retriever):
    query = "Need an automated sync engine for Shopify storefront inventory."
    results = retriever.retrieve(query=query, top_k=2)

    assert len(results) == 2
    top_case = results[0]
    assert top_case["id"] == "proj-003"
    assert "Shopify API" in top_case["technologies"]