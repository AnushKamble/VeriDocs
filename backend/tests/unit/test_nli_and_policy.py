"""
Unit tests for NLI Auditor, Response Policy Engine, and Threshold Calibration.
Tests precedence hierarchy (Precedence 1 -> 2 -> 3 -> 4 -> 5), abstention rules, and threshold tuning.
"""

from decimal import Decimal
from pathlib import Path
import pytest

from veridocs.audit.response_policy import (
    PolicyThresholds,
    ResponsePolicyEngine,
)
from veridocs.schemas.data_models import ChunkKind, ChunkRecord
from veridocs.schemas.query_models import (
    AnswerStatus,
    AtomicClaim,
    AuditStatus,
    ClaimKind,
)


def create_test_chunk(chunk_id: str, text: str) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        document_id="doc_policy_10k",
        chunk_kind=ChunkKind.NARRATIVE,
        ordinal=0,
        section_id="Item 7",
        section_title="MD&A",
        text=text,
        raw_text=text,
        token_count=25,
        source_url="https://sec.gov",
        source_locator=f"loc_{chunk_id}",
        content_hash="mock_hash",
    )


def test_policy_precedence_invalid_citation():
    # Precedence 1: If cited chunk ID does not exist in evidence, status MUST be INVALID_CITATION
    engine = ResponsePolicyEngine()
    chunk = create_test_chunk("chk_001", "Apple sales grew 5%.")
    claim = AtomicClaim(
        claim_id="c1",
        text="Apple sales grew 5%.",
        source_chunk_ids=["chk_nonexistent_999"],
        nli_entailment_score=0.99,  # High entailment must NOT override invalid citation
    )

    res = engine.evaluate_response([claim], [chunk])
    assert res.audited_claims[0].audit_status == AuditStatus.INVALID_CITATION
    assert res.overall_status == AnswerStatus.ABSTAINED
    assert res.has_invalid_citations is True


def test_policy_precedence_numeric_mismatch_overrules_nli():
    # Precedence 2: Numeric mismatch MUST override even high NLI entailment score
    engine = ResponsePolicyEngine()
    # Source reports parenthetical loss $(312) million
    chunk = create_test_chunk("chk_001", "Derivative contracts unrealized loss: $(312) million.")
    # Claim falsely asserts a gain of $312 million
    claim = AtomicClaim(
        claim_id="c1",
        text="The company recorded an unrealized gain of $312 million.",
        source_chunk_ids=["chk_001"],
        nli_entailment_score=0.90,  # Simulated flawed NLI score
        nli_contradiction_score=0.05,
    )

    res = engine.evaluate_response([claim], [chunk])
    audited = res.audited_claims[0]
    # Numeric auditor must catch the sign mismatch and override NLI
    assert audited.audit_status == AuditStatus.NUMERIC_MISMATCH
    assert "Sign mismatch" in audited.audit_reason
    assert res.has_numeric_mismatches is True


def test_policy_precedence_nli_contradiction():
    # Precedence 3: Contradiction score >= threshold marks CONTRADICTED
    engine = ResponsePolicyEngine(PolicyThresholds(contradiction_threshold=0.50))
    chunk = create_test_chunk("chk_001", "International sales declined across Europe.")
    claim = AtomicClaim(
        claim_id="c1",
        text="European revenue increased dramatically.",
        source_chunk_ids=["chk_001"],
        nli_contradiction_score=0.88,
        nli_entailment_score=0.02,
    )

    res = engine.evaluate_response([claim], [chunk])
    audited = res.audited_claims[0]
    assert audited.audit_status == AuditStatus.CONTRADICTED
    assert res.has_contradictions is True


def test_policy_precedence_nli_entailment():
    # Precedence 4: Entailment score >= threshold marks SUPPORTED
    engine = ResponsePolicyEngine(PolicyThresholds(entailment_threshold=0.65))
    chunk = create_test_chunk("chk_001", "Gross margin improved to 44.1%.")
    claim = AtomicClaim(
        claim_id="c1",
        text="Gross margin reached 44.1%.",
        source_chunk_ids=["chk_001"],
        nli_entailment_score=0.92,
        nli_contradiction_score=0.01,
    )

    res = engine.evaluate_response([claim], [chunk])
    audited = res.audited_claims[0]
    assert audited.audit_status == AuditStatus.SUPPORTED
    assert res.overall_status == AnswerStatus.ANSWERED


def test_policy_precedence_insufficient_evidence():
    # Precedence 5: Low scores default to INSUFFICIENT_EVIDENCE
    engine = ResponsePolicyEngine(PolicyThresholds(entailment_threshold=0.65, contradiction_threshold=0.50))
    chunk = create_test_chunk("chk_001", "Operating costs increased slightly during the quarter.")
    claim = AtomicClaim(
        claim_id="c1",
        text="Management plans to expand retail operations across Latin America.",
        source_chunk_ids=["chk_001"],
        nli_entailment_score=0.30,  # Below entailment threshold
        nli_contradiction_score=0.20,  # Below contradiction threshold
    )

    res = engine.evaluate_response([claim], [chunk])
    audited = res.audited_claims[0]
    assert audited.audit_status == AuditStatus.INSUFFICIENT_EVIDENCE
    assert res.overall_status == AnswerStatus.ABSTAINED



def test_policy_overall_partially_supported():
    engine = ResponsePolicyEngine()
    chunk1 = create_test_chunk("chk_001", "Gross margin was 44.1%.")
    chunk2 = create_test_chunk("chk_002", "Operating expenses rose 10%.")

    claim1 = AtomicClaim(
        claim_id="c1",
        text="Gross margin was 44.1%.",
        source_chunk_ids=["chk_001"],
        nli_entailment_score=0.95,
    )
    claim2 = AtomicClaim(
        claim_id="c2",
        text="Marketing budget will double in 2025.",
        source_chunk_ids=["chk_002"],
        nli_entailment_score=0.20,
        nli_contradiction_score=0.10,
    )

    res = engine.evaluate_response([claim1, claim2], [chunk1, chunk2])
    assert res.overall_status == AnswerStatus.PARTIALLY_SUPPORTED
    assert res.audited_claims[0].audit_status == AuditStatus.SUPPORTED
    assert res.audited_claims[1].audit_status == AuditStatus.INSUFFICIENT_EVIDENCE


def test_nli_auditor_predictions():
    from veridocs.audit.nli_auditor import NLIAuditor

    auditor = NLIAuditor.get_instance()

    # 1. Clear entailment
    premise1 = "Apple Inc. Total net sales were $383,285 million in fiscal year 2023."
    hyp1 = "Apple generated $383,285 million in net sales in fiscal 2023."
    scores1 = auditor.audit_pair(premise1, hyp1)
    assert scores1.dominant_label == "entailment"
    assert scores1.entailment > 0.60

    # 2. Clear contradiction
    premise2 = "Apple Inc. Total net sales were $383,285 million in fiscal year 2023."
    hyp2 = "Apple net sales were zero in 2023."
    scores2 = auditor.audit_pair(premise2, hyp2)
    assert scores2.dominant_label == "contradiction"
    assert scores2.contradiction > 0.60

    # 3. Neutral / unstated speculation
    premise3 = "Apple Inc. Total net sales were $383,285 million in fiscal year 2023."
    hyp3 = "Apple plans to acquire a space exploration company next quarter."
    scores3 = auditor.audit_pair(premise3, hyp3)
    assert scores3.dominant_label == "neutral"
    assert scores3.neutral > 0.40


def test_calibration_runner(tmp_path):
    from veridocs.audit.calibration import calibrate_thresholds

    calib_file = Path(__file__).resolve().parents[2].parent / "benchmarks" / "claim_audit_calibration.jsonl"
    assert calib_file.exists()

    output_file = tmp_path / "calibrated_thresholds.json"
    result = calibrate_thresholds(calibration_file=calib_file, output_file=output_file)

    assert result.total_pairs == 20
    assert result.optimal_entailment_threshold >= 0.50
    assert result.optimal_contradiction_threshold >= 0.40
    assert result.accuracy >= 0.70  # Model should achieve at least 70% accuracy on calibration pairs
    assert output_file.exists()

