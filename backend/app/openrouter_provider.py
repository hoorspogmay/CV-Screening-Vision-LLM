"""OpenRouter provider — wraps models such as qwen/qwen-2.5-7b-instruct."""
from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from app.config import get_settings
from app.prompts import EXTRACTION_PROMPT, SYSTEM_PROMPT, build_user_prompt
from app.job_extraction_types import JobExtraction, parse_job_extraction_response
from app.job_requirements import JobRequirements
from app.providers_base import AIProvider
from app.schemas import ResumeResult
from app.token_logger import OpenRouterProviderAdapter, TokenUsageLogger, safe_record_usage

logger = logging.getLogger(__name__)
token_logger = TokenUsageLogger()


class OpenRouterProvider(AIProvider):
    def __init__(self) -> None:
        settings = get_settings()

        # Use ONLY the OpenRouter key — never fall back to a Groq key here.
        # If OPENROUTER_API_KEY is not set the provider will raise at call time
        # with a clear error rather than silently authenticating as the wrong service.
        raw_keys = settings.openrouter_api_key or ""
        self._api_keys: list[str] = [k.strip() for k in str(raw_keys).split(",") if k.strip()]
        self._model: str = settings.openrouter_model or "qwen/qwen-2.5-7b-instruct"
        self._url: str = settings.openrouter_api_url
        self._timeout: float = settings.ai_request_timeout_seconds
        self._max_retries: int = settings.ai_max_retries
        self._backoff: float = settings.ai_retry_backoff_seconds
        self._rate_limit_pause: float = settings.ai_rate_limit_pause_seconds
        self._failed_keys: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _active_keys(self) -> list[str]:
        """Return keys that have not been exhausted."""
        return [k for k in self._api_keys if self._failed_keys.get(k, 0) < 2]

    def _mark_key_failed(self, api_key: str) -> None:
        self._failed_keys[api_key] = self._failed_keys.get(api_key, 0) + 1

    def _reset_key(self, api_key: str) -> None:
        self._failed_keys.pop(api_key, None)

    @staticmethod
    def _headers(api_key: str, title: str = "ATS Screening") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": title,
        }

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        payload: dict,
        log_label: str,
        title: str = "ATS Screening",
    ) -> dict:
        """
        Attempt the request across all active keys with retries.
        Returns the parsed JSON body on success, raises RuntimeError after exhaustion.
        """
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            active = self._active_keys()
            if not active:
                break

            for api_key in active:
                key_short = api_key[:8] + "..."
                try:
                    logger.info(
                        "OpenRouter request | label=%s | key=%s | attempt=%d/%d",
                        log_label, key_short, attempt, self._max_retries,
                    )
                    response = await client.post(
                        self._url,
                        headers=self._headers(api_key, title),
                        json=payload,
                    )
                    response.raise_for_status()
                    body = response.json()
                    self._reset_key(api_key)
                    logger.info(
                        "OpenRouter request succeeded | label=%s | key=%s | attempt=%d/%d",
                        log_label, key_short, attempt, self._max_retries,
                    )
                    return body

                except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
                    self._mark_key_failed(api_key)
                    logger.warning(
                        "OpenRouter request failed | label=%s | key=%s | attempt=%d/%d | error=%s",
                        log_label, key_short, attempt, self._max_retries, exc,
                    )
                    await asyncio.sleep(self._rate_limit_pause)

            if attempt < self._max_retries:
                await asyncio.sleep(self._backoff * attempt)

        raise RuntimeError(
            f"OpenRouter request '{log_label}' failed after {self._max_retries} attempts: {last_error}"
        )

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

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
        key_label = "OpenRouter"

        if not self._api_keys:
            logger.error(
                "OpenRouter API key is not configured. Set OPENROUTER_API_KEY in your .env file."
            )
            safe_record_usage(
                token_logger,
                resume_filename=file_name,
                provider_adapter=OpenRouterProviderAdapter(api_key_identifier=key_label),
                response=None,
                prompt_text=prompt_text,
                processing_started_at=start_time,
                api_key_identifier=key_label,
                model_name=self._model,
            )
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text},
            ],
            "temperature": 0.1,
            "max_tokens": 300,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                body = await self._post_with_retry(client, payload, log_label=file_name)
            except RuntimeError:
                safe_record_usage(
                    token_logger,
                    resume_filename=file_name,
                    provider_adapter=OpenRouterProviderAdapter(api_key_identifier=key_label),
                    response=None,
                    prompt_text=prompt_text,
                    processing_started_at=start_time,
                    api_key_identifier=key_label,
                    model_name=self._model,
                )
                raise

        content = body["choices"][0]["message"]["content"]

        safe_record_usage(
            token_logger,
            resume_filename=file_name,
            provider_adapter=OpenRouterProviderAdapter(api_key_identifier=key_label),
            response=body,
            prompt_text=prompt_text,
            processing_started_at=start_time,
            api_key_identifier=key_label,
            model_name=self._model,
        )

        return self.parse_resume_json(content, file_name, file_id, requirements)

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 200,
        temperature: float = 0.0,
    ) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            body = await self._post_with_retry(client, payload, log_label="route_resume", title="ATS Screening Routing")

        return body["choices"][0]["message"]["content"]

    async def extract_jobs(self, document_text: str) -> list[JobExtraction]:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"{EXTRACTION_PROMPT}\n\nDocument text:\n{document_text}"},
            ],
            "temperature": 0.0,
            "max_tokens": 1200,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            body = await self._post_with_retry(
                client, payload,
                log_label="job_extraction",
                title="ATS Screening Job Extraction",
            )

        content = body["choices"][0]["message"]["content"]
        return parse_job_extraction_response(content)