"""VeriDocs SEC EDGAR Client Package."""

from veridocs.sec.client import (
    SECClient,
    SECError,
    SECNotFoundError,
    SECRateLimitError,
    SECServerError,
    SECTimeoutError,
    SECSSRFViolationError,
)
from veridocs.sec.cache import SECCache
from veridocs.sec.discovery import (
    CURATED_TICKERS,
    build_primary_doc_url,
    normalize_cik,
    parse_company_submissions,
)
from veridocs.sec.provenance import FilingProvenance, compute_sha256
from veridocs.sec.rate_limiter import SECRateLimiter

__all__ = [
    "SECClient",
    "SECCache",
    "SECRateLimiter",
    "FilingProvenance",
    "compute_sha256",
    "normalize_cik",
    "build_primary_doc_url",
    "parse_company_submissions",
    "CURATED_TICKERS",
    "SECError",
    "SECNotFoundError",
    "SECRateLimitError",
    "SECServerError",
    "SECTimeoutError",
    "SECSSRFViolationError",
]
