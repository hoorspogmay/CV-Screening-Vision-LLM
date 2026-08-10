"""OpenRouter provider wrapper for models such as qwen/qwen-2.5-7b-instruct."""
from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from app.config import get_settings
from app.schemas import Decision, ResumeResult
from app.job_extraction_prompt import EXTRACTION_PROMPT
from app.job_extraction_types import JobExtraction, parse_job_extraction_response
from app.job_requirements import JobRequirements
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.providers_base import AIProvider
from app.decision_utils import (
    classify_by_match_score,
    infer_experience_years,
    parse_optional_int,
)
from app.token_logger import OpenRouterProviderAdapter, TokenUsageLogger, safe_record_usage

logger = logging.getLogger(__name__)
token_logger = TokenUsageLogger()


class OpenRouterProvider(AIProvider):
    def __init__(self) -> None:
        settings = get_settings()
        raw_keys = settings.openrouter_api_key or settings.groq_api_key
        self._api_keys = [key.strip() for key in str(raw_keys).split(",") if key.strip()]
        self._api_key = self._api_keys[0] if self._api_keys else ""
        self._model = settings.openrouter_model or settings.groq_model
        self._url = settings.openrouter_api_url
        self._timeout = settings.ai_request_timeout_seconds
        self._max_retries = settings.ai_max_retries
        self._backoff = settings.ai_retry_backoff_seconds
        self._rate_limit_pause = settings.ai_rate_limit_pause_seconds
        self._failed_keys: dict[str, int] = {}

    async def evaluate_resume(
        self,
        resume_text: str,
        file_name: str,
        file_id: str,
        requirements: JobRequirements | None = None,
        recruitment_document_text: str | None = None,
    ) -> ResumeResult:
        start_time = time.time()  # must use time.time() — perf_counter() breaks token_logger duration calc
        prompt_text = build_user_prompt(resume_text, requirements, recruitment_document_text)

        if not self._api_keys:
            logger.error("OpenRouter API key is not configured. Set OPENROUTER_API_KEY in your .env file.")
            safe_record_usage(
                token_logger,
                resume_filename=file_name,
                provider_adapter=OpenRouterProviderAdapter(api_key_identifier="OpenRouter"),
                response=None,
                prompt_text=prompt_text,
                processing_started_at=start_time,
                api_key_identifier="OpenRouter",
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

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                for api_key in list(self._api_keys):
                    if self._failed_keys.get(api_key, 0) >= 2:
                        logger.warning(
                            "Skipping exhausted OpenRouter key %s... for %s",
                            api_key[:8], file_name,
                        )
                        continue

                    key_index = self._api_keys.index(api_key) + 1
                    key_label = f"OpenRouter Key {key_index}"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:5173",
                        "X-Title": "ATS Screening",
                    }
                    try:
                        logger.info(
                            "OpenRouter API call starting | file=%s | model=%s | key=%s | attempt=%d/%d",
                            file_name, self._model, key_label, attempt, self._max_retries,
                        )
                        response = await client.post(self._url, headers=headers, json=payload)
                        response.raise_for_status()
                        body = response.json()
                        content = body["choices"][0]["message"]["content"]
                        self._failed_keys.pop(api_key, None)
                        self._api_key = api_key
                        logger.info(
                            "OpenRouter API call succeeded | file=%s | key=%s | attempt=%d/%d",
                            file_name, key_label, attempt, self._max_retries,
                        )
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
                        return self._parse_response(content, file_name, file_id, resume_text, requirements)
                    except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                        last_error = exc
                        self._failed_keys[api_key] = self._failed_keys.get(api_key, 0) + 1
                        logger.warning(
                            "OpenRouter call failed for %s with key %s (attempt %d/%d): %s",
                            file_name, api_key[:8] + "...", attempt, self._max_retries, exc,
                        )
                        await asyncio.sleep(self._rate_limit_pause)
                        continue
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff * attempt)

        logger.error(
            "OpenRouter evaluation failed for %s after %d attempts. Last error: %s",
            file_name, self._max_retries, last_error,
        )
        safe_record_usage(
            token_logger,
            resume_filename=file_name,
            provider_adapter=OpenRouterProviderAdapter(api_key_identifier="OpenRouter"),
            response=None,
            prompt_text=prompt_text,
            processing_started_at=start_time,
            api_key_identifier="OpenRouter",
            model_name=self._model,
        )
        raise RuntimeError(f"OpenRouter evaluation failed after {self._max_retries} attempts: {last_error}")

    @staticmethod
    def _parse_response(
        content: str,
        file_name: str,
        file_id: str,
        resume_text: str,
        requirements: JobRequirements | None = None,
    ) -> ResumeResult:
        cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)

        candidate_name = str(data.get("candidate_name") or "").strip()
        if not candidate_name or candidate_name.lower() in {"unknown", "n/a", "null"}:
            candidate_name = "Unknown"

        try:
            match_score = float(data.get("match_score", 0))
        except (TypeError, ValueError):
            match_score = 0.0

        decision_value = str(data.get("decision") or "").strip().upper()
        if decision_value not in {Decision.ACCEPT.value, Decision.REJECT.value, Decision.DOUBTFUL.value}:
            summary = str(data.get("summary") or data.get("reason") or "")
            decision_value = classify_by_match_score(
                match_score,
                Decision.REJECT,
                requirements,
                reasoning=summary,
            ).value

        experience_years = parse_optional_int(data.get("experience_years"))
        summary_text = str(data.get("experience_summary") or data.get("experience") or data.get("summary") or data.get("reason") or "")
        inferred_years = infer_experience_years(summary_text)
        if experience_years is None:
            experience_years = inferred_years
        elif experience_years == 0 and inferred_years is not None:
            text_lower = summary_text.lower()
            if "no relevant experience" not in text_lower and "no experience" not in text_lower:
                experience_years = inferred_years

        return ResumeResult(
            file_id=file_id,
            file_name=file_name,
            candidate_name=candidate_name,
            decision=Decision(decision_value),
            summary=data.get("summary", ""),
            match_score=match_score,
            education_level=str(data.get("education_level") or "None").strip(),
            experience_years=experience_years,
            skills_match=bool(data.get("skills_match", True)),
        )

    async def extract_jobs(self, document_text: str) -> list[JobExtraction]:
        prompt_text = f"{EXTRACTION_PROMPT}\n\nDocument text:\n{document_text}"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": prompt_text},
            ],
            "temperature": 0.0,
            "max_tokens": 1200,
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                for api_key in list(self._api_keys):
                    if self._failed_keys.get(api_key, 0) >= 2:
                        logger.warning(
                            "Skipping exhausted OpenRouter key %s during extraction...",
                            api_key[:8],
                        )
                        continue

                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:5173",
                        "X-Title": "ATS Screening Job Extraction",
                    }
                    try:
                        response = await client.post(self._url, headers=headers, json=payload)
                        response.raise_for_status()
                        body = response.json()
                        content = body["choices"][0]["message"]["content"]
                        jobs = parse_job_extraction_response(content)
                        self._failed_keys.pop(api_key, None)
                        return jobs
                    except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValueError) as exc:
                        last_error = exc
                        self._failed_keys[api_key] = self._failed_keys.get(api_key, 0) + 1
                        logger.warning(
                            "OpenRouter job extraction call failed for key %s (attempt %d/%d): %s",
                            api_key[:8] + "...",
                            attempt,
                            self._max_retries,
                            exc,
                        )
                        if attempt < self._max_retries:
                            await asyncio.sleep(self._rate_limit_pause)
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff * attempt)

        raise RuntimeError(f"OpenRouter job extraction failed after {self._max_retries} attempts: {last_error}")

    