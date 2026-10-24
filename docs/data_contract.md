# VeriDocs Data Contracts & Schemas

## 1. Document Identity & Ingestion Contract

```python
class FilingDocument(BaseModel):
    document_id: str             # e.g., "doc_0000320193_000032019323000106"
    cik: str                     # 10-digit string, e.g., "0000320193"
    ticker: Optional[str]        # e.g., "AAPL"
    company_name: str            # e.g., "Apple Inc."
    form_type: str               # "10-K", "10-Q", "10-K/A", "10-Q/A"
    accession_number: str        # e.g., "0000320193-23-000106"
    filing_date: str             # ISO date "YYYY-MM-DD"
    report_period: str           # Period end date "YYYY-MM-DD"
    fiscal_year: Optional[int]   # e.g., 2023
    fiscal_quarter: Optional[int]# 1, 2, 3, 4, or None for 10-K
    primary_document_name: str   # e.g., "aapl-20230930.htm"
    source_url: str              # Official SEC EDGAR URL
    raw_sha256: str              # SHA-256 hex digest of raw file bytes
    byte_size: int               # Exact byte count
    fetched_at: str              # ISO datetime
    parsed_at: Optional[str]     # ISO datetime
    parser_version: str          # e.g., "1.0.0"
    status: DocumentStatus       # "FETCHED", "PARSED", "INDEXED", "FAILED"
    diagnostics: List[str] = []  # Parser warnings or error messages
```

## 2. Table and Cell Model Contract

```python
class TableCell(BaseModel):
    cell_id: str                 # Unique cell locator
    row_index: int
    column_index: int
    raw_text: str                # Verbatim source string: "$(1,245)"
    normalized_text: str         # Stripped text: "-1245"
    numeric_value: Optional[Decimal] # -1245.0 if numeric, None if text or dash
    is_empty_or_dash: bool       # True for "-", "—", "N/A", ""
    row_label: str               # Effective hierarchical row label
    column_label: str            # Effective hierarchical header path
    unit: Optional[str]          # Extracted unit declaration
    fiscal_period: Optional[str] # Period inferred from column header

class TableRecord(BaseModel):
    table_id: str                # e.g., "tbl_doc_..._0004_a1b2c3d4"
    document_id: str
    section_id: str              # e.g., "Item 8"
    caption: str                 # Extracted table caption
    units_text: Optional[str]    # e.g., "in millions, except per share amounts"
    source_locator: str          # DOM locator / table index
    column_headers: List[str]    # Flattened effective paths for each column
    row_count: int
    column_count: int
    parse_warnings: List[str] = []
```

## 3. Chunk and Index Contract

```python
class ChunkRecord(BaseModel):
    chunk_id: str                # Deterministic SHA-256 derived ID
    document_id: str
    chunk_kind: ChunkKind        # "narrative", "table_group", "table_row", "footnote"
    ordinal: int                 # Sequence order within document
    section_id: str              # "Item 7", "Item 8", etc.
    section_title: str           # Full heading title
    text: str                    # Context-preserving text for retrieval & generation
    raw_text: str                # Exact raw excerpt
    token_count: int             # Approximate token count (character count / 4)
    table_id: Optional[str]      # Populated if table chunk
    row_labels: List[str] = []   # Line items included in chunk
    column_labels: List[str] = []# Columns included in chunk
    units: Optional[str]         # Declared units
    source_url: str
    source_locator: str          # Section/Table DOM locator
    content_hash: str            # SHA-256 of text

class IndexManifest(BaseModel):
    manifest_version: str = "1.0"
    created_at: str
    chunker_version: str
    embedding_model_id: str
    embedding_dimension: int
    normalization: str = "L2"
    total_chunks: int
    source_document_ids: List[str]
    source_corpus_hash: str
    faiss_index_checksum: str
    id_map_checksum: str
```

## 4. Query, Retrieval Trace, and Generation Contract

```python
class QueryRequest(BaseModel):
    query: str
    filters: Optional[MetadataFilter] = None
    retriever_mode: RetrieverMode = RetrieverMode.HYBRID_RRF # BM25, DENSE, HYBRID_RRF, RERANKED
    top_k: int = 5
    enable_reranker: bool = True
    enable_nli: bool = True

class RetrievalCandidate(BaseModel):
    chunk_id: str
    document_id: str
    retriever: str               # "bm25", "dense", "rrf", "reranker"
    rank: int
    raw_score: float             # Lexical BM25 score, cosine similarity, or reranker logit
    rrf_score: Optional[float] = None
    text_preview: str

class RetrievalTrace(BaseModel):
    query_id: str
    query_text: str
    applied_filters: Dict[str, Any]
    bm25_candidates: List[RetrievalCandidate]
    dense_candidates: List[RetrievalCandidate]
    fused_candidates: List[RetrievalCandidate]
    reranked_candidates: List[RetrievalCandidate]
    final_evidence_chunk_ids: List[str]
    timings_ms: Dict[str, float]

class NumericFact(BaseModel):
    metric: str                  # e.g., "Revenue"
    raw_value: str               # e.g., "123,400"
    numeric_value: Optional[Decimal] # e.g., 123400.0
    unit: Optional[str]          # e.g., "USD_MILLIONS"
    period: Optional[str]        # e.g., "FY2023"

class AtomicClaim(BaseModel):
    claim_id: str                # "c1", "c2"
    text: str                    # Claim statement
    claim_kind: ClaimKind        # "numeric", "narrative", "comparison"
    source_chunk_ids: List[str]  # Must match retrieved chunk IDs
    numeric_facts: List[NumericFact] = []
    audit_status: AuditStatus = AuditStatus.AUDITOR_UNAVAILABLE
    audit_reason: str = ""
    nli_entailment_score: Optional[float] = None
    nli_contradiction_score: Optional[float] = None

class QueryResponse(BaseModel):
    query_id: str
    answer_status: AnswerStatus  # "ANSWERED", "PARTIALLY_SUPPORTED", "ABSTAINED", "CONFLICTING_EVIDENCE", "GENERATION_ERROR"
    summary: str
    claims: List[AtomicClaim]
    retrieved_evidence: List[ChunkRecord]
    retrieval_trace: RetrievalTrace
    model_version: str
    prompt_version: str
    limitations: List[str] = []
```

## 5. Audit Status Enum and Precedence Contract

```python
class AuditStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NUMERIC_MISMATCH = "NUMERIC_MISMATCH"
    INVALID_CITATION = "INVALID_CITATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    AUDITOR_UNAVAILABLE = "AUDITOR_UNAVAILABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
```

### Precedence Matrix:
1. `INVALID_CITATION`: Triggered if `source_chunk_ids` contains any ID outside retrieved evidence.
2. `NUMERIC_MISMATCH`: Triggered if explicit numeric claim mismatches cited source figure, unit, sign, or period.
3. `CONTRADICTED`: Triggered if NLI contradiction score $\ge \tau_{\text{contradict}}$ or deterministic check detects direct negation.
4. `CONFLICTING_EVIDENCE`: Triggered if multiple cited sources provide contradictory figures or statements.
5. `SUPPORTED`: Triggered only when citations are valid, numeric checks pass, and NLI entailment $\ge \tau_{\text{support}}$.
6. `INSUFFICIENT_EVIDENCE`: Default when evidence fails to meet support criteria without direct contradiction.
