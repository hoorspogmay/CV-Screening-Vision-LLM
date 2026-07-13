"""Google provider wrapper for Gemini-style free models such as google/gemma-4-31b-it:free."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

from app.config import get_settings
from app.models.schemas import Decision, ResumeResult
from app.services.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.providers.base import AIProvider

logger = logging.getLogger(__name__)


class GoogleProvider(AIProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.google_api_key
        self._model = settings.google_model or "google/gemma-4-31b-it:free"
        self._url = settings.google_api_url or "https://generativelanguage.googleapis.com/v1beta/models/" + self._model + ":generateContent"
        self._timeout = settings.ai_request_timeout_seconds
        self._max_retries = settings.ai_max_retries
        self._backoff = settings.ai_retry_backoff_seconds

    async def evaluate_resume(self, resume_text: str, file_name: str, file_id: str) -> ResumeResult:
        if not self._api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured.")

        payload = {
            "contents": [{"parts": [{"text": f"System prompt: {SYSTEM_PROMPT}\n\nUser prompt: {build_user_prompt(resume_text)}"}]}],
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
                    return self._parse_response(content, file_name, file_id, resume_text)
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

        raise RuntimeError(f"Google evaluation failed after {self._max_retries} attempts: {last_error}")

    @staticmethod
    def _parse_response(content: str, file_name: str, file_id: str, resume_text: str) -> ResumeResult:
        cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)
        decision_raw = str(data.get("decision", "")).strip().upper()
        decision = Decision.ACCEPT if decision_raw == "ACCEPT" else Decision.REJECT
        candidate_name = str(data.get("candidate_name") or "").strip()
        if not candidate_name or candidate_name.lower() in {"unknown", "n/a", "null"}:
            candidate_name = "Unknown"
        return ResumeResult(
            file_id=file_id,
            file_name=file_name,
            candidate_name=candidate_name,
            decision=decision,
            skills_summary=data.get("skills", ""),
            education_summary=data.get("education", ""),
            experience_summary=data.get("experience", ""),
            reason=data.get("reason", ""),
        )
