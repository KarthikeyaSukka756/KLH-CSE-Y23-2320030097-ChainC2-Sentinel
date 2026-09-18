# ChainC2 Sentinel — Protection Evaluation Exporter
"""Exports processed research artifacts from raw protection evaluation JSON to results/protection/.

Produces:
1. results/protection/evaluation_summary.json — structured summary with formulas
2. results/protection/protection_metrics.csv — tabular metrics summary
3. results/protection/experiment_results.csv — detailed per-experiment history
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("chainc2_sentinel.protection.evaluation.exporter")


def export_protection_results_artifacts(
    source_json_path: str = "data/evaluation/protection_evaluation.json",
    output_dir: str = "results/protection",
) -> dict[str, str]:
    """Generate processed research artifacts in /results/protection/ from protection evaluation JSON.

    All generated values are strictly derived from the source evaluation JSON;
    zero values are fabricated or altered.

    Args:
        source_json_path: Path to the raw protection evaluation JSON file.
        output_dir: Directory where processed research artifacts will be written.

    Returns:
        Dictionary mapping artifact name to its generated file path.
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
        "rule_id": data.get("rule_id", "RULE-CHAINC2-001"),
        "total_experiments": data.get("total_experiments"),
        "scenario_counts": data.get("scenario_counts", {}),
        "successful_experiments": metrics.get("successful_experiments"),
        "failed_experiments": metrics.get("failed_experiments"),
        "experiment_success_rate": metrics.get("experiment_success_rate"),
        "mitigation_success_rate": metrics.get("mitigation_success_rate"),
        "rpc_blocking_rate": metrics.get("rpc_blocking_rate"),
        "beacon_blocking_rate": metrics.get("beacon_blocking_rate"),
        "process_isolation_success_rate": metrics.get("process_isolation_success_rate"),
        "legitimate_traffic_preservation_rate": metrics.get("legitimate_traffic_preservation_rate"),
        "false_mitigation_rate": metrics.get("false_mitigation_rate"),
        "rollback_success_rate": metrics.get("rollback_success_rate"),
        "evidence_preservation_rate": metrics.get("evidence_preservation_rate"),
        "containment_latency": {
            "min_ms": metrics.get("containment_latency_min_ms"),
            "max_ms": metrics.get("containment_latency_max_ms"),
            "avg_ms": metrics.get("containment_latency_avg_ms"),
            "median_ms": metrics.get("containment_latency_median_ms"),
        },
        "metric_formulas": metric_formulas,
        "research_limitation": data.get(
            "research_disclaimer",
            "Laboratory evaluation result only. Measures containment efficacy, latency, "
            "and baseline preservation of defensive mechanisms under controlled synthetic conditions. "
            "Does not assert real-world malware containment or universal blockchain security efficacy."
        ),
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_content, f, indent=2)

    # 2. Generate protection_metrics.csv
    metrics_csv_path = out_path / "protection_metrics.csv"
    metric_rows = [
        ("total_experiments", metrics.get("total_experiments"), "count", "Total evaluated protection experiments"),
        ("successful_experiments", metrics.get("successful_experiments"), "count", "Successful runs meeting all criteria"),
        ("failed_experiments", metrics.get("failed_experiments"), "count", "Failed runs"),
        ("experiment_success_rate", metrics.get("experiment_success_rate"), "ratio", "successful_experiments / total_experiments"),
        ("scenario_a_runs", metrics.get("scenario_a_runs"), "count", "Benign negative control runs"),
        ("scenario_b_runs", metrics.get("scenario_b_runs"), "count", "Synthetic C2 positive control runs"),
        ("fault_injection_runs", metrics.get("fault_injection_runs"), "count", "Fault injection negative control runs"),
        ("mitigation_success_rate", metrics.get("mitigation_success_rate"), "ratio", "verified_actions / requested_actions (triggered)"),
        ("rpc_blocking_rate", metrics.get("rpc_blocking_rate"), "ratio", "verified_rpc_blocks / runs_with_rpc_filter"),
        ("beacon_blocking_rate", metrics.get("beacon_blocking_rate"), "ratio", "verified_beacon_blocks / runs_with_net_containment"),
        ("process_isolation_success_rate", metrics.get("process_isolation_success_rate"), "ratio", "verified_isolations / runs_with_isolation"),
        ("legitimate_traffic_preservation_rate", metrics.get("legitimate_traffic_preservation_rate"), "ratio", "runs_preserving_legitimate / total"),
        ("false_mitigation_rate", metrics.get("false_mitigation_rate"), "ratio", "benign_runs_with_mitigation / total_scenario_a"),
        ("rollback_success_rate", metrics.get("rollback_success_rate"), "ratio", "successful_rollbacks / attempted_rollbacks"),
        ("evidence_preservation_rate", metrics.get("evidence_preservation_rate"), "ratio", "verified_evidence / total_triggered_runs"),
        ("containment_latency_min_ms", metrics.get("containment_latency_min_ms"), "ms", "Minimum containment latency"),
        ("containment_latency_max_ms", metrics.get("containment_latency_max_ms"), "ms", "Maximum containment latency"),
        ("containment_latency_avg_ms", metrics.get("containment_latency_avg_ms"), "ms", "Average containment latency"),
        ("containment_latency_median_ms", metrics.get("containment_latency_median_ms"), "ms", "Median containment latency"),
    ]

    with open(metrics_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric_name", "value", "unit", "description"])
        for row in metric_rows:
            writer.writerow(row)

    # 3. Generate experiment_results.csv
    history_csv_path = out_path / "experiment_results.csv"
    with open(history_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "experiment_id",
            "run_id",
            "scenario_id",
            "detection_status",
            "plan_status",
            "requested_actions",
            "executed_actions",
            "verified_actions",
            "containment_latency_ms",
            "rpc_blocking_verified",
            "beacon_blocking_verified",
            "process_isolation_verified",
            "legitimate_traffic_preserved",
            "false_mitigation_applied",
            "evidence_preserved",
            "rollback_success",
            "final_verdict",
        ])
        for exp in experiments:
            writer.writerow([
                exp.get("experiment_id"),
                exp.get("run_id"),
                exp.get("scenario_id"),
                exp.get("detection_status"),
                exp.get("protection_plan_status"),
                exp.get("requested_actions_count"),
                exp.get("executed_actions_count"),
                exp.get("verified_actions_count"),
                exp.get("containment_latency_ms"),
                exp.get("rpc_blocking_verified"),
                exp.get("beacon_blocking_verified"),
                exp.get("process_isolation_verified"),
                exp.get("legitimate_traffic_preserved"),
                exp.get("false_mitigation_applied"),
                exp.get("evidence_preserved"),
                exp.get("rollback_success"),
                exp.get("final_verdict"),
            ])

    logger.info("Exported protection results to %s", out_path)
    return {
        "summary_json": str(summary_path),
        "metrics_csv": str(metrics_csv_path),
        "history_csv": str(history_csv_path),
    }
