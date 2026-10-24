from veridocs.chunking.fixed_window import FixedWindowChunker
from veridocs.schemas.data_models import FilingDocument


def test_fixed_window_chunker():
    doc = FilingDocument(
        document_id="doc_test_fixed",
        cik="0000320193",
        company_name="Apple Inc.",
        form_type="10-K",
        accession_number="0000320193-23-000106",
        filing_date="2023-11-03",
        report_period="2023-09-30",
        primary_document_name="aapl.htm",
        source_url="https://www.sec.gov/...",
        raw_sha256="abc",
        byte_size=1000,
        fetched_at="2026-10-24T12:00:00Z",
    )
    chunker = FixedWindowChunker(window_size=100, overlap=20)
    text = "The quick brown fox jumps over the lazy dog. " * 10
    chunks = chunker.chunk_document(doc, text)

    assert len(chunks) > 1
    assert chunks[0].chunk_id.startswith("chk_doc_test_fixed_fixed_00001_")
    assert chunks[0].ordinal == 1
    assert chunks[0].token_count > 0
