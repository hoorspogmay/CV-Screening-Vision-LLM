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


def test_does_not_route_based_on_degree_alone_when_experience_mismatches() -> None:
    profiles = [
        JobOpeningProfile(
            title="Site Engineer",
            requirements=JobRequirements(job_role="Site Engineer", required_skills=["Site supervision", "Health and Safety", "Construction schedule"]),
        ),
        JobOpeningProfile(
            title="Structural Engineer",
            requirements=JobRequirements(job_role="Structural Engineer", required_skills=["Structural design", "Revit", "ETABS"]),
        ),
        JobOpeningProfile(
            title="Quantity Surveyor",
            requirements=JobRequirements(job_role="Quantity Surveyor", required_skills=["Cost estimates", "Tender documentation", "Surveying"]),
        ),
    ]

    selected_profiles, reject = _route_resume_to_job_profiles(
        "Civil engineering graduate with experience in land surveying, quantity take-offs, and site measurement. Familiar with field survey equipment and cost estimating.",
        profiles,
    )

    assert reject is False
    assert [profile.title for profile in selected_profiles] == ["Quantity Surveyor"]


def test_prefers_role_with_required_tools_and_role_specific_responsibilities() -> None:
    profiles = [
        JobOpeningProfile(
            title="Site Engineer",
            requirements=JobRequirements(job_role="Site Engineer", required_skills=["Site supervision", "stakeout", "construction drawings"]),
        ),
        JobOpeningProfile(
            title="Structural Engineer",
            requirements=JobRequirements(job_role="Structural Engineer", required_skills=["Structural analysis", "AutoCAD", "Revit"]),
        ),
    ]

    selected_profiles, reject = _route_resume_to_job_profiles(
        "Experienced in structural analysis, preparing Revit models and AutoCAD drawings for reinforced concrete buildings. Worked closely with design teams on load calculations.",
        profiles,
    )

    assert reject is False
    assert [profile.title for profile in selected_profiles] == ["Structural Engineer"]


def test_rejects_when_only_generic_skills_are_present() -> None:
    profiles = [
        JobOpeningProfile(
            title="Data Analyst",
            requirements=JobRequirements(job_role="Data Analyst", required_skills=["Python", "SQL", "Tableau"]),
        ),
        JobOpeningProfile(
            title="Product Manager",
            requirements=JobRequirements(job_role="Product Manager", required_skills=["Roadmapping", "stakeholder management"]),
        ),
    ]

    selected_profiles, reject = _route_resume_to_job_profiles(
        "Candidate with strong communication, teamwork, and project support skills. Comfortable using Microsoft Office and collaborating with cross-functional teams.",
        profiles,
    )

    assert reject is True
    assert selected_profiles == []


def test_routes_to_none_when_evidence_does_not_support_any_job() -> None:
    profiles = [
        JobOpeningProfile(
            title="Software Engineer",
            requirements=JobRequirements(job_role="Software Engineer", required_skills=["Python", "Django"]),
        ),
        JobOpeningProfile(
            title="Marketing Specialist",
            requirements=JobRequirements(job_role="Marketing Specialist", required_skills=["SEO", "content strategy"]),
        ),
    ]

    selected_profiles, reject = _route_resume_to_job_profiles(
        "Experienced office administrator with bookkeeping and customer service responsibilities. No technical development or marketing strategy work.",
        profiles,
    )

    assert reject is True
    assert selected_profiles == []
