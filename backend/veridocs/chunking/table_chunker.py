"""
Production table chunker: groups table rows while continuously repeating
document metadata, table caption, units, and hierarchical column headers.
"""

from typing import Dict, List
from veridocs.schemas.data_models import ChunkKind, ChunkRecord, FilingDocument, TableCell, TableRecord
from veridocs.sec.provenance import compute_sha256


class TableChunker:
    """
    Context-preserving table chunker that prevents financial numbers from being
    separated from their units, column dates, or row line-item labels.
    """

    def __init__(self, rows_per_chunk: int = 6):
        self.rows_per_chunk = rows_per_chunk
        self.version = "table_chunker_1.0.0"

    def _build_table_context_header(self, doc: FilingDocument, table: TableRecord) -> str:
        fiscal = f"FY{doc.fiscal_year}" if doc.fiscal_year else doc.report_period
        units_str = table.units_text or "Standard / As reported"
        columns_str = " | ".join(table.column_headers)

        lines = [
            f"Filing: {doc.company_name} | Form: {doc.form_type} | Period: {fiscal} | Date: {doc.filing_date}",
            f"Section: {table.section_id} | Table: {table.caption}",
            f"Units: {units_str}",
            f"Columns: {columns_str}",
        ]
        return "\n".join(lines)

    def chunk_table(
        self,
        document: FilingDocument,
        table: TableRecord,
        cells: List[TableCell],
        starting_ordinal: int = 1,
    ) -> List[ChunkRecord]:
        if not cells:
            return []

        # Group cells by row_index
        rows_by_idx: Dict[int, List[TableCell]] = {}
        for c in cells:
            rows_by_idx.setdefault(c.row_index, []).append(c)

        sorted_row_indices = sorted(rows_by_idx.keys())
        chunks: List[ChunkRecord] = []
        ordinal = starting_ordinal
        context_header = self._build_table_context_header(document, table)

        # Iterate in batches of rows_per_chunk
        for i in range(0, len(sorted_row_indices), self.rows_per_chunk):
            chunk_row_indices = sorted_row_indices[i : i + self.rows_per_chunk]
            row_lines: List[str] = []
            chunk_row_labels: List[str] = []

            for r_idx in chunk_row_indices:
                row_cells = sorted(rows_by_idx[r_idx], key=lambda x: x.column_index)
                if not row_cells:
                    continue
                row_label = row_cells[0].row_label
                chunk_row_labels.append(row_label)

                # Format row line: Row: Label | Cell 1 | Cell 2 ...
                cell_vals = [c.raw_text if not c.is_empty_or_dash else "—" for c in row_cells]
                row_lines.append(f"Row: {row_label} | " + " | ".join(cell_vals))

            if not row_lines:
                continue

            raw_body = "\n".join(row_lines)
            full_chunk_text = f"{context_header}\n{raw_body}"
            c_hash = compute_sha256(full_chunk_text.encode("utf-8"))[:12]
            chunk_id = f"chk_{document.document_id}_tblgroup_{ordinal:05d}_{c_hash}"

            chunks.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    chunk_kind=ChunkKind.TABLE_GROUP,
                    ordinal=ordinal,
                    section_id=table.section_id,
                    section_title=table.caption,
                    text=full_chunk_text,
                    raw_text=raw_body,
                    token_count=max(1, len(full_chunk_text) // 4),
                    table_id=table.table_id,
                    row_labels=chunk_row_labels,
                    column_labels=table.column_headers,
                    units=table.units_text,
                    source_url=document.source_url,
                    source_locator=f"{table.table_id}_r{chunk_row_indices[0]}-{chunk_row_indices[-1]}",
                    content_hash=compute_sha256(full_chunk_text.encode("utf-8")),
                )
            )
            ordinal += 1

        return chunks
