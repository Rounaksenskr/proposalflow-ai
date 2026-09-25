import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rank_bm25 import BM25Okapi
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Extract YAML frontmatter and markdown body cleanly."""
    frontmatter: Dict[str, Any] = {}
    body = content

    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    if match:
        raw_meta, body = match.groups()
        for line in raw_meta.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                clean_key = key.strip()
                clean_val = val.strip().strip('"').strip("'")
                
                if clean_val.startswith("[") and clean_val.endswith("]"):
                    items = [item.strip().strip('"').strip("'") for item in clean_val[1:-1].split(",") if item.strip()]
                    frontmatter[clean_key] = items
                else:
                    frontmatter[clean_key] = clean_val

    return frontmatter, body.strip()


class HybridRetriever:
    """Combines dense vector retrieval (Chroma) and lexical retrieval (BM25) with RRF."""

    def __init__(self, docs_dir: str = "data/knowledge_base", persist_dir: str = "proposal_db/chroma"):
        self.docs_dir = Path(docs_dir)
        self.persist_dir = persist_dir
        self.documents: List[Document] = []
        self.bm25: BM25Okapi | None = None
        self.vector_store: Chroma | None = None
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self._load_and_index()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def _load_and_index(self):
        if not self.docs_dir.exists():
            raise FileNotFoundError(f"Knowledge base directory '{self.docs_dir}' not found.")

        raw_docs = []
        tokenized_corpus = []

        for md_file in sorted(self.docs_dir.glob("*.md")):
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            metadata, body = parse_frontmatter(content)
            metadata["source_file"] = md_file.name
            
            searchable_text = (
                f"{metadata.get('title', '')}\n"
                f"Industry: {metadata.get('industry', '')}\n"
                f"Technologies: {', '.join(metadata.get('technologies', []))}\n\n"
                f"{body}"
            )
            
            doc = Document(page_content=searchable_text, metadata=metadata)
            raw_docs.append(doc)
            tokenized_corpus.append(self._tokenize(searchable_text))

        if not raw_docs:
            raise ValueError(f"No markdown documents found in {self.docs_dir}")

        self.documents = raw_docs
        self.bm25 = BM25Okapi(tokenized_corpus)

        self.vector_store = Chroma.from_documents(
            documents=self.documents,
            embedding=self.embeddings,
            persist_directory=self.persist_dir,
            collection_name="portfolio_cases"
        )

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Executes BM25 and Vector search, fusing results using Reciprocal Rank Fusion (RRF)."""
        # 1. Vector Search
        vector_results = self.vector_store.similarity_search_with_score(query, k=len(self.documents))
        
        # 2. BM25 Search
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_ranked_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)

        # 3. Reciprocal Rank Fusion (k=60 standard)
        rrf_scores: Dict[int, float] = {i: 0.0 for i in range(len(self.documents))}

        for rank, (doc, _dist) in enumerate(vector_results):
            doc_idx = next(i for i, d in enumerate(self.documents) if d.metadata.get("id") == doc.metadata.get("id"))
            rrf_scores[doc_idx] += 1.0 / (60 + rank + 1)

        for rank, doc_idx in enumerate(bm25_ranked_indices):
            rrf_scores[doc_idx] += 1.0 / (60 + rank + 1)

        # 4. Sort and return top-k
        sorted_indices = sorted(rrf_scores.keys(), key=lambda idx: rrf_scores[idx], reverse=True)[:top_k]

        results = []
        for idx in sorted_indices:
            doc = self.documents[idx]
            results.append({
                "id": doc.metadata.get("id"),
                "title": doc.metadata.get("title"),
                "industry": doc.metadata.get("industry"),
                "technologies": doc.metadata.get("technologies", []),
                "similarity_score": round(rrf_scores[idx], 4),
                "summary": doc.page_content[:350] + "..."
            })

        return results