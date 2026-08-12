"""Token usage logging — CSV writer and structured logger in a single module.

token_csv_logger.py is superseded by this file. Delete it once all imports
have been updated to point here.
"""
from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CSV writer (previously token_csv_logger.py)
# ---------------------------------------------------------------------------

_FIELDNAMES = [
    "resume_filename",
    "provider",
    "model_name",
    "api_key_identifier",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "processing_time_seconds",
    "f1_score",
]

_DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "token_usage_log.csv"


class TokenCSVLogger:
    """Append-only CSV sink for token usage records."""

    def __init__(self, csv_path: Optional[str | Path] = None) -> None:
        self.csv_path = Path(csv_path or _DEFAULT_CSV_PATH)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_header()

    @staticmethod
    def fieldnames() -> list[str]:
        return list(_FIELDNAMES)

    def _ensure_header(self) -> None:
        if self.csv_path.exists():
            return
        with self.csv_path.open("w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=_FIELDNAMES).writeheader()

    def append(self, record: Mapping[str, Any]) -> None:
        with self.csv_path.open("a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=_FIELDNAMES).writerow(self._normalize(record))

    def _normalize(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        def fmt(v: Any) -> Any:
            if v is None:
                return ""
            if isinstance(v, float):
                return f"{v:.2f}"
            return v

        return {
            "resume_filename": record.get("resume_filename", ""),
            "provider": record.get("provider", ""),
            "model_name": record.get("model_name", ""),
            "api_key_identifier": record.get("api_key_identifier", ""),
            "prompt_tokens": fmt(record.get("prompt_tokens")),
            "completion_tokens": fmt(record.get("completion_tokens")),
            "total_tokens": fmt(record.get("total_tokens")),
            "processing_time_seconds": fmt(record.get("processing_time_seconds")),
            "f1_score": fmt(record.get("f1_score")),
        }


# ---------------------------------------------------------------------------
# Provider adapter protocol + concrete adapters
# ---------------------------------------------------------------------------

class ProviderAdapter(Protocol):
    """Minimal protocol for extracting token usage from a provider response."""

    def get_provider_name(self) -> str: ...
    def get_model_name(self, response: Mapping[str, Any]) -> str: ...
    def get_api_key_identifier(self) -> str: ...
    def get_usage(self, response: Mapping[str, Any]) -> Optional[Mapping[str, Any]]: ...


class _BaseAdapter:
    """Shared implementation for the standard OpenAI-compatible usage shape."""

    def __init__(self, provider_name: str, api_key_identifier: str) -> None:
        self._provider_name = provider_name
        self._api_key_identifier = api_key_identifier

    def get_provider_name(self) -> str:
        return self._provider_name

    def get_model_name(self, response: Mapping[str, Any]) -> str:
        return str(response.get("model") or response.get("model_name") or "unknown")

    def get_api_key_identifier(self) -> str:
        return self._api_key_identifier

    def get_usage(self, response: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        usage = (
            response.get("usage")
            or response.get("token_usage")
            or response.get("usage_details")
        )
        return usage if isinstance(usage, Mapping) else None


class GroqProviderAdapter(_BaseAdapter):
    def __init__(self, api_key_identifier: str = "Groq") -> None:
        super().__init__("Groq", api_key_identifier)


class OpenRouterProviderAdapter(_BaseAdapter):
    def __init__(self, api_key_identifier: str = "OpenRouter") -> None:
        super().__init__("OpenRouter", api_key_identifier)


class GoogleProviderAdapter(_BaseAdapter):
    """Google Gemini responses use different token field names."""

    def __init__(self, api_key_identifier: str = "Google") -> None:
        super().__init__("Google", api_key_identifier)

    def get_usage(self, response: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        # Gemini wraps usage under usageMetadata with camelCase keys.
        usage = (
            response.get("usageMetadata")
            or response.get("usage")
            or response.get("token_usage")
            or response.get("usage_details")
        )
        return usage if isinstance(usage, Mapping) else None


class ClaudeProviderAdapter(_BaseAdapter):
    def __init__(self, api_key_identifier: str = "Claude") -> None:
        super().__init__("Claude", api_key_identifier)

    def get_usage(self, response: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        usage = response.get("usage")
        return usage if isinstance(usage, Mapping) else None


# ---------------------------------------------------------------------------
# Usage record
# ---------------------------------------------------------------------------

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
    accuracy_score: Optional[float] = None
    precision_score: Optional[float] = None
    recall_score: Optional[float] = None
    f1_score: Optional[float] = None

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
            "accuracy_score": self.accuracy_score,
            "precision_score": self.precision_score,
            "recall_score": self.recall_score,
            "f1_score": self.f1_score,
        }


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class TokenUsageLogger:
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
        evaluation_metrics: Optional[Mapping[str, Any]] = None,
    ) -> TokenUsageRecord:
        processing_started_at = processing_started_at or time.time()
        processing_time = round(max(time.time() - processing_started_at, 0.0), 2)

        usage = provider_adapter.get_usage(response) if response is not None else None

        prompt_tokens = self._prompt_tokens(usage, prompt_text)
        completion_tokens = self._completion_tokens(usage)
        total_tokens = self._total_tokens(usage, prompt_tokens, completion_tokens)

        record = TokenUsageRecord(
            resume_filename=resume_filename,
            provider=provider_adapter.get_provider_name(),
            model_name=model_name or provider_adapter.get_model_name(response or {}),
            api_key_identifier=api_key_identifier or provider_adapter.get_api_key_identifier(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            processing_time_seconds=processing_time,
            accuracy_score=self._metric(evaluation_metrics, "accuracy"),
            precision_score=self._metric(evaluation_metrics, "precision"),
            recall_score=self._metric(evaluation_metrics, "recall"),
            f1_score=self._metric(evaluation_metrics, "f1_score"),
        )

        self._log(record)
        self.csv_logger.append(record.to_dict())
        return record

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _prompt_tokens(
        self, usage: Optional[Mapping[str, Any]], prompt_text: Optional[str]
    ) -> Optional[int]:
        if usage is None:
            return self._estimate(prompt_text)
        for key in ("prompt_tokens", "promptTokenCount", "input_tokens"):
            if key in usage:
                return self._to_int(usage[key])
        return self._estimate(prompt_text)

    def _completion_tokens(self, usage: Optional[Mapping[str, Any]]) -> Optional[int]:
        if usage is None:
            return None
        for key in ("completion_tokens", "completionTokenCount", "output_tokens"):
            if key in usage:
                return self._to_int(usage[key])
        return None

    def _total_tokens(
        self,
        usage: Optional[Mapping[str, Any]],
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
    ) -> Optional[int]:
        if usage is not None:
            for key in ("total_tokens", "totalTokenCount"):
                if key in usage:
                    return self._to_int(usage[key])
        if prompt_tokens is None and completion_tokens is None:
            return None
        return (prompt_tokens or 0) + (completion_tokens or 0)

    @staticmethod
    def _metric(metrics: Optional[Mapping[str, Any]], key: str) -> Optional[float]:
        if not metrics:
            return None
        v = metrics.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _estimate(prompt_text: Optional[str]) -> Optional[int]:
        if not prompt_text:
            return None
        return max(1, len(prompt_text.split()))

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _log(self, record: TokenUsageRecord) -> None:
        logger.info(
            "Token usage | resume=%s | provider=%s | model=%s | key=%s | "
            "prompt_tokens=%s | completion_tokens=%s | total_tokens=%s | time=%.2fs",
            record.resume_filename,
            record.provider,
            record.model_name,
            record.api_key_identifier,
            "unavailable" if record.prompt_tokens is None else record.prompt_tokens,
            "unavailable" if record.completion_tokens is None else record.completion_tokens,
            "unavailable" if record.total_tokens is None else record.total_tokens,
            record.processing_time_seconds,
        )


def safe_record_usage(
    token_logger: TokenUsageLogger,
    *,
    resume_filename: str,
    provider_adapter: ProviderAdapter,
    response: Optional[Mapping[str, Any]] = None,
    prompt_text: Optional[str] = None,
    processing_started_at: Optional[float] = None,
    api_key_identifier: Optional[str] = None,
    model_name: Optional[str] = None,
    evaluation_metrics: Optional[Mapping[str, Any]] = None,
) -> Optional[TokenUsageRecord]:
    """Record token usage without interrupting the main screening flow."""
    try:
        return token_logger.record_usage(
            resume_filename=resume_filename,
            provider_adapter=provider_adapter,
            response=response,
            prompt_text=prompt_text,
            processing_started_at=processing_started_at,
            api_key_identifier=api_key_identifier,
            model_name=model_name,
            evaluation_metrics=evaluation_metrics,
        )
    except Exception as exc:
        logger.error(
            "Token usage logging FAILED for %s: %s",
            resume_filename, exc,
            exc_info=True,
        )
        return None