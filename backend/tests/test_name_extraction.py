from app.services.providers.groq_provider import GroqProvider


def test_extract_candidate_name_from_resume_text() -> None:
    resume_text = """
    John Doe
    Senior Software Engineer
    john.doe@example.com
    """

    candidate_name = GroqProvider._infer_candidate_name(resume_text)

    assert candidate_name == "John Doe"


def test_extract_candidate_name_returns_unknown_when_absent() -> None:
    candidate_name = GroqProvider._infer_candidate_name("No personal details here")

    assert candidate_name == "Unknown"
