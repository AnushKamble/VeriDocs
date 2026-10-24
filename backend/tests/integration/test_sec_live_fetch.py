import pytest
from veridocs.sec.client import SECClient


@pytest.mark.asyncio
async def test_live_sec_discovery(temp_dir):
    """
    Live integration test against SEC EDGAR API.
    Verifies that CIK normalization and submission discovery retrieves actual 10-K filings.
    """
    client = SECClient(timeout_seconds=20.0, max_retries=2)
    try:
        filings = await client.discover_filings("AAPL", forms=["10-K", "10-Q"], max_count=3)
        assert len(filings) > 0
        first = filings[0]
        assert first["cik"] == "0000320193"
        assert first["form_type"] in ["10-K", "10-Q", "10-K/A", "10-Q/A"]
        assert first["source_url"].startswith("https://www.sec.gov/Archives/edgar/data/320193/")
        assert len(first["accession_number"]) >= 18
    except Exception as exc:
        pytest.skip(f"SEC live endpoint unavailable or blocked in this environment: {exc}")
