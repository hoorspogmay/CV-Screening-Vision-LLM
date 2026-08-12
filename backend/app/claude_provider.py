"""Claude provider wrapper for Anthropic's Messages API."""
from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from app.config import get_settings
from app.job_requirements import JobRequirements
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.providers_base import AIProvider
from app.schemas import Decision, ResumeResult
from app.token_logger import ClaudeProviderAdapter, TokenUsageLogger, safe_record_usage

logger = logging.getLogger(__name__)
token_logger = TokenUsageLogger()


class ClaudeProvider(AIProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.claude_api_key
        self._model = settings.claude_model
        self._url = settings.claude_api_url
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
        start_time = time.time()
        prompt_text = build_user_prompt(resume_text, requirements, recruitment_document_text)

        if not self._api_key:
            logger.error("CLAUDE_API_KEY is not configured.")
            safe_record_usage(
                token_logger,
                resume_filename=file_name,
                provider_adapter=ClaudeProviderAdapter(api_key_identifier="Claude"),
                response=None,
                prompt_text=prompt_text,
                processing_started_at=start_time,
                api_key_identifier="Claude",
                model_name=self._model,
            )
            raise RuntimeError("CLAUDE_API_KEY is not configured.")

        payload = {
            "model": self._model,
            "max_tokens": 400,
            "temperature": 0.0,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt_text}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(self._url, headers=headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    content = body["content"][0]["text"]
                    safe_record_usage(
                        token_logger,
                        resume_filename=file_name,
                        provider_adapter=ClaudeProviderAdapter(api_key_identifier="Claude"),
                        response=body,
                        prompt_text=prompt_text,
                        processing_started_at=start_time,
                        api_key_identifier="Claude",
                        model_name=self._model,
                    )
                    return self.parse_resume_json(content, file_name, file_id, requirements)
                except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
                    logger.warning(
                        "Claude call failed for %s (attempt %d/%d): %s",
                        file_name,
                        attempt,
                        self._max_retries,
                        exc,
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * attempt)

        raise RuntimeError(f"Claude evaluation failed after {self._max_retries} attempts: {last_error}")

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 200,
        temperature: float = 0.0,
    ) -> str:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(self._url, headers=headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    return body["content"][0]["text"]
                except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
                    logger.warning(
                        "Claude completion failed for %s (attempt %d/%d): %s",
                        file_name,
                        attempt,
                        self._max_retries,
                        exc,
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * attempt)

        raise RuntimeError(f"Claude completion failed after {self._max_retries} attempts: {last_error}")


    @staticmethod
    def _parse_response(
        content: str,
        file_name: str,
        file_id: str,
        resume_text: str,
        requirements: JobRequirements | None = None,
    ) -> ResumeResult:
        return ClaudeProvider.parse_resume_json(content, file_name, file_id, requirements)
