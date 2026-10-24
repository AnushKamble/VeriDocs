"""
Unit tests for VeriDocs-SEC-50 benchmark dataset and calibration fixtures.
Ensures zero missing fields, valid Pydantic models, valid splits, and label sanity.
"""

import json
from pathlib import Path
import pytest
from veridocs.schemas.benchmark_models import BenchmarkCase, BenchmarkManifest, QuestionCategory

BENCHMARK_DIR = Path(__file__).resolve().parents[2].parent / "benchmarks"


def test_benchmark_manifest():
    manifest_path = BENCHMARK_DIR / "manifest.json"
    assert manifest_path.exists(), "benchmarks/manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    manifest = BenchmarkManifest.model_validate(data)
    assert manifest.total_questions == 50
    assert manifest.splits["dev_calibration_count"] == 15
    assert manifest.splits["held_out_test_count"] == 35
    assert len(manifest.covered_companies) == 4


def test_benchmark_questions_schema_and_distribution():
    questions_path = BENCHMARK_DIR / "questions.jsonl"
    assert questions_path.exists(), "benchmarks/questions.jsonl must exist"

    cases = []
    with open(questions_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            case = BenchmarkCase.model_validate_json(line)
            cases.append(case)

    assert len(cases) == 50, f"Expected 50 benchmark cases, got {len(cases)}"

    # Check unique IDs
    ids = [c.question_id for c in cases]
    assert len(ids) == len(set(ids)), "All question_ids must be unique"

    # Check distribution across categories
    cat_counts = {}
    for c in cases:
        cat_counts[c.category] = cat_counts.get(c.category, 0) + 1

    expected_counts = {
        QuestionCategory.NUMERIC_TABLE_LOOKUP: 10,
        QuestionCategory.PERIOD_COMPARISON: 8,
        QuestionCategory.UNITS_SIGN_EDGE_CASE: 6,
        QuestionCategory.NARRATIVE_MDA: 8,
        QuestionCategory.MULTI_EVIDENCE: 6,
        QuestionCategory.UNANSWERABLE: 6,
        QuestionCategory.AMBIGUOUS_PERIOD: 3,
        QuestionCategory.CONFLICTING: 3,
    }
    assert cat_counts == expected_counts, f"Category distribution mismatch: {cat_counts}"

    # Verify each case has valid fields
    for c in cases:
        assert c.question_text.strip()
        tickers = [t.strip() for t in c.ticker.split(",")]
        assert all(t in ["AAPL", "MSFT", "GOOGL", "NVDA"] for t in tickers)
        assert c.form_type in ["10-K", "10-Q"]
        if not c.is_answerable:
            assert "abstain" in c.reference_answer.lower() or "insufficient" in c.reference_answer.lower()
        else:
            assert c.reference_answer and len(c.reference_answer.strip()) > 0
            assert len(c.gold_evidence) > 0



def test_benchmark_splits():
    splits_path = BENCHMARK_DIR / "splits.json"
    assert splits_path.exists(), "benchmarks/splits.json must exist"

    with open(splits_path, "r", encoding="utf-8") as f:
        splits = json.load(f)

    assert "dev" in splits
    assert "test" in splits
    assert len(splits["dev"]) == 15
    assert len(splits["test"]) == 35

    dev_set = set(splits["dev"])
    test_set = set(splits["test"])

    # Disjoint check
    assert dev_set.isdisjoint(test_set), "Dev and Test splits must be disjoint"
    assert len(dev_set | test_set) == 50, "Union of Dev and Test must equal 50 questions"


def test_claim_audit_calibration_pairs():
    calib_path = BENCHMARK_DIR / "claim_audit_calibration.jsonl"
    assert calib_path.exists(), "benchmarks/claim_audit_calibration.jsonl must exist"

    pairs = []
    with open(calib_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            pairs.append(json.loads(line))

    assert len(pairs) == 20, f"Expected 20 calibration pairs, got {len(pairs)}"

    allowed_labels = {"entailment", "contradiction", "neutral"}
    label_counts = {lbl: 0 for lbl in allowed_labels}

    for p in pairs:
        assert "id" in p
        assert p["premise"].strip(), "Premise cannot be empty"
        assert p["hypothesis"].strip(), "Hypothesis cannot be empty"
        assert p["ground_truth_label"] in allowed_labels, f"Invalid label: {p['ground_truth_label']}"
        label_counts[p["ground_truth_label"]] += 1

    # Ensure all three labels are represented
    for lbl in allowed_labels:
        assert label_counts[lbl] >= 3, f"Label {lbl} underrepresented with count {label_counts[lbl]}"
