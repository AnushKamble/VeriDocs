"""
Audit response policy engine.
Applies deterministic precedence rules: citation verification, numeric consistency,
and NLI entailment/contradiction thresholds to determine claim and response status.
"""

from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from veridocs.schemas.data_models import ChunkRecord
from veridocs.schemas.query_models import (
    AnswerStatus,
    AtomicClaim,
    AuditStatus,
    ClaimKind,
)
from veridocs.audit.numeric_comparator import NumericAuditEvaluation, NumericComparator


class PolicyThresholds(BaseModel):
    entailment_threshold: float = 0.65
    contradiction_threshold: float = 0.50
    numeric_tolerance: Decimal = Decimal("0.001")


class PolicyAuditResult(BaseModel):
    overall_status: AnswerStatus
    audited_claims: List[AtomicClaim]
    policy_summary: str
    has_contradictions: bool = False
    has_numeric_mismatches: bool = False
    has_invalid_citations: bool = False
    abstention_recommended: bool = False


class ResponsePolicyEngine:
    """Enforces strict evaluation precedence and response governance."""

    def __init__(self, thresholds: Optional[PolicyThresholds] = None):
        self.thresholds = thresholds or PolicyThresholds()

    def evaluate_response(
        self,
        claims: List[AtomicClaim],
        evidence_chunks: List[ChunkRecord],
        is_generation_abstained: bool = False,
    ) -> PolicyAuditResult:
        """
        Evaluate full set of claims against evidence chunks according to ADR-006 precedence rules.
        """
        if is_generation_abstained or not evidence_chunks or not claims:
            return PolicyAuditResult(
                overall_status=AnswerStatus.ABSTAINED,
                audited_claims=claims,
                policy_summary="Engine abstained due to missing evidence or explicit generator abstention.",
                abstention_recommended=True,
            )

        chunk_map: Dict[str, ChunkRecord] = {c.chunk_id: c for c in evidence_chunks}
        audited_claims: List[AtomicClaim] = []

        has_contradictions = False
        has_numeric_mismatches = False
        has_invalid_citations = False
        supported_count = 0

        for claim in claims:
            audited_claim = self._evaluate_single_claim(claim, chunk_map)
            audited_claims.append(audited_claim)

            if audited_claim.audit_status == AuditStatus.SUPPORTED:
                supported_count += 1
            elif audited_claim.audit_status == AuditStatus.CONTRADICTED:
                has_contradictions = True
            elif audited_claim.audit_status == AuditStatus.NUMERIC_MISMATCH:
                has_numeric_mismatches = True
            elif audited_claim.audit_status == AuditStatus.INVALID_CITATION:
                has_invalid_citations = True

        total_claims = len(audited_claims)

        # Determine overall answer status
        if supported_count == total_claims and total_claims > 0:
            overall_status = AnswerStatus.ANSWERED
            summary = f"All {total_claims} claim(s) fully supported by cited evidence."
            abstain = False
        elif supported_count > 0:
            overall_status = AnswerStatus.PARTIALLY_SUPPORTED
            summary = f"{supported_count} of {total_claims} claim(s) supported. Unverified or mismatched claims present."
            abstain = False
        else:
            # Zero supported claims -> abstain rather than assert unverified data
            overall_status = AnswerStatus.ABSTAINED
            summary = "No claims could be verified against cited evidence; response abstained."
            abstain = True

        return PolicyAuditResult(
            overall_status=overall_status,
            audited_claims=audited_claims,
            policy_summary=summary,
            has_contradictions=has_contradictions,
            has_numeric_mismatches=has_numeric_mismatches,
            has_invalid_citations=has_invalid_citations,
            abstention_recommended=abstain,
        )

    def _evaluate_single_claim(
        self,
        claim: AtomicClaim,
        chunk_map: Dict[str, ChunkRecord],
    ) -> AtomicClaim:
        """Apply Precedence Rules 1 -> 2 -> 3 -> 4 -> 5 to an individual claim."""
        c = claim.model_copy(deep=True)

        # Precedence 1: Invalid Citation
        if c.audit_status == AuditStatus.INVALID_CITATION or not c.source_chunk_ids:
            c.audit_status = AuditStatus.INVALID_CITATION
            if not c.audit_reason:
                c.audit_reason = "Claim lacks valid cited chunk IDs."
            return c

        missing_cids = [cid for cid in c.source_chunk_ids if cid not in chunk_map]
        if missing_cids:
            c.audit_status = AuditStatus.INVALID_CITATION
            c.audit_reason = f"Cited chunk IDs not found in evidence pool: {missing_cids}"
            return c

        cited_chunks = [chunk_map[cid] for cid in c.source_chunk_ids]

        # Precedence 2: Numeric Consistency (Deterministic math overrules NLI)
        num_eval = NumericComparator.audit_claim(
            claim_text=c.text,
            cited_chunks=cited_chunks,
            tolerance=self.thresholds.numeric_tolerance,
        )

        if num_eval.status == AuditStatus.NUMERIC_MISMATCH:
            c.audit_status = AuditStatus.NUMERIC_MISMATCH
            c.audit_reason = "; ".join(num_eval.mismatches)
            return c

        # Precedence 3: NLI Contradiction
        if c.nli_contradiction_score is not None:
            if c.nli_contradiction_score >= self.thresholds.contradiction_threshold:
                c.audit_status = AuditStatus.CONTRADICTED
                c.audit_reason = f"NLI contradiction score {c.nli_contradiction_score:.3f} >= threshold {self.thresholds.contradiction_threshold:.3f}"
                return c

        # Precedence 4: NLI Entailment
        if c.nli_entailment_score is not None:
            if c.nli_entailment_score >= self.thresholds.entailment_threshold:
                c.audit_status = AuditStatus.SUPPORTED
                c.audit_reason = f"NLI entailment score {c.nli_entailment_score:.3f} >= threshold {self.thresholds.entailment_threshold:.3f}"
                return c

        # Precedence 5: Numeric verification or Insufficient Evidence
        # Only mark SUPPORTED if actual numeric figures existed and were verified:
        if num_eval.is_verified and len(num_eval.verified_facts) > 0:
            c.audit_status = AuditStatus.SUPPORTED
            c.audit_reason = f"Numerically verified against source evidence: {'; '.join(num_eval.verified_facts)}"
        elif c.nli_entailment_score is None:
            # Missing NLI cannot verify narrative claims
            c.audit_status = AuditStatus.AUDITOR_UNAVAILABLE if c.claim_kind == ClaimKind.NARRATIVE else AuditStatus.INSUFFICIENT_EVIDENCE
            c.audit_reason = "NLI auditor unavailable; narrative claim cannot be verified without natural language entailment."
        else:
            c.audit_status = AuditStatus.INSUFFICIENT_EVIDENCE
            c.audit_reason = "Evidence is insufficient to confirm or refute claim."

        return c
