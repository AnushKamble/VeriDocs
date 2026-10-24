"""
BM25 lexical retriever with metadata pre-filtering.
"""

from typing import List, Optional, Set
from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.indexing.bm25_index import BM25Index
from veridocs.schemas.query_models import MetadataFilter, RetrievalCandidate


class BM25Retriever:
    """
    Lexical retriever utilizing BM25Plus index and metadata constraint enforcement.
    """

    def __init__(self, bm25_index: BM25Index, catalog: SQLiteCatalog):
        self.bm25_index = bm25_index
        self.catalog = catalog

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[MetadataFilter] = None,
    ) -> List[RetrievalCandidate]:
        # Determine allowed chunk IDs if filters are provided
        allowed_ids: Optional[Set[str]] = None
        if filters and any(v is not None for v in filters.model_dump().values()):
            matching_chunks = self.catalog.list_chunks(filters)
            allowed_ids = {c.chunk_id for c in matching_chunks}
            if not allowed_ids:
                return []

        # Retrieve more candidates from BM25 to allow post-filtering without starvation
        fetch_limit = top_k * 5 if allowed_ids is not None else top_k
        raw_results = self.bm25_index.search(query, top_k=fetch_limit)

        candidates: List[RetrievalCandidate] = []
        rank = 1

        for chunk_id, score in raw_results:
            if allowed_ids is not None and chunk_id not in allowed_ids:
                continue

            chunk = self.catalog.get_chunk(chunk_id)
            if not chunk:
                continue

            candidates.append(
                RetrievalCandidate(
                    chunk_id=chunk_id,
                    document_id=chunk.document_id,
                    retriever="bm25",
                    rank=rank,
                    raw_score=float(score),
                    rrf_score=None,
                    text_preview=chunk.text[:200],
                )
            )
            rank += 1
            if len(candidates) >= top_k:
                break

        return candidates
