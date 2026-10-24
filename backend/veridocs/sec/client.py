"""
Polite, rate-limited, and cached SEC EDGAR client.
"""

import asyncio
import random
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import httpx

from veridocs.config.settings import settings
from veridocs.sec.cache import SECCache
from veridocs.sec.discovery import (
    SEC_SUBMISSIONS_URL_TEMPLATE,
    build_primary_doc_url,
    normalize_cik,
    parse_company_submissions,
)
from veridocs.sec.provenance import FilingProvenance
from veridocs.sec.rate_limiter import SECRateLimiter
from veridocs.utils.logging import logger


class SECError(Exception):
    """Base exception for SEC operations."""
    pass


class SECNotFoundError(SECError):
    """Raised when an accession or submission document returns 404."""
    pass


class SECRateLimitError(SECError):
    """Raised when request is throttled with HTTP 429 after retries."""
    pass


class SECServerError(SECError):
    """Raised when SEC server returns 5xx."""
    pass


class SECTimeoutError(SECError):
    """Raised when network request times out."""
    pass


class SECSSRFViolationError(SECError):
    """Raised when a URL attempts to navigate outside approved SEC domains."""
    pass


class SECClient:
    """
    Polite SEC EDGAR HTTP client enforcing declared User-Agent, request rate-limits,
    idempotent caching, exponential backoff, and host restriction.
    """

    ALLOWED_HOSTS = {"data.sec.gov", "www.sec.gov", "sec.gov"}

    def __init__(
        self,
        rate_limiter: Optional[SECRateLimiter] = None,
        cache: Optional[SECCache] = None,
        user_agent: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 4,
        max_response_bytes: int = 50 * 1024 * 1024,  # 50 MB
    ):
        self.user_agent = user_agent or settings.sec_user_agent
        self.rate_limiter = rate_limiter or SECRateLimiter(settings.sec_request_rate_limit)
        self.cache = cache or SECCache(settings.cache_dir)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_response_bytes = max_response_bytes

    def _validate_sec_url(self, url: str) -> None:
        """Enforces that outbound requests only target approved SEC domains."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise SECSSRFViolationError(f"Disallowed URL scheme: {parsed.scheme}")
        hostname = (parsed.hostname or "").lower()
        if hostname not in self.ALLOWED_HOSTS and not any(hostname.endswith("." + h) for h in self.ALLOWED_HOSTS):
            raise SECSSRFViolationError(f"Host '{hostname}' is not an authorized SEC EDGAR domain")

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: Dict[str, str],
    ) -> httpx.Response:
        self._validate_sec_url(url)
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            await self.rate_limiter.acquire()
            try:
                logger.info(f"SEC Request (attempt {attempt}/{self.max_retries}): {url}")
                resp = await client.get(url, headers=headers, timeout=self.timeout_seconds)

                if resp.status_code == 200 or resp.status_code == 304:
                    return resp
                elif resp.status_code == 404:
                    raise SECNotFoundError(f"SEC resource not found (404): {url}")
                elif resp.status_code == 429:
                    logger.warning(f"SEC 429 Rate Limit encountered on attempt {attempt}")
                    if attempt == self.max_retries:
                        raise SECRateLimitError(f"SEC rate limit (429) persisted after {self.max_retries} attempts: {url}")
                elif resp.status_code >= 500:
                    logger.warning(f"SEC 5xx Server Error ({resp.status_code}) on attempt {attempt}")
                    if attempt == self.max_retries:
                        raise SECServerError(f"SEC server error ({resp.status_code}) on {url}")
                else:
                    raise SECError(f"Unexpected SEC response {resp.status_code} for {url}")

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                logger.warning(f"SEC Network/Timeout error on attempt {attempt}: {exc}")
                if attempt == self.max_retries:
                    raise SECTimeoutError(f"SEC request timed out after {self.max_retries} attempts: {url}") from exc

            # Bounded exponential backoff with jitter
            base_backoff = 0.5 * (2 ** (attempt - 1))
            jitter = random.uniform(0.1, 0.4)
            sleep_sec = min(8.0, base_backoff + jitter)
            logger.info(f"Backing off for {sleep_sec:.2f}s before retry...")
            await asyncio.sleep(sleep_sec)

        raise SECError(f"Failed to fetch {url}: {last_error}")

    async def fetch_submissions(self, cik_or_ticker: str) -> Dict[str, Any]:
        """
        Fetches official company submissions JSON from data.sec.gov.
        """
        cik = normalize_cik(cik_or_ticker)
        url = SEC_SUBMISSIONS_URL_TEMPLATE.format(cik=cik)
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }

        async with httpx.AsyncClient() as client:
            resp = await self._request_with_retry(client, url, headers)
            return resp.json()

    async def discover_filings(
        self,
        cik_or_ticker: str,
        forms: Optional[List[str]] = None,
        max_count: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Discovers 10-K and 10-Q filings for a company.
        """
        data = await self.fetch_submissions(cik_or_ticker)
        return parse_company_submissions(data, forms=forms, max_count=max_count)

    async def fetch_filing_document(
        self,
        cik: str,
        accession_number: str,
        primary_doc: str,
        source_url: Optional[str] = None,
    ) -> Tuple[bytes, FilingProvenance]:
        """
        Fetches the raw filing document HTML bytes, utilizing the local cache when available.
        """
        norm_cik = normalize_cik(cik)
        url = source_url or build_primary_doc_url(norm_cik, accession_number, primary_doc)

        # Check local cache first
        cached = self.cache.get(accession_number, primary_doc)
        if cached is not None:
            logger.info(f"SEC Cache HIT: {accession_number} / {primary_doc}")
            return cached

        logger.info(f"SEC Cache MISS: Fetching {url}")
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

        async with httpx.AsyncClient() as client:
            resp = await self._request_with_retry(client, url, headers)
            content = resp.content

            if len(content) > self.max_response_bytes:
                raise SECError(f"Response size {len(content)} exceeds maximum limit {self.max_response_bytes} bytes")

            etag = resp.headers.get("ETag")
            provenance = self.cache.put(
                accession_number=accession_number,
                primary_doc=primary_doc,
                content=content,
                source_url=url,
                etag=etag,
                http_status=resp.status_code,
            )
            return content, provenance
