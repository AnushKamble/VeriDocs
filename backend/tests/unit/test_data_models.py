from decimal import Decimal
import pytest
from pydantic import ValidationError

from veridocs.schemas.data_models import (
    ChunkKind,
    ChunkRecord,
    DocumentStatus,
    FilingDocument,
    IndexManifest,
    TableCell,
    TableRecord,
)


def test_filing_document_creation():
    doc = FilingDocument(
        document_id="doc_0000320193_000032019323000106",
        cik="0000320193",
        ticker="AAPL",
        company_name="Apple Inc.",
        form_type="10-K",
        accession_number="0000320193-23-000106",
        filing_date="2023-11-03",
        report_period="2023-09-30",
        fiscal_year=2023,
        fiscal_quarter=4,
        primary_document_name="aapl-20230930.htm",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
        raw_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        byte_size=1542300,
        fetched_at="2026-10-24T12:00:00Z",
        status=DocumentStatus.FETCHED,
    )
    assert doc.document_id.startswith("doc_0000320193")
    assert doc.fiscal_year == 2023
    assert doc.status == DocumentStatus.FETCHED


def test_table_cell_numeric_and_empty():
    # Numeric cell with accounting negative
    cell_num = TableCell(
        cell_id="c_0_1",
        row_index=0,
        column_index=1,
        raw_text="$(1,245)",
        normalized_text="-1245",
        numeric_value=Decimal("-1245"),
        is_empty_or_dash=False,
        row_label="Research and Development",
        column_label="Year Ended September 30 > 2023",
        unit="USD_MILLIONS",
        fiscal_period="FY2023",
    )
    assert cell_num.numeric_value == Decimal("-1245")
    assert not cell_num.is_empty_or_dash

    # Dash / missing cell
    cell_dash = TableCell(
        cell_id="c_1_1",
        row_index=1,
        column_index=1,
        raw_text="—",
        normalized_text="",
        numeric_value=None,
        is_empty_or_dash=True,
        row_label="Discontinued Operations",
        column_label="Year Ended September 30 > 2023",
    )
    assert cell_dash.numeric_value is None
    assert cell_dash.is_empty_or_dash


def test_chunk_record_validation():
    chunk = ChunkRecord(
        chunk_id="chk_doc_0000320193_000032019323000106_narrative_00001_abc123",
        document_id="doc_0000320193_000032019323000106",
        chunk_kind=ChunkKind.NARRATIVE,
        ordinal=1,
        section_id="Item 7",
        section_title="Management's Discussion and Analysis",
        text="Total net sales increased 2% during fiscal 2023.",
        raw_text="Total net sales increased 2% during fiscal 2023.",
        token_count=12,
        source_url="https://www.sec.gov/...",
        source_locator="item7_p1",
        content_hash="abc123hash",
    )
    assert chunk.chunk_kind == ChunkKind.NARRATIVE
    assert chunk.ordinal == 1


def test_index_manifest():
    manifest = IndexManifest(
        created_at="2026-10-24T12:00:00Z",
        chunker_version="1.0.0",
        embedding_model_id="BAAI/bge-small-en-v1.5",
        embedding_dimension=384,
        total_chunks=150,
        source_document_ids=["doc_1", "doc_2"],
        source_corpus_hash="corpus_hash_123",
        faiss_index_checksum="faiss_sum_abc",
        id_map_checksum="id_sum_xyz",
    )
    assert manifest.embedding_dimension == 384
    assert manifest.normalization == "L2"
