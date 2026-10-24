from decimal import Decimal
from veridocs.chunking.table_chunker import TableChunker
from veridocs.schemas.data_models import FilingDocument, TableCell, TableRecord


def test_table_chunker_context_headers():
    doc = FilingDocument(
        document_id="doc_aapl_2023",
        cik="0000320193",
        company_name="Apple Inc.",
        form_type="10-K",
        accession_number="0000320193-23-000106",
        filing_date="2023-11-03",
        report_period="2023-09-30",
        fiscal_year=2023,
        primary_document_name="aapl.htm",
        source_url="https://www.sec.gov/...",
        raw_sha256="abc",
        byte_size=1000,
        fetched_at="2026-10-24T12:00:00Z",
    )

    table = TableRecord(
        table_id="tbl_operations",
        document_id=doc.document_id,
        section_id="Item 8",
        caption="Consolidated Statements of Operations",
        units_text="USD_MILLIONS",
        source_locator="tbl_01",
        column_headers=["Line Item", "FY2023", "FY2022"],
        row_count=2,
        column_count=3,
    )

    cells = [
        TableCell(
            cell_id="c_0_1",
            row_index=0,
            column_index=1,
            raw_text="383,285",
            normalized_text="383285",
            numeric_value=Decimal("383285"),
            is_empty_or_dash=False,
            row_label="Total net sales",
            column_label="FY2023",
            unit="USD_MILLIONS",
        ),
        TableCell(
            cell_id="c_0_2",
            row_index=0,
            column_index=2,
            raw_text="394,328",
            normalized_text="394328",
            numeric_value=Decimal("394328"),
            is_empty_or_dash=False,
            row_label="Total net sales",
            column_label="FY2022",
            unit="USD_MILLIONS",
        ),
    ]

    chunker = TableChunker(rows_per_chunk=5)
    chunks = chunker.chunk_table(doc, table, cells)

    assert len(chunks) == 1
    chk = chunks[0]
    assert chk.chunk_id.startswith("chk_doc_aapl_2023_tblgroup_")
    # Verify that essential corporate and table context is repeated in chunk text
    assert "Filing: Apple Inc." in chk.text
    assert "Form: 10-K | Period: FY2023" in chk.text
    assert "Table: Consolidated Statements of Operations" in chk.text
    assert "Units: USD_MILLIONS" in chk.text
    assert "Row: Total net sales | 383,285 | 394,328" in chk.text
