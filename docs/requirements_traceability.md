# Requirements Traceability Matrix: VeriDocs

| Req ID | Concise Description | Planned Source Module(s) | Tests / Verification Commands | Evidence Artifact / Path | Current Status | Rationale / Notes |
|---|---|---|---|---|---|---|
| **REQ-01** | Polite SEC EDGAR Client | `backend/veridocs/sec/client.py`, `backend/veridocs/sec/rate_limiter.py` | `pytest backend/tests/unit/test_sec_cache_retry.py` | `docs/environment_audit.md`, test logs | `IN_PROGRESS` | Live SEC connectivity verified; client module being built |
| **REQ-02** | Provenance & Idempotent Fetch | `backend/veridocs/sec/provenance.py`, `backend/veridocs/sec/cache.py` | `pytest backend/tests/unit/test_sec_provenance.py` | Cache tests & raw SHA256 manifests | `NOT_STARTED` | Ingestion pipeline |
| **REQ-03** | Structural HTML & Section Parser | `backend/veridocs/ingestion/html_parser.py`, `section_parser.py` | `pytest backend/tests/unit/test_section_parser.py` | Hand-crafted HTML fixtures | `NOT_STARTED` | Phase 4 |
| **REQ-04** | Financial Table Reconstruction | `backend/veridocs/ingestion/table_parser.py` | `pytest backend/tests/unit/test_table_parser.py` | Table fixtures with headers, units, negatives | `NOT_STARTED` | Phase 4 |
| **REQ-05** | Numeric Normalization & Diagnostics | `backend/veridocs/ingestion/numeric_normalizer.py` | `pytest backend/tests/unit/test_numeric_normalizer.py` | Unit tests for parentheses, scales, currencies | `NOT_STARTED` | Phase 4 |
| **REQ-06** | Structure-Aware Narrative & Table Chunker | `backend/veridocs/chunking/narrative_chunker.py`, `table_chunker.py` | `pytest backend/tests/unit/test_table_chunker.py` | Chunk inspection tests | `NOT_STARTED` | Phase 5 |
| **REQ-07** | Deterministic Catalog & Versioned Index | `backend/veridocs/catalog/sqlite_store.py`, `backend/veridocs/indexing/manifest.py` | `pytest backend/tests/unit/test_catalog_store.py` | SQLite schema and manifest validator | `NOT_STARTED` | Phase 5 |
| **REQ-08** | Financial Token BM25 Lexical Retriever | `backend/veridocs/indexing/bm25_index.py`, `backend/veridocs/retrieval/bm25_retriever.py` | `pytest backend/tests/unit/test_bm25_retrieval.py` | Exact token match tests | `NOT_STARTED` | Phase 6 |
| **REQ-09** | Dense Embedding Retriever (FAISS CPU) | `backend/veridocs/retrieval/dense_retriever.py`, `indexing/faiss_index.py` | `pytest backend/tests/unit/test_dense_retrieval.py` | Vector index tests | `NOT_STARTED` | Phase 6 |
| **REQ-10** | Reciprocal Rank Fusion (RRF) | `backend/veridocs/retrieval/rrf_fusion.py` | `pytest backend/tests/unit/test_rrf_fusion.py` | Math & deduplication tests | `NOT_STARTED` | Phase 6 |
| **REQ-11** | Cross-Encoder Reranker | `backend/veridocs/retrieval/reranker.py` | `pytest backend/tests/unit/test_reranker.py` | Reranker candidate tests | `NOT_STARTED` | Phase 6 |
| **REQ-12** | Inspectable Retrieval Trace | `backend/veridocs/retrieval/retrieval_trace.py` | `pytest backend/tests/unit/test_retrieval_pipeline.py` | Trace JSON schema validation | `NOT_STARTED` | Phase 6 |
| **REQ-13** | 50-Question Source-Grounded Benchmark | `benchmarks/questions.jsonl`, `benchmarks/schema.py` | `pytest backend/tests/unit/test_benchmark_labels.py` | Audited benchmark files | `NOT_STARTED` | Phase 7 |
| **REQ-14** | Local Ollama Generation Provider | `backend/veridocs/generation/ollama_adapter.py` | `pytest backend/tests/unit/test_ollama_adapter.py` | Ollama tag check & generation tests | `NOT_STARTED` | Phase 8 |
| **REQ-15** | Untrusted Source Delimiting (Prompt Injection) | `backend/veridocs/generation/prompt_builder.py` | `pytest backend/tests/security/test_prompt_injection.py` | Prompt test fixtures | `NOT_STARTED` | Phase 8 |
| **REQ-16** | Atomic Claims & Citation Validation | `backend/veridocs/generation/structured_answerer.py` | `pytest backend/tests/unit/test_structured_answerer.py` | Citation resolution tests | `NOT_STARTED` | Phase 8 |
| **REQ-17** | Deterministic Numeric Audit & Safe Calculator | `backend/veridocs/audit/numeric_comparator.py`, `calculator.py` | `pytest backend/tests/unit/test_calculator.py` | Math & mismatch tests | `NOT_STARTED` | Phase 9 |
| **REQ-18** | NLI Support Auditor | `backend/veridocs/audit/nli_auditor.py` | `pytest backend/tests/unit/test_nli_auditor.py` | Label order & premise/hypothesis tests | `NOT_STARTED` | Phase 10 |
| **REQ-19** | Categorical Response Policy & Abstention | `backend/veridocs/audit/response_policy.py` | `pytest backend/tests/unit/test_response_policy.py` | Abstention & conflict tests | `NOT_STARTED` | Phase 10 |
| **REQ-20** | FastAPI Contract & Endpoints | `backend/veridocs/api/routes/*` | `pytest backend/tests/integration/test_api_endpoints.py` | API integration tests | `NOT_STARTED` | Phase 11 |
| **REQ-21** | React + TypeScript Product UI | `frontend/src/*` | `npm run build`, UI unit tests | Web build output | `NOT_STARTED` | Phase 12 |
| **REQ-22** | Benchmark Evaluation Runner & Baselines | `backend/veridocs/evaluation/runner.py`, `metrics.py` | `pytest backend/tests/integration/test_eval_runner.py` | Evaluation report & JSONL artifacts | `NOT_STARTED` | Phase 13 |
| **REQ-23** | Security, SSRF & Sanitization Hardening | `backend/veridocs/sec/client.py`, `backend/veridocs/api/middleware.py` | `pytest backend/tests/security/*` | Red-team test suites | `NOT_STARTED` | Phase 14 |
| **REQ-24** | Comprehensive Documentation & Final Audit | `README.md`, `docs/*`, `FINAL_AUDIT_REPORT.md` | `pytest backend/tests` (full suite) | Audit report artifact | `NOT_STARTED` | Phase 15 |
