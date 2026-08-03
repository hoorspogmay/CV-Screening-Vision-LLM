"""Standalone evaluation utilities for comparing predictions with a ground-truth CSV."""
from __future__ import annotations

import csv
from collections import defaultdict
from io import StringIO
from typing import BinaryIO, TextIO

from pathlib import Path

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


def evaluate_predictions(predictions_source: TextIO | BinaryIO, ground_truth_source: TextIO | BinaryIO) -> dict[str, object]:
    """Compare predicted decisions with ground truth labels and return evaluation metrics."""
    predictions = _read_decisions(predictions_source)
    ground_truth = _read_decisions(ground_truth_source)

    if len(predictions) != len(ground_truth):
        raise ValueError("Prediction and ground-truth CSV files must contain the same number of rows.")

    labels = sorted({*predictions, *ground_truth})
    if not labels:
        raise ValueError("No decision values were found in the provided CSV files.")

    confusion_matrix: dict[str, dict[str, int]] = {label: defaultdict(int) for label in labels}
    for predicted, actual in zip(predictions, ground_truth):
        confusion_matrix[actual][predicted] += 1

    total_correct = sum(confusion_matrix[label][label] for label in labels)
    accuracy = total_correct / len(predictions) if predictions else 0.0

    precision_values: list[float] = []
    recall_values: list[float] = []
    f1_values: list[float] = []

    for label in labels:
        true_positives = confusion_matrix[label][label]
        false_positives = sum(confusion_matrix[other][label] for other in labels if other != label)
        false_negatives = sum(confusion_matrix[label][other] for other in labels if other != label)

        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 0.0
        f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        precision_values.append(precision)
        recall_values.append(recall)
        f1_values.append(f1_score)

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(sum(precision_values) / len(precision_values), 4) if precision_values else 0.0,
        "recall": round(sum(recall_values) / len(recall_values), 4) if recall_values else 0.0,
        "f1_score": round(sum(f1_values) / len(f1_values), 4) if f1_values else 0.0,
        "confusion_matrix": {label: dict(confusion_matrix[label]) for label in labels},
    }


@router.post("/compare")
async def compare_predictions(
    predictions_file: UploadFile = File(...),
    ground_truth_file: UploadFile | None = File(default=None),
) -> dict[str, object]:
    """Compare uploaded prediction CSV files against the backend ground-truth reference."""
    if predictions_file.filename is None:
        raise HTTPException(status_code=400, detail="A prediction CSV file is required.")

    try:
        predictions_bytes = await predictions_file.read()
        predictions_stream = StringIO(predictions_bytes.decode("utf-8"))

        if ground_truth_file is not None and ground_truth_file.filename:
            ground_truth_bytes = await ground_truth_file.read()
            ground_truth_stream = StringIO(ground_truth_bytes.decode("utf-8"))
        else:
            ground_truth_path = Path(__file__).resolve().parent.parent / "ground_truth_master.csv"
            with ground_truth_path.open("r", encoding="utf-8", newline="") as handle:
                ground_truth_stream = StringIO(handle.read())

        return evaluate_predictions(predictions_stream, ground_truth_stream)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV files must be UTF-8 encoded.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
