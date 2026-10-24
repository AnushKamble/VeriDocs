# Audit Log: VeriDocs

## 2026-10-24 16:07:00 IST - Phase 0 Reconnaissance Audit

- **Action**: Initial workspace reconnaissance, specification review, and environment verification.
- **Auditor**: Senior Staff AI Systems Engineer (Antigravity).
- **Findings**:
  - `faiss-cpu` was not installed in Python 3.11 environment. Installed `faiss-cpu==1.15.1`. Verification: `faiss.IndexFlatIP(64).ntotal == 0`.
  - SEC EDGAR API tested with polite User-Agent (`VeriDocsResearchBot/1.0 (anush.test@example.com)`). Received HTTP 200 OK.
  - Ollama 0.40.9 verified running locally with `qwen3:8b` and `qwen2.5-coder:7b`.
  - Dense embedding model `BAAI/bge-small-en-v1.5` downloaded and verified with embedding dimension 384.
  - Node v24.15.0 and npm 11.12.1 verified.
  - Git repository initialized.
- **Defects Identified**: None.
- **Status**: Phase 0 Gate Passed.

## 2026-10-24 16:13:00 IST - Phase 1 Technical Design & Contracts Audit

- **Action**: Formalized architecture documentation, ADRs 001-006, canonical schemas, and schema validation tests.
- **Auditor**: Senior Staff AI Systems Engineer (Antigravity).
- **Findings**:
  - `docs/architecture.md` and `docs/data_contract.md` created with complete subsystem interfaces.
  - Six Architectural Decision Records (`ADR-001` through `ADR-006`) established for SQLite/FAISS, stable hashing, table reconstruction, RRF, citation validation, and numeric/NLI audit policy.
  - Pydantic models for filings, tables, cells, chunks, index manifests, query requests, traces, claims, and benchmark cases implemented in `backend/veridocs/schemas/`.
  - Schema test suite (`backend/tests/unit/test_data_models.py`, `backend/tests/unit/test_query_models.py`) ran with 8 tests passed (0 failures).
- **Defects Identified**: None.
- **Status**: Phase 1 Gate Passed.

## 2026-10-24 16:17:30 IST - Phase 2 Repository Scaffold & Engineering Standards Audit

- **Action**: Verified full repository scaffold, settings validation, logging, health endpoints, and frontend build.
- **Auditor**: Senior Staff AI Systems Engineer (Antigravity).
- **Findings**:
  - `Settings` properly validates User-Agent format and conservative rate limits.
  - Initial defect identified in `test_secret_redaction` where `Bearer <token>` space separator was not matched by regex; resolved immediately and re-verified.
  - Frontend TypeScript/Vite project initialized; fixed unused React import error under strict `noUnusedLocals`; `npm run build` completed in 905ms generating production bundle.
  - Backend pytest suite: 16 passed in 1.58s.
- **Defects Identified and Fixed**:
  - `backend/veridocs/utils/logging.py`: Added regex pattern to redact `Bearer <token>` headers.
  - `frontend/src/App.tsx`: Removed unused `React` default import to comply with TypeScript strict mode.
- **Status**: Phase 2 Gate Passed.

## 2026-10-24 16:20:00 IST - Phase 3 SEC Filing Discovery, Retrieval & Provenance Audit

- **Action**: Verified SEC client, CIK normalization, submissions parser, token-bucket rate limiter, cache, and provenance SHA-256 verification.
- **Auditor**: Senior Staff AI Systems Engineer (Antigravity).
- **Findings**:
  - `pytest-asyncio` installed and enabled via `pyproject.toml` (`asyncio_mode = "auto"`).
  - Rate limiter verified enforcing interval tokens.
  - SSRF protection tested rejecting unauthorized domains (`malicious-site.com`, `169.254.169.254`).
  - Cache corruption detection verified rejecting tampered raw bytes.
  - Live SEC discovery test executed against official EDGAR API: successfully retrieved live AAPL 10-K metadata.
  - Test suite: 26 passed in 5.16s (0 failures).
- **Defects Identified**: None.
- **Status**: Phase 3 Gate Passed.

## 2026-10-24 16:24:00 IST - Phase 4 Filing Parser & Table Reconstruction Audit

- **Action**: Verified structural table parser, multi-level headers, accounting parentheses negative values, units, category hierarchy, and SEC section parsing.
- **Auditor**: Senior Staff AI Systems Engineer (Antigravity).
- **Findings**:
  - `TableParser` successfully computes 2D grids with `colspan`/`rowspan` propagation, retaining cell coordinates, row labels, and effective column headers.
  - Three initial unit test defects diagnosed and corrected:
    1. Parenthetical percentages `(3.8%)` adjusted in regex to accept `%` inside parens.
    2. Spanned category divider rows distinguished from multi-row column headers.
    3. Table-level units (`USD_THOUSANDS`) prioritized over generic cell currency symbol `$` when determining cell magnitude.
  - Full suite passed: 37 passed in 5.26s.
- **Defects Identified and Fixed**:
  - `backend/veridocs/ingestion/numeric_normalizer.py`: Updated `PAREN_NEGATIVE_PATTERN` to support percentages inside parentheses.
  - `backend/veridocs/ingestion/table_parser.py`: Added check for category divider rows with uniform text spanning all columns.
  - `backend/veridocs/ingestion/table_parser.py`: Corrected unit precedence to preserve table-level scale.
- **Status**: Phase 4 Gate Passed.

## 2026-10-24 16:30:00 IST - Phase 5 Structure-Aware Chunking, Catalog & Index Audit

- **Action**: Verified narrative chunker, table row-group chunker, SQLite catalog, BM25Plus index, dense FAISS index, and manifest integrity.
- **Auditor**: Senior Staff AI Systems Engineer (Antigravity).
- **Findings**:
  - `NarrativeChunker` preserves paragraph boundaries and prepends company/filing/section context headers.
  - `TableChunker` groups adjacent rows while continuously repeating caption, column headers, units, and corporate metadata.
  - `SQLiteCatalog` enforces WAL mode, foreign key cascades, and atomic entity re-ingestion.
  - Initial defect in BM25: Okapi IDF was 0 on small 2-document corpus; upgraded to `BM25Plus` which guarantees positive scoring for matching tokens regardless of document frequency.
  - `DenseIndexer` embeds with `BAAI/bge-small-en-v1.5`, applies L2 normalization, creates `IndexFlatIP(384)`, verifies checksums, and detects tampered index artifacts.
  - Full suite passed: 43 passed in 31.93s.
- **Defects Identified and Fixed**:
  - `backend/veridocs/indexing/dense_indexer.py`: Added missing `Dict` typing import.
  - `backend/veridocs/indexing/bm25_index.py`: Upgraded to `BM25Plus` from `BM25Okapi` to avoid zero-scoring on low document frequency terms.
- **Status**: Phase 5 Gate Passed.
