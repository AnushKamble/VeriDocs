"""
Provenance tracking and SHA-256 validation for SEC EDGAR filings.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


def compute_sha256(data: bytes) -> str:
    """Computes hexadecimal SHA-256 digest of raw byte content."""
    return hashlib.sha256(data).hexdigest()


class FilingProvenance(BaseModel):
    accession_number: str
    source_url: str
    raw_sha256: str
    byte_size: int
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    etag: Optional[str] = None
    http_status: int = 200
    cache_path: Optional[str] = None

    def save_manifest(self, directory: Path) -> Path:
        """Persists the provenance manifest to the target directory."""
        directory.mkdir(parents=True, exist_ok=True)
        manifest_file = directory / "provenance.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2)
        return manifest_file

    @classmethod
    def load_manifest(cls, directory: Path) -> Optional["FilingProvenance"]:
        """Loads existing provenance manifest if present."""
        manifest_file = directory / "provenance.json"
        if not manifest_file.exists():
            return None
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)
