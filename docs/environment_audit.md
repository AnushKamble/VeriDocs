# Environment Audit: VeriDocs

Date: 2026-10-24
Platform: Windows (OS Version Windows 11 / AMD64)
Command Shell: PowerShell / CMD
Execution Environment: Local developer environment

## 1. System Run-time & Tools

| Component | Found Version | Requirement in Spec | Status | Notes |
|---|---|---|---|---|
| Python | 3.11.9 | Python 3.11+ | COMPLIANT | Local Python 3.11.9 |
| pip | 24.0 | Package management | COMPLIANT | Wheel / pip operational |
| Node.js | v24.15.0 | Modern Node for React/Vite | COMPLIANT | LTS/Current |
| npm | 11.12.1 | Modern npm | COMPLIANT | npm CLI operational |
| Git | 2.54.0.windows.1 | Version control | COMPLIANT | Git initialized in workspace |
| Ollama | 0.40.9 | Local LLM host | COMPLIANT | Local daemon active on http://localhost:11434 |

## 2. Local AI Models Available (Ollama)

Query against `http://localhost:11434/api/tags`:
- `qwen3:8b` (5.2 GB, Q4_K_M, parameter_size: 8.2B, context_length: 40960)
- `qwen2.5-coder:7b` (4.7 GB, Q4_K_M, parameter_size: 7.6B, context_length: 32768)

Design selection: Default generation model set to `qwen3:8b` (configurable via `VERIDOCS_GENERATOR_MODEL`).

## 3. Python Package Environment Check

| Library | Installed Version | Role | Notes |
|---|---|---|---|
| `fastapi` | 0.136.3 | REST API framework | High-performance async API |
| `pydantic` | 2.13.4 | Schema validation & serialization | Strict typing |
| `uvicorn` | 0.51.0 | ASGI Server | Production HTTP server |
| `httpx` | 0.28.1 | Async HTTP client | SEC EDGAR polite client |
| `beautifulsoup4` | 4.14.3 | HTML parsing | Robust HTML element parsing |
| `lxml` | 6.1.1 | XML/HTML parser engine | High-speed C-based parser |
| `rank-bm25` | 0.2.2 | BM25 lexical retriever | Lexical financial scoring |
| `faiss-cpu` | 1.15.1 | Dense vector indexing | Local, reproducible FAISS index |
| `sentence-transformers` | 5.5.1 | Neural embeddings & cross-encoders | Transformer inference |
| `torch` | 2.13.0 | PyTorch runtime | CPU backend configured |
| `pytest` | 9.1.1 | Test suite runner | Comprehensive testing |
| `sqlite3` | Built-in (3.45.1+) | Relational catalog / persistence | Durable transactions & manifests |

## 4. Network and External Access Check

- **SEC EDGAR API**: Verified via `https://data.sec.gov/submissions/CIK0000320193.json`. Response: `HTTP/1.1 200 OK`.
- **HuggingFace Hub**: Access permitted for verified open-weights models (`BAAI/bge-small-en-v1.5`, `cross-encoder/nli-deberta-v3-small`).
- **Ollama Local Endpoint**: Active and responsive at `http://localhost:11434`.

## 5. Security & Isolation Boundaries

- No sensitive credentials detected in repository or environment.
- Outbound network requests to SEC EDGAR will use a declared, polite `SEC_USER_AGENT` with rate limiting strictly <= 2 requests/sec (well below SEC 10 req/sec cap).
- Ingested HTML documents will be treated strictly as untrusted data.
