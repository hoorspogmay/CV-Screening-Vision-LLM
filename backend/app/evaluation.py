"""Standalone evaluation utilities for comparing predictions with a ground-truth CSV."""
from __future__ import annotations

import csv
from collections import defaultdict
from io import StringIO
from typing import BinaryIO, TextIO

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


def _read_decisions(csv_source: TextIO | BinaryIO) -> list[str]:
    reader = csv.DictReader(csv_source)
    if reader.fieldnames is None:
        raise ValueError("CSV file is missing a header row.")
    if "decision" not in reader.fieldnames:
        raise ValueError("CSV file must include a 'decision' column.")

    decisions: list[str] = []
    for row in reader:
        decision = (row.get("decision") or "").strip().upper()
        if decision:
            decisions.append(decision)
    return decisions


def evaluate_predictions(
    predictions_source: TextIO | BinaryIO,
    ground_truth_source: TextIO | BinaryIO,
) -> dict[str, object]:
    """Compare predicted decisions with ground truth labels and return evaluation metrics."""
    predictions = _read_decisions(predictions_source)
    ground_truth = _read_decisions(ground_truth_source)

    if not predictions:
        raise ValueError("The predictions CSV contains no decision rows.")
    if not ground_truth:
        raise ValueError("The ground-truth CSV contains no decision rows.")
    if len(predictions) != len(ground_truth):
        raise ValueError(
            f"Row count mismatch: predictions has {len(predictions)} rows, "
            f"ground truth has {len(ground_truth)} rows."
        )

    labels = sorted({*predictions, *ground_truth})

    confusion_matrix: dict[str, dict[str, int]] = {label: defaultdict(int) for label in labels}
    for predicted, actual in zip(predictions, ground_truth):
        confusion_matrix[actual][predicted] += 1

    total_correct = sum(confusion_matrix[label][label] for label in labels)
    accuracy = total_correct / len(predictions)

    precision_values: list[float] = []
    recall_values: list[float] = []
    f1_values: list[float] = []

    for label in labels:
        tp = confusion_matrix[label][label]
        fp = sum(confusion_matrix[other][label] for other in labels if other != label)
        fn = sum(confusion_matrix[label][other] for other in labels if other != label)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        precision_values.append(precision)
        recall_values.append(recall)
        f1_values.append(f1)

    n = len(labels)
    return {
        "accuracy": round(accuracy, 4),
        "precision": round(sum(precision_values) / n, 4),
        "recall": round(sum(recall_values) / n, 4),
        "f1_score": round(sum(f1_values) / n, 4),
        "confusion_matrix": {label: dict(confusion_matrix[label]) for label in labels},
    }


@router.post("/compare")
async def compare_predictions(
    predictions_file: UploadFile = File(...),
    ground_truth_file: UploadFile = File(...),
) -> dict[str, object]:
    """
    Compare a predictions CSV against an uploaded ground-truth CSV.

    Both files must:
      - be UTF-8 encoded
      - contain a header row with a 'decision' column
      - have the same number of data rows
    """
    if not predictions_file.filename:
        raise HTTPException(status_code=400, detail="A predictions CSV file is required.")
    if not ground_truth_file.filename:
        raise HTTPException(status_code=400, detail="A ground-truth CSV file is required.")

    try:
        predictions_bytes = await predictions_file.read()
        ground_truth_bytes = await ground_truth_file.read()

        predictions_stream = StringIO(predictions_bytes.decode("utf-8"))
        ground_truth_stream = StringIO(ground_truth_bytes.decode("utf-8"))

        return evaluate_predictions(predictions_stream, ground_truth_stream)

    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV files must be UTF-8 encoded.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc