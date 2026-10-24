"""VeriDocs Ingestion Package."""

from veridocs.ingestion.numeric_normalizer import (
    extract_unit_and_multiplier,
    is_dash_or_missing,
    normalize_financial_number,
)
from veridocs.ingestion.table_parser import TableParser
from veridocs.ingestion.section_parser import SectionBlock, SectionParser, classify_section_heading
from veridocs.ingestion.html_parser import FilingParser, ParsedFilingResult

__all__ = [
    "extract_unit_and_multiplier",
    "is_dash_or_missing",
    "normalize_financial_number",
    "TableParser",
    "SectionBlock",
    "SectionParser",
    "classify_section_heading",
    "FilingParser",
    "ParsedFilingResult",
]
