from __future__ import annotations

import csv
import time
from pathlib import Path

import pytest

from app.csv_export import results_to_csv
from app.groq_provider import GroqProvider
from app.schemas import Decision, ResumeResult
from app.token_logger import TokenCSVLogger, GroqProviderAdapter, TokenUsageLogger, safe_record_usage


def test_safe_record_usage_writes_csv_and_returns_record(tmp_path: Path) -> None:
    csv_path = tmp_path / "token_usage.csv"
    csv_logger = TokenCSVLogger(csv_path=csv_path)
    token_logger = TokenUsageLogger(csv_logger=csv_logger)

    record = safe_record_usage(
        token_logger,
        resume_filename="resume.pdf",
        provider_adapter=GroqProviderAdapter(api_key_identifier="groq-test"),
        response={"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        prompt_text="Software engineer with Python experience",
        processing_started_at=time.time() - 0.2,
        api_key_identifier="groq-test",
        model_name="llama-3",
    )

    assert record.total_tokens == 15
    assert csv_path.exists()

    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["resume_filename"] == "resume.pdf"
    assert rows[0]["provider"] == "Groq"


def test_safe_record_usage_writes_only_f1_metrics_to_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "token_usage.csv"
    csv_logger = TokenCSVLogger(csv_path=csv_path)
    token_logger = TokenUsageLogger(csv_logger=csv_logger)

    record = safe_record_usage(
        token_logger,
        resume_filename="resume.pdf",
        provider_adapter=GroqProviderAdapter(api_key_identifier="groq-test"),
        response={"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        prompt_text="Software engineer with Python experience",
        processing_started_at=time.time() - 0.2,
        api_key_identifier="groq-test",
        model_name="llama-3",
        evaluation_metrics={"accuracy": 0.87, "precision": 0.84, "recall": 0.82, "f1_score": 0.83},
    )

    assert record.accuracy_score == 0.87
    assert record.precision_score == 0.84
    assert record.recall_score == 0.82
    assert record.f1_score == 0.83

    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert "accuracy_score" not in rows[0]
    assert "precision_score" not in rows[0]
    assert "recall_score" not in rows[0]
    assert rows[0]["f1_score"] == "0.83"


def test_results_to_csv_omits_metric_columns() -> None:
    result = ResumeResult(
        file_id="file-1",
        file_name="resume.pdf",
        candidate_name="Jane Doe",
        decision=Decision.ACCEPT,
        summary="Strong fit",
        match_score=85,
        education_level="Bachelor",
        experience_years=5,
        skills_match=True,
    )

    csv_text = results_to_csv([result])
    rows = list(csv.reader(csv_text.splitlines()))

    assert rows[0] == [
        "Candidate Name",
        "File Name",
        "Job Role",
        "Decision",
        "Summary",
        "Match Score",
        "Education Level",
        "Experience Years",
        "Skills Match",
    ]
    assert rows[1][0] == "Jane Doe"
    assert len(rows[1]) == 9


def test_csv_logger_writes_to_primary_and_legacy_paths(tmp_path: Path) -> None:
    primary_path = tmp_path / "token_usage_log.csv"
    legacy_path = tmp_path / "app" / "token_usage_log.csv"
    csv_logger = TokenCSVLogger(csv_path=primary_path)

    csv_logger.append({
        "resume_filename": "resume.pdf",
        "provider": "Groq",
        "model_name": "test-model",
        "api_key_identifier": "test-key",
        "prompt_tokens": 8,
        "completion_tokens": 2,
        "total_tokens": 10,
        "processing_time_seconds": 0.12,
    })

    assert primary_path.exists()
    with primary_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["resume_filename"] == "resume.pdf"


def test_groq_provider_calls_logger_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    def fake_safe_record_usage(token_logger, **kwargs):
        calls.append(kwargs)
        return None

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse({
                "choices": [{"message": {"content": '{"candidate_name": "Jane Doe", "decision": "ACCEPT", "match_score": 0.9}'}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
            })

    monkeypatch.setattr("app.groq_provider.safe_record_usage", fake_safe_record_usage, raising=False)
    monkeypatch.setattr("app.groq_provider.httpx.AsyncClient", FakeAsyncClient)

    provider = GroqProvider()
    provider._api_key = "dummy"
    provider._model = "mock-model"
    provider._url = "https://example.test"
    provider._timeout = 5
    provider._max_retries = 1
    provider._backoff = 0.0

    import asyncio
    asyncio.run(provider.evaluate_resume("resume text", "resume.pdf", "file-1"))

    assert len(calls) == 1
    assert calls[0]["resume_filename"] == "resume.pdf"
    assert calls[0]["response"]["usage"]["total_tokens"] == 15
