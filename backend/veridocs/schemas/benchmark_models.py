"""
Benchmark dataset and calibration models for reproducible evaluation.
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class QuestionCategory(str, Enum):
    NUMERIC_TABLE_LOOKUP = "numeric_table_lookup"
    PERIOD_COMPARISON = "period_comparison"
    UNITS_SIGN_EDGE_CASE = "units_sign_edge_case"
    NARRATIVE_MDA = "narrative_mda"
    MULTI_EVIDENCE = "multi_evidence"
    UNANSWERABLE = "unanswerable"
    AMBIGUOUS_PERIOD = "ambiguous_period"
    CONFLICTING = "conflicting"


class BenchmarkGoldEvidence(BaseModel):
    document_id: str
    section_id: str
    source_locator: str
    verbatim_text: str
    table_caption: Optional[str] = None
    row_label: Optional[str] = None
    column_label: Optional[str] = None


class BenchmarkCase(BaseModel):
    question_id: str
    question_text: str
    category: QuestionCategory
    company_name: str
    ticker: Optional[str] = None
    form_type: str
    fiscal_period: Optional[str] = None
    is_answerable: bool = True
    reference_answer: str
    expected_numeric_value: Optional[Decimal] = None
    expected_unit: Optional[str] = None
    expected_period: Optional[str] = None
    gold_evidence: List[BenchmarkGoldEvidence] = Field(default_factory=list)
    annotation_rationale: str
    split: str = "test"  # "dev" / "test"


class CalibrationClaim(BaseModel):
    claim_id: str
    premise_text: str
    hypothesis_text: str
    gold_label: str  # "entailment", "contradiction", "neutral"
    category: str
    rationale: str
