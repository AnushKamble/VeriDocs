"""
Health and model status endpoints for VeriDocs.
"""

from typing import Any, Dict
from fastapi import APIRouter
import httpx

from veridocs.config.settings import settings
from veridocs.utils.logging import logger

router = APIRouter(prefix="/api/v1", tags=["Health & Status"])


@router.get("/health")
async def get_health() -> Dict[str, Any]:
    """Basic service health check."""
    return {
        "status": "healthy",
        "service": "veridocs",
        "version": "1.0.0",
    }


@router.get("/models/status")
async def get_models_status() -> Dict[str, Any]:
    """Check availability and active versions of all local models."""
    ollama_ok = False
    ollama_models = []
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                ollama_ok = True
                data = resp.json()
                ollama_models = [m.get("name") for m in data.get("models", [])]
    except Exception as exc:
        logger.warning(f"Ollama health check failed: {exc}")

    # Check FAISS
    faiss_ok = False
    try:
        import faiss
        faiss_ok = True
    except ImportError:
        faiss_ok = False

    return {
        "generator": {
            "provider": "ollama",
            "base_url": settings.ollama_base_url,
            "configured_model": settings.generator_model,
            "available": ollama_ok,
            "installed_models": ollama_models,
        },
        "retrieval": {
            "embedding_model_id": settings.embedding_model_id,
            "embedding_dimension": 384,
            "reranker_model_id": settings.reranker_model_id,
            "faiss_installed": faiss_ok,
            "rrf_k0": settings.rrf_k0,
        },
        "auditor": {
            "nli_model_id": settings.nli_model_id,
            "numeric_audit_engine": "deterministic_decimal",
        },
    }
