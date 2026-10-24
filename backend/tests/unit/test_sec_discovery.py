import pytest
from veridocs.sec.discovery import (
    build_primary_doc_url,
    normalize_cik,
    parse_company_submissions,
)


def test_normalize_cik():
    # Ticker resolution
    assert normalize_cik("AAPL") == "0000320193"
    assert normalize_cik("msft") == "0000789019"

    # Numeric strings
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik("0000320193") == "0000320193"
    assert normalize_cik("CIK0000320193") == "0000320193"

    with pytest.raises(ValueError):
        normalize_cik("INVALID_NO_DIGITS_TICKER")


def test_build_primary_doc_url():
    url = build_primary_doc_url(
        cik="0000320193",
        accession_number="0000320193-23-000106",
        primary_doc="aapl-20230930.htm",
    )
    # The SEC archive path uses integer CIK 320193 without leading zeros
    assert url == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm"


def test_parse_company_submissions():
    sample_submissions = {
        "cik": "320193",
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0000320193-23-000106",
                    "0000320193-23-000077",
                    "0000320193-23-000064",
                    "0000320193-23-000005",
                ],
                "filingDate": ["2023-11-03", "2023-08-04", "2023-05-05", "2023-01-15"],
                "reportDate": ["2023-09-30", "2023-07-01", "2023-04-01", "2023-01-15"],
                "form": ["10-K", "10-Q", "10-Q", "8-K"],
                "primaryDocument": [
                    "aapl-20230930.htm",
                    "aapl-20230701.htm",
                    "aapl-20230401.htm",
                    "aapl-20230115.htm",
                ],
                "primaryDocDescription": ["10-K", "10-Q", "10-Q", "8-K"],
            }
        },
    }

    filings = parse_company_submissions(sample_submissions, forms=["10-K", "10-Q"], max_count=5)
    # Should ignore 8-K
    assert len(filings) == 3
    assert filings[0]["form_type"] == "10-K"
    assert filings[0]["accession_number"] == "0000320193-23-000106"
    assert filings[0]["primary_document_name"] == "aapl-20230930.htm"
    assert filings[0]["source_url"].startswith("https://www.sec.gov/Archives/edgar/data/320193/")
