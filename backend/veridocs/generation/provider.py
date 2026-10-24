"""
Base provider abstraction and fake implementation for LLM generation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field


class GenerationResult(BaseModel):
    raw_text: str
    parsed_json: Optional[Dict[str, Any]] = None
    model_name: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: float = 0.0


class GeneratorProvider(ABC):
    """Abstract interface for LLM generation backends."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs,
    ) -> GenerationResult:
        """Generate response from model, optionally constrained to a Pydantic schema."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if provider backend is reachable and ready."""
        pass


class FakeTestProvider(GeneratorProvider):
    """
    Deterministic mock provider for unit tests only.
    Never used in production endpoints.
    """

    def __init__(self, canned_response: Optional[str] = None, canned_json: Optional[Dict[str, Any]] = None):
        self.canned_response = canned_response or '{"summary": "Test summary", "claims": [], "limitations": []}'
        self.canned_json = canned_json
        self.call_count = 0
        self.last_prompt = ""
        self.last_system_prompt = ""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs,
    ) -> GenerationResult:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt or ""

        parsed = self.canned_json
        if parsed is None and self.canned_response:
            import json
            try:
                parsed = json.loads(self.canned_response)
            except Exception:
                parsed = None

        return GenerationResult(
            raw_text=self.canned_response,
            parsed_json=parsed,
            model_name="fake-test-provider",
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=1.5,
        )

    async def is_healthy(self) -> bool:
        return True
