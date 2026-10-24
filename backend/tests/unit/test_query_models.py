from decimal import Decimal
import pytest
from pydantic import ValidationError

from veridocs.schemas.data_models import ChunkKind, ChunkRecord
from veridocs.schemas.query_models import (
    AnswerStatus,
    AtomicClaim,
    AuditStatus,
    ClaimKind,
    GeneratorRawOutput,
    MetadataFilter,
    NumericFact,
    QueryRequest,
    QueryResponse,
    RetrievalCandidate,
    RetrievalTrace,
    RetrieverMode,
)


def test_query_request_defaults_and_validation():
    req = QueryRequest(query="What was Apple's total revenue in FY2023?")
    assert req.retriever_mode == RetrieverMode.HYBRID_RRF
    assert req.top_k == 5
    assert req.enable_reranker is True
    assert req.enable_nli is True

    # Empty query must fail
    with pytest.raises(ValidationError):
        QueryRequest(query="")


def test_atomic_claim_and_numeric_fact():
    claim = AtomicClaim(
        claim_id="c1",
        text="Total revenue in FY2023 was $383,285 million.",
        claim_kind=ClaimKind.NUMERIC,
        source_chunk_ids=["chk_123"],
        numeric_facts=[
            NumericFact(
                metric="Total net sales",
                raw_value="383,285",
                numeric_value=Decimal("383285"),
                unit="USD_MILLIONS",
                period="FY2023",
            )
        ],
        audit_status=AuditStatus.SUPPORTED,
        audit_reason="Verified by Consolidated Statements of Operations table row",
        nli_entailment_score=0.98,
        nli_contradiction_score=0.01,
    )
    assert claim.claim_id == "c1"
    assert claim.audit_status == AuditStatus.SUPPORTED
    assert claim.numeric_facts[0].numeric_value == Decimal("383285")


def test_generator_raw_output_schema():
    raw_json = {
        "summary": "Apple reported total net sales of $383,285 million in fiscal year 2023.",
        "claims": [
            {
                "claim_id": "c1",
                "text": "Total net sales were $383,285 million in FY2023.",
                "claim_kind": "numeric",
                "source_chunk_ids": ["chk_1"],
                "numeric_facts": [
                    {
                        "metric": "Total net sales",
                        "raw_value": "383,285",
                        "unit": "USD_MILLIONS",
                        "period": "FY2023",
                    }
                ],
            }
        ],
        "limitations": [],
    }
    parsed = GeneratorRawOutput.model_validate(raw_json)
    assert len(parsed.claims) == 1
    assert parsed.claims[0].claim_kind == ClaimKind.NUMERIC


def test_retrieval_trace_and_query_response():
    trace = RetrievalTrace(
        query_id="q_123",
        query_text="FY2023 revenue",
        applied_filters={"ticker": "AAPL"},
        bm25_candidates=[
            RetrievalCandidate(
                chunk_id="chk_1",
                document_id="doc_1",
                retriever="bm25",
                rank=1,
                raw_score=15.4,
            )
        ],
        dense_candidates=[
            RetrievalCandidate(
                chunk_id="chk_1",
                document_id="doc_1",
                retriever="dense",
                rank=1,
                raw_score=0.88,
            )
        ],
        fused_candidates=[
            RetrievalCandidate(
                chunk_id="chk_1",
                document_id="doc_1",
                retriever="rrf",
                rank=1,
                raw_score=0.032,
                rrf_score=0.032,
            )
        ],
        final_evidence_chunk_ids=["chk_1"],
        timings_ms={"bm25_ms": 2.1, "dense_ms": 15.3, "rrf_ms": 0.4},
    )

    resp = QueryResponse(
        query_id="q_123",
        answer_status=AnswerStatus.ANSWERED,
        summary="Test summary",
        claims=[],
        retrieval_trace=trace,
        model_version="qwen3:8b",
        prompt_version="1.0",
    )
    assert resp.answer_status == AnswerStatus.ANSWERED
    assert resp.retrieval_trace.timings_ms["dense_ms"] == 15.3
