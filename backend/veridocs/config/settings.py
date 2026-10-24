"""
Application settings and environment validation for VeriDocs.
"""

from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SEC EDGAR Settings
    sec_user_agent: str = Field(
        default="VeriDocsResearchBot/1.0 (researcher@example.com)",
        description="Declared SEC User-Agent header with product name and email address",
    )
    sec_request_rate_limit: float = Field(
        default=2.0,
        description="Max SEC requests per second (must be well below SEC fair-access cap of 10.0)",
    )
    sec_timeout_seconds: float = Field(default=30.0, description="HTTP request timeout")
    sec_max_retries: int = Field(default=4, description="Max retry attempts with backoff")

    # Storage Paths
    data_dir: Path = Field(default=Path("data"))
    cache_dir: Path = Field(default=Path("data/cache"))
    db_path: Path = Field(default=Path("data/veridocs.db"))
    artifacts_dir: Path = Field(default=Path("artifacts"))

    # Local LLM Generator (Ollama)
    ollama_base_url: str = Field(default="http://localhost:11434")
    generator_model: str = Field(default="qwen3:8b")
    generator_timeout_seconds: float = Field(default=60.0)

    # Embeddings, Reranker & NLI Models
    embedding_model_id: str = Field(default="BAAI/bge-small-en-v1.5")
    reranker_model_id: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    nli_model_id: str = Field(default="cross-encoder/nli-deberta-v3-small")
    rrf_k0: int = Field(default=60, description="Reciprocal Rank Fusion smoothing parameter")

    # API Server
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    @field_validator("sec_request_rate_limit")
    @classmethod
    def validate_rate_limit(cls, v: float) -> float:
        if v <= 0.0 or v > 8.0:
            raise ValueError("sec_request_rate_limit must be between 0.1 and 8.0 req/sec")
        return v

    @field_validator("sec_user_agent")
    @classmethod
    def validate_user_agent(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped or "@" not in v_stripped:
            raise ValueError("sec_user_agent must contain a descriptive name and a contact email")
        return v_stripped

    def ensure_directories(self) -> None:
        """Create necessary data, cache, and artifact directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)


# Global settings singleton
settings = Settings()
