# ChainC2 Sentinel — Scenario Runner
"""Orchestrator for executing controlled detection scenarios and collecting multi-source telemetry.

Matrix v2 Capabilities:
    Supports executing individual parameterized variants (A01-A08b, B01-B09, C01-C08)
    with experimental unit tracking, deterministic seeding, telemetry counting, and
    authoritative detection evaluation producing formal MatrixV2ExecutionRecord structures.

Usage:
    runner = ScenarioRunner(output_path="data/telemetry/events.jsonl")
    result, record = runner.run_variant(
        variant_id="A01",
        run_id="run-matrix-v2-001",
        replicate_id=1,
    )
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.correlation.engine import CrossLayerCorrelationEngine
from src.correlation.models import CorrelatedSequence
from src.detection.detector import DetectionEngine
from src.http_target.server import LocalHttpTargetServer
from src.models.events import TelemetrySource
from src.models.matrix_v2 import (
    Classification,
    ExecutionStatus,
    GroundTruth,
    MatrixV2ExecutionRecord,
    Provenance,
    VARIANT_REGISTRY,
    compute_deterministic_seed,
)
from src.normalizer.normalizer import EventStore
from src.scenarios.base import ScenarioResult
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.definitions.legitimate_dapp_scenario import LegitimateDAppScenario

logger = logging.getLogger("chainc2_sentinel.scenarios.runner")


class ScenarioRunner:
    """Orchestrates the execution of laboratory scenarios and manages persistence."""

    def __init__(
        self,
        output_path: Optional[str] = None,
        host: str = "127.0.0.1",
        rpc_proxy_url: str = "http://127.0.0.1:8546",
        upstream_url: str = "http://127.0.0.1:8545",
    ) -> None:
        """Initialize scenario runner.

        Args:
            output_path: Optional path to JSONL file for appending telemetry events.
            host: Host identifier.
            rpc_proxy_url: Client-facing RPC proxy URL.
            upstream_url: Upstream Hardhat node URL.
        """
        self.output_path = output_path
        self.host = host
        self.rpc_proxy_url = rpc_proxy_url
        self.upstream_url = upstream_url

        self.event_store = EventStore(output_path) if output_path else None
        self._correlation_engine = CrossLayerCorrelationEngine()
        self._detection_engine = DetectionEngine()

    def run_benign(self, run_id: Optional[str] = None) -> ScenarioResult:
        """Run Scenario A (Benign Web3 Activity - Default A04)."""
        scenario = BenignWeb3Scenario(
            run_id=run_id,
            event_store=self.event_store,
            host=self.host,
            rpc_proxy_url=self.rpc_proxy_url,
            upstream_url=self.upstream_url,
        )
        return scenario.run()

    def run_legitimate_dapp(self, run_id: Optional[str] = None) -> ScenarioResult:
        """Run Scenario C (Legitimate DApp Baseline - Default C01)."""
        scenario = LegitimateDAppScenario(
            run_id=run_id,
            event_store=self.event_store,
            host=self.host,
            rpc_proxy_url=self.rpc_proxy_url,
            upstream_url=self.upstream_url,
        )
        return scenario.run()

    def run_synthetic_c2(
        self,
        target_server: Optional[LocalHttpTargetServer] = None,
        run_id: Optional[str] = None,
    ) -> ScenarioResult:
        """Run Scenario B (Synthetic Blockchain-Mediated C2-Like Activity - Default B01)."""
        scenario = SyntheticC2Scenario(
            target_server=target_server,
            run_id=run_id,
            event_store=self.event_store,
            host=self.host,
            rpc_proxy_url=self.rpc_proxy_url,
            upstream_url=self.upstream_url,
        )
        return scenario.run()

    def run_variant(
        self,
        variant_id: str,
        parameters: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
        experimental_unit_id: Optional[str] = None,
        replicate_id: int = 1,
        state_context_id: Optional[str] = None,
        seed: Optional[int] = None,
        target_server: Optional[LocalHttpTargetServer] = None,
        evaluate_detection: bool = True,
    ) -> tuple[ScenarioResult, MatrixV2ExecutionRecord]:
        """Execute ONE explicitly selected Matrix v2 variant with parameters and produce a research execution record.

        Args:
            variant_id: Registered variant identifier (e.g. 'A01'..'A08b', 'B01'..'B09', 'C01'..'C08').
            parameters: Optional parameter dictionary for variant customization.
            run_id: Unique run identifier. Auto-generated if None.
            experimental_unit_id: Structural ID for experimental unit.
            replicate_id: Integer replicate index within variant.
            state_context_id: State context tracker.
            seed: Deterministic PRNG seed. Derived if None.
            target_server: Optional local HTTP target server for Scenario B variants.
            evaluate_detection: Whether to run correlation and detector evaluation.

        Returns:
            Tuple of (ScenarioResult, MatrixV2ExecutionRecord).
        """
        if variant_id not in VARIANT_REGISTRY:
            raise ValueError(f"Unknown Matrix v2 variant: {variant_id}. Must be one of {list(VARIANT_REGISTRY.keys())}")

        variant_spec = VARIANT_REGISTRY[variant_id]
        scenario_key = variant_spec["scenario"]
        behavior_family = variant_spec["behavior_family"]
        ground_truth = variant_spec["ground_truth"]
        detection_hypothesis = variant_spec["detection_hypothesis"]
        default_provenance = variant_spec["provenance"]

        t_start = datetime.now(timezone.utc)
        r_id = run_id or f"run-mat2-{variant_id.lower()}-{uuid.uuid4().hex[:8]}"
        computed_seed = seed if seed is not None else compute_deterministic_seed(r_id)
        unit_id = experimental_unit_id or f"unit-{variant_id}-rep{replicate_id:03d}"
        state_id = state_context_id or f"ctx-{variant_id}-r{replicate_id}"
        exp_id = f"exp-{variant_id.lower()}-{r_id[:12]}"
        params = parameters or {}

        # Instantiate appropriate scenario
        if variant_id.startswith("A"):
            scenario = BenignWeb3Scenario(
                variant_id=variant_id,
                parameters=params,
                experimental_unit_id=unit_id,
                replicate_id=replicate_id,
                state_context_id=state_id,
                seed=computed_seed,
                run_id=r_id,
                event_store=self.event_store,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
            )
        elif variant_id.startswith("B"):
            scenario = SyntheticC2Scenario(
                variant_id=variant_id,
                parameters=params,
                experimental_unit_id=unit_id,
                replicate_id=replicate_id,
                state_context_id=state_id,
                seed=computed_seed,
                target_server=target_server,
                run_id=r_id,
                event_store=self.event_store,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
            )
        elif variant_id.startswith("C"):
            scenario = LegitimateDAppScenario(
                variant_id=variant_id,
                parameters=params,
                experimental_unit_id=unit_id,
                replicate_id=replicate_id,
                state_context_id=state_id,
                seed=computed_seed,
                run_id=r_id,
                event_store=self.event_store,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
            )
        else:
            raise ValueError(f"Unmapped variant namespace for: {variant_id}")

        # Execute scenario
        scenario_result = scenario.run()
        t_end = datetime.now(timezone.utc)

        # Inspect scenario details for execution status, errors, and provenance
        details = scenario_result.details or {}
        raw_status = details.get("execution_status", "SUCCESS" if scenario_result.success else "FAILED")
        if raw_status == "VALIDATION_REJECTED":
            exec_status = ExecutionStatus.VALIDATION_REJECTED
        elif raw_status == "SUCCESS":
            exec_status = ExecutionStatus.SUCCESS
        else:
            exec_status = ExecutionStatus.FAILED

        rec_provenance = default_provenance
        if details.get("provenance") == "SIMULATED_FIXTURE":
            rec_provenance = Provenance.SIMULATED_FIXTURE

        # Extract per-layer event counts
        ep_count = scenario_result.event_counts_by_source.get(TelemetrySource.ENDPOINT.value, 0)
        rpc_count = scenario_result.event_counts_by_source.get(TelemetrySource.RPC.value, 0)
        bc_count = scenario_result.event_counts_by_source.get(TelemetrySource.BLOCKCHAIN.value, 0)
        net_count = scenario_result.event_counts_by_source.get(TelemetrySource.NETWORK.value, 0)
        tot_count = len(scenario_result.events)

        # Detection evaluation
        detector_score = 0.0
        detector_threshold = 80.0
        rule_conjunction_triggered = False
        score_threshold_met = False
        triggered = False
        classification = Classification.TN
        detection_latency_ms: Optional[float] = None

        if evaluate_detection and tot_count > 0:
            perf_start = time.perf_counter()
            sequences = self._correlation_engine.correlate(scenario_result.events)
            sequence = sequences[0] if sequences else CorrelatedSequence(
                run_id=r_id,
                scenario_id=scenario_result.scenario_id,
            )
            det_results = self._detection_engine.evaluate_sequence(sequence)
            detection_latency_ms = (time.perf_counter() - perf_start) * 1000.0

            if det_results:
                primary_result = det_results[0]
                detector_score = float(primary_result.total_score or 0.0)
                detector_threshold = float(primary_result.threshold or 80.0)
                rule_conjunction_triggered = bool(primary_result.triggered)
                score_threshold_met = bool(detector_score >= detector_threshold)
                # CRITICAL: Preserve existing detector decision semantics
                triggered = bool(primary_result.triggered)

        # Compute classification against ground truth
        if ground_truth == GroundTruth.SYNTHETIC_C2:
            if exec_status == ExecutionStatus.VALIDATION_REJECTED:
                # Validated rejection prior to socket creation does not reach detector C1-C7
                classification = Classification.EXCLUDED
            else:
                classification = Classification.TP if triggered else Classification.FN
        elif ground_truth == GroundTruth.INVALID_EXECUTION:
            classification = Classification.EXCLUDED
        else:  # BENIGN or LEGITIMATE_DAPP
            classification = Classification.FP if triggered else Classification.TN

        record = MatrixV2ExecutionRecord(
            run_id=r_id,
            experiment_id=exp_id,
            experimental_unit_id=unit_id,
            workload_variant_id=variant_id,
            replicate_id=replicate_id,
            state_context_id=state_id,
            scenario=scenario_key,
            behavior_family=behavior_family,
            variant_id=variant_id,
            parameters=params,
            seed=computed_seed,
            timestamp_start=t_start,
            timestamp_end=t_end,
            execution_status=exec_status,
            ground_truth=ground_truth,
            detection_hypothesis=detection_hypothesis,
            provenance=rec_provenance,
            endpoint_event_count=ep_count,
            rpc_event_count=rpc_count,
            blockchain_event_count=bc_count,
            network_event_count=net_count,
            total_events=tot_count,
            detector_score=detector_score,
            detector_threshold=detector_threshold,
            rule_conjunction_triggered=rule_conjunction_triggered,
            score_threshold_met=score_threshold_met,
            triggered=triggered,
            classification=classification,
            detection_latency_ms=detection_latency_ms,
            mitigation_result=details.get("mitigation_result"),
            mitigation_latency_ms=details.get("mitigation_latency_ms"),
            failure_type=details.get("failure_type"),
            failure_stage=details.get("failure_stage"),
            error_details=details.get("error_details"),
        )

        return scenario_result, record

    def run_all(self, target_server: Optional[LocalHttpTargetServer] = None) -> list[ScenarioResult]:
        """Run legacy baseline Phase 1 scenarios in sequence (Scenario A, Scenario B, Scenario C)."""
        results = [
            self.run_benign(),
            self.run_synthetic_c2(target_server=target_server),
            self.run_legitimate_dapp(),
        ]
        return results

    @staticmethod
    def summarize(results: list[ScenarioResult]) -> dict[str, Any]:
        """Generate a structured summary report of scenario execution runs."""
        total_events = sum(len(r.events) for r in results)
        total_by_source: dict[str, int] = {
            TelemetrySource.ENDPOINT.value: 0,
            TelemetrySource.RPC.value: 0,
            TelemetrySource.BLOCKCHAIN.value: 0,
            TelemetrySource.NETWORK.value: 0,
        }
        scenario_summaries = []

        for r in results:
            for source, count in r.event_counts_by_source.items():
                total_by_source[source] = total_by_source.get(source, 0) + count

            scenario_summaries.append({
                "scenario_id": r.scenario_id,
                "run_id": r.run_id,
                "success": r.success,
                "total_events": len(r.events),
                "event_counts": r.event_counts_by_source,
                "details": r.details,
            })

        return {
            "total_scenarios": len(results),
            "total_events": total_events,
            "events_by_source": total_by_source,
            "scenarios": scenario_summaries,
        }
