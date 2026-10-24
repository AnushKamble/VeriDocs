"""
Idempotent local filesystem cache for SEC filings with SHA-256 verification.
"""

from pathlib import Path
from typing import Optional, Tuple
from veridocs.sec.provenance import FilingProvenance, compute_sha256
from veridocs.utils.logging import logger


class SECCache:
    """
    Manages local cached raw filings indexed by accession number and primary document name.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_filing_dir(self, accession_number: str) -> Path:
        clean_acc = accession_number.replace("-", "").strip()
        return self.cache_dir / clean_acc

    def get(self, accession_number: str, primary_doc: str) -> Optional[Tuple[bytes, FilingProvenance]]:
        """
        Retrieves cached filing bytes and validated provenance if available and intact.
        Returns None on cache miss or checksum mismatch.
        """
        filing_dir = self._get_filing_dir(accession_number)
        doc_path = filing_dir / primary_doc
        manifest = FilingProvenance.load_manifest(filing_dir)

        if not doc_path.exists() or manifest is None:
            return None

        try:
            with open(doc_path, "rb") as f:
                content = f.read()
        except OSError as exc:
            logger.warning(f"Error reading cached filing {doc_path}: {exc}")
            return None

        # Verify raw bytes integrity against manifest
        current_hash = compute_sha256(content)
        if current_hash != manifest.raw_sha256:
            logger.warning(f"Cache corruption detected for {accession_number}: hash mismatch")
            return None

        return content, manifest

    def put(
        self,
        accession_number: str,
        primary_doc: str,
        content: bytes,
        source_url: str,
        etag: Optional[str] = None,
        http_status: int = 200,
    ) -> FilingProvenance:
        """
        Stores filing bytes and provenance manifest idempotently.
        """
        filing_dir = self._get_filing_dir(accession_number)
        filing_dir.mkdir(parents=True, exist_ok=True)

        doc_path = filing_dir / primary_doc
        with open(doc_path, "wb") as f:
            f.write(content)

        raw_sha256 = compute_sha256(content)
        manifest = FilingProvenance(
            accession_number=accession_number,
            source_url=source_url,
            raw_sha256=raw_sha256,
            byte_size=len(content),
            etag=etag,
            http_status=http_status,
            cache_path=str(doc_path),
        )
        manifest.save_manifest(filing_dir)
        return manifest
