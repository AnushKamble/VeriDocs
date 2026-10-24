"""
Canonical data models for VeriDocs filings, sections, tables, cells, chunks, and index manifests.
"""

from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    FETCHED = "FETCHED"
    PARSED = "PARSED"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class ChunkKind(str, Enum):
    NARRATIVE = "narrative"
    TABLE_GROUP = "table_group"
    TABLE_ROW = "table_row"
    FOOTNOTE = "footnote"


class FilingDocument(BaseModel):
    document_id: str = Field(..., description="Deterministic document ID, e.g. doc_0000320193_000032019323000106")
    cik: str = Field(..., description="10-digit zero-padded CIK string")
    ticker: Optional[str] = Field(None, description="Stock ticker symbol if available")
    company_name: str
    form_type: str = Field(..., description="Form type: 10-K, 10-Q, 10-K/A, etc.")
    accession_number: str
    filing_date: str = Field(..., description="Filing submission date ISO format YYYY-MM-DD")
    report_period: str = Field(..., description="Period end date ISO format YYYY-MM-DD")
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    primary_document_name: str
    source_url: str
    raw_sha256: str
    byte_size: int
    fetched_at: str
    parsed_at: Optional[str] = None
    parser_version: str = "1.0.0"
    status: DocumentStatus = DocumentStatus.FETCHED
    diagnostics: List[str] = Field(default_factory=list)


class TableCell(BaseModel):
    cell_id: str
    row_index: int
    column_index: int
    raw_text: str
    normalized_text: str
    numeric_value: Optional[Decimal] = None
    is_empty_or_dash: bool = False
    row_label: str
    column_label: str
    unit: Optional[str] = None
    fiscal_period: Optional[str] = None


class TableRecord(BaseModel):
    table_id: str
    document_id: str
    section_id: str
    caption: str
    units_text: Optional[str] = None
    source_locator: str
    column_headers: List[str] = Field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    parse_warnings: List[str] = Field(default_factory=list)


class ChunkRecord(BaseModel):
    chunk_id: str = Field(..., description="Deterministic content-derived chunk identifier")
    document_id: str
    chunk_kind: ChunkKind
    ordinal: int
    section_id: str
    section_title: str
    text: str = Field(..., description="Context-preserving formatted text")
    raw_text: str = Field(..., description="Verbatim source excerpt")
    token_count: int
    table_id: Optional[str] = None
    row_labels: List[str] = Field(default_factory=list)
    column_labels: List[str] = Field(default_factory=list)
    units: Optional[str] = None
    source_url: str
    source_locator: str
    content_hash: str


class IndexManifest(BaseModel):
    manifest_version: str = "1.0"
    created_at: str
    chunker_version: str
    embedding_model_id: str
    embedding_dimension: int = 384
    normalization: str = "L2"
    total_chunks: int
    source_document_ids: List[str]
    source_corpus_hash: str
    faiss_index_checksum: str
    id_map_checksum: str
