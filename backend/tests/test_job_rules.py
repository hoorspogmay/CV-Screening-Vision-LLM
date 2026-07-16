from app.schemas import Decision
from app.job_requirements import JobRequirements
from app.job_rules import apply_business_rules


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
