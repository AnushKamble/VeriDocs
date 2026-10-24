from pathlib import Path
import pytest
from veridocs.indexing.dense_indexer import DenseIndexer
from veridocs.schemas.data_models import ChunkKind, ChunkRecord


def test_dense_indexer_build_save_load(temp_dir: Path):
    chunks = [
        ChunkRecord(
            chunk_id="chk_01",
            document_id="doc_1",
            chunk_kind=ChunkKind.NARRATIVE,
            ordinal=1,
            section_id="Item 7",
            section_title="MD&A",
            text="Revenue increased significantly due to strong iPhone demand in fiscal 2023.",
            raw_text="Revenue increased significantly...",
            token_count=12,
            source_url="https://sec.gov",
            source_locator="item7",
            content_hash="hash1",
        ),
        ChunkRecord(
            chunk_id="chk_02",
            document_id="doc_1",
            chunk_kind=ChunkKind.NARRATIVE,
            ordinal=2,
            section_id="Item 1A",
            section_title="Risk Factors",
            text="Macroeconomic volatility, inflation, and interest rates pose commercial challenges.",
            raw_text="Macroeconomic volatility...",
            token_count=12,
            source_url="https://sec.gov",
            source_locator="item1a",
            content_hash="hash2",
        ),
    ]

    indexer = DenseIndexer(batch_size=8)
    manifest = indexer.build_and_save_index(
        chunks=chunks,
        output_dir=temp_dir / "dense_index",
        chunker_version="1.0.0",
        corpus_hash="test_corpus_hash_123",
    )

    assert manifest.embedding_dimension == 384
    assert manifest.normalization == "L2"
    assert manifest.total_chunks == 2
    assert len(manifest.faiss_index_checksum) == 64

    # Load index and verify mapping
    faiss_idx, id_map, loaded_manifest = DenseIndexer.load_index(temp_dir / "dense_index")
    assert faiss_idx.ntotal == 2
    assert id_map[0] == "chk_01"
    assert id_map[1] == "chk_02"
    assert loaded_manifest.source_corpus_hash == "test_corpus_hash_123"

    # Test corruption detection on tampered index
    with open(temp_dir / "dense_index" / "index.faiss", "wb") as f:
        f.write(b"tampered content")

    with pytest.raises(ValueError, match="Corrupt FAISS index"):
        DenseIndexer.load_index(temp_dir / "dense_index")
