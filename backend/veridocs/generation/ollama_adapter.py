"""
Local Ollama generation provider implementation.
Connects to local Ollama server, supports structured JSON schemas, timeouts, and latency tracking.
"""

import json
import time
from typing import Any, Dict, Optional, Type
import httpx
from pydantic import BaseModel

from veridocs.generation.provider import GenerationResult, GeneratorProvider
from veridocs.utils.logging import get_logger

logger = get_logger("veridocs.generation.ollama")


class OllamaProviderError(Exception):
    """Base exception for Ollama provider errors."""
    pass


class OllamaConnectionError(OllamaProviderError):
    """Raised when Ollama cannot be reached."""
    pass


class OllamaTimeoutError(OllamaProviderError):
    """Raised when Ollama request times out."""
    pass


class OllamaGenerationProvider(GeneratorProvider):
    """Production provider integrating with locally hosted Ollama."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "qwen3:8b",
        timeout_seconds: float = 90.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    async def is_healthy(self) -> bool:
        """Check if Ollama service is reachable and responsive."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs,
    ) -> GenerationResult:
        """
        Execute generation against Ollama /api/generate endpoint.
        """
        start_time = time.perf_counter()
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        if schema is not None:
            # Newer Ollama versions support full JSON schema; fallback to 'json' string
            try:
                payload["format"] = schema.model_json_schema()
            except Exception:
                payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Ollama generation timed out after {self.timeout_seconds}s: {e}") from e
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Failed to connect to Ollama at {self.base_url}: {e}") from e
        except Exception as e:
            raise OllamaProviderError(f"Unexpected error communicating with Ollama: {e}") from e

        if resp.status_code != 200:
            raise OllamaProviderError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        raw_text = data.get("response", "").strip()
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        parsed_json = None
        if schema is not None or "json" in prompt.lower() or payload.get("format") is not None:
            try:
                parsed_json = json.loads(raw_text)
            except json.JSONDecodeError:
                # Attempt to extract JSON from markdown code block if present
                clean_text = raw_text
                if "```json" in clean_text:
                    clean_text = clean_text.split("```json", 1)[1].split("```", 1)[0].strip()
                elif "```" in clean_text:
                    clean_text = clean_text.split("```", 1)[1].split("```", 1)[0].strip()
                try:
                    parsed_json = json.loads(clean_text)
                except Exception:
                    logger.warning(f"Could not parse response as JSON: {raw_text[:200]}")
                    parsed_json = None

        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")

        return GenerationResult(
            raw_text=raw_text,
            parsed_json=parsed_json,
            model_name=self.model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )
