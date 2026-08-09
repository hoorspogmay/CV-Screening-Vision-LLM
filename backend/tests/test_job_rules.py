from app.schemas import Decision, ResumeResult
from app.job_requirements import JobOpeningProfile, JobRequirements, build_job_profiles_from_text, build_job_requirements_from_text
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


def test_final_classification_uses_reasoning_when_match_score_missing() -> None:
    requirements = JobRequirements(job_role="Software Engineer", required_education="Bachelor's", min_experience=2)
    result = ResumeResult(
        file_id="resume-3",
        file_name="resume-3.pdf",
        candidate_name="Chris Example",
        decision=Decision.REJECT,
        summary="Strong fit with relevant experience and matching skills. Candidate clearly meets the role requirements.",
        match_score=None,
        education_level="Bachelor",
        education_relevant=True,
        experience_years=3,
        experience_relevant=True,
        skills_match=True,
    )

    finalized = _finalize_result(result, requirements)

    assert finalized.decision == Decision.ACCEPT


def test_business_rules_do_not_reject_unclear_experience_with_positive_summary() -> None:
    requirements = JobRequirements(job_role="Software Engineer", min_experience=2)
    decision, _ = apply_business_rules(
        requirements,
        {
            "education_level": "Bachelor",
            "education_relevant": None,
            "experience_years": None,
            "experience_relevant": None,
            "skills_match": True,
            "reason": "Strong fit with relevant experience and demonstrated required skills.",
            "skills_summary": "Python, SQL, cloud deployment",
        },
    )

    assert decision == Decision.ACCEPT


def test_business_rules_does_not_hard_reject_missing_preferred_skill_without_negative_summary() -> None:
    requirements = JobRequirements(job_role="Software Engineer", required_skills=["Python", "TypeScript"])
    decision, _ = apply_business_rules(
        requirements,
        {
            "education_level": "Bachelor",
            "education_relevant": True,
            "experience_years": 3,
            "experience_relevant": True,
            "skills_match": None,
            "reason": "Strong fit with relevant experience and matching skills, with one preferred frontend skill gap.",
            "skills_summary": "Python, Docker, AWS",
        },
    )

    assert decision != Decision.REJECT


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


def test_final_classification_uses_fixed_thresholds_over_custom_settings() -> None:
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

    assert finalized.decision == Decision.DOUBTFUL


def test_final_score_buckets_are_strictly_enforced() -> None:
    requirements = JobRequirements(job_role="Software Engineer")

    for score, expected in [
        (49, Decision.REJECT),
        (50, Decision.DOUBTFUL),
        (65, Decision.DOUBTFUL),
        (79, Decision.DOUBTFUL),
        (80, Decision.ACCEPT),
        (87, Decision.ACCEPT),
    ]:
        result = ResumeResult(
            file_id=f"resume-{score}",
            file_name=f"resume-{score}.pdf",
            candidate_name="Tester",
            decision=Decision.REJECT,
            summary="",
            match_score=score,
            education_level="Bachelor",
            education_relevant=True,
            experience_years=3,
            experience_relevant=True,
            skills_match=True,
        )
        assert _finalize_result(result, requirements).decision == expected


def test_minimum_experience_is_not_overqualification() -> None:
    requirements = JobRequirements(job_role="Software Engineer", min_experience=3)
    decision, _ = apply_business_rules(
        requirements,
        {
            "education_level": "Bachelor",
            "education_relevant": True,
            "experience_years": 4,
            "experience_relevant": True,
            "skills_match": True,
            "reason": "Strong fit with relevant professional experience.",
            "skills_summary": "Python, SQL",
        },
    )
    assert decision == Decision.ACCEPT


def test_no_minimum_experience_requirement_does_not_penalize_candidate() -> None:
    requirements = JobRequirements(job_role="Software Engineer")
    decision, _ = apply_business_rules(
        requirements,
        {
            "education_level": "Bachelor",
            "education_relevant": True,
            "experience_years": 4,
            "experience_relevant": True,
            "skills_match": True,
            "reason": "Strong fit with relevant professional experience.",
            "skills_summary": "Python, SQL",
        },
    )
    assert decision == Decision.ACCEPT


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


def test_build_job_profiles_from_text_detects_multiple_explicit_job_titles() -> None:
    spec_text = """
    Position 1: AI Engineer
    Required Education: Bachelor's
    Required Skills: Python, Machine Learning

    Position 2: HR Specialist
    Required Education: Bachelor's
    Required Skills: Recruiting, Employee Relations

    Position 3: Financial Analyst
    Required Education: Bachelor's
    Required Skills: Excel, Financial Modeling
    """

    profiles = build_job_profiles_from_text(spec_text)

    assert [profile.title for profile in profiles] == ["AI Engineer", "HR Specialist", "Financial Analyst"]
    assert len(profiles) == 3


def test_build_job_profiles_from_text_ignores_generic_department_headers() -> None:
    spec_text = """
    Department: Artificial Intelligence
    Position: Senior Machine Learning Engineer
    Required Education: Master's
    Required Skills: Python, TensorFlow
    """

    profiles = build_job_profiles_from_text(spec_text)

    assert [profile.title for profile in profiles] == ["Senior Machine Learning Engineer"]
    assert len(profiles) == 1
