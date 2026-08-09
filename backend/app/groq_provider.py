"""
Groq provider — default AI backend for the app.

Uses Groq's OpenAI-compatible chat completions endpoint directly over
httpx so the app has no hard dependency on the groq SDK.
"""
import asyncio
import json
import logging
import re
import time

import httpx

from app.config import get_settings
from app.job_extraction_prompt import EXTRACTION_PROMPT
from app.job_extraction_types import JobExtraction, parse_job_extraction_response
from app.schemas import Decision, ResumeResult
from app.job_requirements import JobRequirements
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.providers_base import AIProvider
from app.decision_utils import (
    classify_by_match_score,
    infer_experience_years,
    parse_optional_int,
)
from app.token_logger import GroqProviderAdapter, TokenUsageLogger, safe_record_usage

logger = logging.getLogger(__name__)
token_logger = TokenUsageLogger()


class GroqProvider(AIProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.groq_api_key
        self._model = settings.groq_model
        self._url = settings.groq_api_url
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
        start_time = time.time()  # must use time.time() — perf_counter() breaks token_logger duration calc
        prompt_text = build_user_prompt(resume_text, requirements, recruitment_document_text)

        if not self._api_key:
            logger.error("Groq API key is not configured. Set GROQ_API_KEY in your .env file.")
            safe_record_usage(
                token_logger,
                resume_filename=file_name,
                provider_adapter=GroqProviderAdapter(api_key_identifier="Groq"),
                response=None,
                prompt_text=prompt_text,
                processing_started_at=start_time,
                api_key_identifier="Groq",
                model_name=self._model,
            )
            raise RuntimeError("GROQ_API_KEY is not configured. Set it in your .env file.")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text},
            ],
            "temperature": 0.0,
            "max_tokens": 300,
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
                    logger.info(
                        "Groq API call starting | file=%s | model=%s | attempt=%d/%d",
                        file_name, self._model, attempt, self._max_retries,
                    )
                    response = await client.post(self._url, headers=headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                    logger.info(
                        "Groq API call succeeded | file=%s | attempt=%d/%d",
                        file_name, attempt, self._max_retries,
                    )
                    safe_record_usage(
                        token_logger,
                        resume_filename=file_name,
                        provider_adapter=GroqProviderAdapter(api_key_identifier="Groq"),
                        response=body,
                        prompt_text=prompt_text,
                        processing_started_at=start_time,
                        api_key_identifier="Groq",
                        model_name=self._model,
                    )
                    return self._parse_response(content, file_name, file_id, resume_text, requirements)
                except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
                    logger.warning(
                        "Groq call failed for %s (attempt %d/%d): %s",
                        file_name, attempt, self._max_retries, exc,
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * attempt)

        logger.error(
            "Groq evaluation failed for %s after %d attempts. Last error: %s",
            file_name, self._max_retries, last_error,
        )
        safe_record_usage(
            token_logger,
            resume_filename=file_name,
            provider_adapter=GroqProviderAdapter(api_key_identifier="Groq"),
            response=None,
            prompt_text=prompt_text,
            processing_started_at=start_time,
            api_key_identifier="Groq",
            model_name=self._model,
        )
        raise RuntimeError(f"Groq evaluation failed after {self._max_retries} attempts: {last_error}")

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
            candidate_name = GroqProvider._infer_candidate_name(resume_text)

        try:
            match_score = float(data.get("match_score", 0))
        except (TypeError, ValueError):
            match_score = 0.0

        decision_value = str(data.get("decision") or "").strip().upper()
        if decision_value not in {Decision.ACCEPT.value, Decision.REJECT.value, Decision.DOUBTFUL.value}:
            summary = str(data.get("summary") or "")
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
            candidate_name=candidate_name or "Unknown",
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
                    return parse_job_extraction_response(content)
                except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValueError) as exc:
                    last_error = exc
                    logger.warning(
                        "Groq job extraction call failed for %s (attempt %d/%d): %s",
                        self._api_key[:8] + "...",
                        attempt,
                        self._max_retries,
                        exc,
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * attempt)

        raise RuntimeError(f"Groq job extraction failed after {self._max_retries} attempts: {last_error}")

    @staticmethod
    def _infer_candidate_name(resume_text: str) -> str:
        if not resume_text:
            return "Unknown"

        role_keywords = (
            "software engineer", "developer", "architect", "manager",
            "coordinator", "analyst", "administrator", "support",
            "specialist", "consultant", "engineer", "director",
            "lead", "senior", "junior", "intern", "team", "it",
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
                "summary", "skills", "education", "experience",
                "professional summary", "objective", "profile",
                "work experience", "contact",
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
                if any(word.lower() in {
                    "the", "and", "for", "resume", "skills", "experience",
                    "education", "summary", "here", "details", "personal", "no",
                } for word in words):
                    continue
                if any(char.isdigit() for char in candidate):
                    continue
                if candidate.endswith((".", "!", "?", ":")):
                    continue
                return candidate

        return "Unknown"