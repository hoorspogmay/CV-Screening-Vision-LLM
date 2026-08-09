from app.job_requirements import JobOpeningProfile, JobRequirements
from app.resume_service import _route_resume_to_job_profiles


def test_routes_to_single_best_profile_when_one_job_is_a_clear_match() -> None:
    profiles = [
        JobOpeningProfile(
            title="Data Analyst",
            requirements=JobRequirements(job_role="Data Analyst", required_skills=["Python", "SQL"]),
        ),
        JobOpeningProfile(
            title="Product Manager",
            requirements=JobRequirements(job_role="Product Manager", required_skills=["Roadmapping"]),
        ),
    ]

    selected_profiles, reject = _route_resume_to_job_profiles(
        "Experienced data analyst with Python, SQL, and dashboard reporting skills.",
        profiles,
    )

    assert reject is False
    assert [profile.title for profile in selected_profiles] == ["Data Analyst"]


def test_routes_to_top_two_profiles_when_multiple_jobs_are_strong_matches() -> None:
    profiles = [
        JobOpeningProfile(
            title="Software Engineer",
            requirements=JobRequirements(job_role="Software Engineer", required_skills=["Python", "Django"]),
        ),
        JobOpeningProfile(
            title="Backend Engineer",
            requirements=JobRequirements(job_role="Backend Engineer", required_skills=["Python", "FastAPI", "PostgreSQL"]),
        ),
        JobOpeningProfile(
            title="Frontend Engineer",
            requirements=JobRequirements(job_role="Frontend Engineer", required_skills=["React", "TypeScript"]),
        ),
    ]

    selected_profiles, reject = _route_resume_to_job_profiles(
        "Backend-focused engineer with Python, FastAPI, PostgreSQL, and cloud deployment experience.",
        profiles,
    )

    assert reject is False
    assert len(selected_profiles) == 2
    assert {profile.title for profile in selected_profiles} == {"Software Engineer", "Backend Engineer"}


def test_rejects_when_no_job_profile_is_a_good_match() -> None:
    profiles = [
        JobOpeningProfile(
            title="Data Analyst",
            requirements=JobRequirements(job_role="Data Analyst", required_skills=["Python", "SQL"]),
        ),
        JobOpeningProfile(
            title="Product Manager",
            requirements=JobRequirements(job_role="Product Manager", required_skills=["Roadmapping"]),
        ),
    ]

    selected_profiles, reject = _route_resume_to_job_profiles(
        "Candidate has extensive experience in hospitality and customer service with no technical background.",
        profiles,
    )

    assert reject is True
    assert selected_profiles == []
