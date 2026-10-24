import pytest
from pydantic import ValidationError

from veridocs.config.settings import Settings


def test_default_settings():
    s = Settings()
    assert s.sec_request_rate_limit <= 8.0
    assert "@" in s.sec_user_agent
    assert s.port == 8000
    assert s.embedding_model_id == "BAAI/bge-small-en-v1.5"


def test_invalid_rate_limit():
    with pytest.raises(ValidationError):
        Settings(sec_request_rate_limit=15.0)  # Exceeds safe boundary <= 8.0

    with pytest.raises(ValidationError):
        Settings(sec_request_rate_limit=0.0)


def test_invalid_user_agent():
    with pytest.raises(ValidationError):
        Settings(sec_user_agent="NoEmailBot")


def test_ensure_directories(temp_dir):
    s = Settings(
        data_dir=temp_dir / "data",
        cache_dir=temp_dir / "cache",
        artifacts_dir=temp_dir / "artifacts",
    )
    s.ensure_directories()
    assert s.data_dir.exists()
    assert s.cache_dir.exists()
    assert s.artifacts_dir.exists()
