"""
Safe, deterministic financial arithmetic calculator using Decimal precision.
Strictly prohibits eval(), handles division by zero, and computes exact differences,
growth rates, margins, and ratios.
"""

from decimal import Decimal, DivisionByZero, InvalidOperation, ROUND_HALF_UP
from typing import Optional


class FinancialCalculationError(Exception):
    """Base exception for financial calculator errors."""
    pass


class FinancialDivisionByZeroError(FinancialCalculationError):
    """Raised when dividing by zero in a financial calculation."""
    pass


class FinancialCalculator:
    """Deterministic, zero-eval financial calculator."""

    @staticmethod
    def to_decimal(val: object) -> Optional[Decimal]:
        """Safely convert float, int, str to Decimal."""
        if val is None:
            return None
        if isinstance(val, Decimal):
            return val
        try:
            # Clean string if formatted
            s = str(val).strip().replace(",", "").replace("$", "")
            return Decimal(s)
        except (InvalidOperation, ValueError):
            return None

    @classmethod
    def difference(cls, current: object, prior: object) -> Decimal:
        """Compute absolute difference: current - prior."""
        c = cls.to_decimal(current)
        p = cls.to_decimal(prior)
        if c is None or p is None:
            raise FinancialCalculationError(f"Cannot compute difference between {current} and {prior}")
        return c - p

    @classmethod
    def percentage_change(
        cls,
        prior: object,
        current: object,
        round_places: int = 2,
    ) -> Decimal:
        """
        Compute percentage change: ((current - prior) / abs(prior)) * 100.
        Raises FinancialDivisionByZeroError if prior is 0.
        """
        p = cls.to_decimal(prior)
        c = cls.to_decimal(current)
        if p is None or c is None:
            raise FinancialCalculationError(f"Cannot compute percentage change between {prior} and {current}")
        if p == 0:
            raise FinancialDivisionByZeroError("Cannot compute percentage change from base value of zero.")

        change = ((c - p) / abs(p)) * Decimal("100")
        quantum = Decimal("10") ** -round_places
        return change.quantize(quantum, rounding=ROUND_HALF_UP)

    @classmethod
    def percentage_points_difference(
        cls,
        rate1: object,
        rate2: object,
        round_places: int = 2,
    ) -> Decimal:
        """
        Compute difference in percentage points between two percentage rates: rate1 - rate2.
        For example: 72.7% - 56.9% = 15.8 percentage points.
        """
        r1 = cls.to_decimal(rate1)
        r2 = cls.to_decimal(rate2)
        if r1 is None or r2 is None:
            raise FinancialCalculationError(f"Cannot compute percentage points between {rate1} and {rate2}")
        diff = r1 - r2
        quantum = Decimal("10") ** -round_places
        return diff.quantize(quantum, rounding=ROUND_HALF_UP)

    @classmethod
    def ratio(
        cls,
        numerator: object,
        denominator: object,
        round_places: int = 4,
    ) -> Decimal:
        """
        Compute ratio: numerator / denominator.
        """
        num = cls.to_decimal(numerator)
        den = cls.to_decimal(denominator)
        if num is None or den is None:
            raise FinancialCalculationError(f"Cannot compute ratio between {numerator} and {denominator}")
        if den == 0:
            raise FinancialDivisionByZeroError("Denominator cannot be zero when computing ratio.")

        res = num / den
        quantum = Decimal("10") ** -round_places
        return res.quantize(quantum, rounding=ROUND_HALF_UP)
