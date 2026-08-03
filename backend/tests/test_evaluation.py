from __future__ import annotations

import csv
import io

from app.evaluation import evaluate_predictions


def test_evaluate_predictions_returns_metrics_and_confusion_matrix() -> None:
    predictions_csv = io.StringIO(
        "decision\nACCEPT\nREJECT\nDOUBTFUL\nACCEPT\n"
    )
    ground_truth_csv = io.StringIO(
        "decision\nACCEPT\nACCEPT\nREJECT\nDOUBTFUL\n"
    )

    result = evaluate_predictions(predictions_csv, ground_truth_csv)

    assert result["accuracy"] == 0.75
    assert result["precision"] == 0.75
    assert result["recall"] == 0.75
    assert result["f1_score"] == 0.75
    assert result["confusion_matrix"]["ACCEPT"]["ACCEPT"] == 1
    assert result["confusion_matrix"]["REJECT"]["ACCEPT"] == 1
