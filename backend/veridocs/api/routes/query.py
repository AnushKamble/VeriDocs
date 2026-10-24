"""
FastAPI route handlers for grounded query processing, retrieval tracing, and claim auditing.
"""

import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException

from veridocs.api.dependencies import (
    QUERY_TRACES,
    get_generator_provider,
    get_nli_auditor,
    get_policy_engine,
    get_retrieval_pipeline,
)
from veridocs.audit.nli_auditor import NLIAuditor
from veridocs.audit.response_policy import ResponsePolicyEngine
from veridocs.config.settings import settings
from veridocs.generation.provider import GeneratorProvider
from veridocs.generation.structured_answerer import StructuredAnswerer
from veridocs.retrieval.pipeline import RetrievalPipeline
from veridocs.schemas.query_models import (
    AnswerStatus,
    AuditStatus,
    QueryRequest,
    QueryResponse,
    RetrievalTrace,
)
from veridocs.utils.logging import get_logger

logger = get_logger("veridocs.api.query")
router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def execute_query(
    req: QueryRequest,
    retrieval_pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline),
    generator_provider: GeneratorProvider = Depends(get_generator_provider),
    nli_auditor: NLIAuditor = Depends(get_nli_auditor),
    policy_engine: ResponsePolicyEngine = Depends(get_policy_engine),
) -> QueryResponse:
    """
    Execute end-to-end grounded query:
    1. Hybrid retrieval (BM25 + Dense + RRF + Cross-Encoder Reranker)
    2. Structured answer generation with claim-level citations
    3. NLI directional premise->hypothesis audit
    4. Deterministic numeric verification and response policy precedence
    """
    query_id = f"q_{uuid.uuid4().hex[:12]}"
    start_total = time.perf_counter()

    # 1. Retrieval
    try:
        retrieved_chunks, trace = retrieval_pipeline.execute(
            query=req.query,
            filters=req.filters,
            retriever_mode=req.retriever_mode,
            top_k=req.top_k,
            query_id=query_id,
        )
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        retrieved_chunks = []
        trace = RetrievalTrace(query_id=query_id, query_text=req.query)


    # 2. Structured Generation
    answerer = StructuredAnswerer(generator_provider)
    try:
        answer_result = await answerer.answer(
            query=req.query,
            retrieved_evidence=retrieved_chunks,
        )
    except Exception as e:
        logger.error(f"Generation error: {e}")
        return QueryResponse(
            query_id=query_id,
            answer_status=AnswerStatus.GENERATION_ERROR,
            summary=f"Error generating answer: {str(e)}",
            claims=[],
            retrieved_evidence=retrieved_chunks,
            retrieval_trace=trace,
            model_version=settings.ollama_model_name,
            limitations=["Generator execution error."],
        )

    claims = answer_result.claims
    chunk_map = {c.chunk_id: c for c in retrieved_chunks}

    # 3. NLI Audit (if enabled and claims present)
    if req.enable_nli and claims and retrieved_chunks:
        pairs_to_audit = []
        claim_pair_indices = []

        for c_idx, claim in enumerate(claims):
            # Gather premise text from cited chunks
            cited_texts = [chunk_map[cid].text for cid in claim.source_chunk_ids if cid in chunk_map]
            if cited_texts:
                premise = "\n".join(cited_texts)
                pairs_to_audit.append((premise, claim.text))
                claim_pair_indices.append(c_idx)

        if pairs_to_audit:
            try:
                nli_scores_list = nli_auditor.audit_batch(pairs_to_audit)
                for c_idx, scores in zip(claim_pair_indices, nli_scores_list):
                    claims[c_idx].nli_entailment_score = scores.entailment
                    claims[c_idx].nli_contradiction_score = scores.contradiction
            except Exception as e:
                logger.warning(f"NLI auditing warning: {e}")

    # 4. Response Policy Engine (Precedence rules + numeric check + abstention)
    is_abstained = answer_result.answer_status == AnswerStatus.ABSTAINED
    policy_res = policy_engine.evaluate_response(
        claims=claims,
        evidence_chunks=retrieved_chunks,
        is_generation_abstained=is_abstained,
    )

    total_time_ms = (time.perf_counter() - start_total) * 1000.0
    trace.timings_ms["total_query_execution_ms"] = round(total_time_ms, 2)

    # Store trace for auditing
    QUERY_TRACES[query_id] = trace

    return QueryResponse(
        query_id=query_id,
        answer_status=policy_res.overall_status,
        summary=answer_result.summary,
        claims=policy_res.audited_claims,
        retrieved_evidence=retrieved_chunks,
        retrieval_trace=trace,
        model_version=answer_result.model_name or settings.ollama_model_name,
        prompt_version="1.0",
        limitations=answer_result.limitations,
    )


@router.get("/traces/{query_id}", response_model=RetrievalTrace)
async def get_query_trace(query_id: str) -> RetrievalTrace:
    """Retrieve the full retrieval trace and stage breakdown for a query."""
    if query_id not in QUERY_TRACES:
        raise HTTPException(status_code=404, detail=f"Trace not found for query_id '{query_id}'")
    return QUERY_TRACES[query_id]
