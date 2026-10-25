"""
Unit tests for Generation Provider, Prompt Builder, and Structured Answerer.
Tests citation validation, hallucination detection, schema compliance, and abstention.
"""

from decimal import Decimal
import pytest

from veridocs.generation.prompt_builder import build_generation_prompt, format_chunk_for_evidence
from veridocs.generation.provider import FakeTestProvider, GenerationResult
from veridocs.generation.ollama_adapter import (
    OllamaConnectionError,
    OllamaGenerationProvider,
    OllamaTimeoutError,
)
from veridocs.generation.structured_answerer import StructuredAnswerer
from veridocs.schemas.data_models import ChunkKind, ChunkRecord
from veridocs.schemas.query_models import (
    AnswerStatus,
    AtomicClaim,
    AuditStatus,
    ClaimKind,
    GeneratorRawOutput,
    NumericFact,
)


def create_sample_chunk(chunk_id: str, text: str, section="Item 8") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        document_id="doc_aapl_10k_2023",
        chunk_kind=ChunkKind.NARRATIVE,
        ordinal=0,
        section_id=section,
        section_title="Financial Statements",
        text=text,
        raw_text=text,
        token_count=20,
        source_url="https://www.sec.gov/edgar/test.htm",
        source_locator=f"loc_{chunk_id}",
        content_hash="abc123hash",
    )



def test_format_chunk_for_evidence():
    chunk = create_sample_chunk("chk_001", "Total revenue was $383,285 million in 2023.")
    formatted = format_chunk_for_evidence(chunk)
    assert '<evidence_chunk id="chk_001" type="NARRATIVE">' in formatted
    assert "doc_aapl_10k_2023" in formatted
    assert "Total revenue was $383,285 million" in formatted
    assert "</evidence_chunk>" in formatted



def test_prompt_builder_structure():
    chunk1 = create_sample_chunk("chk_001", "Revenue in 2023 was $383,285 million.")
    chunk2 = create_sample_chunk("chk_002", "Cost of sales was $214,137 million.")
    prompt = build_generation_prompt("What was Apple's revenue?", [chunk1, chunk2])

    assert "EVIDENCE SECTION:" in prompt
    assert 'id="chk_001"' in prompt
    assert 'id="chk_002"' in prompt
    assert "USER QUESTION:" in prompt
    assert "What was Apple's revenue?" in prompt
    assert "RESPONSE INSTRUCTIONS:" in prompt


def test_prompt_builder_empty_chunks():
    prompt = build_generation_prompt("What was revenue?", [])
    assert "No evidence chunks were retrieved" in prompt


@pytest.mark.asyncio
async def test_fake_provider_deterministic():
    provider = FakeTestProvider(canned_response='{"summary": "Test", "claims": [], "limitations": []}')
    res = await provider.generate("Test prompt")
    assert res.raw_text.startswith('{"summary"')
    assert res.parsed_json is not None
    assert res.parsed_json["summary"] == "Test"
    assert provider.call_count == 1
    assert provider.last_prompt == "Test prompt"


@pytest.mark.asyncio
async def test_structured_answerer_empty_evidence_abstention():
    provider = FakeTestProvider()
    answerer = StructuredAnswerer(provider)
    result = await answerer.answer("What was Apple revenue?", [])

    assert result.answer_status == AnswerStatus.ABSTAINED
    assert len(result.claims) == 0
    assert "abstains" in result.summary.lower()
    # Provider must NOT have been called
    assert provider.call_count == 0


@pytest.mark.asyncio
async def test_structured_answerer_valid_citation():
    chunk1 = create_sample_chunk("chk_001", "Apple net sales were $383,285 million.")
    canned_json = {
        "summary": "Apple net sales were $383,285 million in fiscal 2023.",
        "claims": [
            {
                "claim_id": "c1",
                "text": "Apple generated $383,285 million in net sales in fiscal 2023.",
                "claim_kind": "numeric",
                "source_chunk_ids": ["chk_001"],
                "numeric_facts": [
                    {
                        "metric": "Net Sales",
                        "raw_value": "$383,285 million",
                        "numeric_value": 383285,
                        "unit": "USD_MILLIONS",
                        "period": "FY2023",
                    }
                ],
            }
        ],
        "limitations": [],
    }

    provider = FakeTestProvider(canned_json=canned_json)
    answerer = StructuredAnswerer(provider)
    result = await answerer.answer("What was Apple's net sales in 2023?", [chunk1])

    assert result.answer_status == AnswerStatus.ANSWERED
    assert len(result.claims) == 1
    assert result.claims[0].claim_id == "c1"
    assert result.claims[0].source_chunk_ids == ["chk_001"]
    assert result.claims[0].audit_status != AuditStatus.INVALID_CITATION


@pytest.mark.asyncio
async def test_structured_answerer_hallucinated_citation_detected():
    chunk1 = create_sample_chunk("chk_001", "Apple net sales were $383,285 million.")
    # Model hallucinated citing "chk_999_fake" which was never retrieved!
    canned_json = {
        "summary": "Apple reported net sales.",
        "claims": [
            {
                "claim_id": "c1",
                "text": "Apple generated $383,285 million.",
                "claim_kind": "numeric",
                "source_chunk_ids": ["chk_999_fake"],
                "numeric_facts": [],
            }
        ],
        "limitations": [],
    }

    provider = FakeTestProvider(canned_json=canned_json)
    answerer = StructuredAnswerer(provider)
    result = await answerer.answer("What was Apple's net sales?", [chunk1])

    assert len(result.claims) == 1
    claim = result.claims[0]
    assert claim.audit_status == AuditStatus.INVALID_CITATION
    assert "chk_999_fake" in claim.audit_reason
    # When all claims cite invalid/hallucinated chunk IDs, engine must abstain
    assert result.answer_status == AnswerStatus.ABSTAINED


@pytest.mark.asyncio
async def test_structured_answerer_abstention_keywords():
    chunk1 = create_sample_chunk("chk_001", "Apple product warranty details.")
    canned_json = {
        "summary": "The evidence does not contain sufficient evidence to answer what Apple's CEO compensation was.",
        "claims": [],
        "limitations": ["Information not found in retrieved chunks."],
    }

    provider = FakeTestProvider(canned_json=canned_json)
    answerer = StructuredAnswerer(provider)
    result = await answerer.answer("What was CEO compensation?", [chunk1])

    assert result.answer_status == AnswerStatus.ABSTAINED
    assert len(result.claims) == 0


@pytest.mark.asyncio
async def test_ollama_markdown_codeblock_fallback():
    # Test JSON extraction when model returns ```json { ... } ```
    provider = OllamaGenerationProvider()
    raw = """Here is the response:
```json
{
  "summary": "Apple sales were strong.",
  "claims": [],
  "limitations": []
}
```
"""
    answerer = StructuredAnswerer(provider)
    extracted = answerer._try_extract_json(raw)
    assert extracted is not None
    assert extracted["summary"] == "Apple sales were strong."
