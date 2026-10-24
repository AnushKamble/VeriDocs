# ADR-002: Stable ID Generation and Content Hashing Rules

## Context
In a verifiable RAG and citation audit system, chunk IDs, table IDs, and document IDs cannot be ephemeral auto-incrementing integers or random UUIDs. A re-ingestion of the identical filing HTML must produce identical chunk IDs. Furthermore, any change to the parsing or chunking logic must be detectable via hash mismatch.

## Decision
All entity identifiers in VeriDocs are deterministically derived using SHA-256 digests and structured natural keys.

### 1. Document ID
`doc_{cik}_{accession_number_clean}`
Example: `doc_0000320193_000032019323000106`
- `cik`: 10-digit zero-padded CIK string.
- `accession_number_clean`: 18-digit alphanumeric string without hyphens.

### 2. Table ID
`tbl_{document_id}_{table_ordinal:04d}_{sha256(raw_table_html[:500])[:8]}`
Example: `tbl_doc_0000320193_000032019323000106_0004_a1b2c3d4`

### 3. Chunk ID
`chk_{document_id}_{chunk_kind}_{ordinal:05d}_{sha256(canonical_chunk_text)[:12]}`
- `chunk_kind`: `narrative` or `table_group` or `table_row`.
- `canonical_chunk_text`: normalized UTF-8 text representation with standardized whitespace.

### 4. Index Manifest Hash
Every generated index artifact (BM25 artifact or FAISS `.index` + ID map) records:
- `manifest_version`: "1.0"
- `chunker_version`: semantic version string (e.g. "1.0.0")
- `embedding_model_id`: "BAAI/bge-small-en-v1.5"
- `embedding_dimension`: 384
- `source_corpus_hash`: SHA-256 of sorted list of all active chunk IDs and their content hashes.

## Validation
Re-running chunking on identical HTML yields 100% bit-for-bit identical IDs. Any mutation of text or table cell yields a distinct chunk ID.
