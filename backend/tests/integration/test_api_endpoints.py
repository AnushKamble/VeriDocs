"""
Integration tests for FastAPI endpoints: filings discovery/ingestion, grounded query,
retrieval trace inspection, and benchmark metadata.
"""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from veridocs.api.dependencies import set_generator_provider
from veridocs.generation.provider import FakeTestProvider
from veridocs.main import app

client = TestClient(app)

SAMPLE_FILING_HTML = """<!DOCTYPE html>
<html>
<head><title>Apple Inc. Form 10-K</title></head>
<body>
<h1>PART I</h1>
<h2>Item 1. Business</h2>
<p>Apple Inc. designs, manufactures, and markets smartphones, personal computers, and tablets.</p>

<h1>PART II</h1>
<h2>Item 7. Management's Discussion and Analysis</h2>
<p>Total net sales decreased 3% during fiscal year 2023 driven by foreign exchange headwinds.</p>

<h2>Item 8. Financial Statements and Supplementary Data</h2>
<p>The following consolidated statements of operations are presented below:</p>
<table border="1">
  <caption>Consolidated Statements of Operations (in millions)</caption>
  <tr>
    <th>Three Years Ended</th>
    <th>September 30, 2023</th>
    <th>September 24, 2022</th>
  </tr>
  <tr>
    <td>Total net sales</td>
    <td>$383,285</td>
    <td>$394,328</td>
  </tr>
  <tr>
    <td>Cost of sales</td>
    <td>$214,137</td>
    <td>$223,546</td>
  </tr>
  <tr>
    <td>Gross margin</td>
    <td>$169,148</td>
    <td>$170,782</td>
  </tr>
</table>
</body>
</html>
"""


@pytest.fixture(autouse=True)
def setup_test_provider():
    # Use deterministic FakeTestProvider for API integration tests
    canned_json = {
        "summary": "Apple Inc. reported total net sales of $383,285 million in fiscal 2023.",
        "claims": [
            {
                "claim_id": "c1",
                "text": "Total net sales were $383,285 million in fiscal 2023.",
                "claim_kind": "numeric",
                "source_chunk_ids": [],  # Will be dynamically set or tested
                "numeric_facts": [
                    {
                        "metric": "Total net sales",
                        "raw_value": "$383,285 million",
                        "numeric_value": 383285,
                        "unit": "USD_MILLIONS",
                        "period": "FY2023",
                    }
                ],
            }
        ],
        "limitations": [],
    }
    provider = FakeTestProvider(canned_json=canned_json)
    set_generator_provider(provider)


def test_api_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_api_ingest_and_list_filings():
    # Ingest direct HTML
    payload = {
        "ticker": "AAPL",
        "cik": "0000320193",
        "form_type": "10-K",
        "accession_number": "0000320193-23-000106",
        "primary_document_name": "aapl-20230930.htm",
        "raw_html": SAMPLE_FILING_HTML,
        "fiscal_year": 2023,
    }
    res = client.post("/api/v1/filings/ingest", json=payload)
    assert res.status_code == 200
    manifest = res.json()
    doc_id = manifest["document_id"]
    assert doc_id == "doc_0000320193_000032019323000106"
    assert manifest["status"] == "PARSED"
    assert manifest["section_count"] >= 3
    assert manifest["table_count"] >= 1
    assert manifest["chunk_count"] >= 3


    # List filings
    res_list = client.get("/api/v1/filings?ticker=AAPL")
    assert res_list.status_code == 200
    filings = res_list.json()["filings"]
    assert len(filings) >= 1
    assert any(f["document_id"] == doc_id for f in filings)

    # Get filing details
    res_detail = client.get(f"/api/v1/filings/{doc_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["document"]["document_id"] == doc_id
    assert detail["section_count"] >= 3
    assert len(detail["tables"]) >= 1


def test_api_query_and_trace():
    # Execute query over ingested filing
    query_payload = {
        "query": "What were Apple's net sales in fiscal 2023?",
        "filters": {"ticker": "AAPL"},
        "retriever_mode": "bm25",
        "top_k": 3,
        "enable_nli": False,  # Keep test fast without full NLI model load
    }
    res = client.post("/api/v1/query", json=query_payload)
    assert res.status_code == 200
    resp_data = res.json()

    assert "query_id" in resp_data
    assert resp_data["query_id"].startswith("q_")
    assert len(resp_data["retrieved_evidence"]) > 0

    query_id = resp_data["query_id"]

    # Inspect trace
    res_trace = client.get(f"/api/v1/traces/{query_id}")
    assert res_trace.status_code == 200
    trace = res_trace.json()
    assert trace["query_id"] == query_id
    assert "total_query_execution_ms" in trace["timings_ms"]


def test_api_evaluation_benchmark_manifest():
    res = client.get("/api/v1/evaluation/benchmark")
    assert res.status_code == 200
    data = res.json()
    assert data["manifest"]["total_questions"] == 50
    assert len(data["splits"]["dev"]) == 15
    assert len(data["splits"]["test"]) == 35


def test_api_evaluation_questions_filter():
    res_dev = client.get("/api/v1/evaluation/benchmark/questions?split=dev")
    assert res_dev.status_code == 200
    dev_questions = res_dev.json()
    assert len(dev_questions) == 15

    res_test = client.get("/api/v1/evaluation/benchmark/questions?split=test")
    assert res_test.status_code == 200
    test_questions = res_test.json()
    assert len(test_questions) == 35
