"""
Fixed-window baseline text chunker for experimental comparative evaluation (RQ1).
"""

from typing import List
from veridocs.schemas.data_models import ChunkKind, ChunkRecord, FilingDocument
from veridocs.sec.provenance import compute_sha256


class FixedWindowChunker:
    """
    Fixed-window text chunker without table or section awareness.
    Splits text blindly by character window with overlap.
    Used strictly as an IR evaluation baseline to measure value of structure awareness.
    """

    def __init__(self, window_size: int = 600, overlap: int = 100):
        self.window_size = window_size
        self.overlap = overlap
        self.version = "fixed_window_1.0.0"

    def chunk_document(self, document: FilingDocument, full_text: str) -> List[ChunkRecord]:
        chunks: List[ChunkRecord] = []
        clean_text = full_text.strip()
        text_len = len(clean_text)

        if text_len == 0:
            return []

        step = max(1, self.window_size - self.overlap)
        start = 0
        ordinal = 0

        while start < text_len:
            end = min(text_len, start + self.window_size)
            window_slice = clean_text[start:end].strip()

            if window_slice:
                ordinal += 1
                c_hash = compute_sha256(window_slice.encode("utf-8"))[:12]
                chunk_id = f"chk_{document.document_id}_fixed_{ordinal:05d}_{c_hash}"

                chunks.append(
                    ChunkRecord(
                        chunk_id=chunk_id,
                        document_id=document.document_id,
                        chunk_kind=ChunkKind.NARRATIVE,
                        ordinal=ordinal,
                        section_id="General",
                        section_title="Unstructured Window",
                        text=window_slice,
                        raw_text=window_slice,
                        token_count=max(1, len(window_slice) // 4),
                        source_url=document.source_url,
                        source_locator=f"fixed_char_{start}_{end}",
                        content_hash=compute_sha256(window_slice.encode("utf-8")),
                    )
                )

            if end >= text_len:
                break
            start += step

        return chunks
