# Dependency and Model Inventory

## 1. Third-Party Python Libraries

| Package | Version | License | Intended Role | Verified Safe for Commercial / Academic Use |
|---|---|---|---|---|
| `fastapi` | 0.136.3 | MIT | REST API Server | Yes |
| `pydantic` | 2.13.4 | MIT | Data parsing & validation | Yes |
| `uvicorn` | 0.51.0 | BSD-3-Clause | ASGI Server | Yes |
| `httpx` | 0.28.1 | BSD-3-Clause | HTTP Client for SEC retrieval | Yes |
| `beautifulsoup4` | 4.14.3 | MIT | HTML structure parser | Yes |
| `lxml` | 6.1.1 | BSD-3-Clause | HTML/XML C-engine | Yes |
| `rank-bm25` | 0.2.2 | Apache 2.0 | Lexical BM25 retrieval | Yes |
| `faiss-cpu` | 1.15.1 | MIT | Dense vector search | Yes |
| `sentence-transformers` | 5.5.1 | Apache 2.0 | Embeddings & Cross-Encoders | Yes |
| `torch` | 2.13.0 | BSD-style | Deep Learning tensor framework | Yes |
| `pytest` | 9.1.1 | MIT | Test framework | Yes |

## 2. Machine Learning Models

### A. Embedding Model (Dense Retriever)
- **Model Name**: `BAAI/bge-small-en-v1.5`
- **Architecture**: Bi-Encoder Transformer (BERT-based)
- **Embedding Dimension**: 384
- **Context Length**: 512 tokens
- **License**: MIT / Apache 2.0 compatible (open research & commercial use)
- **Role**: Computes dense vector embeddings for narrative chunks and table group chunks.
- **Normalization**: L2 normalization for inner product (cosine similarity) compatibility.

### B. Cross-Encoder Reranker
- **Model Name**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Architecture**: Cross-Encoder (pairwise query-chunk scoring)
- **License**: Apache 2.0
- **Role**: Re-scores top-k fused candidate pool.
- **Operational Principle**: Output score is a ranking logit, NOT a calibrated probability of relevance.

### C. Natural Language Inference (NLI) Auditor
- **Model Name**: `cross-encoder/nli-deberta-v3-small`
- **Architecture**: Cross-Encoder (DeBERTa-v3)
- **Labels**: `[contradiction, entailment, neutral]` (configured & verified dynamically)
- **License**: Apache 2.0 / MIT compatible
- **Role**: Evaluates claim entailment against cited premise passages.
- **Operational Principle**: Model signals are categorical evidence checks, NOT objective truth probabilities. Ambiguities fall back to `NEEDS_REVIEW` or `INSUFFICIENT_EVIDENCE`.

### D. Generator Provider (Local LLM via Ollama)
- **Model Name**: `qwen3:8b` (default) / `qwen2.5-coder:7b` (configurable via `VERIDOCS_GENERATOR_MODEL`)
- **Host**: Local Ollama server (`http://localhost:11434`)
- **License**: Open-weights permissive license (Qwen license allows commercial/research use)
- **Role**: Produces structured JSON output containing atomic factual claims and citation identifiers under evidence-only constraints.
- **Security Rule**: Retrieved chunks are untrusted data. No code execution, no shell permissions.
