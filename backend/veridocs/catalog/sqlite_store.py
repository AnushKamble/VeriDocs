"""
SQLite durable catalog for documents, sections, tables, cells, chunks, and index manifests.
"""

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from veridocs.sec.provenance import compute_sha256
from veridocs.utils.logging import logger


class SQLiteCatalog:
    """
    Transactional SQLite persistence layer ensuring relational integrity,
    deterministic metadata queries, and atomic re-ingestion.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high-concurrency read/writes
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                cik TEXT NOT NULL,
                ticker TEXT,
                company_name TEXT NOT NULL,
                form_type TEXT NOT NULL,
                accession_number TEXT NOT NULL,
                filing_date TEXT NOT NULL,
                report_period TEXT NOT NULL,
                fiscal_year INTEGER,
                fiscal_quarter INTEGER,
                primary_document_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                raw_sha256 TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                fetched_at TEXT NOT NULL,
                parsed_at TEXT,
                parser_version TEXT NOT NULL,
                status TEXT NOT NULL,
                diagnostics_json TEXT
            );

            CREATE TABLE IF NOT EXISTS tables (
                table_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                section_id TEXT NOT NULL,
                caption TEXT NOT NULL,
                units_text TEXT,
                source_locator TEXT NOT NULL,
                column_headers_json TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                column_count INTEGER NOT NULL,
                parse_warnings_json TEXT,
                footnotes_json TEXT
            );

            CREATE TABLE IF NOT EXISTS cells (
                cell_id TEXT PRIMARY KEY,
                table_id TEXT NOT NULL REFERENCES tables(table_id) ON DELETE CASCADE,
                document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                row_index INTEGER NOT NULL,
                column_index INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                numeric_value TEXT,
                is_empty_or_dash INTEGER NOT NULL,
                row_label TEXT NOT NULL,
                column_label TEXT NOT NULL,
                unit TEXT,
                fiscal_period TEXT
            );

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                chunk_kind TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                section_id TEXT NOT NULL,
                section_title TEXT NOT NULL,
                text TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                table_id TEXT,
                row_labels_json TEXT,
                column_labels_json TEXT,
                units TEXT,
                source_url TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                content_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS manifests (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                manifest_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_docs_cik ON documents(cik);
            CREATE INDEX IF NOT EXISTS idx_docs_ticker ON documents(ticker);
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_cells_table ON cells(table_id);
            """)

            # Ensure schema migration for existing databases
            try:
                conn.execute("ALTER TABLE tables ADD COLUMN footnotes_json TEXT")
            except sqlite3.OperationalError:
                pass

    def save_document(
        self,
        document: FilingDocument,
        tables: List[TableRecord],
        cells: List[TableCell],
        chunks: List[ChunkRecord],
    ) -> None:
        """
        Atomically saves or updates a document and all related tables, cells, and chunks.
        """
        with self._get_connection() as conn:
            with conn:
                # 1. Upsert document
                conn.execute(
                    """
                    INSERT INTO documents (
                        document_id, cik, ticker, company_name, form_type,
                        accession_number, filing_date, report_period, fiscal_year,
                        fiscal_quarter, primary_document_name, source_url, raw_sha256,
                        byte_size, fetched_at, parsed_at, parser_version, status,
                        diagnostics_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(document_id) DO UPDATE SET
                        status=excluded.status,
                        parsed_at=excluded.parsed_at,
                        diagnostics_json=excluded.diagnostics_json;
                    """,
                    (
                        document.document_id,
                        document.cik,
                        document.ticker,
                        document.company_name,
                        document.form_type,
                        document.accession_number,
                        document.filing_date,
                        document.report_period,
                        document.fiscal_year,
                        document.fiscal_quarter,
                        document.primary_document_name,
                        document.source_url,
                        document.raw_sha256,
                        document.byte_size,
                        document.fetched_at,
                        document.parsed_at,
                        document.parser_version,
                        document.status.value,
                        json.dumps(document.diagnostics),
                    ),
                )

                # 2. Delete existing child entities to ensure atomic clean replacement
                conn.execute("DELETE FROM tables WHERE document_id = ?", (document.document_id,))
                conn.execute("DELETE FROM cells WHERE document_id = ?", (document.document_id,))
                conn.execute("DELETE FROM chunks WHERE document_id = ?", (document.document_id,))

                # 3. Insert tables
                table_params = [
                    (
                        t.table_id,
                        t.document_id,
                        t.section_id,
                        t.caption,
                        t.units_text,
                        t.source_locator,
                        json.dumps(t.column_headers),
                        t.row_count,
                        t.column_count,
                        json.dumps(t.parse_warnings),
                        json.dumps(t.footnotes),
                    )
                    for t in tables
                ]
                conn.executemany(
                    """
                    INSERT INTO tables (
                        table_id, document_id, section_id, caption, units_text,
                        source_locator, column_headers_json, row_count, column_count,
                        parse_warnings_json, footnotes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    table_params,
                )

                # 4. Insert cells
                cell_params = [
                    (
                        c.cell_id,
                        t_id,
                        document.document_id,
                        c.row_index,
                        c.column_index,
                        c.raw_text,
                        c.normalized_text,
                        str(c.numeric_value) if c.numeric_value is not None else None,
                        1 if c.is_empty_or_dash else 0,
                        c.row_label,
                        c.column_label,
                        c.unit,
                        c.fiscal_period,
                    )
                    for t_id, c in ((c.cell_id.rsplit("_r", 1)[0], c) for c in cells)
                ]
                conn.executemany(
                    """
                    INSERT INTO cells (
                        cell_id, table_id, document_id, row_index, column_index,
                        raw_text, normalized_text, numeric_value, is_empty_or_dash,
                        row_label, column_label, unit, fiscal_period
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    cell_params,
                )

                # 5. Insert chunks
                chunk_params = [
                    (
                        chk.chunk_id,
                        chk.document_id,
                        chk.chunk_kind.value,
                        chk.ordinal,
                        chk.section_id,
                        chk.section_title,
                        chk.text,
                        chk.raw_text,
                        chk.token_count,
                        chk.table_id,
                        json.dumps(chk.row_labels),
                        json.dumps(chk.column_labels),
                        chk.units,
                        chk.source_url,
                        chk.source_locator,
                        chk.content_hash,
                    )
                    for chk in chunks
                ]
                conn.executemany(
                    """
                    INSERT INTO chunks (
                        chunk_id, document_id, chunk_kind, ordinal, section_id,
                        section_title, text, raw_text, token_count, table_id,
                        row_labels_json, column_labels_json, units, source_url,
                        source_locator, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    chunk_params,
                )

    def get_document(self, document_id: str) -> Optional[FilingDocument]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)).fetchone()
            if not row:
                return None
            return FilingDocument(
                document_id=row["document_id"],
                cik=row["cik"],
                ticker=row["ticker"],
                company_name=row["company_name"],
                form_type=row["form_type"],
                accession_number=row["accession_number"],
                filing_date=row["filing_date"],
                report_period=row["report_period"],
                fiscal_year=row["fiscal_year"],
                fiscal_quarter=row["fiscal_quarter"],
                primary_document_name=row["primary_document_name"],
                source_url=row["source_url"],
                raw_sha256=row["raw_sha256"],
                byte_size=row["byte_size"],
                fetched_at=row["fetched_at"],
                parsed_at=row["parsed_at"],
                parser_version=row["parser_version"],
                status=DocumentStatus(row["status"]),
                diagnostics=json.loads(row["diagnostics_json"] or "[]"),
            )

    def list_documents(
        self,
        ticker: Optional[str] = None,
        form_type: Optional[str] = None,
    ) -> List[FilingDocument]:
        with self._get_connection() as conn:
            query = "SELECT * FROM documents"
            params = []
            conditions = []
            if ticker:
                conditions.append("ticker = ?")
                params.append(ticker)
            if form_type:
                conditions.append("form_type = ?")
                params.append(form_type)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY filing_date DESC"

            rows = conn.execute(query, params).fetchall()
            return [

                FilingDocument(
                    document_id=r["document_id"],
                    cik=r["cik"],
                    ticker=r["ticker"],
                    company_name=r["company_name"],
                    form_type=r["form_type"],
                    accession_number=r["accession_number"],
                    filing_date=r["filing_date"],
                    report_period=r["report_period"],
                    fiscal_year=r["fiscal_year"],
                    fiscal_quarter=r["fiscal_quarter"],
                    primary_document_name=r["primary_document_name"],
                    source_url=r["source_url"],
                    raw_sha256=r["raw_sha256"],
                    byte_size=r["byte_size"],
                    fetched_at=r["fetched_at"],
                    parsed_at=r["parsed_at"],
                    parser_version=r["parser_version"],
                    status=DocumentStatus(r["status"]),
                    diagnostics=json.loads(r["diagnostics_json"] or "[]"),
                )
                for r in rows
            ]

    def get_chunk(self, chunk_id: str) -> Optional[ChunkRecord]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
            if not row:
                return None
            return ChunkRecord(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                chunk_kind=ChunkKind(row["chunk_kind"]),
                ordinal=row["ordinal"],
                section_id=row["section_id"],
                section_title=row["section_title"],
                text=row["text"],
                raw_text=row["raw_text"],
                token_count=row["token_count"],
                table_id=row["table_id"],
                row_labels=json.loads(row["row_labels_json"] or "[]"),
                column_labels=json.loads(row["column_labels_json"] or "[]"),
                units=row["units"],
                source_url=row["source_url"],
                source_locator=row["source_locator"],
                content_hash=row["content_hash"],
            )

    def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[ChunkRecord]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        with self._get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM chunks WHERE chunk_id IN ({placeholders})",
                chunk_ids,
            ).fetchall()
            return [
                ChunkRecord(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    chunk_kind=ChunkKind(row["chunk_kind"]),
                    ordinal=row["ordinal"],
                    section_id=row["section_id"],
                    section_title=row["section_title"],
                    text=row["text"],
                    raw_text=row["raw_text"],
                    token_count=row["token_count"],
                    table_id=row["table_id"],
                    row_labels=json.loads(row["row_labels_json"] or "[]"),
                    column_labels=json.loads(row["column_labels_json"] or "[]"),
                    units=row["units"],
                    source_url=row["source_url"],
                    source_locator=row["source_locator"],
                    content_hash=row["content_hash"],
                )
                for row in rows
            ]

    def list_chunks(self, filters: Optional[MetadataFilter] = None) -> List[ChunkRecord]:
        """Lists chunks matching optional metadata filters."""
        query = "SELECT c.* FROM chunks c JOIN documents d ON c.document_id = d.document_id"
        conditions = []
        params = []

        if filters:
            if filters.ticker:
                conditions.append("d.ticker = ?")
                params.append(filters.ticker.upper())
            if filters.cik:
                conditions.append("d.cik = ?")
                params.append(filters.cik.zfill(10))
            if filters.form_type:
                conditions.append("d.form_type = ?")
                params.append(filters.form_type)
            if filters.fiscal_year:
                conditions.append("d.fiscal_year = ?")
                params.append(filters.fiscal_year)
            if filters.fiscal_quarter:
                conditions.append("d.fiscal_quarter = ?")
                params.append(filters.fiscal_quarter)
            if filters.section_id:
                conditions.append("c.section_id = ?")
                params.append(filters.section_id)
            if filters.document_ids:
                placeholders = ",".join("?" for _ in filters.document_ids)
                conditions.append(f"c.document_id IN ({placeholders})")
                params.extend(filters.document_ids)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY c.document_id, c.ordinal ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                ChunkRecord(
                    chunk_id=r["chunk_id"],
                    document_id=r["document_id"],
                    chunk_kind=ChunkKind(r["chunk_kind"]),
                    ordinal=r["ordinal"],
                    section_id=r["section_id"],
                    section_title=r["section_title"],
                    text=r["text"],
                    raw_text=r["raw_text"],
                    token_count=r["token_count"],
                    table_id=r["table_id"],
                    row_labels=json.loads(r["row_labels_json"] or "[]"),
                    column_labels=json.loads(r["column_labels_json"] or "[]"),
                    units=r["units"],
                    source_url=r["source_url"],
                    source_locator=r["source_locator"],
                    content_hash=r["content_hash"],
                )
                for r in rows
            ]

    def list_tables(self, document_id: str) -> List[TableRecord]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM tables WHERE document_id = ?", (document_id,)).fetchall()
            return [
                TableRecord(
                    table_id=r["table_id"],
                    document_id=r["document_id"],
                    section_id=r["section_id"],
                    caption=r["caption"],
                    units_text=r["units_text"],
                    source_locator=r["source_locator"],
                    column_headers=json.loads(r["column_headers_json"] or "[]"),
                    row_count=r["row_count"],
                    column_count=r["column_count"],
                    parse_warnings=json.loads(r["parse_warnings_json"] or "[]"),
                    footnotes=json.loads(r["footnotes_json"] or "[]") if ("footnotes_json" in r.keys() and r["footnotes_json"]) else [],
                )
                for r in rows
            ]

    def list_sections(self, document_id: str) -> List[Dict[str, str]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT section_id, section_title FROM chunks WHERE document_id = ?",
                (document_id,),
            ).fetchall()
            return [
                {"section_id": r["section_id"], "section_title": r["section_title"]}
                for r in rows
            ]

    def compute_corpus_hash(self) -> str:

        """Computes SHA-256 of sorted list of all chunk IDs and content hashes."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT chunk_id, content_hash FROM chunks ORDER BY chunk_id ASC").fetchall()
            combined = "".join(f"{r['chunk_id']}:{r['content_hash']}" for r in rows)
            return compute_sha256(combined.encode("utf-8"))

    def save_manifest(self, manifest: IndexManifest) -> None:
        with self._get_connection() as conn:
            with conn:
                conn.execute(
                    "INSERT INTO manifests (id, manifest_json) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET manifest_json=excluded.manifest_json;",
                    (manifest.model_dump_json(),),
                )

    def get_manifest(self) -> Optional[IndexManifest]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT manifest_json FROM manifests WHERE id = 1").fetchone()
            if not row:
                return None
            return IndexManifest.model_validate_json(row["manifest_json"])
