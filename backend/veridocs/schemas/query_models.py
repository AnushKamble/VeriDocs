"""
Query, retrieval trace, claim, citation, and audit response models for VeriDocs.
"""

from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from veridocs.schemas.data_models import ChunkRecord


class RetrieverMode(str, Enum):
    BM25 = "bm25"
    DENSE = "dense"
    HYBRID_RRF = "hybrid_rrf"
    RERANKED = "reranked"


class ClaimKind(str, Enum):
    NUMERIC = "numeric"
    NARRATIVE = "narrative"
    COMPARISON = "comparison"


class AuditStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NUMERIC_MISMATCH = "NUMERIC_MISMATCH"
    INVALID_CITATION = "INVALID_CITATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    AUDITOR_UNAVAILABLE = "AUDITOR_UNAVAILABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    PARTIALLY_SUPPORTED = "partially_supported"
    ABSTAINED = "abstained"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    GENERATION_ERROR = "generation_error"
    AUDITOR_UNAVAILABLE = "auditor_unavailable"


class MetadataFilter(BaseModel):
    ticker: Optional[str] = None
    cik: Optional[str] = None
    form_type: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    section_id: Optional[str] = None
    document_ids: Optional[List[str]] = None


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    filters: Optional[MetadataFilter] = None
    retriever_mode: RetrieverMode = RetrieverMode.HYBRID_RRF
    top_k: int = Field(default=5, ge=1, le=50)
    enable_reranker: bool = True
    enable_nli: bool = True


class RetrievalCandidate(BaseModel):
    chunk_id: str
    document_id: str
    retriever: str
    rank: int
    raw_score: float
    rrf_score: Optional[float] = None
    text_preview: str = ""


class RetrievalTrace(BaseModel):
    query_id: str
    query_text: str
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    bm25_candidates: List[RetrievalCandidate] = Field(default_factory=list)
    dense_candidates: List[RetrievalCandidate] = Field(default_factory=list)
    fused_candidates: List[RetrievalCandidate] = Field(default_factory=list)
    reranked_candidates: List[RetrievalCandidate] = Field(default_factory=list)
    final_evidence_chunk_ids: List[str] = Field(default_factory=list)
    timings_ms: Dict[str, float] = Field(default_factory=dict)


class NumericFact(BaseModel):
    metric: str
    raw_value: str
    numeric_value: Optional[Decimal] = None
    unit: Optional[str] = None
    period: Optional[str] = None


class AtomicClaim(BaseModel):
    claim_id: str
    text: str
    claim_kind: ClaimKind = ClaimKind.NARRATIVE
    source_chunk_ids: List[str] = Field(default_factory=list)
    numeric_facts: List[NumericFact] = Field(default_factory=list)
    audit_status: AuditStatus = AuditStatus.AUDITOR_UNAVAILABLE
    audit_reason: str = ""
    nli_entailment_score: Optional[float] = None
    nli_contradiction_score: Optional[float] = None


class GeneratorRawOutput(BaseModel):
    """Structured JSON schema that the LLM is instructed to emit."""
    summary: str
    claims: List[AtomicClaim]
    limitations: List[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    query_id: str
    answer_status: AnswerStatus
    summary: str
    claims: List[AtomicClaim]
    retrieved_evidence: List[ChunkRecord] = Field(default_factory=list)
    retrieval_trace: RetrievalTrace
    model_version: str
    prompt_version: str = "1.0"
    limitations: List[str] = Field(default_factory=list)
