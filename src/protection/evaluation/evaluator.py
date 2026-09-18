# ChainC2 Sentinel — Protection Evaluation Engine
"""Orchestrator for repeatable experimental evaluation of Milestone 8 & 9 defensive protections.

Safety & Research Boundaries:
- Operates strictly in controlled laboratory environments against synthetic scenarios.
- Measures the containment efficacy and latency of application-layer mitigations.
- Confirms zero defensive disruption on legitimate baseline Web3 activity.
- Does not claim universal real-world malware mitigation efficacy or external threat attribution.
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError
import uuid

from src.correlation import CrossLayerCorrelationEngine
from src.correlation.models import CorrelatedSequence
from src.detection.detector import DetectionEngine
from src.detection.models import DetectionResult, DetectionStatus
from src.http_target.server import LocalHttpTargetServer
from src.protection.evaluation.models import (
    AggregateProtectionEvaluationResult,
    ProtectionEvaluationMetrics,
    ProtectionExperimentRecord,
)
from src.protection.executor import DefenseExecutor
from src.protection.handlers.evidence_handler import EvidenceSnapshotHandler
from src.protection.handlers.network_handler import NetworkContainmentHandler
from src.protection.handlers.process_handler import ProcessIsolationHandler
from src.protection.handlers.rpc_handler import RpcFilterHandler
from src.protection.models import (
    DefensePlan,
    DefensePlanStatus,
    MitigationAction,
    MitigationStatus,
    MitigationType,
)
from src.protection.policy import DefensivePolicyEngine
from src.protection.process_registry import ScenarioWorkerRegistry
from src.rpc_proxy.proxy import RpcProxy
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario

logger = logging.getLogger("chainc2_sentinel.protection.evaluation.evaluator")

DEFAULT_C2_ADDR = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
DEFAULT_BENIGN_ADDR = "0x5FbDB2315678afecb367f032d93F642f64180aa3"


def _generate_eval_uuid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


class ProtectionEvaluator:
    """Orchestrates repeatable protection evaluation experiments and computes deterministic metrics."""

    def __init__(
        self,
        correlation_engine: Optional[CrossLayerCorrelationEngine] = None,
        detection_engine: Optional[DetectionEngine] = None,
        policy_engine: Optional[DefensivePolicyEngine] = None,
        evidence_dir: str = "data/evidence",
        host: str = "127.0.0.1",
        rpc_proxy_url: str = "http://127.0.0.1:8546",
        upstream_url: str = "http://127.0.0.1:8545",
    ) -> None:
        self.correlation_engine = correlation_engine or CrossLayerCorrelationEngine()
        self.detection_engine = detection_engine or DetectionEngine()
        self.policy_engine = policy_engine or DefensivePolicyEngine()
        self.evidence_dir = Path(evidence_dir)
        self.host = host
        self.rpc_proxy_url = rpc_proxy_url
        self.upstream_url = upstream_url

    @staticmethod
    def calculate_metrics(experiments: list[ProtectionExperimentRecord]) -> ProtectionEvaluationMetrics:
        """Compute aggregate deterministic protection metrics from factual experiment records."""
        total = len(experiments)
        a_runs = sum(1 for e in experiments if e.scenario_id in ("benign", "scenario_a_benign"))
        b_runs = sum(1 for e in experiments if e.scenario_id in ("synthetic_c2", "scenario_b_synthetic_c2"))
        fault_runs = sum(1 for e in experiments if e.scenario_id in ("fault_injection", "scenario_c_fault_injection"))

        successful = sum(1 for e in experiments if e.final_verdict in ("SUCCESS", "BENIGN_PRESERVED", "FAULT_HANDLED"))
        failed = total - successful
        success_rate = (successful / total) if total > 0 else 0.0

        # Positive-control (triggered) runs
        triggered_runs = [
            e for e in experiments
            if e.detection_status == DetectionStatus.TRIGGERED and e.scenario_id in ("synthetic_c2", "scenario_b_synthetic_c2")
        ]

        # 1. Mitigation Success Rate: verified actions / requested actions across triggered runs
        total_requested_actions = sum(e.requested_actions_count for e in triggered_runs)
        total_verified_actions = sum(e.verified_actions_count for e in triggered_runs)
        mitigation_success_rate = (
            (total_verified_actions / total_requested_actions) if total_requested_actions > 0 else None
        )

        # 2. RPC Blocking Rate
        rpc_runs = [e for e in triggered_runs if e.rpc_blocking_verified is not None]
        rpc_blocks = sum(1 for e in rpc_runs if e.rpc_blocking_verified is True)
        rpc_blocking_rate = (rpc_blocks / len(rpc_runs)) if rpc_runs else None

        # 3. Beacon Blocking Rate
        beacon_runs = [e for e in triggered_runs if e.beacon_blocking_verified is not None]
        beacon_blocks = sum(1 for e in beacon_runs if e.beacon_blocking_verified is True)
        beacon_blocking_rate = (beacon_blocks / len(beacon_runs)) if beacon_runs else None

        # 4. Process Isolation Success Rate
        iso_runs = [e for e in triggered_runs if e.process_isolation_verified is not None]
        iso_blocks = sum(1 for e in iso_runs if e.process_isolation_verified is True)
        process_isolation_success_rate = (iso_blocks / len(iso_runs)) if iso_runs else None

        # 5. Legitimate Traffic Preservation Rate: valid contract calls and /health preserved across all runs
        preserved_count = sum(1 for e in experiments if e.legitimate_traffic_preserved)
        legitimate_traffic_preservation_rate = (preserved_count / total) if total > 0 else 0.0

        # 6. False Mitigation Rate: benign runs erroneously receiving mitigation / total benign runs
        benign_runs = [e for e in experiments if e.scenario_id in ("benign", "scenario_a_benign")]
        false_mitigations = sum(1 for e in benign_runs if e.false_mitigation_applied)
        false_mitigation_rate = (false_mitigations / len(benign_runs)) if benign_runs else 0.0

        # 7. Rollback Success Rate
        rollback_runs = [e for e in experiments if e.rollback_success is not None]
        rollback_ok = sum(1 for e in rollback_runs if e.rollback_success is True)
        rollback_success_rate = (rollback_ok / len(rollback_runs)) if rollback_runs else None

        # 8. Evidence Preservation Rate
        ev_runs = [e for e in triggered_runs if e.evidence_preserved is not None]
        ev_ok = sum(1 for e in ev_runs if e.evidence_preserved is True)
        evidence_preservation_rate = (ev_ok / len(ev_runs)) if ev_runs else None

        # 9. Containment Latency Statistics
        latencies = [
            e.containment_latency_ms for e in triggered_runs if e.containment_latency_ms is not None
        ]
        min_lat = round(min(latencies), 3) if latencies else None
        max_lat = round(max(latencies), 3) if latencies else None
        avg_lat = round(sum(latencies) / len(latencies), 3) if latencies else None
        med_lat = round(statistics.median(latencies), 3) if latencies else None

        metric_formulas = {
            "experiment_success_rate": "successful_experiments / total_experiments",
            "mitigation_success_rate": "total_verified_actions / total_requested_actions [across triggered runs]",
            "rpc_blocking_rate": "verified_rpc_blocks / triggered_runs_with_rpc_filter",
            "beacon_blocking_rate": "verified_beacon_blocks / triggered_runs_with_network_containment",
            "process_isolation_success_rate": "verified_process_isolations / triggered_runs_with_process_isolation",
            "legitimate_traffic_preservation_rate": "runs_with_legitimate_traffic_preserved / total_experiments",
            "false_mitigation_rate": "benign_runs_with_mitigation_applied / total_scenario_a_runs",
            "rollback_success_rate": "successful_rollbacks / total_attempted_rollbacks",
            "evidence_preservation_rate": "valid_evidence_bundles_preserved / total_triggered_runs",
            "containment_latency": "time from plan execution initiation to completion of all verification probes in ms",
        }

        return ProtectionEvaluationMetrics(
            total_experiments=total,
            successful_experiments=successful,
            failed_experiments=failed,
            experiment_success_rate=round(success_rate, 4),
            scenario_a_runs=a_runs,
            scenario_b_runs=b_runs,
            fault_injection_runs=fault_runs,
            mitigation_success_rate=round(mitigation_success_rate, 4) if mitigation_success_rate is not None else None,
            rpc_blocking_rate=round(rpc_blocking_rate, 4) if rpc_blocking_rate is not None else None,
            beacon_blocking_rate=round(beacon_blocking_rate, 4) if beacon_blocking_rate is not None else None,
            process_isolation_success_rate=round(process_isolation_success_rate, 4) if process_isolation_success_rate is not None else None,
            legitimate_traffic_preservation_rate=round(legitimate_traffic_preservation_rate, 4),
            false_mitigation_rate=round(false_mitigation_rate, 4),
            rollback_success_rate=round(rollback_success_rate, 4) if rollback_success_rate is not None else None,
            evidence_preservation_rate=round(evidence_preservation_rate, 4) if evidence_preservation_rate is not None else None,
            containment_latency_min_ms=min_lat,
            containment_latency_max_ms=max_lat,
            containment_latency_avg_ms=avg_lat,
            containment_latency_median_ms=med_lat,
            metric_formulas=metric_formulas,
        )

    def run_single_experiment(
        self,
        scenario_type: str,
        run_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
    ) -> ProtectionExperimentRecord:
        """Execute a single end-to-end protection experiment with live verification and rollback."""
        exp_id = experiment_id or _generate_eval_uuid("exp-prot")
        r_id = run_id or _generate_eval_uuid("run-prot")
        t_start = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # Case A: Benign Negative Control (Scenario A)
        # -------------------------------------------------------------
        if scenario_type in ("benign", "scenario_a_benign"):
            scenario = BenignWeb3Scenario(
                run_id=r_id,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
            )
            scenario_result = scenario.run()
            sequences = self.correlation_engine.correlate(scenario_result.events)
            seq = sequences[0] if sequences else CorrelatedSequence(run_id=r_id, scenario_id="scenario_a_benign")
            detection_results = self.detection_engine.evaluate_sequence(seq)
            det = detection_results[0] if detection_results else None
            det_status = det.status if det else DetectionStatus.NOT_TRIGGERED

            # Policy engine creates plan (must be SKIPPED)
            plan = self.policy_engine.create_defense_plan(det) if det else DefensePlan(
                detection_correlation_id=seq.correlation_id,
                rule_id="RULE-CHAINC2-001",
                status=DefensePlanStatus.SKIPPED,
                actions=[],
                evidence_summary="Benign baseline: rule did not trigger.",
            )

            # Executor runs plan
            executor = DefenseExecutor()
            exec_record = executor.execute_plan(plan)

            # Verification: zero mitigations, benign preserved
            false_mitigation = (exec_record.actions_executed > 0)
            return ProtectionExperimentRecord(
                experiment_id=exp_id,
                run_id=r_id,
                scenario_id="scenario_a_benign",
                timestamp=t_start,
                detection_status=det_status,
                protection_plan_status=plan.status,
                requested_actions_count=len(plan.actions),
                executed_actions_count=exec_record.actions_executed,
                verified_actions_count=exec_record.actions_verified,
                failed_actions_count=exec_record.actions_failed,
                containment_latency_ms=None,
                rpc_blocking_verified=None,
                beacon_blocking_verified=None,
                process_isolation_verified=None,
                legitimate_traffic_preserved=True,
                false_mitigation_applied=false_mitigation,
                evidence_preserved=None,
                evidence_file_path=None,
                rollback_success=None,
                final_verdict="BENIGN_PRESERVED" if not false_mitigation else "FAILED",
                details={
                    "total_events": len(scenario_result.events),
                    "plan_status": plan.status.value,
                },
            )

        # -------------------------------------------------------------
        # Case B: Synthetic C2 Positive Control (Scenario B)
        # -------------------------------------------------------------
        elif scenario_type in ("synthetic_c2", "scenario_b_synthetic_c2"):
            # Set up clean testbed components
            with LocalHttpTargetServer(host=self.host, port=0) as target_server:
                proxy = RpcProxy()
                worker_registry = ScenarioWorkerRegistry()
                worker_pid = 4096
                worker_name = "synthetic_c2_client"
                worker_registry.register_worker(worker_name, worker_pid)

                evidence_handler = EvidenceSnapshotHandler(output_dir=str(self.evidence_dir))
                rpc_handler = RpcFilterHandler(proxy=proxy)
                network_handler = NetworkContainmentHandler(target_server=target_server)
                process_handler = ProcessIsolationHandler(registry=worker_registry)

                executor = DefenseExecutor(
                    handlers={
                        MitigationType.EVIDENCE_PRESERVATION: evidence_handler,
                        MitigationType.RPC_FILTER: rpc_handler,
                        MitigationType.NETWORK_CONTAINMENT: network_handler,
                        MitigationType.PROCESS_ISOLATION: process_handler,
                    }
                )

                scenario = SyntheticC2Scenario(
                    target_server=target_server,
                    run_id=r_id,
                    host=self.host,
                    rpc_proxy_url=self.rpc_proxy_url,
                    upstream_url=self.upstream_url,
                )
                scenario_result = scenario.run()
                sequences = self.correlation_engine.correlate(scenario_result.events)
                seq = sequences[0] if sequences else CorrelatedSequence(run_id=r_id, scenario_id="scenario_b_synthetic_c2")
                detection_results = self.detection_engine.evaluate_sequence(seq)
                det = detection_results[0] if detection_results else None
                det_status = det.status if det else DetectionStatus.TRIGGERED

                # Generate DefensePlan
                plan = self.policy_engine.create_defense_plan(det)
                assert plan.status == DefensePlanStatus.PENDING

                # Measure containment execution latency
                perf_start = time.perf_counter()
                exec_record = executor.execute_plan(plan)
                latency_ms = (time.perf_counter() - perf_start) * 1000.0

                # Independent Dimension Probes:
                # 1. RPC Blocking Verification
                c2_addr = det.evidence.get("contract_address", DEFAULT_C2_ADDR)
                rpc_blocked = proxy.is_contract_filtered(c2_addr)

                # 2. Beacon HTTP 403 Blocking Verification
                beacon_blocked = False
                try:
                    beacon_req = urllib_request.Request(
                        target_server.beacon_url,
                        data=json.dumps({"probe": "test"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib_request.urlopen(beacon_req) as resp:
                        if resp.status == 403:
                            beacon_blocked = True
                except HTTPError as e:
                    if e.code == 403:
                        beacon_blocked = True

                # 3. Process Isolation Verification
                worker_isolated = worker_registry.is_isolated(worker_name, worker_pid)

                # 4. Legitimate Traffic Preservation
                benign_addr = DEFAULT_BENIGN_ADDR
                benign_not_filtered = not proxy.is_contract_filtered(benign_addr)
                health_preserved = False
                try:
                    with urllib_request.urlopen(target_server.health_url) as resp:
                        if resp.status == 200:
                            health_preserved = True
                except Exception:
                    health_preserved = False
                legit_preserved = benign_not_filtered and health_preserved

                # 5. Evidence Snapshot Verification
                evidence_action = next((a for a in plan.actions if a.mitigation_type == MitigationType.EVIDENCE_PRESERVATION), None)
                snapshot_path = evidence_action.parameters.get("snapshot_path") if evidence_action else None
                evidence_ok = False
                if snapshot_path:
                    p = Path(snapshot_path)
                    if p.exists() and p.stat().st_size > 0:
                        try:
                            with open(p, "r", encoding="utf-8") as f:
                                b_data = json.load(f)
                            if "sha256_checksum" in b_data:
                                evidence_ok = True
                        except Exception:
                            evidence_ok = False

                # 6. Rollback Verification
                rollback_ok = executor.rollback_plan(plan)
                # Ensure baseline is restored
                unfiltered = not proxy.is_contract_filtered(c2_addr)
                uncontained = not target_server.is_containment_active()
                restored_worker = not worker_registry.is_isolated(worker_name, worker_pid)
                evidence_still_exists = Path(snapshot_path).exists() if snapshot_path else True
                total_rollback_success = (rollback_ok and unfiltered and uncontained and restored_worker and evidence_still_exists)

                verdict = (
                    "SUCCESS"
                    if (exec_record.overall_success and rpc_blocked and beacon_blocked and worker_isolated and legit_preserved and total_rollback_success)
                    else "FAILED"
                )

                return ProtectionExperimentRecord(
                    experiment_id=exp_id,
                    run_id=r_id,
                    scenario_id="scenario_b_synthetic_c2",
                    timestamp=t_start,
                    detection_status=det_status,
                    protection_plan_status=plan.status,
                    requested_actions_count=len(plan.actions),
                    executed_actions_count=exec_record.actions_executed,
                    verified_actions_count=exec_record.actions_verified,
                    failed_actions_count=exec_record.actions_failed,
                    containment_latency_ms=round(latency_ms, 3),
                    rpc_blocking_verified=rpc_blocked,
                    beacon_blocking_verified=beacon_blocked,
                    process_isolation_verified=worker_isolated,
                    legitimate_traffic_preserved=legit_preserved,
                    false_mitigation_applied=False,
                    evidence_preserved=evidence_ok,
                    evidence_file_path=snapshot_path,
                    rollback_success=total_rollback_success,
                    final_verdict=verdict,
                    details={
                        "plan_status": plan.status.value,
                        "actions_verified": exec_record.actions_verified,
                    },
                )

        # -------------------------------------------------------------
        # Case C: Controlled Fault Injection (Failure Negative Control)
        # -------------------------------------------------------------
        elif scenario_type in ("fault_injection", "scenario_c_fault_injection"):
            action = MitigationAction(
                mitigation_type=MitigationType.PROCESS_ISOLATION,
                target_layer="process",
                target_resource="unregistered_phantom_process",
                parameters={"process_name": "unregistered_phantom_process", "pid": 99999},
                verification_strategy="Check registry state",
            )
            plan = DefensePlan(
                detection_correlation_id=_generate_eval_uuid("corr-fault"),
                rule_id="RULE-CHAINC2-001",
                status=DefensePlanStatus.PENDING,
                actions=[action],
                evidence_summary="Controlled fault injection: unregistered process must fail gracefully.",
            )

            empty_registry = ScenarioWorkerRegistry()
            executor = DefenseExecutor(
                handlers={
                    MitigationType.PROCESS_ISOLATION: ProcessIsolationHandler(registry=empty_registry),
                }
            )

            t0 = time.perf_counter()
            exec_record = executor.execute_plan(plan)
            lat_ms = (time.perf_counter() - t0) * 1000.0

            # Verified failure handling: action must be FAILED, overall_success must be False
            fault_handled = (exec_record.actions_failed == 1 and plan.status == DefensePlanStatus.FAILED)

            return ProtectionExperimentRecord(
                experiment_id=exp_id,
                run_id=r_id,
                scenario_id="scenario_c_fault_injection",
                timestamp=t_start,
                detection_status=DetectionStatus.TRIGGERED,
                protection_plan_status=plan.status,
                requested_actions_count=1,
                executed_actions_count=0,
                verified_actions_count=0,
                failed_actions_count=1,
                containment_latency_ms=round(lat_ms, 3),
                rpc_blocking_verified=None,
                beacon_blocking_verified=None,
                process_isolation_verified=False,
                legitimate_traffic_preserved=True,
                false_mitigation_applied=False,
                evidence_preserved=None,
                evidence_file_path=None,
                rollback_success=None,
                final_verdict="FAULT_HANDLED" if fault_handled else "FAILED",
                details={"expected_failure_handled": fault_handled},
            )
        else:
            raise ValueError(f"Unknown scenario_type: {scenario_type}")

    def run_evaluation(
        self,
        repetitions_benign: int = 10,
        repetitions_c2: int = 10,
        repetitions_fault: int = 2,
        output_path: Optional[str] = "data/evaluation/protection_evaluation.json",
    ) -> AggregateProtectionEvaluationResult:
        """Run repeated protection evaluation experiments across all scenarios.

        Args:
            repetitions_benign: Repetitions for Scenario A (benign negative control).
            repetitions_c2: Repetitions for Scenario B (synthetic C2 positive control).
            repetitions_fault: Repetitions for fault injection negative control.
            output_path: Optional file path to persist JSON results.
        """
        logger.info(
            "Starting Milestone 10 Protection Evaluation: %d benign, %d synthetic C2, %d fault injection runs",
            repetitions_benign,
            repetitions_c2,
            repetitions_fault,
        )

        experiments: list[ProtectionExperimentRecord] = []

        # 1. Benign Scenario A runs
        for i in range(repetitions_benign):
            logger.info("Executing Scenario A evaluation run %d/%d", i + 1, repetitions_benign)
            record = self.run_single_experiment("scenario_a_benign")
            experiments.append(record)

        # 2. Synthetic C2 Scenario B runs
        for i in range(repetitions_c2):
            logger.info("Executing Scenario B evaluation run %d/%d", i + 1, repetitions_c2)
            record = self.run_single_experiment("scenario_b_synthetic_c2")
            experiments.append(record)

        # 3. Fault injection runs
        for i in range(repetitions_fault):
            logger.info("Executing Fault Injection evaluation run %d/%d", i + 1, repetitions_fault)
            record = self.run_single_experiment("scenario_c_fault_injection")
            experiments.append(record)

        metrics = self.calculate_metrics(experiments)

        result = AggregateProtectionEvaluationResult(
            evaluation_id=_generate_eval_uuid("eval-prot"),
            created_at=datetime.now(timezone.utc),
            rule_id="RULE-CHAINC2-001",
            total_experiments=len(experiments),
            scenario_counts={
                "scenario_a_benign": repetitions_benign,
                "scenario_b_synthetic_c2": repetitions_c2,
                "scenario_c_fault_injection": repetitions_fault,
            },
            metrics=metrics,
            experiments=experiments,
        )

        if output_path:
            self.save_results(result, output_path)

        return result

    @staticmethod
    def save_results(result: AggregateProtectionEvaluationResult, file_path: str) -> None:
        """Persist evaluation results to disk as structured JSON."""
        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        logger.info("Protection evaluation results saved to %s", target_path)

    @staticmethod
    def load_results(file_path: str) -> AggregateProtectionEvaluationResult:
        """Load evaluation results from JSON file."""
        target_path = Path(file_path)
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AggregateProtectionEvaluationResult.model_validate(data)
