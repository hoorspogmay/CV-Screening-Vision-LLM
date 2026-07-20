"""OpenRouter provider wrapper for models such as qwen/qwen-2.5-7b-instruct."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

from app.config import get_settings
from app.schemas import Decision, ResumeResult
from app.job_requirements import JobRequirements
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.providers_base import AIProvider

logger = logging.getLogger(__name__)


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
    ) -> ResumeResult:
        if not self._api_keys:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(resume_text, requirements)},
            ],
            "temperature": 0.1,
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                for api_key in list(self._api_keys):
                    if self._failed_keys.get(api_key, 0) >= 2:
                        continue
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:5173",
                        "X-Title": "ATS Screening",
                    }
                    try:
                        response = await client.post(self._url, headers=headers, json=payload)
                        response.raise_for_status()
                        body = response.json()
                        content = body["choices"][0]["message"]["content"]
                        self._failed_keys.pop(api_key, None)
                        self._api_key = api_key
                        return self._parse_response(content, file_name, file_id, resume_text)
                    except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                        last_error = exc
                        self._failed_keys[api_key] = self._failed_keys.get(api_key, 0) + 1
                        logger.warning(
                            "OpenRouter call failed for %s with key %s (attempt %d/%d): %s",
                            file_name,
                            api_key[:8] + "...",
                            attempt,
                            self._max_retries,
                            exc,
                        )
                        await asyncio.sleep(self._rate_limit_pause)
                        continue
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff * attempt)

        raise RuntimeError(f"OpenRouter evaluation failed after {self._max_retries} attempts: {last_error}")

    @staticmethod
    def _parse_response(content: str, file_name: str, file_id: str, resume_text: str) -> ResumeResult:
        cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)
        candidate_name = str(data.get("candidate_name") or "").strip()
        if not candidate_name or candidate_name.lower() in {"unknown", "n/a", "null"}:
            candidate_name = "Unknown"
        decision_value = str(data.get("decision") or "").strip().upper()
        if decision_value not in {Decision.ACCEPT.value, Decision.REJECT.value}:
            decision_value = Decision.REJECT.value
        try:
            match_score = float(data.get("match_score", 0))
        except (TypeError, ValueError):
            match_score = 0.0

        return ResumeResult(
            file_id=file_id,
            file_name=file_name,
            candidate_name=candidate_name,
            decision=Decision(decision_value),
            skills_summary=data.get("skills_summary", data.get("skills", "")),
            education_summary=data.get("education_summary", data.get("education", "")),
            experience_summary=data.get("experience_summary", data.get("experience", "")),
            reason=data.get("reason", ""),
            match_score=match_score,
            education_level=data.get("education_level"),
            education_relevant=data.get("education_relevant"),
            experience_years=data.get("experience_years"),
            experience_relevant=data.get("experience_relevant"),
            skills_match=data.get("skills_match"),
        )
