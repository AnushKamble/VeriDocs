"""
Complete filing HTML parser orchestrating section and table reconstruction.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from veridocs.ingestion.section_parser import SectionBlock, SectionParser
from veridocs.ingestion.table_parser import TableParser
from veridocs.schemas.data_models import DocumentStatus, FilingDocument, TableCell, TableRecord
from veridocs.sec.provenance import compute_sha256
from veridocs.utils.logging import logger


class ParsedFilingResult:
    def __init__(
        self,
        document: FilingDocument,
        sections: List[SectionBlock],
        tables: List[TableRecord],
        cells: List[TableCell],
        warnings: List[str],
    ):
        self.document = document
        self.sections = sections
        self.tables = tables
        self.cells = cells
        self.warnings = warnings


class FilingParser:
    """
    Parses raw SEC filing HTML into structured FilingDocument, SectionBlock,
    TableRecord, and TableCell records with full provenance.
    """

    def __init__(self, raw_html: bytes, metadata: Dict[str, Any], parser_version: str = "1.0.0"):
        self.raw_html = raw_html
        self.metadata = metadata
        self.parser_version = parser_version
        self.warnings: List[str] = []

    def parse(self) -> ParsedFilingResult:
        raw_sha256 = compute_sha256(self.raw_html)
        html_str = self.raw_html.decode("utf-8", errors="replace")

        # Parse with lxml HTML parser for robust handling of irregular markup
        soup = BeautifulSoup(html_str, "lxml")

        document_id = self.metadata.get(
            "document_id",
            f"doc_{self.metadata.get('cik', '0000000000')}_{self.metadata.get('accession_number', '').replace('-', '')}",
        )

        # 1. Parse tables first before modifying or flattening DOM
        tables: List[TableRecord] = []
        all_cells: List[TableCell] = []
        table_tags = soup.find_all("table")

        for idx, t_tag in enumerate(table_tags):
            # Deterministic table ID
            table_id = f"tbl_{document_id}_{idx:04d}"
            # Associate with nearest section if possible
            prev_heading = t_tag.find_previous(["h1", "h2", "h3", "h4", "p"])
            section_hint = prev_heading.get_text(" ", strip=True)[:40] if prev_heading else "General"

            parser = TableParser(
                table_tag=t_tag,
                table_id=table_id,
                document_id=document_id,
                section_id=section_hint,
            )
            table_rec, cells = parser.parse()
            tables.append(table_rec)
            all_cells.extend(cells)
            self.warnings.extend(parser.parse_warnings)

        # 2. Parse narrative sections
        section_parser = SectionParser(soup=soup, document_id=document_id)
        sections = section_parser.extract_sections()

        # 3. Create FilingDocument
        doc_record = FilingDocument(
            document_id=document_id,
            cik=self.metadata.get("cik", "0000000000"),
            ticker=self.metadata.get("ticker"),
            company_name=self.metadata.get("company_name", "Unknown Company"),
            form_type=self.metadata.get("form_type", "10-K"),
            accession_number=self.metadata.get("accession_number", "0000000000-00-000000"),
            filing_date=self.metadata.get("filing_date", "1970-01-01"),
            report_period=self.metadata.get("report_period", "1970-01-01"),
            fiscal_year=self.metadata.get("fiscal_year"),
            fiscal_quarter=self.metadata.get("fiscal_quarter"),
            primary_document_name=self.metadata.get("primary_document_name", "filing.htm"),
            source_url=self.metadata.get("source_url", ""),
            raw_sha256=raw_sha256,
            byte_size=len(self.raw_html),
            fetched_at=self.metadata.get("fetched_at", datetime.now(timezone.utc).isoformat()),
            parsed_at=datetime.now(timezone.utc).isoformat(),
            parser_version=self.parser_version,
            status=DocumentStatus.PARSED,
            diagnostics=self.warnings,
        )

        return ParsedFilingResult(
            document=doc_record,
            sections=sections,
            tables=tables,
            cells=all_cells,
            warnings=self.warnings,
        )
