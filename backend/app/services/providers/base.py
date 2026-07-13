"""
Abstract interface every AI provider must implement.

Adding a new provider (Gemini, OpenRouter, Together AI, Cerebras, OpenAI...)
means creating one class here that implements `evaluate_resume` and
registering it in `services/ai_provider.py`. Nothing else in the app
needs to know which provider is active.
"""
from abc import ABC, abstractmethod

from app.models.schemas import ResumeResult


class AIProvider(ABC):
    """Contract for a resume-screening AI backend."""

    @abstractmethod
    async def evaluate_resume(self, resume_text: str, file_name: str, file_id: str) -> ResumeResult:
        """
        Send resume text to the LLM and return a structured ResumeResult.

        Implementations are responsible for:
          - building the prompt
          - calling the provider's API
          - parsing the response into the ACCEPT/REJECT + summaries shape
          - retrying on transient failures
        Any unrecoverable failure should raise an exception; the caller
        (resume_service) turns that into a failed ResumeResult so one bad
        resume never stops the batch.
        """
        raise NotImplementedError
