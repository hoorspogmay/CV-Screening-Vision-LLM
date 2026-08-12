"""Google provider wrapper for Gemini-style free models such as google/gemma-4-31b-it:free."""
from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from app.config import get_settings
from app.schemas import Decision, ResumeResult
from app.job_requirements import JobRequirements
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.providers_base import AIProvider
from app.token_logger import GoogleProviderAdapter, TokenUsageLogger, safe_record_usage

logger = logging.getLogger(__name__)
token_logger = TokenUsageLogger()


class GoogleProvider(AIProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.google_api_key
        self._model = settings.google_model or "google/gemma-4-31b-it:free"
        self._url = settings.google_api_url or "https://generativelanguage.googleapis.com/v1beta/models/" + self._model + ":generateContent"
        self._timeout = settings.ai_request_timeout_seconds
        self._max_retries = settings.ai_max_retries
        self._backoff = settings.ai_retry_backoff_seconds

    async def evaluate_resume(
        self,
        resume_text: str,
        file_name: str,
        file_id: str,
        requirements: JobRequirements | None = None,
        recruitment_document_text: str | None = None,
    ) -> ResumeResult:
        start_time = time.perf_counter()
        prompt_text = f"System prompt: {SYSTEM_PROMPT}\n\nUser prompt: {build_user_prompt(resume_text, requirements, recruitment_document_text)}"
        if not self._api_key:
            safe_record_usage(
                token_logger,
                resume_filename=file_name,
                provider_adapter=GoogleProviderAdapter(api_key_identifier="Google"),
                response=None,
                prompt_text=prompt_text,
                processing_started_at=start_time,
                api_key_identifier="Google",
                model_name=self._model,
            )
            raise RuntimeError("GOOGLE_API_KEY is not configured.")

        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.1},
        }
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(self._url, headers=headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    content = body["candidates"][0]["content"]["parts"][0]["text"]
                    safe_record_usage(
                        token_logger,
                        resume_filename=file_name,
                        provider_adapter=GoogleProviderAdapter(api_key_identifier="Google"),
                        response=body,
                        prompt_text=prompt_text,
                        processing_started_at=start_time,
                        api_key_identifier="Google",
                        model_name=self._model,
                    )
                    return self.parse_resume_json(content, file_name, file_id, requirements)
                except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
                    logger.warning(
                        "Google call failed for %s (attempt %d/%d): %s",
                        file_name,
                        attempt,
                        self._max_retries,
                        exc,
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * attempt)

        safe_record_usage(
            token_logger,
            resume_filename=file_name,
            provider_adapter=GoogleProviderAdapter(api_key_identifier="Google"),
            response=None,
            prompt_text=prompt_text,
            processing_started_at=start_time,
            api_key_identifier="Google",
            model_name=self._model,
        )
        raise RuntimeError(f"Google evaluation failed after {self._max_retries} attempts: {last_error}")

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 200,
        temperature: float = 0.0,
    ) -> str:
        prompt_text = f"System prompt: {system}\n\nUser prompt: {user}"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(self._url, headers=headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    return body["candidates"][0]["content"][0]["text"]
                except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
                    logger.warning(
                        "Google completion failed for %s (attempt %d/%d): %s",
                        self._model,
                        attempt,
                        self._max_retries,
                        exc,
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * attempt)

        raise RuntimeError(f"Google completion failed after {self._max_retries} attempts: {last_error}")

    @staticmethod
    def _parse_response(
        content: str,
        file_name: str,
        file_id: str,
        resume_text: str,
        requirements: JobRequirements | None = None,
    ) -> ResumeResult:
        return GoogleProvider.parse_resume_json(content, file_name, file_id, requirements)

    
