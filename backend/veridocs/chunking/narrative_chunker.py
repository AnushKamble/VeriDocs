"""
Production structure-aware narrative chunker preserving section hierarchy and context headers.
"""

from typing import List
from veridocs.ingestion.section_parser import SectionBlock
from veridocs.schemas.data_models import ChunkKind, ChunkRecord, FilingDocument
from veridocs.sec.provenance import compute_sha256


class NarrativeChunker:
    """
    Structure-aware narrative chunker that splits on paragraph boundaries,
    observes token limits, and prepends essential corporate context headers.
    """

    def __init__(self, max_characters: int = 1500, overlap_paragraphs: int = 1):
        self.max_characters = max_characters
        self.overlap_paragraphs = overlap_paragraphs
        self.version = "narrative_1.0.0"

    def _build_context_header(self, doc: FilingDocument, section: SectionBlock) -> str:
        fiscal = f"FY{doc.fiscal_year}" if doc.fiscal_year else doc.report_period
        return f"Filing: {doc.company_name} | Form: {doc.form_type} | Period: {fiscal} | Section: {section.section_id} — {section.section_title}\n"

    def chunk_section(
        self,
        document: FilingDocument,
        section: SectionBlock,
        starting_ordinal: int = 1,
    ) -> List[ChunkRecord]:
        chunks: List[ChunkRecord] = []
        paragraphs = [p.strip() for p in section.text_content.split("\n\n") if p.strip()]

        if not paragraphs:
            return []

        header = self._build_context_header(document, section)
        current_paragraphs: List[str] = []
        current_len = len(header)
        ordinal = starting_ordinal

        for p in paragraphs:
            p_len = len(p)
            if current_paragraphs and (current_len + p_len > self.max_characters):
                # Flush current chunk
                body = "\n\n".join(current_paragraphs)
                full_chunk_text = f"{header}\n{body}"
                c_hash = compute_sha256(full_chunk_text.encode("utf-8"))[:12]
                chunk_id = f"chk_{document.document_id}_narrative_{ordinal:05d}_{c_hash}"

                chunks.append(
                    ChunkRecord(
                        chunk_id=chunk_id,
                        document_id=document.document_id,
                        chunk_kind=ChunkKind.NARRATIVE,
                        ordinal=ordinal,
                        section_id=section.section_id,
                        section_title=section.section_title,
                        text=full_chunk_text,
                        raw_text=body,
                        token_count=max(1, len(full_chunk_text) // 4),
                        source_url=document.source_url,
                        source_locator=f"{section.section_id}_p{ordinal}",
                        content_hash=compute_sha256(full_chunk_text.encode("utf-8")),
                    )
                )
                ordinal += 1

                # Keep overlap paragraphs if configured
                if self.overlap_paragraphs > 0 and len(current_paragraphs) >= self.overlap_paragraphs:
                    current_paragraphs = current_paragraphs[-self.overlap_paragraphs:]
                    current_len = len(header) + sum(len(x) + 2 for x in current_paragraphs)
                else:
                    current_paragraphs = []
                    current_len = len(header)

            current_paragraphs.append(p)
            current_len += p_len + 2

        # Flush final chunk
        if current_paragraphs:
            body = "\n\n".join(current_paragraphs)
            full_chunk_text = f"{header}\n{body}"
            c_hash = compute_sha256(full_chunk_text.encode("utf-8"))[:12]
            chunk_id = f"chk_{document.document_id}_narrative_{ordinal:05d}_{c_hash}"

            chunks.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    chunk_kind=ChunkKind.NARRATIVE,
                    ordinal=ordinal,
                    section_id=section.section_id,
                    section_title=section.section_title,
                    text=full_chunk_text,
                    raw_text=body,
                    token_count=max(1, len(full_chunk_text) // 4),
                    source_url=document.source_url,
                    source_locator=f"{section.section_id}_p{ordinal}",
                    content_hash=compute_sha256(full_chunk_text.encode("utf-8")),
                )
            )

        return chunks
