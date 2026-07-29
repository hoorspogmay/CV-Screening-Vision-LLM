from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class TokenCSVLogger:
    """Standalone CSV helper for token-usage logging.

    This keeps the token logging feature isolated from the existing screening
    workflow. It can be connected later to the current export pipeline without
    changing the existing CSV export code.
    """

    def __init__(self, csv_path: Optional[str | Path] = None) -> None:
        self.csv_path = Path(csv_path or Path(__file__).resolve().parent.parent / "token_usage_log.csv")
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_header()
        self._migrate_legacy_rows()

    @staticmethod
    def fieldnames() -> list[str]:
        return [
            "resume_filename",
            "provider",
            "model_name",
            "api_key_identifier",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "processing_time_seconds",
        ]

    def _ensure_header(self) -> None:
        if self.csv_path.exists():
            return

        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fieldnames())
            writer.writeheader()

    def append(self, record: Mapping[str, Any]) -> None:
        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fieldnames())
            writer.writerow(self._normalize_record(record))

    def _migrate_legacy_rows(self) -> None:
        legacy_path = Path(__file__).resolve().parent / "token_usage_log.csv"
        if not legacy_path.exists() or legacy_path.resolve() == self.csv_path.resolve():
            return

        with legacy_path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        if not rows:
            legacy_path.unlink(missing_ok=True)
            return

        existing_rows: set[tuple[str, ...]] = set()
        if self.csv_path.exists() and self.csv_path.stat().st_size > 0:
            with self.csv_path.open("r", newline="", encoding="utf-8") as handle:
                existing_rows = {tuple(row[field] for field in self.fieldnames()) for row in csv.DictReader(handle)}

        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fieldnames())
            for row in rows:
                normalized = self._normalize_record(row)
                row_key = tuple(str(normalized.get(field, "")) for field in self.fieldnames())
                if row_key in existing_rows:
                    continue
                writer.writerow(normalized)
                existing_rows.add(row_key)

        legacy_path.unlink(missing_ok=True)

    def _normalize_record(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "resume_filename": record.get("resume_filename", ""),
            "provider": record.get("provider", ""),
            "model_name": record.get("model_name", ""),
            "api_key_identifier": record.get("api_key_identifier", ""),
            "prompt_tokens": self._format_value(record.get("prompt_tokens")),
            "completion_tokens": self._format_value(record.get("completion_tokens")),
            "total_tokens": self._format_value(record.get("total_tokens")),
            "processing_time_seconds": self._format_value(record.get("processing_time_seconds")),
        }

    @staticmethod
    def _format_value(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}"
        return value

    def extend_existing_row(self, existing_row: Mapping[str, Any], token_record: Mapping[str, Any]) -> Dict[str, Any]:
        """Helper for future integration into an existing export row."""
        row = dict(existing_row)
        for field in self.fieldnames():
            row[f"token_{field}"] = token_record.get(field)
        return row
