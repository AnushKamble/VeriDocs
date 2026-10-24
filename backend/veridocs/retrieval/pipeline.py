"""
Unified retrieval pipeline coordinating BM25, Dense, RRF, and Reranking with execution tracing.
"""

import time
import uuid
from typing import Dict, List, Optional, Tuple

from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.config.settings import settings
from veridocs.retrieval.bm25_retriever import BM25Retriever
from veridocs.retrieval.dense_retriever import DenseRetriever
from veridocs.retrieval.reranker import CrossEncoderReranker
from veridocs.retrieval.rrf_fusion import reciprocal_rank_fusion
from veridocs.schemas.data_models import ChunkRecord
from veridocs.schemas.query_models import (
    MetadataFilter,
    RetrievalCandidate,
    RetrievalTrace,
    RetrieverMode,
)


class RetrievalPipeline:
    """
    Coordinates distinct retrieval strategies: BM25-only, Dense-only, Hybrid RRF, and Reranked,
    generating an inspectable, non-secret retrieval trace for every execution.
    """

    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        dense_retriever: DenseRetriever,
        reranker: CrossEncoderReranker,
        catalog: SQLiteCatalog,
    ):
        self.bm25_retriever = bm25_retriever
        self.dense_retriever = dense_retriever
        self.reranker = reranker
        self.catalog = catalog

    def execute(
        self,
        query: str,
        retriever_mode: RetrieverMode = RetrieverMode.HYBRID_RRF,
        top_k: int = 5,
        filters: Optional[MetadataFilter] = None,
        query_id: Optional[str] = None,
    ) -> Tuple[List[ChunkRecord], RetrievalTrace]:
        qid = query_id or f"q_{uuid.uuid4().hex[:12]}"
        timings: Dict[str, float] = {}
        start_total = time.perf_counter()

        bm25_candidates: List[RetrievalCandidate] = []
        dense_candidates: List[RetrievalCandidate] = []
        fused_candidates: List[RetrievalCandidate] = []
        reranked_candidates: List[RetrievalCandidate] = []
        final_candidates: List[RetrievalCandidate] = []

        pool_size = max(top_k * 2, 10)

        # 1. BM25 Branch
        if self.bm25_retriever is not None and retriever_mode in (RetrieverMode.BM25, RetrieverMode.HYBRID_RRF, RetrieverMode.RERANKED):
            t0 = time.perf_counter()
            bm25_candidates = self.bm25_retriever.retrieve(
                query=query,
                top_k=pool_size,
                filters=filters,
            )
            timings["bm25_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # 2. Dense Branch
        if self.dense_retriever is not None and retriever_mode in (RetrieverMode.DENSE, RetrieverMode.HYBRID_RRF, RetrieverMode.RERANKED):
            t0 = time.perf_counter()
            dense_candidates = self.dense_retriever.retrieve(
                query=query,
                top_k=pool_size,
                filters=filters,
            )
            timings["dense_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)


        # 3. Mode Resolution & Fusion
        if retriever_mode == RetrieverMode.BM25:
            final_candidates = bm25_candidates[:top_k]
        elif retriever_mode == RetrieverMode.DENSE:
            final_candidates = dense_candidates[:top_k]
        else:
            # Hybrid or Reranked: perform RRF
            t0 = time.perf_counter()
            fused_candidates = reciprocal_rank_fusion(
                candidate_lists={
                    "bm25": bm25_candidates,
                    "dense": dense_candidates,
                },
                k0=settings.rrf_k0,
                top_k=pool_size,
            )
            timings["rrf_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

            if retriever_mode == RetrieverMode.HYBRID_RRF:
                final_candidates = fused_candidates[:top_k]
            elif retriever_mode == RetrieverMode.RERANKED:
                # 4. Cross-Encoder Reranking
                if self.reranker is not None:
                    t0 = time.perf_counter()
                    reranked_candidates = self.reranker.rerank(
                        query=query,
                        candidates=fused_candidates[:pool_size],
                        catalog=self.catalog,
                        top_k=top_k,
                    )
                    timings["rerank_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
                    final_candidates = reranked_candidates
                else:
                    final_candidates = fused_candidates[:top_k]

        # 5. Retrieve final chunk entities
        final_chunk_ids = [c.chunk_id for c in final_candidates]
        chunks = self.catalog.get_chunks_by_ids(final_chunk_ids) if self.catalog is not None else []

        # Preserve the exact rank order of final_candidates
        chunk_map = {c.chunk_id: c for c in chunks}
        ordered_chunks = [chunk_map[cid] for cid in final_chunk_ids if cid in chunk_map]

        timings["total_retrieval_ms"] = round((time.perf_counter() - start_total) * 1000.0, 2)

        trace = RetrievalTrace(
            query_id=qid,
            query_text=query,
            applied_filters=filters.model_dump(exclude_none=True) if filters else {},
            bm25_candidates=bm25_candidates,
            dense_candidates=dense_candidates,
            fused_candidates=fused_candidates,
            reranked_candidates=reranked_candidates,
            final_evidence_chunk_ids=final_chunk_ids,
            timings_ms=timings,
        )

        return ordered_chunks, trace
