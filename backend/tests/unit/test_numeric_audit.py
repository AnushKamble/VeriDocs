"""
Unit tests for numeric claim extraction, scale comparison, and consistency audit.
"""

from decimal import Decimal
import pytest

from veridocs.audit.numeric_parser import parse_numeric_claims, extract_period
from veridocs.audit.numeric_comparator import NumericComparator
from veridocs.schemas.data_models import ChunkKind, ChunkRecord
from veridocs.schemas.query_models import AuditStatus


def create_mock_chunk(text: str) -> ChunkRecord:
    return ChunkRecord(
        chunk_id="chunk_test_audit",
        document_id="doc_audit_10k",
        chunk_kind=ChunkKind.TABLE_ROW,
        ordinal=1,
        section_id="Item 8",
        section_title="Financial Statements",
        text=text,
        raw_text=text,
        token_count=30,
        source_url="https://sec.gov",
        source_locator="loc_1",
        content_hash="h123",
    )


def test_parse_numeric_claims_millions_and_period():
    text = "Apple net sales were $383,285 million in fiscal 2023."
    claims = parse_numeric_claims(text)
    assert len(claims) == 1
    c = claims[0]
    assert c.numeric_value == Decimal("383285")
    assert c.scaled_value == Decimal("383285000000")
    assert c.unit == "USD_MILLIONS"
    assert c.period == "FY2023"


def test_parse_numeric_claims_percentage():
    text = "Operating margin expanded to 27.5%."
    claims = parse_numeric_claims(text)
    assert len(claims) == 1
    c = claims[0]
    assert c.numeric_value == Decimal("27.5")
    assert c.is_percentage is True
    assert c.unit == "PERCENT"


def test_parse_accounting_parentheses_negative():
    text = "Unrealized losses were $(312) million."
    claims = parse_numeric_claims(text)
    assert len(claims) == 1
    c = claims[0]
    assert c.numeric_value == Decimal("-312")
    assert c.unit == "USD_MILLIONS"


def test_numeric_comparator_exact_match():
    chunk = create_mock_chunk("Total net sales in 2023 were $383,285 million.")
    claim = "Apple reported net sales of $383,285 million in fiscal 2023."
    eval_res = NumericComparator.audit_claim(claim, [chunk])

    assert eval_res.is_verified is True
    assert eval_res.status == AuditStatus.SUPPORTED
    assert len(eval_res.verified_facts) == 1


def test_numeric_comparator_scale_mismatch():
    # Source reports millions, claim incorrectly says thousands
    chunk = create_mock_chunk("Total net sales were $383,285 million.")
    claim = "Apple reported net sales of $383,285 thousand."
    eval_res = NumericComparator.audit_claim(claim, [chunk])

    assert eval_res.is_verified is False
    assert eval_res.status == AuditStatus.NUMERIC_MISMATCH
    assert any("Scale mismatch" in m for m in eval_res.mismatches)


def test_numeric_comparator_sign_mismatch():
    # Source reports parenthetical loss $(312)M, claim claims positive gain $312M
    chunk = create_mock_chunk("Derivative contracts unrealized loss: $(312) million.")
    claim = "The company recorded an unrealized gain of $312 million."
    eval_res = NumericComparator.audit_claim(claim, [chunk])

    assert eval_res.is_verified is False
    assert eval_res.status == AuditStatus.NUMERIC_MISMATCH
    assert any("Sign mismatch" in m for m in eval_res.mismatches)


def test_numeric_comparator_period_mismatch():
    # Source associates $47,405 million with 2024, but claim attributes it to 2023
    chunk = create_mock_chunk("Compute revenue was $47,405 million in 2024, compared to $15,068 million in 2023.")
    claim = "NVIDIA Compute revenue was $47,405 million in 2023."
    eval_res = NumericComparator.audit_claim(claim, [chunk])

    assert eval_res.is_verified is False
    assert eval_res.status == AuditStatus.NUMERIC_MISMATCH
    assert any("Period mismatch" in m for m in eval_res.mismatches)


def test_numeric_comparator_narrative_claim():
    # Narrative claim without numbers should be deferred to NLI
    chunk = create_mock_chunk("The company experienced supply chain disruptions.")
    claim = "Supply chain disruptions affected delivery times."
    eval_res = NumericComparator.audit_claim(claim, [chunk])

    assert eval_res.is_verified is True
    assert eval_res.status == AuditStatus.SUPPORTED
    assert "deferred to NLI" in eval_res.summary
