# ChainC2 Sentinel — Tests for Protection Evaluation (Milestone 10)
"""Unit tests verifying Milestone 10 Protection Evaluation models, metrics calculations,
scenario executions, containment dimensions, rollback, and artifact exports.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from src.detection.models import DetectionStatus
from src.protection.evaluation.evaluator import ProtectionEvaluator
from src.protection.evaluation.exporter import export_protection_results_artifacts
from src.protection.evaluation.models import (
    AggregateProtectionEvaluationResult,
    ProtectionEvaluationMetrics,
    ProtectionExperimentRecord,
)
from src.protection.models import DefensePlanStatus


@pytest.fixture
def sample_benign_record() -> ProtectionExperimentRecord:
    """Fixture of a successful Scenario A evaluation record."""
    return ProtectionExperimentRecord(
        experiment_id="exp-benign-001",
        run_id="run-benign-001",
        scenario_id="scenario_a_benign",
        detection_status=DetectionStatus.NOT_TRIGGERED,
        protection_plan_status=DefensePlanStatus.SKIPPED,
        requested_actions_count=0,
        executed_actions_count=0,
        verified_actions_count=0,
        failed_actions_count=0,
        containment_latency_ms=None,
        rpc_blocking_verified=None,
        beacon_blocking_verified=None,
        process_isolation_verified=None,
        legitimate_traffic_preserved=True,
        false_mitigation_applied=False,
        evidence_preserved=None,
        evidence_file_path=None,
        rollback_success=None,
        final_verdict="BENIGN_PRESERVED",
    )


@pytest.fixture
def sample_triggered_record() -> ProtectionExperimentRecord:
    """Fixture of a successful Scenario B evaluation record."""
    return ProtectionExperimentRecord(
        experiment_id="exp-c2-001",
        run_id="run-c2-001",
        scenario_id="scenario_b_synthetic_c2",
        detection_status=DetectionStatus.TRIGGERED,
        protection_plan_status=DefensePlanStatus.VERIFIED,
        requested_actions_count=4,
        executed_actions_count=4,
        verified_actions_count=4,
        failed_actions_count=0,
        containment_latency_ms=12.5,
        rpc_blocking_verified=True,
        beacon_blocking_verified=True,
        process_isolation_verified=True,
        legitimate_traffic_preserved=True,
        false_mitigation_applied=False,
        evidence_preserved=True,
        evidence_file_path="data/evidence/test_evidence.json",
        rollback_success=True,
        final_verdict="SUCCESS",
    )


@pytest.fixture
def sample_fault_record() -> ProtectionExperimentRecord:
    """Fixture of a fault-injection failure-handling evaluation record."""
    return ProtectionExperimentRecord(
        experiment_id="exp-fault-001",
        run_id="run-fault-001",
        scenario_id="scenario_c_fault_injection",
        detection_status=DetectionStatus.TRIGGERED,
        protection_plan_status=DefensePlanStatus.FAILED,
        requested_actions_count=1,
        executed_actions_count=0,
        verified_actions_count=0,
        failed_actions_count=1,
        containment_latency_ms=1.2,
        rpc_blocking_verified=None,
        beacon_blocking_verified=None,
        process_isolation_verified=False,
        legitimate_traffic_preserved=True,
        false_mitigation_applied=False,
        evidence_preserved=None,
        evidence_file_path=None,
        rollback_success=None,
        final_verdict="FAULT_HANDLED",
    )


@pytest.mark.unit
class TestProtectionEvaluation:
    """Validation suite for Milestone 10 Protection Evaluation framework."""

    def test_single_benign_experiment(self):
        """Scenario A produces SKIPPED plan, zero actions, and preserves legitimate traffic."""
        evaluator = ProtectionEvaluator()
        record = evaluator.run_single_experiment("scenario_a_benign")

        assert record.scenario_id == "scenario_a_benign"
        assert record.detection_status == DetectionStatus.NOT_TRIGGERED
        assert record.protection_plan_status == DefensePlanStatus.SKIPPED
        assert record.requested_actions_count == 0
        assert record.executed_actions_count == 0
        assert record.verified_actions_count == 0
        assert record.failed_actions_count == 0
        assert record.false_mitigation_applied is False
        assert record.legitimate_traffic_preserved is True
        assert record.final_verdict == "BENIGN_PRESERVED"
        assert record.containment_latency_ms is None

    def test_single_synthetic_c2_experiment(self, tmp_path: Path):
        """Scenario B produces complete protection, active containment, verification, and rollback."""
        evaluator = ProtectionEvaluator(evidence_dir=str(tmp_path / "evidence"))
        record = evaluator.run_single_experiment("scenario_b_synthetic_c2")

        assert record.scenario_id == "scenario_b_synthetic_c2"
        assert record.detection_status == DetectionStatus.TRIGGERED
        assert record.protection_plan_status in (DefensePlanStatus.VERIFIED, DefensePlanStatus.ROLLED_BACK)
        assert record.requested_actions_count == 4
        assert record.executed_actions_count == 4
        assert record.verified_actions_count == 4
        assert record.failed_actions_count == 0
        assert record.containment_latency_ms is not None
        assert record.containment_latency_ms > 0
        assert record.rpc_blocking_verified is True
        assert record.beacon_blocking_verified is True
        assert record.process_isolation_verified is True
        assert record.legitimate_traffic_preserved is True
        assert record.evidence_preserved is True
        assert record.rollback_success is True
        assert record.final_verdict == "SUCCESS"

    def test_single_fault_injection_experiment(self):
        """Controlled fault injection gracefully fails action and records handled failure."""
        evaluator = ProtectionEvaluator()
        record = evaluator.run_single_experiment("scenario_c_fault_injection")

        assert record.scenario_id == "scenario_c_fault_injection"
        assert record.protection_plan_status == DefensePlanStatus.FAILED
        assert record.requested_actions_count == 1
        assert record.executed_actions_count == 0
        assert record.failed_actions_count == 1
        assert record.final_verdict == "FAULT_HANDLED"

    def test_metrics_calculation_standard_batch(
        self,
        sample_benign_record: ProtectionExperimentRecord,
        sample_triggered_record: ProtectionExperimentRecord,
        sample_fault_record: ProtectionExperimentRecord,
    ):
        """Metrics calculation correctly computes rates, latencies, and formulas across mixed runs."""
        experiments = [sample_benign_record, sample_triggered_record, sample_fault_record]
        metrics = ProtectionEvaluator.calculate_metrics(experiments)

        assert metrics.total_experiments == 3
        assert metrics.successful_experiments == 3  # BENIGN_PRESERVED, SUCCESS, FAULT_HANDLED are all valid outcomes
        assert metrics.failed_experiments == 0
        assert metrics.experiment_success_rate == 1.0

        # Efficacy metrics
        assert metrics.mitigation_success_rate == 1.0  # 4 verified / 4 requested
        assert metrics.rpc_blocking_rate == 1.0
        assert metrics.beacon_blocking_rate == 1.0
        assert metrics.process_isolation_success_rate == 1.0
        assert metrics.legitimate_traffic_preservation_rate == 1.0
        assert metrics.false_mitigation_rate == 0.0
        assert metrics.rollback_success_rate == 1.0
        assert metrics.evidence_preservation_rate == 1.0

        # Latency
        assert metrics.containment_latency_min_ms == 12.5
        assert metrics.containment_latency_max_ms == 12.5
        assert metrics.containment_latency_avg_ms == 12.5
        assert metrics.containment_latency_median_ms == 12.5

        # Formulas documentation exists
        assert "mitigation_success_rate" in metrics.metric_formulas
        assert "containment_latency" in metrics.metric_formulas

    def test_zero_denominator_safe_handling_all_benign(
        self,
        sample_benign_record: ProtectionExperimentRecord,
    ):
        """When only benign runs exist, protection-specific metrics safely return None without ZeroDivisionError."""
        experiments = [sample_benign_record, sample_benign_record]
        metrics = ProtectionEvaluator.calculate_metrics(experiments)

        assert metrics.total_experiments == 2
        assert metrics.scenario_a_runs == 2
        assert metrics.scenario_b_runs == 0
        assert metrics.mitigation_success_rate is None
        assert metrics.rpc_blocking_rate is None
        assert metrics.beacon_blocking_rate is None
        assert metrics.process_isolation_success_rate is None
        assert metrics.rollback_success_rate is None
        assert metrics.evidence_preservation_rate is None
        assert metrics.containment_latency_avg_ms is None
        assert metrics.false_mitigation_rate == 0.0
        assert metrics.legitimate_traffic_preservation_rate == 1.0

    def test_zero_denominator_safe_handling_empty_list(self):
        """When an empty experiment list is evaluated, metrics handle all zero denominators safely."""
        metrics = ProtectionEvaluator.calculate_metrics([])
        assert metrics.total_experiments == 0
        assert metrics.experiment_success_rate == 0.0
        assert metrics.mitigation_success_rate is None
        assert metrics.rpc_blocking_rate is None
        assert metrics.false_mitigation_rate == 0.0
        assert metrics.legitimate_traffic_preservation_rate == 0.0

    def test_false_mitigation_detected(
        self,
        sample_benign_record: ProtectionExperimentRecord,
    ):
        """If a benign run has a mitigation erroneously applied, false_mitigation_rate reflects it."""
        corrupted_benign = sample_benign_record.model_copy()
        corrupted_benign.false_mitigation_applied = True
        corrupted_benign.final_verdict = "FAILED"

        experiments = [sample_benign_record, corrupted_benign]
        metrics = ProtectionEvaluator.calculate_metrics(experiments)

        assert metrics.false_mitigation_rate == 0.5
        assert metrics.successful_experiments == 1
        assert metrics.failed_experiments == 1

    def test_run_evaluation_batch_and_persistence(self, tmp_path: Path):
        """Repeated evaluation batch executes cleanly and persists structured JSON."""
        eval_path = tmp_path / "protection_eval.json"
        evaluator = ProtectionEvaluator(evidence_dir=str(tmp_path / "evidence"))

        # Run small batch: 2 benign, 2 synthetic C2, 1 fault injection
        result = evaluator.run_evaluation(
            repetitions_benign=2,
            repetitions_c2=2,
            repetitions_fault=1,
            output_path=str(eval_path),
        )

        assert isinstance(result, AggregateProtectionEvaluationResult)
        assert result.total_experiments == 5
        assert len(result.experiments) == 5
        assert result.scenario_counts["scenario_a_benign"] == 2
        assert result.scenario_counts["scenario_b_synthetic_c2"] == 2
        assert result.scenario_counts["scenario_c_fault_injection"] == 1

        assert result.metrics.mitigation_success_rate == 1.0
        assert result.metrics.rpc_blocking_rate == 1.0
        assert result.metrics.beacon_blocking_rate == 1.0
        assert result.metrics.process_isolation_success_rate == 1.0
        assert result.metrics.false_mitigation_rate == 0.0
        assert result.metrics.legitimate_traffic_preservation_rate == 1.0
        assert result.metrics.rollback_success_rate == 1.0
        assert result.metrics.evidence_preservation_rate == 1.0
        assert result.metrics.containment_latency_avg_ms is not None

        # Verify persisted JSON
        assert eval_path.exists()
        reloaded = evaluator.load_results(str(eval_path))
        assert reloaded.total_experiments == 5
        assert reloaded.metrics.experiment_success_rate == 1.0

    def test_export_protection_results_artifacts(self, tmp_path: Path):
        """Exporter produces evaluation_summary.json, protection_metrics.csv, and experiment_results.csv."""
        eval_path = tmp_path / "protection_evaluation.json"
        out_dir = tmp_path / "results_protection"

        evaluator = ProtectionEvaluator(evidence_dir=str(tmp_path / "evidence"))
        evaluator.run_evaluation(
            repetitions_benign=1,
            repetitions_c2=1,
            repetitions_fault=1,
            output_path=str(eval_path),
        )

        artifacts = export_protection_results_artifacts(
            source_json_path=str(eval_path),
            output_dir=str(out_dir),
        )

        summary_file = Path(artifacts["summary_json"])
        metrics_file = Path(artifacts["metrics_csv"])
        history_file = Path(artifacts["history_csv"])

        assert summary_file.exists()
        assert metrics_file.exists()
        assert history_file.exists()

        # Check summary JSON
        with open(summary_file, "r", encoding="utf-8") as f:
            summary = json.load(f)
        assert summary["total_experiments"] == 3
        assert "containment_latency" in summary
        assert "metric_formulas" in summary

        # Check metrics CSV
        metrics_text = metrics_file.read_text(encoding="utf-8")
        assert "metric_name,value,unit,description" in metrics_text
        assert "mitigation_success_rate" in metrics_text
        assert "containment_latency_avg_ms" in metrics_text

        # Check experiment history CSV
        history_text = history_file.read_text(encoding="utf-8")
        assert "experiment_id,run_id,scenario_id" in history_text
        assert "scenario_a_benign" in history_text
        assert "scenario_b_synthetic_c2" in history_text
