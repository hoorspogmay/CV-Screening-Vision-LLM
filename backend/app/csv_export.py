"""CSV export helpers for the screening job results."""
import csv
import io

from app.schemas import ResumeResult

CSV_COLUMNS = [
    "Candidate Name",
    "File Name",
    "Decision",
    "Summary",
    "Match Score",
    "Education Level",
    "Experience Years",
    "Skills Match",
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
            result.summary,
            result.match_score,
            result.education_level or "",
            result.experience_years if result.experience_years is not None else "",
            result.skills_match if result.skills_match is not None else "",
        ])

    return buffer.getvalue()