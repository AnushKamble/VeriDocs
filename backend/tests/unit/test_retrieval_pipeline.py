from pathlib import Path
from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.indexing.bm25_index import BM25Index
from veridocs.indexing.dense_indexer import DenseIndexer
from veridocs.retrieval.bm25_retriever import BM25Retriever
from veridocs.retrieval.dense_retriever import DenseRetriever
from veridocs.retrieval.pipeline import RetrievalPipeline
from veridocs.retrieval.reranker import CrossEncoderReranker
from veridocs.retrieval.rrf_fusion import reciprocal_rank_fusion
from veridocs.schemas.data_models import (
    ChunkKind,
    ChunkRecord,
    DocumentStatus,
    FilingDocument,
)
from veridocs.schemas.query_models import (
    MetadataFilter,
    RetrievalCandidate,
    RetrieverMode,
)


def build_test_environment(temp_dir: Path):
    db_path = temp_dir / "retrieval_test.db"
    catalog = SQLiteCatalog(db_path)

    doc_apple = FilingDocument(
        document_id="doc_apple_2023",
        cik="0000320193",
        ticker="AAPL",
        company_name="Apple Inc.",
        form_type="10-K",
        accession_number="0000320193-23-000106",
        filing_date="2023-11-03",
        report_period="2023-09-30",
        fiscal_year=2023,
        primary_document_name="aapl.htm",
        source_url="https://sec.gov/apple",
        raw_sha256="raw_apple",
        byte_size=1000,
        fetched_at="2026-10-24T12:00:00Z",
        status=DocumentStatus.INDEXED,
    )

    doc_msft = FilingDocument(
        document_id="doc_msft_2023",
        cik="0000789019",
        ticker="MSFT",
        company_name="Microsoft Corp",
        form_type="10-K",
        accession_number="0000789019-23-000085",
        filing_date="2023-08-01",
        report_period="2023-06-30",
        fiscal_year=2023,
        primary_document_name="msft.htm",
        source_url="https://sec.gov/msft",
        raw_sha256="raw_msft",
        byte_size=1000,
        fetched_at="2026-10-24T12:00:00Z",
        status=DocumentStatus.INDEXED,
    )

    chunks = [
        ChunkRecord(
            chunk_id="chk_apple_revenue",
            document_id=doc_apple.document_id,
            chunk_kind=ChunkKind.NARRATIVE,
            ordinal=1,
            section_id="Item 7",
            section_title="MD&A",
            text="Apple reported FY2023 total net sales of $383,285 million, driven by Services growth.",
            raw_text="Apple net sales $383,285 million.",
            token_count=15,
            source_url=doc_apple.source_url,
            source_locator="item7_p1",
            content_hash="h1",
        ),
        ChunkRecord(
            chunk_id="chk_apple_footnote",
            document_id=doc_apple.document_id,
            chunk_kind=ChunkKind.FOOTNOTE,
            ordinal=2,
            section_id="Item 8",
            section_title="Financial Statements",
            text="Refer to Note 14(b) for specialized derivative hedging contracts in foreign currencies.",
            raw_text="Refer to Note 14(b)...",
            token_count=12,
            source_url=doc_apple.source_url,
            source_locator="item8_fn1",
            content_hash="h2",
        ),
        ChunkRecord(
            chunk_id="chk_apple_macro",
            document_id=doc_apple.document_id,
            chunk_kind=ChunkKind.NARRATIVE,
            ordinal=3,
            section_id="Item 1A",
            section_title="Risk Factors",
            text="Adverse macroeconomic climate, inflationary pressures, and semiconductor shortages affect supply lines.",
            raw_text="Adverse macroeconomic climate...",
            token_count=14,
            source_url=doc_apple.source_url,
            source_locator="item1a_p1",
            content_hash="h3",
        ),
        ChunkRecord(
            chunk_id="chk_msft_cloud",
            document_id=doc_msft.document_id,
            chunk_kind=ChunkKind.NARRATIVE,
            ordinal=1,
            section_id="Item 7",
            section_title="MD&A",
            text="Microsoft Intelligent Cloud revenue reached $87,907 million in fiscal 2023.",
            raw_text="Microsoft Cloud revenue...",
            token_count=12,
            source_url=doc_msft.source_url,
            source_locator="item7_p1",
            content_hash="h4",
        ),
    ]

    catalog.save_document(doc_apple, [], [], [chunks[0], chunks[1], chunks[2]])
    catalog.save_document(doc_msft, [], [], [chunks[3]])

    # Build BM25
    bm25_index = BM25Index.build(chunks)

    # Build Dense Index
    indexer = DenseIndexer(batch_size=4)
    manifest = indexer.build_and_save_index(
        chunks=chunks,
        output_dir=temp_dir / "dense_test",
        corpus_hash="corpus_test",
    )
    faiss_idx, id_map, _ = DenseIndexer.load_index(temp_dir / "dense_test")

    bm25_retriever = BM25Retriever(bm25_index, catalog)
    dense_retriever = DenseRetriever(faiss_idx, id_map, indexer, catalog)
    reranker = CrossEncoderReranker()
    pipeline = RetrievalPipeline(bm25_retriever, dense_retriever, reranker, catalog)

    return pipeline, catalog


def test_rrf_math_and_tie_breaking():
    # Test RRF formula and tie breaking
    c1 = RetrievalCandidate(chunk_id="chk_b", document_id="doc_1", retriever="bm25", rank=1, raw_score=10.0)
    c2 = RetrievalCandidate(chunk_id="chk_a", document_id="doc_1", retriever="dense", rank=1, raw_score=0.9)

    # Both are rank 1 in their respective lists, so RRF score = 1/(60+1) = 1/61 = 0.016393
    # chk_a and chk_b have identical RRF score, so tie-breaker must place chk_a before chk_b
    fused = reciprocal_rank_fusion(
        candidate_lists={"bm25": [c1], "dense": [c2]},
        k0=60,
        top_k=2,
    )
    assert len(fused) == 2
    assert fused[0].chunk_id == "chk_a"
    assert fused[1].chunk_id == "chk_b"
    assert abs(fused[0].rrf_score - (1.0 / 61.0)) < 1e-6


def test_lexical_only_discovery(temp_dir: Path):
    pipeline, _ = build_test_environment(temp_dir)
    # Note 14(b) is an exact lexical token
    chunks, trace = pipeline.execute(
        query="Note 14(b)",
        retriever_mode=RetrieverMode.BM25,
        top_k=3,
    )
    assert len(chunks) > 0
    assert chunks[0].chunk_id == "chk_apple_footnote"
    assert trace.timings_ms["bm25_ms"] >= 0.0


def test_paraphrase_semantic_discovery(temp_dir: Path):
    pipeline, _ = build_test_environment(temp_dir)
    # Paraphrased query: "headwinds in global chip manufacturing"
    chunks, trace = pipeline.execute(
        query="headwinds in global chip manufacturing and economic slowdown",
        retriever_mode=RetrieverMode.DENSE,
        top_k=3,
    )
    assert len(chunks) > 0
    assert chunks[0].chunk_id == "chk_apple_macro"
    assert trace.timings_ms["dense_ms"] >= 0.0


def test_metadata_filtering(temp_dir: Path):
    pipeline, _ = build_test_environment(temp_dir)
    # Query for cloud revenue filtered to Apple only: MSFT cloud must be excluded
    chunks, trace = pipeline.execute(
        query="Cloud revenue",
        retriever_mode=RetrieverMode.HYBRID_RRF,
        top_k=5,
        filters=MetadataFilter(ticker="AAPL"),
    )
    assert all(c.document_id == "doc_apple_2023" for c in chunks)
    assert not any(c.chunk_id == "chk_msft_cloud" for c in chunks)


def test_all_retrieval_modes_runnable(temp_dir: Path):
    pipeline, _ = build_test_environment(temp_dir)
    query = "FY2023 revenue growth"

    # 1. BM25 Mode
    c_bm25, t_bm25 = pipeline.execute(query, retriever_mode=RetrieverMode.BM25, top_k=2)
    assert len(c_bm25) > 0
    assert "bm25_ms" in t_bm25.timings_ms

    # 2. Dense Mode
    c_dense, t_dense = pipeline.execute(query, retriever_mode=RetrieverMode.DENSE, top_k=2)
    assert len(c_dense) > 0
    assert "dense_ms" in t_dense.timings_ms

    # 3. Hybrid RRF Mode
    c_hybrid, t_hybrid = pipeline.execute(query, retriever_mode=RetrieverMode.HYBRID_RRF, top_k=2)
    assert len(c_hybrid) > 0
    assert "rrf_ms" in t_hybrid.timings_ms

    # 4. Reranked Mode
    c_rerank, t_rerank = pipeline.execute(query, retriever_mode=RetrieverMode.RERANKED, top_k=2)
    assert len(c_rerank) > 0
    assert "rerank_ms" in t_rerank.timings_ms
    assert len(t_rerank.final_evidence_chunk_ids) <= 2
