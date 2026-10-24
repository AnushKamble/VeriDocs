"""
Unit tests for deterministic financial calculator using Decimal arithmetic.
Validates exact precision, division-by-zero checks, percentage points, and lack of float rounding errors.
"""

from decimal import Decimal
import pytest

from veridocs.audit.calculator import (
    FinancialCalculator,
    FinancialDivisionByZeroError,
    FinancialCalculationError,
)


def test_difference_exact():
    # 383,285 - 394,328 = -11,043
    diff = FinancialCalculator.difference("383285", "394328")
    assert diff == Decimal("-11043")


def test_percentage_change_standard():
    # Microsoft net income from 72,738 in FY22 to 72,361 in FY23:
    # ((72361 - 72738) / 72738) * 100 = -0.52%
    pct = FinancialCalculator.percentage_change(prior=72738, current=72361, round_places=2)
    assert pct == Decimal("-0.52")


def test_percentage_change_growth():
    # NVIDIA Compute revenue: from 15,068 to 47,405:
    # ((47405 - 15068) / 15068) * 100 = 214.61%
    pct = FinancialCalculator.percentage_change(prior=15068, current=47405, round_places=2)
    assert pct == Decimal("214.61")


def test_percentage_change_zero_division():
    with pytest.raises(FinancialDivisionByZeroError):
        FinancialCalculator.percentage_change(prior=0, current=500)


def test_percentage_points_difference():
    # NVIDIA gross margin from 56.9% to 72.7%:
    # 72.7 - 56.9 = 15.8 percentage points
    pp = FinancialCalculator.percentage_points_difference(rate1="72.7", rate2="56.9")
    assert pp == Decimal("15.80")


def test_ratio_calculation():
    # Current ratio: 120,000 / 60,000 = 2.0
    r = FinancialCalculator.ratio(120000, 60000)
    assert r == Decimal("2.0000")


def test_ratio_zero_denominator():
    with pytest.raises(FinancialDivisionByZeroError):
        FinancialCalculator.ratio(500, 0)


def test_decimal_precision_no_float_imprecision():
    # 0.1 + 0.2 in binary float is 0.30000000000000004; in Decimal it must be 0.3 exactly
    diff = FinancialCalculator.difference("0.3", "0.2")
    assert diff == Decimal("0.1")
