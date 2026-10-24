"""
Reciprocal Rank Fusion (RRF) for combining multiple ranked candidate lists.
"""

from typing import Dict, List, Tuple
from veridocs.schemas.query_models import RetrievalCandidate


def reciprocal_rank_fusion(
    candidate_lists: Dict[str, List[RetrievalCandidate]],
    k0: int = 60,
    top_k: int = 10,
) -> List[RetrievalCandidate]:
    """
    Fuses candidate lists from multiple retrievers (e.g. 'bm25', 'dense') using RRF.

    Formula:
        RRF(d) = sum_{m} 1 / (k0 + rank_m(d))

    Rules:
    - Missing candidates from a retriever contribute 0.
    - Deduplicates by chunk_id.
    - Exact score ties are broken deterministically by chunk_id ascending.
    """
    rrf_scores: Dict[str, float] = {}
    candidate_metadata: Dict[str, RetrievalCandidate] = {}

    for retriever_name, candidates in candidate_lists.items():
        for candidate in candidates:
            cid = candidate.chunk_id
            rank = candidate.rank
            contribution = 1.0 / (k0 + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + contribution

            # Keep candidate reference for metadata
            if cid not in candidate_metadata:
                candidate_metadata[cid] = candidate

    # Sort descending by RRF score; break ties deterministically by chunk_id ascending
    sorted_items = sorted(
        rrf_scores.items(),
        key=lambda item: (-item[1], item[0]),
    )

    fused_candidates: List[RetrievalCandidate] = []
    for rank, (cid, score) in enumerate(sorted_items[:top_k], start=1):
        meta = candidate_metadata[cid]
        fused_candidates.append(
            RetrievalCandidate(
                chunk_id=cid,
                document_id=meta.document_id,
                retriever="rrf",
                rank=rank,
                raw_score=score,
                rrf_score=score,
                text_preview=meta.text_preview,
            )
        )

    return fused_candidates
