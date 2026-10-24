# ADR-004: Hybrid Retrieval via Reciprocal Rank Fusion (RRF) and Bounded Reranking

## Context
Financial queries exhibit distinct search dynamics:
1. Exact keyword & financial-token queries (e.g., `FY2023 revenue`, `Item 8`, `Note 14`, `12.5%`) benefit strongly from BM25 exact lexical term matching.
2. Conceptual or thematic queries (e.g., `impact of foreign exchange fluctuations on operating margin`) benefit from dense semantic vector matching.
3. Neither BM25 scores (unbounded log-odds) nor dense vector inner product similarities (bounded [-1, 1] cosine) share a common probability distribution; linear combinations (alpha * BM25 + beta * dense) are notoriously brittle and uncalibrated without extensive domain-specific tuning.

## Decision
We implement a multi-stage retrieval architecture:

### 1. Independent First-Stage Retrievers
- **BM25 Lexical Retriever**: Uses custom financial tokenization preserving symbols (`$`, `%`), parentheses, tickers, and metric terms.
- **Dense Vector Retriever**: Uses `BAAI/bge-small-en-v1.5` embeddings (384-d, L2 normalized) queried against FAISS `IndexFlatIP`.
- **Pre-Filtering**: Both retrievers accept metadata filters (`company`, `form_type`, `fiscal_period`, `section`) evaluated prior to rank scoring.

### 2. Reciprocal Rank Fusion (RRF)
We fuse the top-K candidates from both retrievers using RRF with standard smoothing factor $k_0 = 60$:
$$\operatorname{RRF}(d) = \sum_{m \in \{\text{BM25}, \text{Dense}\}} \frac{1}{k_0 + \operatorname{rank}_m(d)}$$
- Missing rank rule: If document $d$ does not appear in retriever $m$'s top candidate list, its contribution from $m$ is 0.
- Stable tie-breaker: Any exact RRF score ties are broken deterministically by alphabetical order of `chunk_id`.

### 3. Bounded Cross-Encoder Reranking
- The top fused candidate pool (default $N = 15$ candidates) is optionally passed to a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
- Reranking scores are treated strictly as ordinal ranking logits, never as probabilities of truth.
- Both un-reranked and reranked paths are preserved for baseline ablation experiments.

### 4. Retrieval Trace
Every execution generates a non-secret, fully inspectable `RetrievalTrace` object logging the original query, applied filters, BM25 candidates and ranks, Dense candidates and ranks, RRF fused scores, and reranked logits.
