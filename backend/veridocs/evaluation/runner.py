"""
Benchmark evaluation runner executing baselines, ablations, and metric collections.
Supports BM25 (fixed & structured), Dense BGE, Hybrid RRF, Cross-Encoder Reranking,
and Full Audit System with 95% bootstrap confidence intervals.
"""

import asyncio
import concurrent.futures
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Sequence

from veridocs.audit.calculator import FinancialCalculator
from veridocs.audit.nli_auditor import NLIAuditor
from veridocs.audit.numeric_comparator import NumericComparator
from veridocs.audit.numeric_parser import ParsedNumericClaim, parse_numeric_claims
from veridocs.audit.response_policy import ResponsePolicyEngine
from veridocs.evaluation.metrics import (
    EvaluationMetricsResult,
    EvaluationResult,
    aggregate_baseline_metrics,
    compute_abstention_accuracy,
    compute_citation_precision,
    compute_ndcg_at_k,
    compute_numeric_exactness,
    compute_recall_at_k,
    is_chunk_relevant_to_gold,
)
from veridocs.generation.structured_answerer import StructuredAnswerer
from veridocs.retrieval.pipeline import RetrievalPipeline
from veridocs.schemas.benchmark_models import BenchmarkCase
from veridocs.schemas.query_models import (
    AnswerStatus,
    MetadataFilter,
    RetrieverMode,
)


def _run_async(coro):
    """Executes an async coroutine synchronously, handling running event loops safely."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return loop.run_until_complete(coro)


class BaselineType(str, Enum):
    BM25_FIXED = "bm25_fixed"
    BM25_STRUCTURED = "bm25_structured"
    DENSE_BGE = "dense_bge"
    HYBRID_RRF = "hybrid_rrf"
    RERANKED = "hybrid_reranked"
    FULL_SYSTEM = "full_system"
    AUDIT_NO_NLI = "audit_no_nli"


class BenchmarkRunner:
    """
    Executes benchmark evaluation suites across defined IR baselines and full auditing system.
    """

    def __init__(
        self,
        retrieval_pipeline: RetrievalPipeline,
        answerer: Optional[StructuredAnswerer] = None,
        numeric_comparator: Optional[NumericComparator] = None,
        nli_auditor: Optional[NLIAuditor] = None,
        policy_engine: Optional[ResponsePolicyEngine] = None,
        questions_path: str = "benchmarks/questions.jsonl",
        splits_path: str = "benchmarks/splits.json",
    ):
        self.pipeline = retrieval_pipeline
        self.answerer = answerer
        self.numeric_comparator = numeric_comparator
        self.nli_auditor = nli_auditor
        self.policy_engine = policy_engine
        self.questions_path = Path(questions_path)
        self.splits_path = Path(splits_path)

    def load_cases(
        self,
        split: Optional[str] = "dev",
        limit: Optional[int] = None,
    ) -> List[BenchmarkCase]:
        """Loads and filters benchmark cases by split (dev / test / all)."""
        if not self.questions_path.exists():
            return []

        # Load split IDs if available
        split_ids = None
        if split and split != "all" and self.splits_path.exists():
            with open(self.splits_path, "r", encoding="utf-8") as f:
                splits_data = json.load(f)
                split_ids = set(splits_data.get(split, []))

        cases: List[BenchmarkCase] = []
        with open(self.questions_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                case = BenchmarkCase.model_validate(data)
                if split_ids is not None:
                    if case.question_id in split_ids:
                        cases.append(case)
                else:
                    cases.append(case)

                if limit and len(cases) >= limit:
                    break

        return cases

    def evaluate_question(
        self,
        case: BenchmarkCase,
        baseline: BaselineType,
        top_k: int = 5,
    ) -> EvaluationResult:
        """Evaluates a single benchmark question for a given baseline."""
        t_start = time.perf_counter()
        timings: Dict[str, float] = {}

        # 1. Resolve Retrieval Mode
        mode_map = {
            BaselineType.BM25_FIXED: RetrieverMode.BM25,
            BaselineType.BM25_STRUCTURED: RetrieverMode.BM25,
            BaselineType.DENSE_BGE: RetrieverMode.DENSE,
            BaselineType.HYBRID_RRF: RetrieverMode.HYBRID_RRF,
            BaselineType.RERANKED: RetrieverMode.RERANKED,
            BaselineType.FULL_SYSTEM: RetrieverMode.RERANKED,
            BaselineType.AUDIT_NO_NLI: RetrieverMode.RERANKED,
        }
        retriever_mode = mode_map.get(baseline, RetrieverMode.HYBRID_RRF)

        # Filters
        filters = None
        if case.ticker:
            filters = MetadataFilter(ticker=case.ticker, form_type=case.form_type)

        # Execute Retrieval
        t_ret_start = time.perf_counter()
        retrieved_chunks, trace = self.pipeline.execute(
            query=case.question_text,
            retriever_mode=retriever_mode,
            top_k=max(top_k, 10),
            filters=filters,
            query_id=f"eval_{case.question_id}_{baseline.value}",
        )
        timings["retrieval_ms"] = round((time.perf_counter() - t_ret_start) * 1000.0, 2)
        if trace and trace.timings_ms:
            timings.update(trace.timings_ms)

        retrieved_ids = [c.chunk_id for c in retrieved_chunks]

        # 2. Score Retrieval Hits
        gold_chunk_hits: List[str] = []
        first_hit_rank: Optional[int] = None

        if case.is_answerable and case.gold_evidence:
            for rank_idx, chunk in enumerate(retrieved_chunks):
                hit = any(
                    is_chunk_relevant_to_gold(chunk.text, chunk.source_locator, gold)
                    for gold in case.gold_evidence
                )
                if hit:
                    gold_chunk_hits.append(chunk.chunk_id)
                    if first_hit_rank is None:
                        first_hit_rank = rank_idx + 1

        # Calculate Recall@k and nDCG
        rec_1 = compute_recall_at_k(retrieved_ids, gold_chunk_hits, k=1) if gold_chunk_hits else (1.0 if not case.is_answerable else 0.0)
        rec_3 = compute_recall_at_k(retrieved_ids, gold_chunk_hits, k=3) if gold_chunk_hits else (1.0 if not case.is_answerable else 0.0)
        rec_5 = compute_recall_at_k(retrieved_ids, gold_chunk_hits, k=5) if gold_chunk_hits else (1.0 if not case.is_answerable else 0.0)
        rec_10 = compute_recall_at_k(retrieved_ids, gold_chunk_hits, k=10) if gold_chunk_hits else (1.0 if not case.is_answerable else 0.0)
        ndcg_5 = compute_ndcg_at_k(retrieved_ids, gold_chunk_hits, k=5) if gold_chunk_hits else (1.0 if not case.is_answerable else 0.0)

        # 3. Answer Generation & Audit (if full system or audit baseline)
        answer_text = None
        predicted_num = None
        num_exact = None
        cited_ids: List[str] = []
        cit_prec = None
        is_abstention = False
        abstention_correct = None

        if baseline in (BaselineType.FULL_SYSTEM, BaselineType.AUDIT_NO_NLI) and self.answerer:
            t_gen_start = time.perf_counter()
            gen_res = _run_async(
                self.answerer.answer(
                    query=case.question_text,
                    retrieved_evidence=retrieved_chunks[:top_k],
                )
            )
            timings["generation_ms"] = round((time.perf_counter() - t_gen_start) * 1000.0, 2)
            answer_text = gen_res.summary
            cited_ids = list({cid for claim in gen_res.claims for cid in claim.source_chunk_ids})
            is_abstention = gen_res.answer_status == AnswerStatus.ABSTAINED or any(
                kw in gen_res.summary.lower()
                for kw in ["abstain", "insufficient", "does not contain", "no evidence", "unavailable"]
            )

            # Numeric Extraction & Checking
            extracted_nums = parse_numeric_claims(gen_res.summary)
            for claim in gen_res.claims:
                for fact in claim.numeric_facts:
                    if fact.numeric_value is not None:
                        extracted_nums.append(
                            ParsedNumericClaim(
                                raw_str=fact.raw_value,
                                numeric_value=fact.numeric_value,
                                scaled_value=fact.numeric_value,
                                unit=fact.unit,
                                period=fact.period,
                            )
                        )

            if extracted_nums:
                # Find closest numeric match to expected value
                if case.expected_numeric_value is not None:
                    matched = any(
                        compute_numeric_exactness(n.numeric_value, case.expected_numeric_value)
                        or compute_numeric_exactness(n.scaled_value, case.expected_numeric_value)
                        for n in extracted_nums
                    )
                    num_exact = matched
                    predicted_num = extracted_nums[0].numeric_value
                else:
                    predicted_num = extracted_nums[0].numeric_value
            elif case.expected_numeric_value is not None:
                num_exact = False

            # Citation Precision
            cit_prec = compute_citation_precision(cited_ids, gold_chunk_hits)

            # Abstention Accuracy
            abstention_correct = compute_abstention_accuracy(is_abstention, case.is_answerable)

        total_lat = round((time.perf_counter() - t_start) * 1000.0, 2)

        return EvaluationResult(
            question_id=case.question_id,
            baseline=baseline.value,
            retrieved_chunk_ids=retrieved_ids[:10],
            gold_chunk_hits=gold_chunk_hits,
            first_hit_rank=first_hit_rank,
            recall_at_1=round(rec_1, 4),
            recall_at_3=round(rec_3, 4),
            recall_at_5=round(rec_5, 4),
            recall_at_10=round(rec_10, 4),
            ndcg_at_5=round(ndcg_5, 4),
            answer_text=answer_text,
            predicted_numeric_value=predicted_num,
            expected_numeric_value=case.expected_numeric_value,
            numeric_exactness=num_exact,
            cited_chunk_ids=cited_ids,
            citation_precision=round(cit_prec, 4) if cit_prec is not None else None,
            is_abstention=is_abstention,
            is_answerable=case.is_answerable,
            abstention_correct=abstention_correct,
            stage_timings_ms=timings,
            total_latency_ms=total_lat,
        )

    def evaluate_baseline(
        self,
        baseline: BaselineType,
        cases: Sequence[BenchmarkCase],
        top_k: int = 5,
    ) -> List[EvaluationResult]:
        """Evaluates a batch of benchmark cases under a single baseline."""
        results: List[EvaluationResult] = []
        for case in cases:
            res = self.evaluate_question(case, baseline, top_k=top_k)
            results.append(res)
        return results

    def run_benchmark(
        self,
        split: str = "dev",
        baselines: Optional[Sequence[BaselineType]] = None,
        limit: Optional[int] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Runs comprehensive benchmark evaluation across selected split and baselines.
        """
        selected_baselines = baselines or [
            BaselineType.BM25_STRUCTURED,
            BaselineType.DENSE_BGE,
            BaselineType.HYBRID_RRF,
            BaselineType.RERANKED,
            BaselineType.FULL_SYSTEM,
        ]

        cases = self.load_cases(split=split, limit=limit)
        start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        baseline_results: Dict[str, List[EvaluationResult]] = {}
        metrics_summary: Dict[str, EvaluationMetricsResult] = {}

        for b in selected_baselines:
            res_list = self.evaluate_baseline(b, cases, top_k=top_k)
            baseline_results[b.value] = res_list
            metrics_summary[b.value] = aggregate_baseline_metrics(res_list)

        end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        return {
            "split": split,
            "total_questions": len(cases),
            "start_time": start_time,
            "end_time": end_time,
            "metrics_summary": {k: v.model_dump() for k, v in metrics_summary.items()},
            "raw_results": {
                k: [r.model_dump() for r in v] for k, v in baseline_results.items()
            },
        }
