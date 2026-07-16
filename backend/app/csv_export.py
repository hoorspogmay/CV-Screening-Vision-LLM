"""CSV export helpers for the screening job results."""
import csv
import io

from app.schemas import ResumeResult

CSV_COLUMNS = [
    "Candidate Name",
    "File Name",
    "Decision",
    "Skills Summary",
    "Education Summary",
    "Experience Summary",
    "Reason",
]


def results_to_csv(results: list[ResumeResult]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)

    for result in results:
        if result.error:
            continue  # failed resumes are excluded from the export
        writer.writerow([
            result.candidate_name,
            result.file_name,
            result.decision.value,
            result.skills_summary,
            result.education_summary,
            result.experience_summary,
            result.reason,
        ])

    return buffer.getvalue()
