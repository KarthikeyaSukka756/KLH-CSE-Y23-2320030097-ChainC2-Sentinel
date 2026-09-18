# ChainC2 Sentinel — Tests for Detection Evaluation (Milestone 7)
"""Unit and laboratory evaluation tests for RULE-CHAINC2-001 detection evaluation."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.correlation import CrossLayerCorrelationEngine
from src.correlation.models import CorrelatedSequence
from src.detection.detector import DetectionEngine
from src.detection.models import DetectionStatus
from src.evaluation.evaluator import DetectionEvaluator
from src.evaluation.models import (
    AggregateEvaluationResult,
    ClassificationVerdict,
    EvaluationMetrics,
    ExperimentRecord,
    GroundTruth,
)
from src.http_target.server import LocalHttpTargetServer
from src.models.events import (
    BlockchainInfo,
    NetworkInfo,
    ProcessInfo,
    RpcInfo,
    SentinelEvent,
    TelemetrySource,
)


@pytest.fixture
def evaluator() -> DetectionEvaluator:
    return DetectionEvaluator()


def _create_synthetic_fixture_sequence(
    run_id: str,
    include_endpoint: bool = True,
    include_rpc: bool = True,
    contract_name: str = "C2DataStore",
    include_network: bool = True,
    network_after_blockchain: bool = True,
) -> CorrelatedSequence:
    """Helper to build controlled CorrelatedSequence fixtures for edge-case evaluation."""
    events: list[SentinelEvent] = []
    base_time = 1700000000.0

    if include_endpoint:
        events.append(
            SentinelEvent(
                source=TelemetrySource.ENDPOINT,
                event_type="process_start",
                host="127.0.0.1",
                timestamp=datetime.fromtimestamp(base_time, tz=timezone.utc),
                process=ProcessInfo(process_name="test_proc", pid=1001),
                metadata={"run_id": run_id, "scenario_id": "synthetic_fixture"},
            )
        )

    if include_rpc:
        events.append(
            SentinelEvent(
                source=TelemetrySource.RPC,
                event_type="rpc_call",
                host="127.0.0.1",
                timestamp=datetime.fromtimestamp(base_time + 1.0, tz=timezone.utc),
                rpc=RpcInfo(
                    rpc_endpoint="http://127.0.0.1:8546",
                    upstream_endpoint="http://127.0.0.1:8545",
                    rpc_method="eth_call",
                    status="success",
                ),
                metadata={"run_id": run_id, "scenario_id": "synthetic_fixture"},
            )
        )

    if contract_name:
        events.append(
            SentinelEvent(
                source=TelemetrySource.BLOCKCHAIN,
                event_type="contract_interaction",
                host="127.0.0.1",
                timestamp=datetime.fromtimestamp(base_time + 2.0, tz=timezone.utc),
                blockchain=BlockchainInfo(
                    contract_name=contract_name,
                    contract_address="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
                    function_name="getLatestCommand",
                ),
                metadata={"run_id": run_id, "scenario_id": "synthetic_fixture"},
            )
        )

    if include_network:
        net_time = base_time + (3.0 if network_after_blockchain else 1.5)
        events.append(
            SentinelEvent(
                source=TelemetrySource.NETWORK,
                event_type="http_beacon",
                host="127.0.0.1",
                timestamp=datetime.fromtimestamp(net_time, tz=timezone.utc),
                network=NetworkInfo(
                    destination_host="127.0.0.1",
                    destination_port=8080,
                    protocol="HTTP",
                    status_code=200,
                ),
                metadata={"run_id": run_id, "scenario_id": "synthetic_fixture"},
            )
        )

    engine = CrossLayerCorrelationEngine()
    sequences = engine.correlate(events)
    return sequences[0]


@pytest.mark.unit
class TestDetectionEvaluation:
    """Tests for Milestone 7 experimental evaluation framework."""

    def test_repeated_benign_scenarios(self, evaluator: DetectionEvaluator):
        """Repeated Scenario A runs produce 100% True Negatives with 0% False Positives."""
        repetitions = 3
        experiments = []
        for i in range(repetitions):
            run_id = f"eval-test-benign-{i + 1}"
            rec = evaluator.run_single_experiment("benign", run_id=run_id)
            experiments.append(rec)

            assert rec.execution_status == "SUCCESS"
            assert rec.ground_truth == GroundTruth.BENIGN
            assert rec.classification == ClassificationVerdict.TRUE_NEGATIVE
            assert rec.triggered is False
            assert rec.total_events == 3

        metrics = evaluator.calculate_metrics(experiments)
        assert metrics.total_experiments == repetitions
        assert metrics.successful_runs == repetitions
        assert metrics.true_negatives == repetitions
        assert metrics.true_positives == 0
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.false_positive_rate == 0.0
        assert metrics.true_negative_rate == 1.0
        assert metrics.accuracy == 1.0

    def test_repeated_synthetic_c2_scenarios(self, evaluator: DetectionEvaluator):
        """Repeated Scenario B runs produce 100% True Positives with 0% False Negatives."""
        repetitions = 3
        experiments = []
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            for i in range(repetitions):
                run_id = f"eval-test-c2-{i + 1}"
                rec = evaluator.run_single_experiment(
                    "synthetic_c2",
                    run_id=run_id,
                    target_server=target_srv,
                )
                experiments.append(rec)

                assert rec.execution_status == "SUCCESS"
                assert rec.ground_truth == GroundTruth.SYNTHETIC_C2
                assert rec.classification == ClassificationVerdict.TRUE_POSITIVE
                assert rec.triggered is True
                assert rec.total_events == 4
                assert rec.detection_latency_ms is not None
                assert rec.detection_latency_ms >= 0.0

        metrics = evaluator.calculate_metrics(experiments)
        assert metrics.total_experiments == repetitions
        assert metrics.successful_runs == repetitions
        assert metrics.true_positives == repetitions
        assert metrics.true_negatives == 0
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.detection_rate == 1.0
        assert metrics.precision == 1.0
        assert metrics.accuracy == 1.0
        assert metrics.f1_score == 1.0

    def test_mixed_scenario_evaluation_run(self, evaluator: DetectionEvaluator):
        """Mixed evaluation run with configurable repetitions (Scenario A and Scenario B)."""
        reps_benign = 2
        reps_c2 = 2
        result = evaluator.run_evaluation(
            repetitions_benign=reps_benign,
            repetitions_c2=reps_c2,
        )

        assert isinstance(result, AggregateEvaluationResult)
        assert result.rule_id == "RULE-CHAINC2-001"
        assert result.scenario_counts["scenario_a_benign"] == reps_benign
        assert result.scenario_counts["scenario_b_synthetic_c2"] == reps_c2
        assert len(result.experiments) == (reps_benign + reps_c2)

        metrics = result.metrics
        assert metrics.total_experiments == 4
        assert metrics.successful_runs == 4
        assert metrics.true_positives == 2
        assert metrics.true_negatives == 2
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.detection_rate == 1.0
        assert metrics.false_positive_rate == 0.0
        assert metrics.precision == 1.0
        assert metrics.accuracy == 1.0
        assert metrics.f1_score == 1.0
        assert metrics.average_detection_latency_ms is not None

    def test_synthetic_evaluation_fixtures_false_positive(self, evaluator: DetectionEvaluator):
        """Synthetic fixture labeled BENIGN that triggers rule correctly records False Positive."""
        seq = _create_synthetic_fixture_sequence(
            run_id="fixture-fp-001",
            contract_name="C2DataStore",
            include_network=True,
            network_after_blockchain=True,
        )
        # Sequence satisfies all conditions for RULE-CHAINC2-001
        # Artificially assign ground truth as BENIGN to simulate a false positive
        rec = evaluator.evaluate_correlated_sequence(
            sequence=seq,
            ground_truth=GroundTruth.BENIGN,
            is_synthetic_fixture=True,
        )

        assert rec.is_synthetic_fixture is True
        assert rec.triggered is True
        assert rec.classification == ClassificationVerdict.FALSE_POSITIVE

        # Metrics with 1 TN and 1 FP
        normal_benign_rec = evaluator.run_single_experiment("benign", run_id="eval-fp-control")
        metrics = evaluator.calculate_metrics([normal_benign_rec, rec])

        assert metrics.total_experiments == 2
        assert metrics.true_negatives == 1
        assert metrics.false_positives == 1
        assert metrics.false_positive_rate == 0.5  # FP / (FP + TN) = 1 / 2 = 0.5
        assert metrics.precision == 0.0  # TP / (TP + FP) = 0 / 1 = 0.0

    def test_synthetic_evaluation_fixtures_false_negative(self, evaluator: DetectionEvaluator):
        """Synthetic fixture labeled SYNTHETIC_C2 that fails condition correctly records False Negative."""
        # Sequence is missing network event -> fails detection rule
        seq = _create_synthetic_fixture_sequence(
            run_id="fixture-fn-001",
            contract_name="C2DataStore",
            include_network=False,
        )
        # Assign ground truth as SYNTHETIC_C2
        rec = evaluator.evaluate_correlated_sequence(
            sequence=seq,
            ground_truth=GroundTruth.SYNTHETIC_C2,
            is_synthetic_fixture=True,
        )

        assert rec.is_synthetic_fixture is True
        assert rec.triggered is False
        assert rec.classification == ClassificationVerdict.FALSE_NEGATIVE

        # Metrics with 1 TP and 1 FN
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            normal_c2_rec = evaluator.run_single_experiment(
                "synthetic_c2",
                run_id="eval-fn-control",
                target_server=target_srv,
            )
        metrics = evaluator.calculate_metrics([normal_c2_rec, rec])

        assert metrics.total_experiments == 2
        assert metrics.true_positives == 1
        assert metrics.false_negatives == 1
        assert metrics.detection_rate == 0.5  # TP / (TP + FN) = 1 / 2 = 0.5

    def test_zero_experiments_safe_denominators(self, evaluator: DetectionEvaluator):
        """Empty experiment list safely yields None for derived rates without division by zero."""
        metrics = evaluator.calculate_metrics([])

        assert metrics.total_experiments == 0
        assert metrics.successful_runs == 0
        assert metrics.experiment_success_rate == 0.0
        assert metrics.detection_rate is None
        assert metrics.false_positive_rate is None
        assert metrics.precision is None
        assert metrics.true_negative_rate is None
        assert metrics.accuracy is None
        assert metrics.f1_score is None
        assert metrics.average_detection_latency_ms is None

    def test_zero_positive_denominator_safe_handling(self, evaluator: DetectionEvaluator):
        """When only benign experiments exist, TP+FN is 0 so recall and precision safely return None."""
        rec = evaluator.run_single_experiment("benign", run_id="eval-zero-pos-001")
        metrics = evaluator.calculate_metrics([rec])

        assert metrics.ground_truth_positives == 0
        assert metrics.ground_truth_negatives == 1
        assert metrics.detection_rate is None  # Denominator (TP + FN) is 0
        assert metrics.precision is None  # Denominator (TP + FP) is 0
        assert metrics.false_positive_rate == 0.0  # FP / negatives = 0 / 1 = 0.0
        assert metrics.accuracy == 1.0

    def test_zero_negative_denominator_safe_handling(self, evaluator: DetectionEvaluator):
        """When only synthetic C2 experiments exist, FP+TN is 0 so FPR and TNR safely return None."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            rec = evaluator.run_single_experiment(
                "synthetic_c2",
                run_id="eval-zero-neg-001",
                target_server=target_srv,
            )
        metrics = evaluator.calculate_metrics([rec])

        assert metrics.ground_truth_positives == 1
        assert metrics.ground_truth_negatives == 0
        assert metrics.false_positive_rate is None  # Denominator (FP + TN) is 0
        assert metrics.true_negative_rate is None  # Denominator (TN + FP) is 0
        assert metrics.detection_rate == 1.0
        assert metrics.precision == 1.0
        assert metrics.accuracy == 1.0

    def test_persistence_and_reload(self, evaluator: DetectionEvaluator, tmp_path: Path):
        """AggregateEvaluationResult can be saved to JSON and accurately reloaded."""
        output_file = str(tmp_path / "eval_results.json")
        result = evaluator.run_evaluation(
            repetitions_benign=1,
            repetitions_c2=1,
            output_path=output_file,
        )

        assert Path(output_file).exists()

        # Reload from disk
        loaded = evaluator.load_results(output_file)
        assert loaded.evaluation_id == result.evaluation_id
        assert loaded.rule_id == result.rule_id
        assert loaded.metrics.total_experiments == 2
        assert loaded.metrics.true_positives == 1
        assert loaded.metrics.true_negatives == 1
        assert len(loaded.experiments) == 2
        assert loaded.experiments[0].experiment_id == result.experiments[0].experiment_id

        # Validate JSON content structure directly
        with open(output_file, "r", encoding="utf-8") as f:
            raw_json = json.load(f)
        assert "metrics" in raw_json
        assert "metric_formulas" in raw_json["metrics"]
        assert "experiments" in raw_json
        assert "research_disclaimer" in raw_json

    def test_deterministic_aggregation(self, evaluator: DetectionEvaluator):
        """Repeatedly aggregating the same experiments produces strictly identical metrics."""
        rec1 = evaluator.run_single_experiment("benign", run_id="det-1")
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            rec2 = evaluator.run_single_experiment(
                "synthetic_c2",
                run_id="det-2",
                target_server=target_srv,
            )

        metrics_run_1 = evaluator.calculate_metrics([rec1, rec2])
        metrics_run_2 = evaluator.calculate_metrics([rec1, rec2])

        assert metrics_run_1.model_dump() == metrics_run_2.model_dump()
