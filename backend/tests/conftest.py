"""
Pytest fixtures for VeriDocs testing.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from veridocs.config.settings import Settings, settings
from veridocs.main import app


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provides an isolated temporary directory for test catalogs and indexes."""
    temp_path = Path(tempfile.mkdtemp(prefix="veridocs_test_"))
    yield temp_path
    if temp_path.exists():
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """TestClient instance for FastAPI application."""
    with TestClient(app) as client:
        yield client
