import asyncio
from pathlib import Path
import pytest
import httpx

from veridocs.sec.cache import SECCache
from veridocs.sec.client import (
    SECClient,
    SECNotFoundError,
    SECRateLimitError,
    SECServerError,
    SECSSRFViolationError,
)
from veridocs.sec.provenance import compute_sha256
from veridocs.sec.rate_limiter import SECRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter():
    limiter = SECRateLimiter(requests_per_second=10.0, max_burst=1)
    wait1 = await limiter.acquire()
    assert wait1 == 0.0  # First token is immediate
    wait2 = await limiter.acquire()
    assert wait2 > 0.0  # Second token must wait


def test_sec_cache_put_get(temp_dir: Path):
    cache = SECCache(temp_dir / "sec_cache")
    acc = "0000320193-23-000106"
    doc_name = "test.htm"
    content = b"<html><body>Sample SEC Filing Body</body></html>"
    source_url = "https://www.sec.gov/Archives/edgar/data/320193/test.htm"

    # Initially cache miss
    assert cache.get(acc, doc_name) is None

    # Store
    prov = cache.put(acc, doc_name, content, source_url, etag="etag-123")
    assert prov.raw_sha256 == compute_sha256(content)
    assert prov.byte_size == len(content)

    # Cache hit
    cached_bytes, cached_prov = cache.get(acc, doc_name)
    assert cached_bytes == content
    assert cached_prov.raw_sha256 == prov.raw_sha256

    # Test cache corruption detection
    cached_file = Path(cached_prov.cache_path)
    with open(cached_file, "wb") as f:
        f.write(b"corrupted content")
    assert cache.get(acc, doc_name) is None


@pytest.mark.asyncio
async def test_sec_client_ssrf_protection():
    client = SECClient()
    with pytest.raises(SECSSRFViolationError):
        await client._request_with_retry(
            httpx.AsyncClient(),
            "http://169.254.169.254/latest/meta-data/",
            {},
        )

    with pytest.raises(SECSSRFViolationError):
        await client._request_with_retry(
            httpx.AsyncClient(),
            "https://malicious-site.com/filing.htm",
            {},
        )


@pytest.mark.asyncio
async def test_sec_client_404_not_found(monkeypatch, temp_dir):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"File Not Found")

    transport = httpx.MockTransport(mock_handler)
    client = SECClient(cache=SECCache(temp_dir), max_retries=1)

    async with httpx.AsyncClient(transport=transport) as mock_http:
        with pytest.raises(SECNotFoundError):
            await client._request_with_retry(
                mock_http,
                "https://data.sec.gov/submissions/CIK0000999999.json",
                {},
            )


@pytest.mark.asyncio
async def test_sec_client_429_exhaustion(monkeypatch, temp_dir):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, content=b"Too Many Requests")

    transport = httpx.MockTransport(mock_handler)
    client = SECClient(cache=SECCache(temp_dir), max_retries=2)

    async with httpx.AsyncClient(transport=transport) as mock_http:
        with pytest.raises(SECRateLimitError):
            await client._request_with_retry(
                mock_http,
                "https://data.sec.gov/submissions/CIK0000320193.json",
                {},
            )
