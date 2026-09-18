# ChainC2 Sentinel — Evaluation Artifact Exporter
"""Exports processed research artifacts from raw evaluation JSON to /results/detection/.

Adheres to university research repository requirements by producing:
1. results/detection/evaluation_summary.json — structured high-level summary
2. results/detection/detection_metrics.csv — compact metrics table for dashboards
3. results/detection/experiment_results.csv — granular per-experiment history
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("chainc2_sentinel.evaluation.exporter")


def export_results_artifacts(
    source_json_path: str = "data/evaluation/evaluation_results.json",
    output_dir: str = "results/detection",
) -> dict[str, str]:
    """Generate processed research artifacts in /results/detection/ from evaluation results JSON.

    All generated values are strictly derived from the source evaluation JSON;
    zero values are fabricated or altered.

    Args:
        source_json_path: Path to the source evaluation JSON.
        output_dir: Directory where processed research artifacts will be written.

    Returns:
        Dictionary mapping artifact type to its generated file path.
    """
    src_path = Path(source_json_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Source evaluation file not found: {source_json_path}")

    with open(src_path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    metrics = data.get("metrics", {})
    experiments = data.get("experiments", [])
    metric_formulas = metrics.get("metric_formulas", {})

    # 1. Generate evaluation_summary.json
    summary_path = out_path / "evaluation_summary.json"
    summary_content = {
        "evaluation_id": data.get("evaluation_id"),
        "created_at": data.get("created_at"),
        "rule_id": data.get("rule_id"),
        "rule_version": data.get("rule_version"),
        "scenario_counts": data.get("scenario_counts", {}),
        "total_experiments": metrics.get("total_experiments"),
        "successful_runs": metrics.get("successful_runs"),
        "failed_runs": metrics.get("failed_runs"),
        "experiment_success_rate": metrics.get("experiment_success_rate"),
        "true_positives": metrics.get("true_positives"),
        "true_negatives": metrics.get("true_negatives"),
        "false_positives": metrics.get("false_positives"),
        "false_negatives": metrics.get("false_negatives"),
        "ground_truth_positives": metrics.get("ground_truth_positives"),
        "ground_truth_negatives": metrics.get("ground_truth_negatives"),
        "detection_rate": metrics.get("detection_rate"),
        "false_positive_rate": metrics.get("false_positive_rate"),
        "precision": metrics.get("precision"),
        "true_negative_rate": metrics.get("true_negative_rate"),
        "accuracy": metrics.get("accuracy"),
        "f1_score": metrics.get("f1_score"),
        "detection_latency": {
            "average_ms": metrics.get("average_detection_latency_ms"),
            "min_ms": metrics.get("min_detection_latency_ms"),
            "max_ms": metrics.get("max_detection_latency_ms"),
        },
        "metric_formulas": metric_formulas,
        "research_limitation": data.get(
            "research_disclaimer",
            "Laboratory evaluation result only. Measures detectability of predefined synthetic C2-like "
            "behavioral sequences under controlled conditions. Does not assert real-world malware detection "
            "capabilities, threat actor attribution, or universal blockchain security efficacy."
        ),
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_content, f, indent=2)

    # 2. Generate detection_metrics.csv
    metrics_csv_path = out_path / "detection_metrics.csv"
    metric_rows = [
        ("total_experiments", metrics.get("total_experiments"), "count", "Total evaluated scenario runs"),
        ("successful_runs", metrics.get("successful_runs"), "count", "Successful executions without error"),
        ("failed_runs", metrics.get("failed_runs"), "count", "Failed executions"),
        ("experiment_success_rate", metrics.get("experiment_success_rate"), "ratio", "successful_runs / total_experiments"),
        ("ground_truth_positives", metrics.get("ground_truth_positives"), "count", "TP + FN (Scenario B)"),
        ("ground_truth_negatives", metrics.get("ground_truth_negatives"), "count", "TN + FP (Scenario A)"),
        ("true_positives", metrics.get("true_positives"), "count", "Synthetic C2 correctly triggered"),
        ("true_negatives", metrics.get("true_negatives"), "count", "Benign control correctly not triggered"),
        ("false_positives", metrics.get("false_positives"), "count", "Benign control erroneously triggered"),
        ("false_negatives", metrics.get("false_negatives"), "count", "Synthetic C2 missed"),
        ("detection_rate", metrics.get("detection_rate"), "rate", "TP / (TP + FN) [Recall/Sensitivity]"),
        ("false_positive_rate", metrics.get("false_positive_rate"), "rate", "FP / (FP + TN) [Fall-out]"),
        ("precision", metrics.get("precision"), "rate", "TP / (TP + FP) [Positive Predictive Value]"),
        ("true_negative_rate", metrics.get("true_negative_rate"), "rate", "TN / (TN + FP) [Specificity]"),
        ("accuracy", metrics.get("accuracy"), "rate", "(TP + TN) / total_experiments"),
        ("f1_score", metrics.get("f1_score"), "score", "2 * (Precision * Recall) / (Precision + Recall)"),
        ("average_detection_latency_ms", metrics.get("average_detection_latency_ms"), "ms", "Mean detection processing duration"),
        ("min_detection_latency_ms", metrics.get("min_detection_latency_ms"), "ms", "Minimum detection processing duration"),
        ("max_detection_latency_ms", metrics.get("max_detection_latency_ms"), "ms", "Maximum detection processing duration"),
    ]

    with open(metrics_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric_name", "value", "unit", "description_or_formula"])
        for row in metric_rows:
            writer.writerow(row)

    # 3. Generate experiment_results.csv
    exp_csv_path = out_path / "experiment_results.csv"
    fieldnames = [
        "experiment_id",
        "run_id",
        "scenario_id",
        "ground_truth",
        "classification",
        "triggered",
        "detection_status",
        "total_events",
        "stages_observed",
        "detection_latency_ms",
        "execution_status",
        "timestamp_start",
        "timestamp_end",
        "rule_id",
        "rule_version",
        "correlated_sequence_id",
    ]

    with open(exp_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for exp in experiments:
            stages_str = ";".join(exp.get("stages_observed", []))
            writer.writerow({
                "experiment_id": exp.get("experiment_id"),
                "run_id": exp.get("run_id"),
                "scenario_id": exp.get("scenario_id"),
                "ground_truth": exp.get("ground_truth"),
                "classification": exp.get("classification"),
                "triggered": exp.get("triggered"),
                "detection_status": exp.get("detection_status"),
                "total_events": exp.get("total_events"),
                "stages_observed": stages_str,
                "detection_latency_ms": exp.get("detection_latency_ms"),
                "execution_status": exp.get("execution_status"),
                "timestamp_start": exp.get("timestamp_start"),
                "timestamp_end": exp.get("timestamp_end"),
                "rule_id": exp.get("rule_id"),
                "rule_version": exp.get("rule_version"),
                "correlated_sequence_id": exp.get("correlated_sequence_id"),
            })

    logger.info("Exported evaluation artifacts to %s", output_dir)

    return {
        "summary_json": str(summary_path),
        "metrics_csv": str(metrics_csv_path),
        "experiments_csv": str(exp_csv_path),
    }


if __name__ == "__main__":
    export_results_artifacts()
