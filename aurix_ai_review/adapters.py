from __future__ import annotations

from typing import Any, Protocol


class ReviewAdapter(Protocol):
    def generate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        ...


class LocalTemplateAdapter:
    def generate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return inputs


class ExternalLLMAdapter:
    def __init__(self, allow_external_llm: bool):
        self.allow_external_llm = allow_external_llm

    def generate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if not self.allow_external_llm:
            raise RuntimeError("external LLM calls are disabled")
        raise NotImplementedError("external LLM adapter is intentionally not implemented yet")
