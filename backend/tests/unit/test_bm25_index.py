from pathlib import Path
from veridocs.indexing.bm25_index import BM25Index, tokenize_financial_text
from veridocs.schemas.data_models import ChunkKind, ChunkRecord


def test_tokenize_financial_text():
    raw = "Apple reported FY2023 revenue of $383,285 million, growth of +5.2%, and ($1.2B) in foreign exchange losses under Item 8."
    tokens = tokenize_financial_text(raw)

    # Financial tokens must survive tokenization
    assert "fy2023" in tokens
    assert "$383,285" in tokens
    assert "+5.2%" in tokens
    assert "($1.2b)" in tokens
    assert "item8" in tokens


def test_bm25_index_search_and_save(temp_dir: Path):
    chunks = [
        ChunkRecord(
            chunk_id="chk_01",
            document_id="doc_1",
            chunk_kind=ChunkKind.NARRATIVE,
            ordinal=1,
            section_id="Item 7",
            section_title="MD&A",
            text="Total net sales in FY2023 was $383,285 million.",
            raw_text="Total net sales in FY2023 was $383,285 million.",
            token_count=10,
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
            text="Global supply chain constraints and semiconductor shortages could impact margins.",
            raw_text="Global supply chain constraints...",
            token_count=10,
            source_url="https://sec.gov",
            source_locator="item1a",
            content_hash="hash2",
        ),
    ]

    index = BM25Index.build(chunks)

    # Query with exact financial token
    results = index.search("FY2023 $383,285 sales", top_k=5)
    assert len(results) > 0
    assert results[0][0] == "chk_01"  # chk_01 must rank top for sales figure

    # Save and reload
    art_path = temp_dir / "bm25.pkl"
    checksum = index.save(art_path)
    assert len(checksum) == 64

    reloaded = BM25Index.load(art_path)
    reloaded_results = reloaded.search("FY2023 $383,285 sales", top_k=5)
    assert reloaded_results == results
