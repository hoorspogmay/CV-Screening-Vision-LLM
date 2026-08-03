from app.schemas import Decision, ResumeResult
from app.job_requirements import JobRequirements, build_job_requirements_from_text
from app.job_rules import apply_business_rules
from app.resume_service import _finalize_result


def test_bachelors_requirement_accepts_equivalent_master_and_rejects_phd_without_overqualification() -> None:
    requirements = JobRequirements(job_role="Software Engineer", required_education="Bachelor's", min_experience=2, max_experience=5)

    accepted_master = apply_business_rules(
        requirements,
        {
            "education_level": "Master",
            "education_relevant": True,
            "experience_years": 3,
            "experience_relevant": True,
            "skills_match": True,
            "reason": "Strong fit",
        },
    )
    rejected_phd = apply_business_rules(
        requirements,
        {
            "education_level": "PhD",
            "education_relevant": True,
            "experience_years": 4,
            "experience_relevant": True,
            "skills_match": True,
            "reason": "Strong fit",
        },
    )

    assert accepted_master[0] == Decision.ACCEPT
    assert rejected_phd[0] == Decision.REJECT


def test_experience_rules_reject_outside_minimum_and_maximum_range() -> None:
    requirements = JobRequirements(job_role="Healthcare Specialist", required_education="Bachelor's", min_experience=2, max_experience=5)

    too_low = apply_business_rules(
        requirements,
        {
            "education_level": "Bachelor",
            "education_relevant": True,
            "experience_years": 1,
            "experience_relevant": True,
            "skills_match": True,
            "reason": "Too little experience",
        },
    )
    too_high = apply_business_rules(
        requirements,
        {
            "education_level": "Bachelor",
            "education_relevant": True,
            "experience_years": 8,
            "experience_relevant": True,
            "skills_match": True,
            "reason": "Too much experience",
        },
    )

    assert too_low[0] == Decision.REJECT
    assert too_high[0] == Decision.REJECT


def test_final_classification_uses_score_bucket_for_doubtful() -> None:
    requirements = JobRequirements(job_role="Software Engineer", required_education="Bachelor's", min_experience=2)
    result = ResumeResult(
        file_id="resume-1",
        file_name="resume.pdf",
        candidate_name="Alice Example",
        decision=Decision.REJECT,
        summary="Candidate is a partial match.",
        match_score=60,
        education_level="Bachelor",
        education_relevant=True,
        experience_years=2,
        experience_relevant=True,
        skills_match=True,
    )

    finalized = _finalize_result(result, requirements)

    assert finalized.decision == Decision.DOUBTFUL


def test_skill_gap_does_not_hard_reject_when_overall_fit_is_good() -> None:
    requirements = JobRequirements(job_role="Software Engineer", required_skills=["Python"])

    decision, _ = apply_business_rules(
        requirements,
        {
            "education_level": "Bachelor",
            "education_relevant": True,
            "experience_years": 3,
            "experience_relevant": True,
            "skills_match": False,
            "reason": "Overall strong fit with one minor skill gap.",
            "skills_summary": "Java, SQL, cloud deployment",
        },
    )

    assert decision != Decision.REJECT


def test_final_classification_uses_custom_thresholds() -> None:
    requirements = JobRequirements(
        job_role="Software Engineer",
        required_education="Bachelor's",
        min_experience=2,
        accept_threshold=75,
        doubtful_threshold=60,
    )
    result = ResumeResult(
        file_id="resume-2",
        file_name="resume-2.pdf",
        candidate_name="Bob Example",
        decision=Decision.REJECT,
        summary="Candidate is a strong match.",
        match_score=75,
        education_level="Bachelor",
        education_relevant=True,
        experience_years=3,
        experience_relevant=True,
        skills_match=True,
    )

    finalized = _finalize_result(result, requirements)

    assert finalized.decision == Decision.ACCEPT


def test_build_job_requirements_from_text_extracts_role_and_skills() -> None:
    spec_text = """
    Job Role: Data Analyst
    Required Education: Bachelor's
    Minimum Experience: 2 years
    Maximum Experience: 5 years
    Required Skills: Python, SQL, Excel
    """

    requirements = build_job_requirements_from_text(spec_text)

    assert requirements.job_role == "Data Analyst"
    assert requirements.required_education == "Bachelor's"
    assert requirements.min_experience == 2
    assert requirements.max_experience == 5
    assert requirements.required_skills == ["Python", "SQL", "Excel"]
