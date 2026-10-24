from decimal import Decimal
import pytest
from veridocs.ingestion.numeric_normalizer import (
    extract_unit_and_multiplier,
    is_dash_or_missing,
    normalize_financial_number,
)


def test_standard_numbers():
    val, is_dash, unit = normalize_financial_number("1,234.50")
    assert val == Decimal("1234.50")
    assert not is_dash
    assert unit is None

    val, is_dash, unit = normalize_financial_number("$383,285")
    assert val == Decimal("383285")
    assert not is_dash
    assert unit == "USD"

    val, is_dash, unit = normalize_financial_number("-50.25")
    assert val == Decimal("-50.25")
    assert not is_dash


def test_accounting_parentheses_negatives():
    val, is_dash, unit = normalize_financial_number("(1,245)")
    assert val == Decimal("-1245")
    assert not is_dash

    val, is_dash, unit = normalize_financial_number("$(2,830.4)")
    assert val == Decimal("-2830.4")
    assert not is_dash
    assert unit == "USD"


def test_dash_vs_zero():
    # Em-dash, hyphen, and N/A are distinct from zero
    val, is_dash, _ = normalize_financial_number("—")
    assert val is None
    assert is_dash is True

    val, is_dash, _ = normalize_financial_number("-")
    assert val is None
    assert is_dash is True

    val, is_dash, _ = normalize_financial_number("N/A")
    assert val is None
    assert is_dash is True

    # Actual zero
    val, is_dash, _ = normalize_financial_number("0")
    assert val == Decimal("0")
    assert is_dash is False

    val, is_dash, unit = normalize_financial_number("$0.00")
    assert val == Decimal("0.00")
    assert is_dash is False
    assert unit == "USD"


def test_percentages():
    val, is_dash, unit = normalize_financial_number("12.5%")
    assert val == Decimal("12.5")
    assert not is_dash
    assert unit == "PERCENT"

    val, is_dash, unit = normalize_financial_number("(3.8%)")
    assert val == Decimal("-3.8")
    assert not is_dash
    assert unit == "PERCENT"


def test_unit_and_multiplier():
    unit, mult = extract_unit_and_multiplier("Operating results (in millions, except per share amounts)")
    assert unit == "USD_MILLIONS"
    assert mult == Decimal("1000000")

    unit, mult = extract_unit_and_multiplier("Shares in thousands")
    assert unit == "USD_THOUSANDS"
    assert mult == Decimal("1000")

    unit, mult = extract_unit_and_multiplier("Net income per share")
    assert unit == "PER_SHARE"
    assert mult == Decimal("1")
