"""
Threshold calibration engine for NLI and response policy.
Evaluates empirical calibration pairs to freeze decision thresholds.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel


from veridocs.audit.nli_auditor import NLIAuditor, NLIScores
from veridocs.utils.logging import get_logger

logger = get_logger("veridocs.audit.calibration")


class CalibrationResult(BaseModel):
    total_pairs: int
    optimal_entailment_threshold: float
    optimal_contradiction_threshold: float
    accuracy: float
    calibration_records: List[Dict[str, Any]]


def calibrate_thresholds(
    calibration_file: Path,
    output_file: Optional[Path] = None,
    auditor: Optional[NLIAuditor] = None,
) -> CalibrationResult:
    """
    Run empirical grid search over calibration dataset to find optimal decision thresholds.
    """
    if auditor is None:
        auditor = NLIAuditor.get_instance()

    records = []
    with open(calibration_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    pairs = [(r["premise"], r["hypothesis"]) for r in records]
    scores_list = auditor.audit_batch(pairs)

    detailed_records = []
    for r, scores in zip(records, scores_list):
        rec = dict(r)
        rec["predicted_scores"] = scores.model_dump()
        detailed_records.append(rec)

    # Grid search for best threshold
    best_acc = 0.0
    best_e_thresh = 0.65
    best_c_thresh = 0.50

    e_candidates = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    c_candidates = [0.40, 0.45, 0.50, 0.55, 0.60]

    for e_th in e_candidates:
        for c_th in c_candidates:
            correct = 0
            for r, s in zip(records, scores_list):
                gold = r["ground_truth_label"]
                if s.contradiction >= c_th:
                    pred = "contradiction"
                elif s.entailment >= e_th:
                    pred = "entailment"
                else:
                    pred = "neutral"

                if pred == gold:
                    correct += 1

            acc = correct / len(records)
            if acc > best_acc:
                best_acc = acc
                best_e_thresh = e_th
                best_c_thresh = c_th

    result = CalibrationResult(
        total_pairs=len(records),
        optimal_entailment_threshold=best_e_thresh,
        optimal_contradiction_threshold=best_c_thresh,
        accuracy=best_acc,
        calibration_records=detailed_records,
    )

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        logger.info(f"Saved calibrated thresholds to {output_file}")

    return result
