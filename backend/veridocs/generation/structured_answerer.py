"""
Structured Answerer for VeriDocs.
Executes prompt building, LLM provider invocation, schema validation, citation provenance enforcement,
and atomic claim structuring.
"""

from decimal import Decimal
import json
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from veridocs.generation.prompt_builder import SYSTEM_PROMPT, build_generation_prompt
from veridocs.generation.provider import GeneratorProvider
from veridocs.schemas.data_models import ChunkRecord
from veridocs.schemas.query_models import (
    AnswerStatus,
    AtomicClaim,
    AuditStatus,
    ClaimKind,
    GeneratorRawOutput,
    NumericFact,
)
from veridocs.utils.logging import get_logger

logger = get_logger("veridocs.generation.answerer")


class StructuredAnswerResult(BaseModel):
    summary: str
    claims: List[AtomicClaim]
    limitations: List[str] = Field(default_factory=list)
    answer_status: AnswerStatus
    raw_response: str
    latency_ms: float = 0.0
    model_name: str = ""


class StructuredAnswerer:
    """Coordinates generation, schema enforcement, and citation validation."""

    def __init__(self, provider: GeneratorProvider):
        self.provider = provider

    async def answer(
        self,
        query: str,
        retrieved_evidence: List[ChunkRecord],
        temperature: float = 0.0,
    ) -> StructuredAnswerResult:
        """
        Generate grounded answer, parse claims, and enforce citation integrity.
        """
        # If no evidence was retrieved, abstain immediately without LLM call
        if not retrieved_evidence:
            return StructuredAnswerResult(
                summary="The engine abstains: no relevant filing evidence was retrieved to answer the question.",
                claims=[],
                limitations=["No retrieved documents match the query criteria."],
                answer_status=AnswerStatus.ABSTAINED,
                raw_response="",
                latency_ms=0.0,
                model_name="rule-based-abstention",
            )

        prompt = build_generation_prompt(query, retrieved_evidence)
        valid_chunk_ids: Set[str] = {c.chunk_id for c in retrieved_evidence}

        gen_result = await self.provider.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            schema=GeneratorRawOutput,
            temperature=temperature,
        )

        parsed_data = gen_result.parsed_json
        raw_text = gen_result.raw_text

        # If provider did not parse JSON, try manual extraction
        if parsed_data is None:
            parsed_data = self._try_extract_json(raw_text)

        if parsed_data is None:
            logger.error("Failed to parse LLM output as JSON schema.")
            return StructuredAnswerResult(
                summary="Generation error: the language model failed to produce a valid structured JSON response.",
                claims=[],
                limitations=["Invalid JSON schema emitted by generation provider."],
                answer_status=AnswerStatus.GENERATION_ERROR,
                raw_response=raw_text,
                latency_ms=gen_result.latency_ms,
                model_name=gen_result.model_name,
            )

        # Parse into GeneratorRawOutput
        try:
            raw_output = GeneratorRawOutput.model_validate(parsed_data)
        except Exception as e:
            logger.warning(f"GeneratorRawOutput validation failed: {e}; attempting fallback extraction.")
            raw_output = self._fallback_parse(parsed_data, raw_text)

        # Citation validation: verify every cited source_chunk_id exists in retrieved_evidence
        validated_claims: List[AtomicClaim] = []
        any_invalid_citations = False

        for idx, claim in enumerate(raw_output.claims):
            if not claim.claim_id:
                claim.claim_id = f"claim_{idx+1}"

            invalid_ids = [cid for cid in claim.source_chunk_ids if cid not in valid_chunk_ids]

            if invalid_ids:
                claim.audit_status = AuditStatus.INVALID_CITATION
                claim.audit_reason = f"Hallucinated or unknown chunk IDs cited: {invalid_ids}"
                any_invalid_citations = True
            elif not claim.source_chunk_ids:
                claim.audit_status = AuditStatus.INVALID_CITATION
                claim.audit_reason = "No source chunk ID was cited for this claim."
                any_invalid_citations = True

            validated_claims.append(claim)

        # Detect abstention intent in summary or lack of claims
        abstain_keywords = [
            "abstain",
            "insufficient",
            "does not contain",
            "not contain",
            "no evidence",
            "cannot be determined",
            "not mentioned",
            "not disclosed",
            "not provided",
            "unavailable",
        ]
        is_abstention_text = any(kw in raw_output.summary.lower() for kw in abstain_keywords)

        if len(validated_claims) == 0 and is_abstention_text:
            answer_status = AnswerStatus.ABSTAINED
        elif len(validated_claims) == 0:
            # If no claims could be grounded from evidence, engine must abstain
            answer_status = AnswerStatus.ABSTAINED
        elif any_invalid_citations and all(c.audit_status == AuditStatus.INVALID_CITATION for c in validated_claims):
            answer_status = AnswerStatus.PARTIALLY_SUPPORTED
        else:
            answer_status = AnswerStatus.ANSWERED

        return StructuredAnswerResult(
            summary=raw_output.summary,
            claims=validated_claims,
            limitations=raw_output.limitations,
            answer_status=answer_status,
            raw_response=raw_text,
            latency_ms=gen_result.latency_ms,
            model_name=gen_result.model_name,
        )

    def _try_extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Attempt to extract JSON from markdown code fences or brace substrings."""
        # Try finding markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass

        # Try finding first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass

        return None

    def _fallback_parse(self, parsed_data: Dict[str, Any], raw_text: str) -> GeneratorRawOutput:
        """Gracefully reconstruct GeneratorRawOutput if fields are slightly malformed."""
        summary = parsed_data.get("summary") or raw_text[:200]
        limitations = parsed_data.get("limitations") or []
        claims_raw = parsed_data.get("claims") or []

        claims: List[AtomicClaim] = []
        for idx, cr in enumerate(claims_raw):
            if isinstance(cr, dict):
                cid = cr.get("claim_id") or f"c{idx+1}"
                ctext = cr.get("text") or str(cr)
                kind_str = cr.get("claim_kind") or "narrative"
                try:
                    kind = ClaimKind(kind_str)
                except Exception:
                    kind = ClaimKind.NARRATIVE
                source_chunk_ids = cr.get("source_chunk_ids") or []
                if isinstance(source_chunk_ids, str):
                    source_chunk_ids = [source_chunk_ids]

                numeric_facts: List[NumericFact] = []
                for nf in cr.get("numeric_facts", []):
                    if isinstance(nf, dict):
                        val = nf.get("numeric_value")
                        dec_val = Decimal(str(val)) if val is not None else None
                        numeric_facts.append(
                            NumericFact(
                                metric=nf.get("metric", "metric"),
                                raw_value=str(nf.get("raw_value", "")),
                                numeric_value=dec_val,
                                unit=nf.get("unit"),
                                period=nf.get("period"),
                            )
                        )

                claims.append(
                    AtomicClaim(
                        claim_id=cid,
                        text=ctext,
                        claim_kind=kind,
                        source_chunk_ids=source_chunk_ids,
                        numeric_facts=numeric_facts,
                    )
                )

        return GeneratorRawOutput(summary=summary, claims=claims, limitations=limitations)
