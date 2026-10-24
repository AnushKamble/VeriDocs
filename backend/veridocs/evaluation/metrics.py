"""
Empirical evaluation metrics for information retrieval and financial claim audit.
Includes Recall@k, MRR, nDCG@k, numeric exactness, citation precision, and bootstrap confidence intervals.
"""

from decimal import Decimal
import math
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np
from pydantic import BaseModel, Field

from veridocs.schemas.benchmark_models import BenchmarkGoldEvidence


class EvaluationResult(BaseModel):
    question_id: str
    baseline: str
    retrieved_chunk_ids: List[str] = Field(default_factory=list)
    gold_chunk_hits: List[str] = Field(default_factory=list)
    first_hit_rank: Optional[int] = None
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    ndcg_at_5: float = 0.0
    answer_text: Optional[str] = None
    predicted_numeric_value: Optional[Decimal] = None
    expected_numeric_value: Optional[Decimal] = None
    numeric_exactness: Optional[bool] = None
    cited_chunk_ids: List[str] = Field(default_factory=list)
    citation_precision: Optional[float] = None
    is_abstention: bool = False
    is_answerable: bool = True
    abstention_correct: Optional[bool] = None
    stage_timings_ms: Dict[str, float] = Field(default_factory=dict)
    total_latency_ms: float = 0.0


class EvaluationMetricsResult(BaseModel):
    mrr: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    ndcg_at_5: float
    numeric_exactness: float
    citation_precision: float
    abstention_accuracy: float
    mean_latency_ms: float = 0.0
    confidence_intervals_95: Dict[str, Tuple[float, float]] = Field(default_factory=dict)


def compute_mrr(rank_positions: Sequence[Optional[int]]) -> float:
    """
    Compute Mean Reciprocal Rank (MRR).
    rank_positions: 1-based ranks of first relevant item, or None if not found.
    """
    if not rank_positions:
        return 0.0
    reciprocals = [1.0 / r if r and r > 0 else 0.0 for r in rank_positions]
    return float(np.mean(reciprocals))


def compute_recall_at_k(retrieved_chunk_ids: Sequence[str], gold_chunk_ids: Sequence[str], k: int) -> float:
    """
    Compute Recall@k: fraction of gold chunks retrieved within top-k.
    """
    if not gold_chunk_ids:
        return 1.0  # If no gold chunks required, recall is trivially complete
    top_k_retrieved = set(retrieved_chunk_ids[:k])
    hits = len(set(gold_chunk_ids) & top_k_retrieved)
    return hits / len(gold_chunk_ids)


def compute_ndcg_at_k(retrieved_chunk_ids: Sequence[str], gold_chunk_ids: Sequence[str], k: int = 5) -> float:
    """
    Compute Normalized Discounted Cumulative Gain at k (binary relevance).
    """
    if not gold_chunk_ids:
        return 1.0

    gold_set = set(gold_chunk_ids)
    dcg = 0.0
    for i, cid in enumerate(retrieved_chunk_ids[:k]):
        if cid in gold_set:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because rank is 1-based

    # Ideal DCG
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold_set), k)))
    return dcg / idcg if idcg > 0 else 0.0


def compute_numeric_exactness(
    predicted_val: Optional[Decimal],
    expected_val: Optional[Decimal],
    tolerance: Decimal = Decimal("0.001"),
) -> bool:
    """Checks whether predicted number matches expected gold value within tolerance."""
    if expected_val is None:
        return True
    if predicted_val is None:
        return False
    if expected_val == 0:
        return abs(predicted_val) <= tolerance
    return abs(predicted_val - expected_val) / abs(expected_val) <= tolerance


def compute_citation_precision(
    cited_chunk_ids: Sequence[str],
    relevant_chunk_ids: Sequence[str],
) -> float:
    """
    Compute citation precision: proportion of cited chunks that are relevant.
    If no citations made, precision is 1.0 if no citations were required/appropriate, else 0.0.
    """
    if not cited_chunk_ids:
        return 1.0 if not relevant_chunk_ids else 0.0
    relevant_set = set(relevant_chunk_ids)
    hits = sum(1 for cid in cited_chunk_ids if cid in relevant_set)
    return hits / len(cited_chunk_ids)


def compute_abstention_accuracy(is_abstention: bool, is_answerable: bool) -> bool:
    """
    True if correctly abstained on unanswerable query,
    or correctly answered (did not abstain) on answerable query.
    """
    if not is_answerable:
        return is_abstention
    return not is_abstention


def is_chunk_relevant_to_gold(
    chunk_text: str,
    chunk_locator: str,
    gold: BenchmarkGoldEvidence,
) -> bool:
    """
    Determines if a retrieved chunk matches a gold evidence specification.
    Checks locator match, verbatim excerpt inclusion, or table caption/label alignment.
    """
    chunk_text_clean = chunk_text.strip().lower()
    locator_clean = chunk_locator.strip().lower()

    # 1. Exact locator alignment
    if gold.source_locator and (
        gold.source_locator.lower() in locator_clean or locator_clean in gold.source_locator.lower()
    ):
        return True

    # 2. Verbatim excerpt match (significant substring)
    if gold.verbatim_text:
        vt_clean = gold.verbatim_text.strip().lower()
        if vt_clean in chunk_text_clean:
            return True
        # If verbatim is long, check if 60% of key words appear
        words = [w for w in vt_clean.split() if len(w) > 3]
        if words:
            matches = sum(1 for w in words if w in chunk_text_clean)
            if matches / len(words) >= 0.75:
                return True

    # 3. Table caption + row label alignment
    if gold.table_caption and gold.row_label:
        if gold.table_caption.lower() in chunk_text_clean and gold.row_label.lower() in chunk_text_clean:
            return True

    return False


def compute_bootstrap_ci(
    values: Sequence[float],
    n_resamples: int = 1000,
    confidence_level: float = 0.95,
    random_seed: int = 42,
) -> Tuple[float, float]:
    """
    Compute non-parametric bootstrap confidence interval for the mean.
    """
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        return (float(values[0]), float(values[0]))

    rng = np.random.default_rng(random_seed)
    arr = np.array(values)
    boot_means = []
    n = len(arr)

    for _ in range(n_resamples):
        sample = rng.choice(arr, size=n, replace=True)
        boot_means.append(np.mean(sample))

    alpha = (1.0 - confidence_level) / 2.0
    lower = float(np.percentile(boot_means, alpha * 100))
    upper = float(np.percentile(boot_means, (1.0 - alpha) * 100))
    return (round(lower, 4), round(upper, 4))


def aggregate_baseline_metrics(
    results: Sequence[EvaluationResult],
    n_resamples: int = 1000,
) -> EvaluationMetricsResult:
    """
    Aggregates per-question EvaluationResults for a baseline into summary metrics
    with 95% bootstrap confidence intervals.
    """
    if not results:
        return EvaluationMetricsResult(
            mrr=0.0,
            recall_at_1=0.0,
            recall_at_3=0.0,
            recall_at_5=0.0,
            recall_at_10=0.0,
            ndcg_at_5=0.0,
            numeric_exactness=0.0,
            citation_precision=0.0,
            abstention_accuracy=0.0,
            mean_latency_ms=0.0,
        )

    # 1. Retrieval
    first_hits = [r.first_hit_rank for r in results]
    mrr_val = compute_mrr(first_hits)
    rec_1_vals = [r.recall_at_1 for r in results]
    rec_3_vals = [r.recall_at_3 for r in results]
    rec_5_vals = [r.recall_at_5 for r in results]
    rec_10_vals = [r.recall_at_10 for r in results]
    ndcg_5_vals = [r.ndcg_at_5 for r in results]

    # 2. Numeric Exactness (only on cases where numeric expectation is defined)
    num_results = [1.0 if r.numeric_exactness else 0.0 for r in results if r.numeric_exactness is not None]
    num_exactness_val = float(np.mean(num_results)) if num_results else 1.0

    # 3. Citation Precision
    cit_precisions = [r.citation_precision for r in results if r.citation_precision is not None]
    cit_prec_val = float(np.mean(cit_precisions)) if cit_precisions else 1.0

    # 4. Abstention Accuracy
    abstention_results = [1.0 if r.abstention_correct else 0.0 for r in results if r.abstention_correct is not None]
    abstention_acc_val = float(np.mean(abstention_results)) if abstention_results else 1.0

    # 5. Latency
    mean_lat = float(np.mean([r.total_latency_ms for r in results]))

    # 6. Bootstrap Confidence Intervals
    cis: Dict[str, Tuple[float, float]] = {
        "mrr": compute_bootstrap_ci([1.0 / r if r and r > 0 else 0.0 for r in first_hits], n_resamples),
        "recall_at_5": compute_bootstrap_ci(rec_5_vals, n_resamples),
        "ndcg_at_5": compute_bootstrap_ci(ndcg_5_vals, n_resamples),
        "abstention_accuracy": compute_bootstrap_ci(abstention_results, n_resamples) if abstention_results else (1.0, 1.0),
    }
    if num_results:
        cis["numeric_exactness"] = compute_bootstrap_ci(num_results, n_resamples)

    return EvaluationMetricsResult(
        mrr=round(mrr_val, 4),
        recall_at_1=round(float(np.mean(rec_1_vals)), 4),
        recall_at_3=round(float(np.mean(rec_3_vals)), 4),
        recall_at_5=round(float(np.mean(rec_5_vals)), 4),
        recall_at_10=round(float(np.mean(rec_10_vals)), 4),
        ndcg_at_5=round(float(np.mean(ndcg_5_vals)), 4),
        numeric_exactness=round(num_exactness_val, 4),
        citation_precision=round(cit_prec_val, 4),
        abstention_accuracy=round(abstention_acc_val, 4),
        mean_latency_ms=round(mean_lat, 2),
        confidence_intervals_95=cis,
    )
