"""
Financial numeric normalizer: precise decimal parsing, accounting signs, units, and scales.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

# Patterns for units and scales
SCALE_PATTERNS = [
    (re.compile(r"\b(in\s+billions?|billion\s+dollars?|\$?\s*billions?)\b", re.IGNORECASE), "USD_BILLIONS", Decimal("1000000000")),
    (re.compile(r"\b(in\s+millions?|million\s+dollars?|\$?\s*millions?)\b", re.IGNORECASE), "USD_MILLIONS", Decimal("1000000")),
    (re.compile(r"\b(in\s+thousands?|thousand\s+dollars?|\$?\s*thousands?)\b", re.IGNORECASE), "USD_THOUSANDS", Decimal("1000")),
    (re.compile(r"\b(per\s+share(\s+amounts?)?|per\s+diluted\s+share)\b", re.IGNORECASE), "PER_SHARE", Decimal("1")),
    (re.compile(r"%", re.IGNORECASE), "PERCENT", Decimal("1")),
]

# Patterns for empty / missing / not applicable
DASH_PATTERNS = re.compile(r"^(\s*[-—–]+\s*|\s*N/?A\s*|\s*None\s*|\s*\*\s*|\s*)$", re.IGNORECASE)

# Pattern for accounting parenthetical negative: $(1,234) or (1,234.50) or (3.8%)
PAREN_NEGATIVE_PATTERN = re.compile(r"^\s*([$€£¥]?)\s*\(\s*([0-9,]+(?:\.[0-9]+)?)\s*(%?)\s*\)\s*(%?)\s*$")

# Pattern for standard positive/negative number: -$1,234 or $1,234.50 or +5.2%
STANDARD_NUMBER_PATTERN = re.compile(r"^\s*([+-]?)\s*[$€£¥]?\s*([0-9,]+(?:\.[0-9]+)?)\s*(%?)\s*$")


def extract_unit_and_multiplier(text: str) -> Tuple[Optional[str], Decimal]:
    """
    Extracts explicit financial scale / unit declaration and numeric multiplier from text.
    Returns (unit_name, multiplier). Defaults to (None, Decimal("1")).
    """
    if not text:
        return None, Decimal("1")
    for pattern, unit_name, multiplier in SCALE_PATTERNS:
        if pattern.search(text):
            return unit_name, multiplier
    return None, Decimal("1")


def is_dash_or_missing(raw_str: str) -> bool:
    """Returns True if the raw string represents an em-dash, hyphen, N/A, or empty cell."""
    return bool(DASH_PATTERNS.match(raw_str.strip()))


def normalize_financial_number(raw_str: str) -> Tuple[Optional[Decimal], bool, Optional[str]]:
    """
    Parses a financial cell/claim string into:
    (numeric_value: Optional[Decimal], is_empty_or_dash: bool, detected_unit: Optional[str])

    Rules:
    - Empty, dash, em-dash, N/A -> (None, True, None)
    - Zero: "0", "$0", "$ -", "0.00" -> (Decimal("0"), False, unit)
    - Accounting parenthetical negative: "(1,234)" -> (Decimal("-1234"), False, unit)
    - Percentage: "12.5%" -> (Decimal("12.5"), False, "PERCENT")
    - Decimal precision preserved via Decimal; never floats.
    """
    if not raw_str or is_dash_or_missing(raw_str):
        return None, True, None

    cleaned = raw_str.strip().replace("\xa0", " ").replace(" ", "")

    # Check parenthetical negative first
    paren_match = PAREN_NEGATIVE_PATTERN.match(cleaned)
    if paren_match:
        currency_sym, num_str, pct_inside, pct_outside = paren_match.groups()
        num_clean = num_str.replace(",", "")
        try:
            val = -Decimal(num_clean)
            is_pct = bool(pct_inside or pct_outside or "%" in raw_str)
            unit = "PERCENT" if is_pct else ("USD" if currency_sym == "$" else None)
            return val, False, unit
        except InvalidOperation:
            return None, False, None

    # Check standard number
    std_match = STANDARD_NUMBER_PATTERN.match(cleaned)
    if std_match:
        sign_str, num_str, pct_str = std_match.groups()
        num_clean = num_str.replace(",", "")
        try:
            val = Decimal(num_clean)
            if sign_str == "-":
                val = -val
            unit = "PERCENT" if pct_str == "%" else ("USD" if "$" in raw_str else None)
            return val, False, unit
        except InvalidOperation:
            return None, False, None

    return None, False, None
