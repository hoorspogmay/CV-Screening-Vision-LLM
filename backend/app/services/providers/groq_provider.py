"""
Groq provider — default AI backend for the app.

Uses Groq's OpenAI-compatible chat completions endpoint directly over
httpx so the app has no hard dependency on the groq SDK.
"""
import asyncio
import json
import logging
import re

import httpx

from app.config import get_settings
from app.models.schemas import Decision, ResumeResult
from app.services.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.providers.base import AIProvider

logger = logging.getLogger(__name__)


class GroqProvider(AIProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.groq_api_key
        self._model = settings.groq_model
        self._url = settings.groq_api_url
        self._timeout = settings.ai_request_timeout_seconds
        self._max_retries = settings.ai_max_retries
        self._backoff = settings.ai_retry_backoff_seconds

    async def evaluate_resume(self, resume_text: str, file_name: str, file_id: str) -> ResumeResult:
        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY is not configured. Set it in your .env file.")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(resume_text)},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(self._url, headers=headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                    return self._parse_response(content, file_name, file_id, resume_text)
                except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
                    logger.warning(
                        "Groq call failed for %s (attempt %d/%d): %s",
                        file_name, attempt, self._max_retries, exc,
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * attempt)

        raise RuntimeError(f"Groq evaluation failed after {self._max_retries} attempts: {last_error}")

    @staticmethod
    def _parse_response(content: str, file_name: str, file_id: str, resume_text: str) -> ResumeResult:
        cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)

        decision_raw = str(data.get("decision", "")).strip().upper()
        decision = Decision.ACCEPT if decision_raw == "ACCEPT" else Decision.REJECT

        candidate_name = str(data.get("candidate_name") or "").strip()
        if not candidate_name or candidate_name.lower() in {"unknown", "n/a", "null"}:
            candidate_name = GroqProvider._infer_candidate_name(resume_text)

        return ResumeResult(
            file_id=file_id,
            file_name=file_name,
            candidate_name=candidate_name or "Unknown",
            decision=decision,
            skills_summary=data.get("skills", ""),
            education_summary=data.get("education", ""),
            experience_summary=data.get("experience", ""),
            reason=data.get("reason", ""),
        )

    @staticmethod
    def _infer_candidate_name(resume_text: str) -> str:
        if not resume_text:
            return "Unknown"

        role_keywords = (
            "software engineer",
            "developer",
            "architect",
            "manager",
            "coordinator",
            "analyst",
            "administrator",
            "support",
            "specialist",
            "consultant",
            "engineer",
            "director",
            "lead",
            "senior",
            "junior",
            "intern",
            "team",
            "it",
        )

        for raw_line in resume_text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue

            line = line.replace("\u00a0", " ").strip()
            if not line:
                continue

            lowered = line.lower()
            if lowered.startswith(("email", "phone", "address", "linkedin", "github", "portfolio", "website")):
                continue
            if lowered in {
                "summary",
                "skills",
                "education",
                "experience",
                "professional summary",
                "objective",
                "profile",
                "work experience",
                "contact",
            }:
                continue
            if line.startswith(("•", "-", "*", "●")):
                continue
            if any(keyword in lowered for keyword in role_keywords) and len(line.split()) <= 4:
                continue

            candidate = re.split(r"\s*[|/•-]\s*", line)[0].strip()
            if candidate.endswith((":", ",")):
                candidate = candidate[:-1].strip()
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if not candidate:
                continue

            if re.fullmatch(r"[A-Z][a-zA-ZÀ-ÖØ-öø-ÿ.'-]+(?:\s+[A-Z][a-zA-ZÀ-ÖØ-öø-ÿ.'-]+){1,3}", candidate):
                return candidate
            if re.fullmatch(r"[A-Z][A-Z\s.'-]{2,}", candidate):
                return candidate
            if re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ.'-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ.'-]+){1,3}", candidate):
                words = candidate.split()
                if len(words) < 2:
                    continue
                if any(word.lower() in {"the", "and", "for", "resume", "skills", "experience", "education", "summary", "here", "details", "personal", "no"} for word in words):
                    continue
                if any(char.isdigit() for char in candidate):
                    continue
                if candidate.endswith((".", "!", "?", ":")):
                    continue
                return candidate

        return "Unknown"
