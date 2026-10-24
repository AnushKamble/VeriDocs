from decimal import Decimal
from pathlib import Path
from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.schemas.data_models import (
    ChunkKind,
    ChunkRecord,
    DocumentStatus,
    FilingDocument,
    IndexManifest,
    TableCell,
    TableRecord,
)
from veridocs.schemas.query_models import MetadataFilter


def test_sqlite_catalog_lifecycle(temp_dir: Path):
    db_path = temp_dir / "test_veridocs.db"
    catalog = SQLiteCatalog(db_path)

    doc = FilingDocument(
        document_id="doc_aapl_test",
        cik="0000320193",
        ticker="AAPL",
        company_name="Apple Inc.",
        form_type="10-K",
        accession_number="0000320193-23-000106",
        filing_date="2023-11-03",
        report_period="2023-09-30",
        fiscal_year=2023,
        fiscal_quarter=4,
        primary_document_name="aapl.htm",
        source_url="https://www.sec.gov/...",
        raw_sha256="sha_apple_raw",
        byte_size=5000,
        fetched_at="2026-10-24T12:00:00Z",
        status=DocumentStatus.INDEXED,
    )

    table = TableRecord(
        table_id="tbl_apple_01",
        document_id=doc.document_id,
        section_id="Item 8",
        caption="Balance Sheet",
        units_text="USD_MILLIONS",
        source_locator="tbl_01",
        column_headers=["Metric", "2023"],
    )

    cell = TableCell(
        cell_id="tbl_apple_01_r0_c1",
        row_index=0,
        column_index=1,
        raw_text="30,000",
        normalized_text="30000",
        numeric_value=Decimal("30000"),
        is_empty_or_dash=False,
        row_label="Cash and cash equivalents",
        column_label="2023",
        unit="USD_MILLIONS",
    )

    chunk = ChunkRecord(
        chunk_id="chk_apple_01",
        document_id=doc.document_id,
        chunk_kind=ChunkKind.TABLE_GROUP,
        ordinal=1,
        section_id="Item 8",
        section_title="Balance Sheet",
        text="Cash and cash equivalents was $30,000 million in 2023.",
        raw_text="Cash and cash equivalents 30,000",
        token_count=10,
        source_url="https://sec.gov",
        source_locator="item8_tbl1",
        content_hash="hash123",
    )

    # Save document and entities
    catalog.save_document(doc, [table], [cell], [chunk])

    # Retrieve and verify document
    retrieved_doc = catalog.get_document(doc.document_id)
    assert retrieved_doc is not None
    assert retrieved_doc.company_name == "Apple Inc."
    assert retrieved_doc.fiscal_year == 2023

    # Retrieve chunk
    retrieved_chk = catalog.get_chunk("chk_apple_01")
    assert retrieved_chk is not None
    assert retrieved_chk.section_id == "Item 8"

    # Query with filter
    filtered_chunks = catalog.list_chunks(MetadataFilter(ticker="AAPL", fiscal_year=2023))
    assert len(filtered_chunks) == 1
    assert filtered_chunks[0].chunk_id == "chk_apple_01"

    # Non-matching filter returns empty
    mismatch = catalog.list_chunks(MetadataFilter(ticker="MSFT"))
    assert len(mismatch) == 0

    # Corpus hash is non-empty
    c_hash = catalog.compute_corpus_hash()
    assert len(c_hash) == 64
