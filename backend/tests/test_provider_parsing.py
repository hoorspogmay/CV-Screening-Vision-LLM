from app.groq_provider import GroqProvider
from app.job_requirements import JobRequirements
from app.schemas import Decision


def test_groq_provider_uses_score_and_thresholds_when_decision_missing() -> None:
    requirements = JobRequirements(accept_threshold=75, doubtful_threshold=60)

    result = GroqProvider._parse_response(
        '{"candidate_name":"Jane Doe","summary":"Strong fit","match_score":75,"education_level":"Bachelor","experience_years":4,"skills_match":true}',
        "resume.pdf",
        "file-1",
        "Resume text",
        requirements,
    )

    assert result.decision == Decision.DOUBTFUL
