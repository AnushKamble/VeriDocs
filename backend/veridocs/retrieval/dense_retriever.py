"""
Dense vector retriever querying FAISS with normalized embeddings and metadata filtering.
"""

from typing import Dict, List, Optional, Set
import faiss
import numpy as np

from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.indexing.dense_indexer import DenseIndexer
from veridocs.schemas.query_models import MetadataFilter, RetrievalCandidate


class DenseRetriever:
    """
    Dense semantic retriever executing exact inner product search over L2-normalized embeddings.
    """

    def __init__(
        self,
        faiss_index: faiss.IndexFlatIP,
        id_map: Dict[int, str],
        indexer: DenseIndexer,
        catalog: SQLiteCatalog,
    ):
        self.faiss_index = faiss_index
        self.id_map = id_map
        self.indexer = indexer
        self.catalog = catalog

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[MetadataFilter] = None,
    ) -> List[RetrievalCandidate]:
        if self.faiss_index.ntotal == 0:
            return []

        # Determine allowed chunk IDs if filters are specified
        allowed_ids: Optional[Set[str]] = None
        if filters and any(v is not None for v in filters.model_dump().values()):
            matching_chunks = self.catalog.list_chunks(filters)
            allowed_ids = {c.chunk_id for c in matching_chunks}
            if not allowed_ids:
                return []

        # Embed query vector and normalize
        query_vector = self.indexer.embed_texts([query])

        # Fetch enough candidates to account for potential filter exclusion
        fetch_k = min(self.faiss_index.ntotal, top_k * 5 if allowed_ids is not None else top_k)
        scores, indices = self.faiss_index.search(query_vector, fetch_k)

        candidates: List[RetrievalCandidate] = []
        rank = 1

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx not in self.id_map:
                continue
            chunk_id = self.id_map[idx]

            if allowed_ids is not None and chunk_id not in allowed_ids:
                continue

            chunk = self.catalog.get_chunk(chunk_id)
            if not chunk:
                continue

            candidates.append(
                RetrievalCandidate(
                    chunk_id=chunk_id,
                    document_id=chunk.document_id,
                    retriever="dense",
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
