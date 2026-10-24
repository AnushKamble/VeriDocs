"""
Financial numeric claim parser.
Extracts numbers, accounting signs, currencies, multipliers (millions, billions),
percentages, and fiscal periods from natural language claims.
"""

from decimal import Decimal
import re
from typing import List, Optional
from pydantic import BaseModel

from veridocs.ingestion.numeric_normalizer import SCALE_PATTERNS, normalize_financial_number


class ParsedNumericClaim(BaseModel):
    raw_str: str
    numeric_value: Decimal
    scaled_value: Decimal  # value * multiplier (e.g. 383285 * 10^6)
    unit: Optional[str] = None
    currency: Optional[str] = None
    multiplier: Decimal = Decimal("1")
    is_percentage: bool = False
    period: Optional[str] = None
    metric_hint: Optional[str] = None


# Pattern for year/period in claim text: e.g. FY2023, FY 2023, fiscal 2023, in 2023, Q3 2024
PERIOD_PATTERN = re.compile(
    r"\b(FY\s*20\d\d|fiscal\s*(?:year\s*)?20\d\d|20\d\d|Q[1-4]\s*(?:20\d\d)?)\b",
    re.IGNORECASE,
)

# Pattern for currency symbols or names
CURRENCY_PATTERN = re.compile(r"(\$|€|£|¥|\bUSD\b|\bEUR\b|\bGBP\b)", re.IGNORECASE)

# Pattern for numeric tokens in claim strings
NUMBER_WITH_CONTEXT = re.compile(
    r"([$€£¥]?\s*(?:\(\s*[0-9,]+(?:\.[0-9]+)?%?\s*\)|[+-]?[0-9,]+(?:\.[0-9]+)?%?))"
    r"(\s*(?:billion|million|thousand|percentage points?|percent|%))?",
    re.IGNORECASE,
)


def extract_period(text: str) -> Optional[str]:
    """Extract fiscal period identifier from claim text."""
    match = PERIOD_PATTERN.search(text)
    if match:
        p = match.group(1).upper()
        # Normalize "FISCAL 2023" -> "FY2023", "2023" -> "2023"
        p = re.sub(r"FISCAL\s*(?:YEAR\s*)?", "FY", p)
        p = re.sub(r"\s+", "", p)
        return p
    return None


def parse_numeric_claims(text: str) -> List[ParsedNumericClaim]:
    """
    Extract all numerical assertions from claim text with scale, unit, and period.
    """
    results: List[ParsedNumericClaim] = []
    default_period = extract_period(text)

    # Detect currency in the entire sentence
    default_currency = None
    curr_match = CURRENCY_PATTERN.search(text)
    if curr_match:
        c = curr_match.group(1).upper()
        default_currency = "USD" if c in ("$", "USD") else c

    # Search for all number candidates
    for match in NUMBER_WITH_CONTEXT.finditer(text):
        num_str = match.group(1).strip()
        scale_str = match.group(2).strip() if match.group(2) else ""

        # Normalize number
        val, is_dash, norm_unit = normalize_financial_number(num_str)
        if val is None or is_dash:
            continue

        # Filter out standalone 4-digit calendar years (e.g. 2023, 2024) that are not financial metrics
        if (
            1900 <= val <= 2099
            and not scale_str
            and "$" not in num_str
            and "%" not in num_str
            and "€" not in num_str
            and "£" not in num_str
        ):
            continue

        unit = norm_unit
        multiplier = Decimal("1")
        is_pct = "%" in num_str or "percent" in scale_str.lower()

        # Check scale word
        comb_str = f"{num_str} {scale_str}".lower()
        if "billion" in comb_str:
            unit = "USD_BILLIONS"
            multiplier = Decimal("1000000000")
        elif "million" in comb_str:
            unit = "USD_MILLIONS"
            multiplier = Decimal("1000000")
        elif "thousand" in comb_str:
            unit = "USD_THOUSANDS"
            multiplier = Decimal("1000")
        elif "percentage point" in comb_str:
            unit = "PERCENTAGE_POINTS"
            is_pct = True
        elif is_pct:
            unit = "PERCENT"

        scaled_value = val * multiplier

        results.append(
            ParsedNumericClaim(
                raw_str=f"{num_str} {scale_str}".strip(),
                numeric_value=val,
                scaled_value=scaled_value,
                unit=unit,
                currency=default_currency,
                multiplier=multiplier,
                is_percentage=is_pct,
                period=default_period,
            )
        )

    return results
