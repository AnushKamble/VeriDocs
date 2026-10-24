"""
Unit tests for evaluation metrics (Recall@k, MRR, nDCG, Numeric Exactness, Citation Precision, CIs).
"""

from decimal import Decimal
import pytest

from veridocs.evaluation.metrics import (
    EvaluationResult,
    aggregate_baseline_metrics,
    compute_abstention_accuracy,
    compute_bootstrap_ci,
    compute_citation_precision,
    compute_mrr,
    compute_ndcg_at_k,
    compute_numeric_exactness,
    compute_recall_at_k,
    is_chunk_relevant_to_gold,
)
from veridocs.schemas.benchmark_models import BenchmarkGoldEvidence


def test_compute_mrr():
    # Rank 1 -> 1.0, Rank 2 -> 0.5, None -> 0.0 => mean = 1.5 / 3 = 0.5
    ranks = [1, 2, None]
    mrr = compute_mrr(ranks)
    assert pytest.approx(mrr, 0.001) == 0.5

    assert compute_mrr([]) == 0.0
    assert compute_mrr([None, None]) == 0.0
    assert compute_mrr([1, 1, 1]) == 1.0


def test_compute_recall_at_k():
    retrieved = ["c1", "c2", "c3", "c4", "c5"]
    gold = ["c2", "c4", "c6"]

    # At k=1: retrieved = ['c1'] -> hits = 0/3 = 0.0
    assert compute_recall_at_k(retrieved, gold, k=1) == 0.0

    # At k=2: retrieved = ['c1', 'c2'] -> hits = 1/3
    assert pytest.approx(compute_recall_at_k(retrieved, gold, k=2), 0.001) == 1.0 / 3.0

    # At k=4: retrieved = ['c1', 'c2', 'c3', 'c4'] -> hits = 2/3
    assert pytest.approx(compute_recall_at_k(retrieved, gold, k=4), 0.001) == 2.0 / 3.0

    # No gold items => trivially 1.0
    assert compute_recall_at_k(retrieved, [], k=5) == 1.0


def test_compute_ndcg_at_k():
    # Perfect retrieval: gold = ['c1', 'c2'], retrieved = ['c1', 'c2', 'c3']
    retrieved = ["c1", "c2", "c3"]
    gold = ["c1", "c2"]
    assert pytest.approx(compute_ndcg_at_k(retrieved, gold, k=3), 0.001) == 1.0

    # Reversed: gold = ['c2'], retrieved = ['c1', 'c2']
    # DCG = 1 / log2(1 + 2) = 1 / log2(3) = 0.6309
    # IDCG = 1 / log2(0 + 2) = 1 / log2(2) = 1.0
    # nDCG = 0.6309
    retrieved_subopt = ["c1", "c2"]
    gold_subopt = ["c2"]
    ndcg = compute_ndcg_at_k(retrieved_subopt, gold_subopt, k=2)
    assert 0.6 < ndcg < 0.7


def test_compute_numeric_exactness():
    # Exact match
    assert compute_numeric_exactness(Decimal("383285"), Decimal("383285")) is True

    # Within default 0.1% tolerance
    assert compute_numeric_exactness(Decimal("383286"), Decimal("383285")) is True

    # Outside tolerance
    assert compute_numeric_exactness(Decimal("400000"), Decimal("383285")) is False

    # Sign difference
    assert compute_numeric_exactness(Decimal("-100"), Decimal("100")) is False

    # Expected is None -> True (no numeric assertion expected)
    assert compute_numeric_exactness(Decimal("123"), None) is True

    # Predicted is None but expected exists -> False
    assert compute_numeric_exactness(None, Decimal("100")) is False


def test_compute_citation_precision():
    # 2 citations, both relevant
    assert compute_citation_precision(["c1", "c2"], ["c1", "c2", "c3"]) == 1.0

    # 2 citations, 1 relevant
    assert compute_citation_precision(["c1", "c4"], ["c1", "c2", "c3"]) == 0.5

    # 2 citations, 0 relevant
    assert compute_citation_precision(["c4", "c5"], ["c1", "c2", "c3"]) == 0.0


def test_compute_abstention_accuracy():
    # Unanswerable question: abstention is correct
    assert compute_abstention_accuracy(is_abstention=True, is_answerable=False) is True
    assert compute_abstention_accuracy(is_abstention=False, is_answerable=False) is False

    # Answerable question: abstention is incorrect
    assert compute_abstention_accuracy(is_abstention=False, is_answerable=True) is True
    assert compute_abstention_accuracy(is_abstention=True, is_answerable=True) is False


def test_is_chunk_relevant_to_gold():
    gold = BenchmarkGoldEvidence(
        document_id="doc_aapl_10k",
        section_id="Item 8",
        source_locator="table_004_consolidated_statements_of_operations",
        verbatim_text="Total net sales for fiscal 2023 were $383,285 million.",
        table_caption="Consolidated Statements of Operations",
        row_label="Total net sales",
    )

    # 1. Matches locator
    assert is_chunk_relevant_to_gold("Random text", "table_004_consolidated_statements_of_operations", gold) is True

    # 2. Matches verbatim text
    assert is_chunk_relevant_to_gold("In fiscal 2023, Total net sales for fiscal 2023 were $383,285 million as reported.", "chk_01", gold) is True

    # 3. Matches table caption and row label
    assert is_chunk_relevant_to_gold("Consolidated Statements of Operations table shows Total net sales was up.", "chk_02", gold) is True

    # 4. Irrelevant text
    assert is_chunk_relevant_to_gold("Employees may participate in stock plans.", "chk_03", gold) is False


def test_bootstrap_confidence_interval():
    values = [0.8, 0.85, 0.9, 0.88, 0.82, 0.87]
    ci_lower, ci_upper = compute_bootstrap_ci(values, n_resamples=500, random_seed=42)
    assert ci_lower <= ci_upper
    assert 0.75 <= ci_lower <= 0.95
    assert 0.75 <= ci_upper <= 0.95


def test_aggregate_baseline_metrics():
    res1 = EvaluationResult(
        question_id="q1",
        baseline="bm25",
        retrieved_chunk_ids=["c1", "c2"],
        gold_chunk_hits=["c1"],
        first_hit_rank=1,
        recall_at_1=1.0,
        recall_at_5=1.0,
        ndcg_at_5=1.0,
        numeric_exactness=True,
        citation_precision=1.0,
        is_abstention=False,
        is_answerable=True,
        abstention_correct=True,
        total_latency_ms=12.5,
    )
    res2 = EvaluationResult(
        question_id="q2",
        baseline="bm25",
        retrieved_chunk_ids=["c3", "c4"],
        gold_chunk_hits=[],
        first_hit_rank=None,
        recall_at_1=0.0,
        recall_at_5=0.0,
        ndcg_at_5=0.0,
        numeric_exactness=False,
        citation_precision=0.0,
        is_abstention=True,
        is_answerable=False,
        abstention_correct=True,
        total_latency_ms=15.5,
    )

    agg = aggregate_baseline_metrics([res1, res2], n_resamples=100)
    assert agg.recall_at_1 == 0.5
    assert agg.recall_at_5 == 0.5
    assert agg.mrr == 0.5
    assert agg.numeric_exactness == 0.5
    assert agg.abstention_accuracy == 1.0
    assert agg.mean_latency_ms == 14.0
    assert "recall_at_5" in agg.confidence_intervals_95
