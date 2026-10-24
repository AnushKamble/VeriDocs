"""
Cross-Encoder reranking adapter for bounded candidate pools.
"""

from typing import List, Optional
from sentence_transformers import CrossEncoder

from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.schemas.query_models import RetrievalCandidate
from veridocs.utils.logging import logger


class CrossEncoderReranker:
    """
    Pairwise cross-encoder reranker rescoring candidate passages.
    Operational principle: output logits are ranking scores, NOT calibrated probabilities of truth.
    """

    def __init__(self, model_id: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_id = model_id
        self._model: Optional[CrossEncoder] = None

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            logger.info(f"Loading CrossEncoder reranker: {self.model_id}")
            self._model = CrossEncoder(self.model_id)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalCandidate],
        catalog: SQLiteCatalog,
        top_k: int = 5,
    ) -> List[RetrievalCandidate]:
        if not candidates:
            return []

        # Retrieve text for candidate chunks
        chunk_ids = [c.chunk_id for c in candidates]
        chunks = catalog.get_chunks_by_ids(chunk_ids)
        chunk_map = {c.chunk_id: c for c in chunks}

        # Build query-passage pairs
        valid_candidates = []
        pairs = []
        for c in candidates:
            chunk = chunk_map.get(c.chunk_id)
            if chunk:
                valid_candidates.append(c)
                pairs.append((query, chunk.text))

        if not pairs:
            return []

        try:
            model = self._get_model()
            scores = model.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            logger.warning(f"Reranker model inference failed: {exc}. Returning original candidate order.")
            return candidates[:top_k]

        # Combine with candidate metadata
        scored_candidates = []
        for cand, score in zip(valid_candidates, scores):
            scored_candidates.append((cand, float(score)))

        # Sort descending by reranker score; break ties deterministically by chunk_id ascending
        scored_candidates.sort(key=lambda item: (-item[1], item[0].chunk_id))

        reranked: List[RetrievalCandidate] = []
        for rank, (cand, score) in enumerate(scored_candidates[:top_k], start=1):
            reranked.append(
                RetrievalCandidate(
                    chunk_id=cand.chunk_id,
                    document_id=cand.document_id,
                    retriever="reranker",
                    rank=rank,
                    raw_score=score,
                    rrf_score=cand.rrf_score,
                    text_preview=cand.text_preview,
                )
            )

        return reranked
