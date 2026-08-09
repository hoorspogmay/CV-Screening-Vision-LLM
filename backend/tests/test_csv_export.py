from app.csv_export import results_to_csv
from app.schemas import Decision, ResumeResult


def test_results_to_csv_includes_job_role_column() -> None:
    results = [
        ResumeResult(
            file_id="1",
            file_name="candidate.pdf",
            candidate_name="Jane Doe",
            decision=Decision.ACCEPT,
            summary="Strong fit",
            match_score=90,
            routed_job_titles=["AI Engineer"],
        )
    ]

    csv_content = results_to_csv(results)

    assert "Job Role" in csv_content
    assert "AI Engineer" in csv_content
