"""
Live integration test for Ollama provider using local Qwen model.
Skips gracefully if local Ollama server is not running or model is not downloaded.
"""

import pytest
import httpx
from veridocs.generation.ollama_adapter import OllamaGenerationProvider
from veridocs.generation.structured_answerer import StructuredAnswerer
from veridocs.schemas.data_models import ChunkKind, ChunkRecord
from veridocs.schemas.query_models import AnswerStatus


@pytest.mark.asyncio
async def test_live_ollama_generation_and_schema():
    # Check if Ollama is reachable
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code != 200:
                pytest.skip("Local Ollama server returned non-200 status")
            models = [m["name"] for m in resp.json().get("models", [])]
            if not any("qwen" in m for m in models):
                pytest.skip("Qwen model not found in local Ollama")
    except Exception:
        pytest.skip("Local Ollama server is not reachable on port 11434")

    provider = OllamaGenerationProvider(
        base_url="http://localhost:11434",
        model_name="qwen3:8b",
        timeout_seconds=60.0,
    )
    assert await provider.is_healthy() is True

    chunk = ChunkRecord(
        chunk_id="chunk_aapl_rev_2023",
        document_id="doc_aapl_10k_2023",
        chunk_kind=ChunkKind.NARRATIVE,
        ordinal=1,
        section_id="Item 8",
        section_title="Statements of Operations",
        text="Total net sales for Apple Inc. in fiscal year 2023 were $383,285 million, compared to $394,328 million in fiscal year 2022.",
        raw_text="Total net sales for Apple Inc. in fiscal year 2023 were $383,285 million, compared to $394,328 million in fiscal year 2022.",
        token_count=35,
        source_url="https://www.sec.gov/edgar/test.htm",
        source_locator="aapl_ops_2023",
        content_hash="mock_hash_123",
    )

    answerer = StructuredAnswerer(provider)
    result = await answerer.answer(
        query="What were Apple's net sales in fiscal 2023 according to the filing?",
        retrieved_evidence=[chunk],
    )

    assert result.latency_ms > 0
    assert result.model_name == "qwen3:8b"
    assert result.answer_status in [AnswerStatus.ANSWERED, AnswerStatus.PARTIALLY_SUPPORTED]
    assert len(result.claims) > 0
    # The model should cite our chunk
    first_claim = result.claims[0]
    assert "chunk_aapl_rev_2023" in first_claim.source_chunk_ids
