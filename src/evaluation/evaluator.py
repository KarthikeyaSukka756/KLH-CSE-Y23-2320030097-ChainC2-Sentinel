# ChainC2 Sentinel — Detection Evaluation Engine
"""Experimental evaluation framework for quantifying the laboratory performance of RULE-CHAINC2-001.

Safety & Research Integrity:
- Operates strictly in controlled laboratory environments against synthetic scenarios.
- Quantifies detectability of predefined synthetic C2-like sequences (Scenario B)
  and confirms non-triggering on benign Web3 activity (Scenario A).
- Does not claim proof of real-world malware detection or threat-actor attribution.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.correlation import CrossLayerCorrelationEngine
from src.correlation.models import CorrelatedSequence
from src.detection.detector import DetectionEngine
from src.detection.models import DetectionResult, DetectionStatus
from src.evaluation.models import (
    AggregateEvaluationResult,
    ClassificationVerdict,
    EvaluationMetrics,
    ExperimentRecord,
    GroundTruth,
)
from src.http_target.server import LocalHttpTargetServer
from src.models.events import SentinelEvent
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.definitions.legitimate_dapp_scenario import LegitimateDAppScenario
from src.utils.identifiers import generate_run_id
import uuid


def generate_prefixed_uuid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"

logger = logging.getLogger("chainc2_sentinel.evaluation.evaluator")


class DetectionEvaluator:
    """Orchestrates repeatable scenario evaluation experiments and computes deterministic metrics."""

    def __init__(
        self,
        correlation_engine: Optional[CrossLayerCorrelationEngine] = None,
        detection_engine: Optional[DetectionEngine] = None,
        host: str = "127.0.0.1",
        rpc_proxy_url: str = "http://127.0.0.1:8546",
        upstream_url: str = "http://127.0.0.1:8545",
    ) -> None:
        """Initialize evaluation orchestrator.

        Args:
            correlation_engine: Cross-layer correlation engine instance.
            detection_engine: Detection engine instance.
            host: Target host.
            rpc_proxy_url: RPC proxy URL.
            upstream_url: Upstream node URL.
        """
        self.correlation_engine = correlation_engine or CrossLayerCorrelationEngine()
        self.detection_engine = detection_engine or DetectionEngine()
        self.host = host
        self.rpc_proxy_url = rpc_proxy_url
        self.upstream_url = upstream_url

    @staticmethod
    def calculate_metrics(experiments: list[ExperimentRecord]) -> EvaluationMetrics:
        """Compute deterministic statistical evaluation metrics across experiment records.

        Explicitly defines all mathematical formulas and safeguards against division by zero.
        """
        total = len(experiments)
        successful = sum(1 for e in experiments if e.execution_status == "SUCCESS")
        failed = total - successful
        success_rate = (successful / total) if total > 0 else 0.0

        # Confusion matrix counts
        tp = sum(1 for e in experiments if e.classification == ClassificationVerdict.TRUE_POSITIVE)
        tn = sum(1 for e in experiments if e.classification == ClassificationVerdict.TRUE_NEGATIVE)
        fp = sum(1 for e in experiments if e.classification == ClassificationVerdict.FALSE_POSITIVE)
        fn = sum(1 for e in experiments if e.classification == ClassificationVerdict.FALSE_NEGATIVE)

        positives = sum(1 for e in experiments if e.ground_truth == GroundTruth.SYNTHETIC_C2)
        negatives = sum(1 for e in experiments if e.ground_truth in (GroundTruth.BENIGN, GroundTruth.LEGITIMATE_DAPP))

        # Derived rates with safe zero-denominator handling
        # Detection Rate / Recall / Sensitivity: TP / (TP + FN)
        detection_rate = (tp / positives) if positives > 0 else None

        # False Positive Rate / Fall-out: FP / (FP + TN)
        false_positive_rate = (fp / negatives) if negatives > 0 else None

        # Precision / Positive Predictive Value: TP / (TP + FP)
        precision = (tp / (tp + fp)) if (tp + fp) > 0 else None

        # True Negative Rate / Specificity: TN / (TN + FP)
        true_negative_rate = (tn / negatives) if negatives > 0 else None

        # Accuracy: (TP + TN) / total
        accuracy = ((tp + tn) / total) if total > 0 else None

        # F1 Score: 2 * (Precision * Recall) / (Precision + Recall)
        if precision is not None and detection_rate is not None and (precision + detection_rate) > 0:
            f1_score = 2.0 * (precision * detection_rate) / (precision + detection_rate)
        else:
            f1_score = None

        # Latency statistics
        latencies = [
            e.detection_latency_ms for e in experiments if e.detection_latency_ms is not None
        ]
        avg_latency = (sum(latencies) / len(latencies)) if latencies else None
        min_latency = min(latencies) if latencies else None
        max_latency = max(latencies) if latencies else None

        return EvaluationMetrics(
            total_experiments=total,
            successful_runs=successful,
            failed_runs=failed,
            experiment_success_rate=success_rate,
            ground_truth_positives=positives,
            ground_truth_negatives=negatives,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            detection_rate=detection_rate,
            false_positive_rate=false_positive_rate,
            precision=precision,
            true_negative_rate=true_negative_rate,
            accuracy=accuracy,
            f1_score=f1_score,
            average_detection_latency_ms=avg_latency,
            min_detection_latency_ms=min_latency,
            max_detection_latency_ms=max_latency,
        )

    def evaluate_correlated_sequence(
        self,
        sequence: CorrelatedSequence,
        ground_truth: GroundTruth,
        experiment_id: Optional[str] = None,
        run_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        execution_status: str = "SUCCESS",
        is_synthetic_fixture: bool = False,
        timestamp_start: Optional[datetime] = None,
        total_events: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> ExperimentRecord:
        """Evaluate a single CorrelatedSequence and record factual experimental evidence."""
        t_start = timestamp_start or datetime.now(timezone.utc)
        exp_id = experiment_id or generate_prefixed_uuid("exp")
        r_id = run_id or sequence.run_id or "unknown-run"
        s_id = scenario_id or sequence.scenario_id or "unknown-scenario"
        event_count = total_events if total_events is not None else len(sequence.events)

        # Execute detection rule and measure latency precisely
        perf_start = time.perf_counter()
        detection_results = self.detection_engine.evaluate_sequence(sequence)
        perf_elapsed_ms = (time.perf_counter() - perf_start) * 1000.0
        t_end = datetime.now(timezone.utc)

        # Primary rule evaluation (RULE-CHAINC2-001)
        primary_result = detection_results[0] if detection_results else None
        rule_id = primary_result.rule_id if primary_result else "RULE-CHAINC2-001"
        rule_version = primary_result.rule_version if primary_result else "1.0.0"
        det_status = primary_result.status if primary_result else DetectionStatus.NOT_TRIGGERED
        triggered = primary_result.triggered if primary_result else False

        # Classify verdict against ground truth
        if ground_truth == GroundTruth.SYNTHETIC_C2:
            verdict = ClassificationVerdict.TRUE_POSITIVE if triggered else ClassificationVerdict.FALSE_NEGATIVE
        else:
            verdict = ClassificationVerdict.FALSE_POSITIVE if triggered else ClassificationVerdict.TRUE_NEGATIVE

        return ExperimentRecord(
            experiment_id=exp_id,
            run_id=r_id,
            scenario_id=s_id,
            ground_truth=ground_truth,
            execution_status=execution_status,
            total_events=event_count,
            stages_observed=sequence.stages_present,
            correlated_sequence_id=sequence.correlation_id,
            detection_status=det_status,
            triggered=triggered,
            rule_id=rule_id,
            rule_version=rule_version,
            classification=verdict,
            detection_latency_ms=perf_elapsed_ms,
            timestamp_start=t_start,
            timestamp_end=t_end,
            is_synthetic_fixture=is_synthetic_fixture,
            detection_result=primary_result,
            details=details or {},
        )

    def run_single_experiment(
        self,
        scenario_type: str,
        run_id: Optional[str] = None,
        target_server: Optional[LocalHttpTargetServer] = None,
    ) -> ExperimentRecord:
        """Run a single live scenario, correlate telemetry, and evaluate detection.

        Args:
            scenario_type: 'benign' (Scenario A) or 'synthetic_c2' (Scenario B).
            run_id: Optional unique run identifier.
            target_server: Optional local HTTP target server for Scenario B.
        """
        t_start = datetime.now(timezone.utc)
        r_id = run_id or generate_prefixed_uuid("run")

        if scenario_type in ("benign", "scenario_a_benign"):
            ground_truth = GroundTruth.BENIGN
            scenario = BenignWeb3Scenario(
                run_id=r_id,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
            )
            scenario_result = scenario.run()
        elif scenario_type in ("synthetic_c2", "scenario_b_synthetic_c2"):
            ground_truth = GroundTruth.SYNTHETIC_C2
            scenario = SyntheticC2Scenario(
                target_server=target_server,
                run_id=r_id,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
            )
            scenario_result = scenario.run()
        elif scenario_type in ("legitimate_dapp", "scenario_c_legitimate_dapp"):
            ground_truth = GroundTruth.LEGITIMATE_DAPP
            scenario = LegitimateDAppScenario(
                run_id=r_id,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
            )
            scenario_result = scenario.run()
        else:
            raise ValueError(f"Unknown scenario_type: {scenario_type}")

        # Correlate scenario events
        sequences = self.correlation_engine.correlate(scenario_result.events)
        sequence = sequences[0] if sequences else CorrelatedSequence(
            run_id=r_id,
            scenario_id=scenario_result.scenario_id,
        )

        return self.evaluate_correlated_sequence(
            sequence=sequence,
            ground_truth=ground_truth,
            run_id=r_id,
            scenario_id=scenario_result.scenario_id,
            execution_status="SUCCESS" if scenario_result.success else "FAILED",
            is_synthetic_fixture=False,
            timestamp_start=t_start,
            total_events=len(scenario_result.events),
            details=scenario_result.details,
        )

    def run_evaluation(
        self,
        repetitions_benign: int = 10,
        repetitions_c2: int = 10,
        repetitions_legitimate_dapp: int = 0,
        target_server: Optional[LocalHttpTargetServer] = None,
        output_path: Optional[str] = None,
    ) -> AggregateEvaluationResult:
        """Run repeated evaluation experiments across Scenario A, Scenario B, and Scenario C.

        Args:
            repetitions_benign: Number of Scenario A (benign control) executions.
            repetitions_c2: Number of Scenario B (synthetic C2-like) executions.
            repetitions_legitimate_dapp: Number of Scenario C (legitimate DApp baseline) executions.
            target_server: Optional shared local HTTP target server.
            output_path: Optional file path to persist JSON results.

        Returns:
            AggregateEvaluationResult containing all records and deterministic metrics.
        """
        logger.info(
            "Beginning Phase 1 Detection Evaluation: %d benign, %d synthetic C2, %d legitimate DApp repetitions",
            repetitions_benign,
            repetitions_c2,
            repetitions_legitimate_dapp,
        )

        experiments: list[ExperimentRecord] = []
        scenario_counts: dict[str, int] = {
            "scenario_a_benign": 0,
            "scenario_b_synthetic_c2": 0,
            "scenario_c_legitimate_dapp": 0,
        }

        # Run Scenario A repetitions (Benign Negative Control)
        for i in range(repetitions_benign):
            run_id = f"eval-benign-{i + 1:03d}-{generate_prefixed_uuid('run')}"
            rec = self.run_single_experiment(scenario_type="benign", run_id=run_id)
            experiments.append(rec)
            scenario_counts["scenario_a_benign"] += 1

        # Run Scenario C repetitions (Legitimate DApp Baseline Negative Control)
        for i in range(repetitions_legitimate_dapp):
            run_id = f"eval-legit-{i + 1:03d}-{generate_prefixed_uuid('run')}"
            rec = self.run_single_experiment(scenario_type="legitimate_dapp", run_id=run_id)
            experiments.append(rec)
            scenario_counts["scenario_c_legitimate_dapp"] += 1

        # Run Scenario B repetitions (Synthetic C2 Positive Control)
        if target_server is not None:
            for i in range(repetitions_c2):
                run_id = f"eval-c2-{i + 1:03d}-{generate_prefixed_uuid('run')}"
                rec = self.run_single_experiment(
                    scenario_type="synthetic_c2",
                    run_id=run_id,
                    target_server=target_server,
                )
                experiments.append(rec)
                scenario_counts["scenario_b_synthetic_c2"] += 1
        else:
            with LocalHttpTargetServer(host="127.0.0.1", port=0) as local_srv:
                for i in range(repetitions_c2):
                    run_id = f"eval-c2-{i + 1:03d}-{generate_prefixed_uuid('run')}"
                    rec = self.run_single_experiment(
                        scenario_type="synthetic_c2",
                        run_id=run_id,
                        target_server=local_srv,
                    )
                    experiments.append(rec)
                    scenario_counts["scenario_b_synthetic_c2"] += 1

        # Compute aggregate metrics
        metrics = self.calculate_metrics(experiments)

        result = AggregateEvaluationResult(
            evaluation_id=generate_prefixed_uuid("eval"),
            rule_id="RULE-CHAINC2-001",
            rule_version="1.0.0",
            scenario_counts=scenario_counts,
            metrics=metrics,
            experiments=experiments,
        )

        if output_path:
            self.save_results(result, output_path)

        logger.info(
            "Evaluation complete: %d total, TP=%d, TN=%d, FP=%d, FN=%d, Acc=%s",
            result.metrics.total_experiments,
            result.metrics.true_positives,
            result.metrics.true_negatives,
            result.metrics.false_positives,
            result.metrics.false_negatives,
            f"{result.metrics.accuracy:.2%}" if result.metrics.accuracy is not None else "N/A",
        )

        return result

    @staticmethod
    def save_results(result: AggregateEvaluationResult, file_path: str) -> None:
        """Persist evaluation results as structured, machine-readable JSON."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        logger.info("Evaluation results saved to: %s", file_path)

    @staticmethod
    def load_results(file_path: str) -> AggregateEvaluationResult:
        """Load and parse evaluation results from a machine-readable JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = f.read()
        return AggregateEvaluationResult.model_validate_json(data)
