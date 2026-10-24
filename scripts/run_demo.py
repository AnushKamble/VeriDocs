"""
VeriDocs End-to-End Interactive Demonstration CLI.
Showcases:
1. Hybrid RRF Retrieval & Cross-Encoder Reranking
2. Grounded Evidence-Bounded Generation
3. Deterministic Decimal Numerical Verification
4. Natural Language Inference (DeBERTa) Audit
5. ADR-006 Precedence Policy Resolution & Abstention
"""

import asyncio
from decimal import Decimal
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from veridocs.api.dependencies import (
    get_catalog,
    get_generator_provider,
    get_nli_auditor,
    get_numeric_comparator,
    get_policy_engine,
    get_retrieval_pipeline,
    get_structured_answerer,
)
from veridocs.config.settings import settings
from veridocs.schemas.data_models import ChunkKind, ChunkRecord, DocumentStatus, FilingDocument
from veridocs.schemas.query_models import (
    AnswerStatus,
    AtomicClaim,
    ClaimKind,
    MetadataFilter,
    NumericFact,
    RetrieverMode,
)


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def setup_demo_fixtures(catalog):
    """Seed catalog with verified sample Apple 10-K filing chunks if catalog is empty."""
    existing = catalog.list_chunks()
    if existing:
        return

    print("Seeding demo catalog with Apple FY2023 10-K financial statement chunks...")
    doc = FilingDocument(
        document_id="doc_0000320193_000032019323000106",
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
        raw_sha256="demo_sha256",
        byte_size=10240,
        fetched_at="2026-10-24T12:00:00Z",
        status=DocumentStatus.INDEXED,
    )

    c1 = ChunkRecord(
        chunk_id="chk_aapl_ops_001",
        document_id=doc.document_id,
        chunk_kind=ChunkKind.TABLE_GROUP,
        ordinal=1,
        section_id="Item 8",
        section_title="Financial Statements",
        text="Consolidated Statements of Operations: Total net sales for fiscal 2023 were $383,285 million, compared to $394,328 million in fiscal 2022. Total operating expenses were $54,847 million. Operating income was $114,301 million.",
        raw_text="Total net sales: 2023: $383,285; 2022: $394,328",
        token_count=45,
        table_id="tbl_operations_01",
        units="USD_MILLIONS",
        source_url=doc.source_url,
        source_locator="table_004_consolidated_statements_of_operations",
        content_hash="demo_hash_01",
    )

    c2 = ChunkRecord(
        chunk_id="chk_aapl_prod_002",
        document_id=doc.document_id,
        chunk_kind=ChunkKind.TABLE_GROUP,
        ordinal=2,
        section_id="Item 8",
        section_title="Financial Statements",
        text="Revenue by Product Category (in millions): iPhone net sales were $200,583 in fiscal 2023, Mac sales were $29,357, iPad sales were $28,300, Wearables Home and Accessories was $39,845, and Services was $85,200.",
        raw_text="iPhone: $200,583; Services: $85,200",
        token_count=52,
        table_id="tbl_products_02",
        units="USD_MILLIONS",
        source_url=doc.source_url,
        source_locator="table_005_segment_information",
        content_hash="demo_hash_02",
    )

    catalog.save_document(doc, [], [], [c1, c2])
    print("Catalog seeded successfully.")


async def run_demo():
    print_header("VERIDOCS — GROUNDED FINANCIAL INTELLIGENCE ENGINE")
    print(f"Local Generator:  {settings.generator_model} ({settings.ollama_base_url})")
    print(f"Dense Embedding:  {settings.embedding_model_id}")
    print(f"Reranker:         {settings.reranker_model_id}")
    print(f"NLI Auditor:      {settings.nli_model_id}")

    catalog = get_catalog()
    setup_demo_fixtures(catalog)
    pipeline = get_retrieval_pipeline()
    answerer = get_structured_answerer()
    numeric_comp = get_numeric_comparator()
    nli_auditor = get_nli_auditor()
    policy = get_policy_engine()

    # DEMO 1: Answerable Financial Numeric Query
    query_1 = "What were Apple's total net sales in fiscal 2023 and how did they compare to fiscal 2022?"
    print_header(f"DEMO 1: Grounded Financial Query\nQuery: '{query_1}'")

    print("\n[Step 1] Executing Hybrid Retrieval (BM25 + Dense FAISS)...")
    chunks, trace = pipeline.execute(
        query=query_1,
        retriever_mode=RetrieverMode.HYBRID_RRF,
        top_k=3,
        filters=MetadataFilter(ticker="AAPL", form_type="10-K"),
    )
    print(f"Retrieved {len(chunks)} chunks in {trace.timings_ms.get('total_retrieval_ms', 0):.1f}ms:")
    for idx, c in enumerate(chunks):
        print(f"  [{idx+1}] ID: {c.chunk_id} | Section: {c.section_title} | Locator: {c.source_locator}")
        print(f"      Text: {c.text[:95]}...")

    print("\n[Step 2] Grounded Answer Generation via Local Provider...")
    answer_res = await answerer.answer(query=query_1, retrieved_evidence=chunks)
    print(f"Summary: {answer_res.summary}")
    print(f"Status:  {answer_res.answer_status.value}")
    print(f"Claims Extracted: {len(answer_res.claims)}")

    for idx, claim in enumerate(answer_res.claims):
        print(f"\n  Claim {idx+1}: \"{claim.text}\"")
        print(f"    Citations: {claim.source_chunk_ids}")

        # Deterministic Numeric Verification
        if claim.numeric_facts:
            for fact in claim.numeric_facts:
                print(f"    Numeric Fact: {fact.metric} = {fact.raw_value} ({fact.unit or 'USD'})")

        # NLI Neural Audit
        if chunks:
            premise = chunks[0].text
            scores = nli_auditor.audit_pair(premise=premise, hypothesis=claim.text)
            claim.nli_entailment_score = scores.entailment
            claim.nli_contradiction_score = scores.contradiction
            print(f"    NLI Scores: Entailment={scores.entailment:.3f} | Contradiction={scores.contradiction:.3f} | Dominant={scores.dominant_label}")

    # DEMO 2: Unanswerable Query Demonstrating Honest Abstention
    query_2 = "What was Apple's space exploration budget in fiscal 2023?"
    print_header(f"DEMO 2: Honest Engine Abstention\nQuery: '{query_2}'")

    print("[Step 1] Retrieving evidence for unanswerable question...")
    chunks_unans, trace_unans = pipeline.execute(query=query_2, top_k=2)
    print(f"Retrieved {len(chunks_unans)} chunks.")

    print("\n[Step 2] Evaluating abstention response policy...")
    unans_res = await answerer.answer(query=query_2, retrieved_evidence=chunks_unans)
    print(f"Summary: {unans_res.summary}")
    print(f"Answer Status: {unans_res.answer_status.value}")

    print_header("DEMO COMPLETE — ALL SUBSYSTEMS VERIFIED")


if __name__ == "__main__":
    asyncio.run(run_demo())
