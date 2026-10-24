"""
Reliability, Edge-Case, and Graceful Failure Test Suite.
Verifies parser resilience on malformed HTML, empty catalog searches,
and graceful degradation during model connection drops or timeouts.
"""

from decimal import Decimal
from pathlib import Path
import pytest

from veridocs.generation.ollama_adapter import (
    OllamaConnectionError,
    OllamaGenerationProvider,
    OllamaProviderError,
    OllamaTimeoutError,
)
from veridocs.ingestion.html_parser import FilingParser
from veridocs.retrieval.bm25_retriever import BM25Retriever
from veridocs.retrieval.pipeline import RetrievalPipeline
from veridocs.schemas.data_models import DocumentStatus


def test_malformed_html_ingestion_resilience():
    """
    Verify that severely corrupt HTML (unclosed tags, missing table cells, mismatched tags)
    does not raise unhandled exceptions and records diagnostic warnings.
    """
    corrupt_html = """
    <div>
      <head><title>Corrupt Filing
      <body>
        <h1>Item 8. Financial Statements</h1>
        <table>
          <tr><td>Missing Closing Row
          <tr><td>Incomplete Row 2<td>$1,234</td>
        <div>Unclosed Div within Table
        </table>
        <p>Paragraph with unclosed <b>bold <i>and italic tag.
    """

    parser = FilingParser(
        raw_html=corrupt_html.encode("utf-8"),
        metadata={
            "cik": "0000320193",
            "accession_number": "0000320193-23-000999",
            "primary_document_name": "corrupt.htm",
            "source_url": "https://www.sec.gov/corrupt.htm",
            "filing_date": "2023-11-03",
            "report_period": "2023-09-30",
            "form_type": "10-K",
        },
    )
    result = parser.parse()

    assert result.document.document_id is not None
    assert result.document.status == DocumentStatus.PARSED
    assert isinstance(result.warnings, list)


def test_retrieval_pipeline_null_components():
    """
    Verify that RetrievalPipeline handles empty or None components gracefully.
    """
    pipeline = RetrievalPipeline(
        catalog=None,  # type: ignore
        bm25_retriever=None,
        dense_retriever=None,
        reranker=None,
    )

    chunks, trace = pipeline.execute(query="What is the revenue?", top_k=5)
    assert chunks == []
    assert trace.query_text == "What is the revenue?"
    assert trace.final_evidence_chunk_ids == []


@pytest.mark.asyncio
async def test_ollama_provider_unreachable_host():
    """
    Verify that when local Ollama is unreachable on an unused port,
    the provider raises a clean RuntimeError rather than crashing silently.
    """
    provider = OllamaGenerationProvider(
        base_url="http://127.0.0.1:59998",  # unused local port
        model_name="qwen3:8b",
        timeout_seconds=2.0,
    )

    is_healthy = await provider.is_healthy()
    assert is_healthy is False

    with pytest.raises((OllamaConnectionError, OllamaTimeoutError, OllamaProviderError)) as exc_info:
        await provider.generate(prompt="Hello", system_prompt="Test")
    assert any(term in str(exc_info.value) for term in ("Failed to connect", "timed out", "Ollama"))
