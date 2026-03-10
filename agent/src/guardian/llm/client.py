"""LLM client abstraction.

Default: Ollama (free, local). Supports Anthropic and OpenAI as optional providers.
All LLM outputs that drive actions are validated against Pydantic schemas.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3


class LLMResponse(BaseModel):
    """Raw LLM response before schema validation."""

    content: str
    model: str
    usage: dict[str, int] = {}


class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    async def structured_output(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        system: str | None = None,
        temperature: float = 0.0,
    ) -> BaseModel:
        """Get structured output validated against a Pydantic schema.

        Retries up to MAX_VALIDATION_RETRIES times on validation failure.
        """
        last_error: Exception | None = None

        for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
            response = await self.chat(messages, system, temperature)

            try:
                # Try to parse JSON from the response
                raw = _extract_json(response.content)
                parsed = schema.model_validate_json(raw)
                logger.debug(
                    "Schema validation passed on attempt %d", attempt
                )
                return parsed
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning(
                    "Schema validation failed (attempt %d/%d): %s",
                    attempt,
                    MAX_VALIDATION_RETRIES,
                    e,
                )
                # Add the error to messages for the retry
                messages = [
                    *messages,
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": (
                            f"Your response failed JSON schema validation: {e}\n"
                            f"Expected schema: {schema.model_json_schema()}\n"
                            "Please fix and respond with valid JSON only."
                        ),
                    },
                ]

        raise ValueError(
            f"LLM output failed schema validation after "
            f"{MAX_VALIDATION_RETRIES} attempts: {last_error}"
        )


class OllamaClient(LLMClient):
    """Ollama local LLM client (zero cost)."""

    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        resp = await self._client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": all_messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=self.model,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    async def close(self) -> None:
        await self._client.aclose()


class MockLLMClient(LLMClient):
    """Mock LLM client for testing. Returns pre-configured responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_count = 0

    def add_response(self, content: str) -> None:
        self._responses.append(content)

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        if self._call_count >= len(self._responses):
            raise RuntimeError(
                f"MockLLMClient exhausted: {self._call_count} calls made, "
                f"only {len(self._responses)} responses configured"
            )
        content = self._responses[self._call_count]
        self._call_count += 1
        return LLMResponse(content=content, model="mock", usage={})


def _extract_json(text: str) -> str:
    """Extract JSON from LLM output, handling markdown code blocks."""
    text = text.strip()

    # Handle ```json ... ``` blocks
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return text[start:end].strip()

    # Handle ``` ... ``` blocks
    if text.startswith("```"):
        start = text.index("\n") + 1
        end = text.rindex("```")
        return text[start:end].strip()

    # Try to find JSON object or array
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        if start_char in text:
            start = text.index(start_char)
            # Find matching closing bracket
            depth = 0
            for i in range(start, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]

    return text


def create_llm_client(
    provider: str = "ollama",
    model: str | None = None,
    **kwargs: Any,
) -> LLMClient:
    """Factory function to create an LLM client."""
    if provider == "ollama":
        return OllamaClient(
            model=model or "qwen2.5-coder:7b",
            base_url=kwargs.get("base_url", "http://localhost:11434"),
        )
    elif provider == "mock":
        return MockLLMClient(responses=kwargs.get("responses"))
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
