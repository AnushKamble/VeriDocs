"""
SEC EDGAR discovery module: CIK normalization, submission parsing, and URL construction.
"""

import re
from typing import Any, Dict, List, Optional

# Standard SEC EDGAR URL constants
SEC_SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVE_URL_TEMPLATE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary_doc}"

# Curated reference tickers for instant zero-network lookup
CURATED_TICKERS: Dict[str, Dict[str, str]] = {
    "AAPL": {"cik": "0000320193", "name": "Apple Inc."},
    "MSFT": {"cik": "0000789019", "name": "Microsoft Corp"},
    "GOOGL": {"cik": "0001652044", "name": "Alphabet Inc."},
    "AMZN": {"cik": "0001018724", "name": "Amazon.com Inc."},
    "NVDA": {"cik": "0001045810", "name": "NVIDIA Corp"},
}


def normalize_cik(cik_or_ticker: str) -> str:
    """
    Normalizes a CIK or ticker string to a 10-digit zero-padded CIK string.
    If a known ticker is passed, resolves to its official CIK.
    """
    clean = cik_or_ticker.strip().upper()
    if clean in CURATED_TICKERS:
        return CURATED_TICKERS[clean]["cik"]

    # Extract digits only
    digits = re.sub(r"\D", "", clean)
    if not digits:
        raise ValueError(f"Invalid CIK string: '{cik_or_ticker}' contains no digits and is not a known ticker")
    if len(digits) > 10:
        raise ValueError(f"CIK '{digits}' exceeds 10 digits")
    return digits.zfill(10)


def build_primary_doc_url(cik: str, accession_number: str, primary_doc: str) -> str:
    """
    Constructs the canonical SEC EDGAR URL for a primary filing document.
    SEC EDGAR archive paths use integer CIK without leading zeros in the path.
    """
    normalized_cik = normalize_cik(cik)
    cik_int = int(normalized_cik)
    accession_nodash = accession_number.replace("-", "").strip()
    return SEC_ARCHIVE_URL_TEMPLATE.format(
        cik_int=cik_int,
        accession_nodash=accession_nodash,
        primary_doc=primary_doc.strip(),
    )


def parse_company_submissions(
    submissions_json: Dict[str, Any],
    forms: Optional[List[str]] = None,
    max_count: int = 10,
) -> List[Dict[str, Any]]:
    """
    Parses an SEC submissions JSON payload (from data.sec.gov/submissions/CIK{cik}.json)
    extracting 10-K and 10-Q filings with verified accession numbers and URLs.
    """
    cik = str(submissions_json.get("cik", "")).zfill(10)
    company_name = submissions_json.get("name", "")
    tickers = submissions_json.get("tickers", [])
    ticker = tickers[0] if tickers else None

    allowed_forms = set(forms) if forms else {"10-K", "10-Q", "10-K/A", "10-Q/A"}

    recent = submissions_json.get("filings", {}).get("recent", {})
    if not recent:
        return []

    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    form_types = recent.get("form", [])
    primary_documents = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    results = []
    total = len(accession_numbers)

    for i in range(total):
        form = form_types[i] if i < len(form_types) else ""
        if form not in allowed_forms:
            continue

        acc_num = accession_numbers[i]
        prim_doc = primary_documents[i] if i < len(primary_documents) else ""
        f_date = filing_dates[i] if i < len(filing_dates) else ""
        r_date = report_dates[i] if i < len(report_dates) else f_date
        desc = descriptions[i] if i < len(descriptions) else ""

        if not prim_doc:
            continue

        source_url = build_primary_doc_url(cik, acc_num, prim_doc)

        results.append({
            "cik": cik,
            "company_name": company_name,
            "ticker": ticker,
            "form_type": form,
            "accession_number": acc_num,
            "filing_date": f_date,
            "report_period": r_date,
            "primary_document_name": prim_doc,
            "description": desc,
            "source_url": source_url,
        })

        if len(results) >= max_count:
            break

    return results
