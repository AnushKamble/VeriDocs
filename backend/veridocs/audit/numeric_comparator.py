"""
Financial numeric comparator and consistency auditor.
Cross-references claim numbers against evidence chunks, table cells, and narrative excerpts.
Verifies magnitude, signs, scales, and fiscal periods.
"""

from decimal import Decimal
import re
from typing import List, Optional
from pydantic import BaseModel, Field

from veridocs.audit.numeric_parser import ParsedNumericClaim, parse_numeric_claims
from veridocs.schemas.data_models import ChunkRecord
from veridocs.schemas.query_models import AuditStatus, ClaimKind


class NumericAuditEvaluation(BaseModel):
    status: AuditStatus
    is_verified: bool
    summary: str
    mismatches: List[str] = Field(default_factory=list)
    verified_facts: List[str] = Field(default_factory=list)


class NumericComparator:
    """Verifies numeric claims against cited chunk evidence."""

    @classmethod
    def audit_claim(
        cls,
        claim_text: str,
        cited_chunks: List[ChunkRecord],
        tolerance: Decimal = Decimal("0.001"),
    ) -> NumericAuditEvaluation:
        """
        Extract numerical claims from text and audit them against cited chunk text/tables.
        """
        claim_nums = parse_numeric_claims(claim_text)

        # If claim contains no numbers, it is purely narrative
        if not claim_nums:
            return NumericAuditEvaluation(
                status=AuditStatus.SUPPORTED,
                is_verified=True,
                summary="Claim contains no explicit numeric figures; deferred to NLI audit.",
            )

        if not cited_chunks:
            return NumericAuditEvaluation(
                status=AuditStatus.INSUFFICIENT_EVIDENCE,
                is_verified=False,
                summary="No cited chunks provided to verify numeric claim.",
                mismatches=["No evidence chunk found."],
            )

        # Gather all text from cited chunks
        combined_evidence = "\n".join(c.text for c in cited_chunks)
        evidence_nums = parse_numeric_claims(combined_evidence)

        mismatches: List[str] = []
        verified: List[str] = []

        for cn in claim_nums:
            fact_str = f"{cn.raw_str} (Period: {cn.period or 'Any'})"
            match_found = False

            for en in evidence_nums:
                # Compare magnitudes
                mag_cn = abs(cn.scaled_value)
                mag_en = abs(en.scaled_value)
                mag_diff = abs(mag_cn - mag_en)
                ratio_diff = (mag_diff / mag_en) if mag_en != 0 else mag_diff

                if ratio_diff <= tolerance:
                    # Check sign agreement
                    if (cn.numeric_value < 0) != (en.numeric_value < 0):
                        mismatches.append(
                            f"Sign mismatch: claim asserts {cn.numeric_value} but source reports {en.numeric_value}."
                        )
                        match_found = True
                        break

                    # Check period match if both specify a period
                    if cn.period and en.period:
                        c_clean = cn.period.replace("FY", "").strip()
                        e_clean = en.period.replace("FY", "").strip()
                        if c_clean != e_clean and c_clean.isdigit() and e_clean.isdigit():
                            mismatches.append(
                                f"Period mismatch: claim asserts period {cn.period} for {cn.raw_str}, but source associates this value with period {en.period}."
                            )
                            match_found = True
                            break

                    verified.append(
                        f"Verified {cn.raw_str} against evidence figure {en.raw_str} (scale={cn.unit or 'raw'})."
                    )
                    match_found = True
                    break

                # 2. Check unscaled raw match but wrong scale (e.g., claim said 383,285 thousand instead of million)
                raw_mag_cn = abs(cn.numeric_value)
                raw_mag_en = abs(en.numeric_value)
                if abs(raw_mag_cn - raw_mag_en) <= tolerance:
                    if cn.multiplier != en.multiplier:
                        mismatches.append(
                            f"Scale mismatch: claim asserts {cn.raw_str} (multiplier {cn.multiplier}), but source reports scale {en.unit} (multiplier {en.multiplier})."
                        )
                        match_found = True
                        break


            if not match_found:
                mismatches.append(
                    f"Number {cn.raw_str} not found in cited evidence chunks."
                )

        if mismatches:
            return NumericAuditEvaluation(
                status=AuditStatus.NUMERIC_MISMATCH,
                is_verified=False,
                summary=f"Found {len(mismatches)} numeric discrepancies.",
                mismatches=mismatches,
                verified_facts=verified,
            )

        return NumericAuditEvaluation(
            status=AuditStatus.SUPPORTED,
            is_verified=True,
            summary=f"All {len(verified)} numeric assertions verified against cited evidence.",
            mismatches=[],
            verified_facts=verified,
        )
