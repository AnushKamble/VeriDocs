# ADR-001: SQLite Canonical Catalog and Local FAISS Dense Index

## Context
VeriDocs requires a persistent, reproducible, and verifiable storage architecture for:
1. SEC filing metadata, raw payload provenance, and SHA-256 digests.
2. Parsed sections, tables, rows, cells, and chunks.
3. Sparse BM25 index artifacts and inverted postings.
4. Dense vector embeddings and similarity index.
5. Index build manifests and checksum maps.

The system must run locally on developer hardware without requiring cloud credentials, monthly API billing, or multi-container networking complexity.

## Decision
We select **SQLite (WAL mode)** for canonical relational persistence and **FAISS CPU (IndexFlatIP with L2-normalized embeddings)** for local vector similarity search.

1. **SQLite Role**: The single durable source of truth. Holds all documents, tables, cells, chunks, benchmark labels, and index manifests. SQLite WAL mode provides high read-concurrency and strict ACID guarantees.
2. **FAISS CPU Role**: Auxiliary dense retrieval acceleration. An `IndexFlatIP` (exact inner product) index is stored on disk alongside a deterministic integer-to-chunk-ID mapping JSON file and a SHA-256 manifest.
3. **BM25 Storage**: Lexical corpus and inverted structures are built deterministically from the canonical SQLite chunk catalog using `rank-bm25`.

## Alternatives Considered
- **ChromaDB / Qdrant local**: Good vector features, but introduces background service state, schema migrations, and opaque ID mappings.
- **PostgreSQL + pgvector**: Requires local PostgreSQL daemon, external credentials, and host setup, violating zero-friction local reproducibility.
- **In-memory dictionary with NumPy cosine**: Fine for unit tests, but fails the requirement for a versioned, durable, inspectable vector artifact.

## Consequences & Trade-offs
- **Benefits**: Completely zero-configuration, zero-cost, persistent, deterministic, portable across OS platforms. Full transactional rollback if ingestion fails halfway.
- **Trade-offs**: FAISS requires keeping the integer-to-chunk-ID map in sync. Any drift between the SQLite chunk table and the FAISS mapping must be caught by manifest checksum validation upon index load.
