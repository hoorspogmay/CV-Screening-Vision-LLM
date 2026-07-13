"""CSV export helpers and folder export helpers for the screening job results."""
import csv
import io
import zipfile
from pathlib import Path

from app.models.schemas import Decision, ResumeResult

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


def build_export_archive(results: list[ResumeResult], file_map: dict[str, Path]) -> bytes:
    """Create a ZIP archive with accepted/rejected PDFs grouped into folders."""
    csv_content = results_to_csv(results)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("results.csv", csv_content)
        for result in results:
            if result.error:
                continue
            source_path = None
            for key in (result.file_name, Path(result.file_name).name):
                candidate = file_map.get(key)
                if candidate is not None and candidate.exists():
                    source_path = candidate
                    break
            if source_path is None or not source_path.exists():
                continue
            if source_path.suffix.lower() != ".pdf":
                continue
            folder_name = "accepted" if result.decision == Decision.ACCEPT else "rejected"
            archive.write(source_path, arcname=f"{folder_name}/{source_path.name}")
    return buffer.getvalue()
