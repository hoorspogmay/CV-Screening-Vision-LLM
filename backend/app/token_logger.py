from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol

from app.token_csv_logger import TokenCSVLogger


logger = logging.getLogger(__name__)


class ProviderAdapter(Protocol):
    """Minimal protocol for provider-specific token usage extraction."""

    def get_provider_name(self) -> str:
        ...

    def get_model_name(self, response: Mapping[str, Any]) -> str:
        ...

    def get_api_key_identifier(self) -> str:
        ...

    def get_usage(self, response: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        ...


@dataclass(slots=True)
class TokenUsageRecord:
    resume_filename: str
    provider: str
    model_name: str
    api_key_identifier: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    processing_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "resume_filename": self.resume_filename,
            "provider": self.provider,
            "model_name": self.model_name,
            "api_key_identifier": self.api_key_identifier,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "processing_time_seconds": round(self.processing_time_seconds, 2),
        }


class TokenUsageLogger:
    """Standalone token usage logger that can be connected to the screening flow.

    Integration hook idea:
    - Around the provider call for each resume, capture the start time and the
      provider response.
    - Call record_usage(...) after the LLM response is received.
    - This module is intentionally isolated and can be removed later without
      changing the existing screening workflow.
    """

    def __init__(self, csv_logger: Optional[TokenCSVLogger] = None) -> None:
        self.csv_logger = csv_logger or TokenCSVLogger()

    def record_usage(
        self,
        *,
        resume_filename: str,
        provider_adapter: ProviderAdapter,
        response: Optional[Mapping[str, Any]] = None,
        prompt_text: Optional[str] = None,
        processing_started_at: Optional[float] = None,
        api_key_identifier: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> TokenUsageRecord:
        processing_started_at = processing_started_at or time.time()
        processing_time_seconds = round(max(time.time() - processing_started_at, 0.0), 2)

        usage = None
        if response is not None:
            usage = provider_adapter.get_usage(response)

        prompt_tokens = self._extract_prompt_tokens(usage, prompt_text)
        completion_tokens = self._extract_completion_tokens(usage)
        total_tokens = self._extract_total_tokens(usage, prompt_tokens, completion_tokens)

        record = TokenUsageRecord(
            resume_filename=resume_filename,
            provider=provider_adapter.get_provider_name(),
            model_name=model_name or provider_adapter.get_model_name(response or {}),
            api_key_identifier=api_key_identifier or provider_adapter.get_api_key_identifier(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            processing_time_seconds=processing_time_seconds,
        )

        self._write_console_log(record)
        self.csv_logger.append(record.to_dict())
        return record

    def _extract_prompt_tokens(self, usage: Optional[Mapping[str, Any]], prompt_text: Optional[str]) -> Optional[int]:
        if usage is None:
            return self._estimate_prompt_tokens(prompt_text)

        if "prompt_tokens" in usage:
            return self._to_int(usage.get("prompt_tokens"))
        if "promptTokenCount" in usage:
            return self._to_int(usage.get("promptTokenCount"))
        return self._estimate_prompt_tokens(prompt_text)

    def _extract_completion_tokens(self, usage: Optional[Mapping[str, Any]]) -> Optional[int]:
        if usage is None:
            return None
        if "completion_tokens" in usage:
            return self._to_int(usage.get("completion_tokens"))
        if "completionTokenCount" in usage:
            return self._to_int(usage.get("completionTokenCount"))
        return None

    def _extract_total_tokens(self, usage: Optional[Mapping[str, Any]], prompt_tokens: Optional[int], completion_tokens: Optional[int]) -> Optional[int]:
        if usage is None:
            return None if prompt_tokens is None and completion_tokens is None else (prompt_tokens or 0) + (completion_tokens or 0)

        if "total_tokens" in usage:
            return self._to_int(usage.get("total_tokens"))
        if "totalTokenCount" in usage:
            return self._to_int(usage.get("totalTokenCount"))
        return None if prompt_tokens is None and completion_tokens is None else (prompt_tokens or 0) + (completion_tokens or 0)

    @staticmethod
    def _estimate_prompt_tokens(prompt_text: Optional[str]) -> Optional[int]:
        if not prompt_text:
            return None
        return max(1, len(prompt_text.split()))

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _write_console_log(self, record: TokenUsageRecord) -> None:
        prompt_tokens = "unavailable" if record.prompt_tokens is None else str(record.prompt_tokens)
        completion_tokens = "unavailable" if record.completion_tokens is None else str(record.completion_tokens)
        total_tokens = "unavailable" if record.total_tokens is None else str(record.total_tokens)

        print(
            f"Resume: {record.resume_filename}\n"
            f"Provider: {record.provider}\n"
            f"Model: {record.model_name}\n"
            f"Prompt Tokens: {prompt_tokens}\n"
            f"Completion Tokens: {completion_tokens}\n"
            f"Total Tokens: {total_tokens}\n"
            f"Processing Time: {record.processing_time_seconds:.2f}s"
        )


class GroqProviderAdapter:
    """Adapter for Groq-style responses."""

    def __init__(self, api_key_identifier: str = "Groq") -> None:
        self._api_key_identifier = api_key_identifier

    def get_provider_name(self) -> str:
        return "Groq"

    def get_model_name(self, response: Mapping[str, Any]) -> str:
        model_name = response.get("model") or response.get("model_name") or ""
        return str(model_name or "unknown")

    def get_api_key_identifier(self) -> str:
        return self._api_key_identifier

    def get_usage(self, response: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        usage = response.get("usage") or response.get("token_usage") or response.get("usage_details")
        if isinstance(usage, Mapping):
            return usage
        return None


class OpenRouterProviderAdapter:
    """Adapter for OpenRouter-style responses."""

    def __init__(self, api_key_identifier: str = "OpenRouter") -> None:
        self._api_key_identifier = api_key_identifier

    def get_provider_name(self) -> str:
        return "OpenRouter"

    def get_model_name(self, response: Mapping[str, Any]) -> str:
        model_name = response.get("model") or response.get("model_name") or ""
        return str(model_name or "unknown")

    def get_api_key_identifier(self) -> str:
        return self._api_key_identifier

    def get_usage(self, response: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        usage = response.get("usage") or response.get("token_usage") or response.get("usage_details")
        if isinstance(usage, Mapping):
            return usage
        return None


class ProviderAdapterRegistry:
    """Simple registry for provider adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, type[ProviderAdapter]] = {}

    def register(self, provider_name: str, adapter_cls: type[ProviderAdapter]) -> None:
        self._adapters[provider_name.lower()] = adapter_cls

    def create(self, provider_name: str, **kwargs: Any) -> ProviderAdapter:
        adapter_cls = self._adapters.get(provider_name.lower())
        if adapter_cls is None:
            raise KeyError(f"Unsupported provider: {provider_name}")
        return adapter_cls(**kwargs)


# Optional integration example:
# from app.token_logger import TokenUsageLogger, GroqProviderAdapter
#
# logger = TokenUsageLogger()
# start_time = time.time()
# response = ...  # existing provider call
# logger.record_usage(
#     resume_filename=resume_file_name,
#     provider_adapter=GroqProviderAdapter(api_key_identifier="Groq"),
#     response=response,
#     prompt_text=prompt_text,
#     processing_started_at=start_time,
# )
