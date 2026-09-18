# ChainC2 Sentinel — Tests for Processed Evaluation Artifacts
"""Verifies that processed research artifacts in results/detection/ faithfully

correspond to the source evaluation dataset in data/evaluation/evaluation_results.json.
Ensures no values are fabricated, missing, or corrupted.
"""

import csv
import json
from pathlib import Path

import pytest

from src.evaluation.exporter import export_results_artifacts

SOURCE_JSON_PATH = "data/evaluation/evaluation_results.json"
RESULTS_DIR = "results/detection"


@pytest.fixture(scope="module")
def source_data() -> dict:
    """Load raw source of truth evaluation JSON."""
    src_file = Path(SOURCE_JSON_PATH)
    assert src_file.exists(), f"Missing required source dataset: {SOURCE_JSON_PATH}"
    with open(src_file, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.unit
class TestEvaluationArtifacts:
    """Test suite for research artifact export integrity."""

    def test_evaluation_artifacts_exist(self):
        """All three required university research artifacts exist in results/detection/."""
        summary_file = Path(RESULTS_DIR) / "evaluation_summary.json"
        metrics_file = Path(RESULTS_DIR) / "detection_metrics.csv"
        experiments_file = Path(RESULTS_DIR) / "experiment_results.csv"

        assert summary_file.exists(), f"Missing {summary_file}"
        assert metrics_file.exists(), f"Missing {metrics_file}"
        assert experiments_file.exists(), f"Missing {experiments_file}"

    def test_summary_json_matches_source(self, source_data: dict):
        """evaluation_summary.json fields and metrics match source evaluation_results.json."""
        summary_file = Path(RESULTS_DIR) / "evaluation_summary.json"
        with open(summary_file, "r", encoding="utf-8") as f:
            summary = json.load(f)

        src_metrics = source_data["metrics"]

        assert summary["evaluation_id"] == source_data["evaluation_id"]
        assert summary["rule_id"] == source_data["rule_id"]
        assert summary["rule_version"] == source_data["rule_version"]
        assert summary["scenario_counts"] == source_data["scenario_counts"]

        # Metric fidelity
        assert summary["total_experiments"] == src_metrics["total_experiments"]
        assert summary["successful_runs"] == src_metrics["successful_runs"]
        assert summary["failed_runs"] == src_metrics["failed_runs"]
        assert summary["true_positives"] == src_metrics["true_positives"]
        assert summary["true_negatives"] == src_metrics["true_negatives"]
        assert summary["false_positives"] == src_metrics["false_positives"]
        assert summary["false_negatives"] == src_metrics["false_negatives"]
        assert summary["detection_rate"] == src_metrics["detection_rate"]
        assert summary["false_positive_rate"] == src_metrics["false_positive_rate"]
        assert summary["precision"] == src_metrics["precision"]
        assert summary["accuracy"] == src_metrics["accuracy"]
        assert summary["f1_score"] == src_metrics["f1_score"]

        # Latency fidelity
        assert summary["detection_latency"]["average_ms"] == src_metrics["average_detection_latency_ms"]
        assert summary["detection_latency"]["min_ms"] == src_metrics["min_detection_latency_ms"]
        assert summary["detection_latency"]["max_ms"] == src_metrics["max_detection_latency_ms"]

        # Research limitation statement present
        assert "research_limitation" in summary
        assert len(summary["research_limitation"]) > 20

    def test_metrics_csv_matches_source(self, source_data: dict):
        """detection_metrics.csv contains 19 metric rows strictly corresponding to source data."""
        metrics_file = Path(RESULTS_DIR) / "detection_metrics.csv"
        src_metrics = source_data["metrics"]

        rows = []
        with open(metrics_file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        assert len(rows) == 19
        metrics_map = {r["metric_name"]: r["value"] for r in rows}

        assert int(metrics_map["total_experiments"]) == src_metrics["total_experiments"]
        assert int(metrics_map["successful_runs"]) == src_metrics["successful_runs"]
        assert int(metrics_map["failed_runs"]) == src_metrics["failed_runs"]
        assert int(metrics_map["true_positives"]) == src_metrics["true_positives"]
        assert int(metrics_map["true_negatives"]) == src_metrics["true_negatives"]
        assert int(metrics_map["false_positives"]) == src_metrics["false_positives"]
        assert int(metrics_map["false_negatives"]) == src_metrics["false_negatives"]
        assert float(metrics_map["detection_rate"]) == src_metrics["detection_rate"]
        assert float(metrics_map["false_positive_rate"]) == src_metrics["false_positive_rate"]
        assert float(metrics_map["precision"]) == src_metrics["precision"]
        assert float(metrics_map["accuracy"]) == src_metrics["accuracy"]
        assert float(metrics_map["f1_score"]) == src_metrics["f1_score"]

    def test_experiment_results_csv_matches_source(self, source_data: dict):
        """experiment_results.csv contains exactly one row per experiment matching source JSON."""
        experiments_file = Path(RESULTS_DIR) / "experiment_results.csv"
        src_experiments = source_data["experiments"]

        rows = []
        with open(experiments_file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        assert len(rows) == len(src_experiments)
        assert len(rows) == 30

        for row, src_exp in zip(rows, src_experiments):
            assert row["experiment_id"] == src_exp["experiment_id"]
            assert row["run_id"] == src_exp["run_id"]
            assert row["scenario_id"] == src_exp["scenario_id"]
            assert row["ground_truth"] == src_exp["ground_truth"]
            assert row["classification"] == src_exp["classification"]
            assert (row["triggered"].lower() == "true") == src_exp["triggered"]
            assert row["detection_status"] == src_exp["detection_status"]
            assert int(row["total_events"]) == src_exp["total_events"]
            assert row["stages_observed"] == ";".join(exp_stages if (exp_stages := src_exp.get("stages_observed", [])) else [])
            assert float(row["detection_latency_ms"]) == src_exp["detection_latency_ms"]
            assert row["execution_status"] == src_exp["execution_status"]

    def test_exporter_custom_output_dir(self, tmp_path: Path):
        """export_results_artifacts operates idempotently and accurately in custom output directories."""
        out_dir = str(tmp_path / "custom_results")
        artifacts = export_results_artifacts(
            source_json_path=SOURCE_JSON_PATH,
            output_dir=out_dir,
        )

        assert Path(artifacts["summary_json"]).exists()
        assert Path(artifacts["metrics_csv"]).exists()
        assert Path(artifacts["experiments_csv"]).exists()

        with open(artifacts["summary_json"], "r", encoding="utf-8") as f:
            custom_summary = json.load(f)
        assert custom_summary["total_experiments"] == 30
