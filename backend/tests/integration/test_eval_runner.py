"""
Integration tests for BenchmarkRunner running over benchmark cases.
"""

from decimal import Decimal
import shutil
import tempfile
import pytest

from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.evaluation.runner import BaselineType, BenchmarkRunner
from veridocs.generation.provider import FakeTestProvider
from veridocs.generation.structured_answerer import StructuredAnswerer
from veridocs.indexing.bm25_index import BM25Index
from veridocs.retrieval.bm25_retriever import BM25Retriever
from veridocs.retrieval.pipeline import RetrievalPipeline
from veridocs.schemas.benchmark_models import (
    BenchmarkCase,
    BenchmarkGoldEvidence,
    QuestionCategory,
)
from veridocs.schemas.data_models import (
    ChunkKind,
    ChunkRecord,
    DocumentStatus,
    FilingDocument,
)


@pytest.fixture
def mock_runner_environment():
    tmpdir = tempfile.mkdtemp()
    try:
        catalog = SQLiteCatalog(f"{tmpdir}/eval_catalog.db")

        # Create two sample chunks
        c1 = ChunkRecord(
            chunk_id="chk_aapl_sales_001",
            document_id="doc_aapl_10k_2023",
            chunk_kind=ChunkKind.TABLE_GROUP,
            ordinal=1,
            section_id="Item 8",
            section_title="Financial Statements",
            text="Total net sales for fiscal 2023 were $383,285 million.",
            raw_text="Total net sales $383,285",
            token_count=10,
            table_id="table_004",
            source_url="https://www.sec.gov/ix?doc=/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
            source_locator="table_004_consolidated_statements_of_operations",
            content_hash="hash_001",
        )
        c2 = ChunkRecord(
            chunk_id="chk_aapl_iphone_002",
            document_id="doc_aapl_10k_2023",
            chunk_kind=ChunkKind.TABLE_GROUP,
            ordinal=2,
            section_id="Item 8",
            section_title="Financial Statements",
            text="iPhone net sales were $200,583 million in fiscal 2023.",
            raw_text="iPhone $200,583",
            token_count=10,
            table_id="table_004",
            source_url="https://www.sec.gov/ix?doc=/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
            source_locator="table_004_consolidated_statements_of_operations",
            content_hash="hash_002",
        )
        doc = FilingDocument(
            document_id="doc_aapl_10k_2023",
            cik="0000320193",
            ticker="AAPL",
            company_name="Apple Inc.",
            form_type="10-K",
            accession_number="0000320193-23-000106",
            filing_date="2023-11-03",
            report_period="2023-09-30",
            fiscal_year=2023,
            fiscal_quarter=4,
            primary_document_name="aapl-20230930.htm",
            source_url="https://www.sec.gov/ix?doc=/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
            raw_sha256="sha_apple_raw_sample",
            byte_size=1024,
            fetched_at="2026-10-24T12:00:00Z",
            status=DocumentStatus.INDEXED,
        )

        catalog.save_document(doc, [], [], [c1, c2])

        bm25_index = BM25Index.build([c1, c2])

        bm25_retriever = BM25Retriever(bm25_index, catalog)
        pipeline = RetrievalPipeline(
            bm25_retriever=bm25_retriever,
            dense_retriever=None,
            reranker=None,
            catalog=catalog,
        )

        fake_provider = FakeTestProvider(
            canned_response=(
                '{"summary": "Apple total net sales for fiscal 2023 were $383,285 million [chk_aapl_sales_001].", '
                '"claims": [{"claim_id": "c1", "text": "Total net sales were $383,285 million.", '
                '"source_chunk_ids": ["chk_aapl_sales_001"], '
                '"numeric_facts": [{"metric": "net sales", "raw_value": "$383,285", "numeric_value": 383285, "unit": "USD_MILLIONS", "period": "FY2023"}]}]}'
            )
        )
        answerer = StructuredAnswerer(fake_provider)

        runner = BenchmarkRunner(
            retrieval_pipeline=pipeline,
            answerer=answerer,
            questions_path="benchmarks/questions.jsonl",
            splits_path="benchmarks/splits.json",
        )

        yield runner, c1, c2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_runner_load_cases():
    runner = BenchmarkRunner(
        retrieval_pipeline=None,  # type: ignore
        questions_path="benchmarks/questions.jsonl",
        splits_path="benchmarks/splits.json",
    )
    dev_cases = runner.load_cases(split="dev")
    assert len(dev_cases) == 15

    test_cases = runner.load_cases(split="test")
    assert len(test_cases) == 35

    all_cases = runner.load_cases(split="all")
    assert len(all_cases) == 50


def test_runner_evaluate_single_question(mock_runner_environment):
    runner, c1, _ = mock_runner_environment

    case = BenchmarkCase(
        question_id="q_test_01",
        question_text="What were Apple total net sales in fiscal year 2023?",
        category=QuestionCategory.NUMERIC_TABLE_LOOKUP,
        company_name="Apple Inc.",
        ticker="AAPL",
        form_type="10-K",
        fiscal_period="FY2023",
        is_answerable=True,
        reference_answer="$383,285 million",
        expected_numeric_value=Decimal("383285"),
        expected_unit="USD_MILLIONS",
        expected_period="FY2023",
        gold_evidence=[
            BenchmarkGoldEvidence(
                document_id="doc_aapl_10k_2023",
                section_id="Item 8",
                source_locator="table_004_consolidated_statements_of_operations",
                verbatim_text="Total net sales for fiscal 2023 were $383,285 million.",
            )
        ],
        annotation_rationale="Consolidated statements of operations",
        split="dev",
    )

    # 1. Evaluate BM25
    res_bm25 = runner.evaluate_question(case, baseline=BaselineType.BM25_STRUCTURED)
    assert res_bm25.question_id == "q_test_01"
    assert res_bm25.first_hit_rank == 1
    assert res_bm25.recall_at_1 == 0.5
    assert res_bm25.recall_at_5 == 1.0
    assert res_bm25.ndcg_at_5 == 1.0

    # 2. Evaluate Full System
    res_full = runner.evaluate_question(case, baseline=BaselineType.FULL_SYSTEM)
    assert res_full.numeric_exactness is True
    assert res_full.citation_precision == 1.0
    assert res_full.is_abstention is False
    assert res_full.abstention_correct is True


def test_runner_evaluate_unanswerable_question(mock_runner_environment):
    runner, _, _ = mock_runner_environment

    unanswerable_case = BenchmarkCase(
        question_id="q_test_unans",
        question_text="What was Apple space tourism revenue in 2023?",
        category=QuestionCategory.UNANSWERABLE,
        company_name="Apple Inc.",
        ticker="AAPL",
        form_type="10-K",
        fiscal_period="FY2023",
        is_answerable=False,
        reference_answer="Apple has no space tourism revenue.",
        gold_evidence=[],
        annotation_rationale="Unanswerable",
        split="dev",
    )

    fake_unans_provider = FakeTestProvider(
        canned_response=(
            '{"summary": "The engine abstains: the provided documents do not contain evidence regarding space tourism revenue.", '
            '"claims": []}'
        )
    )
    runner.answerer = StructuredAnswerer(fake_unans_provider)

    res = runner.evaluate_question(unanswerable_case, baseline=BaselineType.FULL_SYSTEM)
    assert res.is_abstention is True
    assert res.abstention_correct is True
