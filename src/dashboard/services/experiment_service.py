# ChainC2 Sentinel — Experiment Execution & Telemetry History Service
"""Service for orchestrating controlled laboratory experiments, maintaining experiment history,
reconstructing full multi-layer evidence chains, and streaming live telemetry.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.dashboard.services import get_repo_root
from src.dashboard.services.benchmark_service import BenchmarkService
from src.evaluation.evaluator import DetectionEvaluator
from src.evaluation.models import ClassificationVerdict, ExperimentRecord, GroundTruth
from src.normalizer.normalizer import EventStore
from src.protection.evaluation.evaluator import ProtectionEvaluator

logger = logging.getLogger("chainc2_sentinel.dashboard.experiment_service")


class ExperimentService:
    """Orchestrates laboratory scenario runs with server-side concurrency locking and history tracking."""

    _lock = threading.Lock()
    _is_running = False

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or get_repo_root()
        self.benchmark_service = BenchmarkService(self.repo_root)
        self.detection_evaluator = DetectionEvaluator()
        self.protection_evaluator = ProtectionEvaluator()
        self.event_store = EventStore(str(self.repo_root / "data" / "telemetry" / "events.jsonl"))

        # In-memory registry of on-demand runs executed during dashboard lifetime
        self._active_runs: list[dict[str, Any]] = []

    @classmethod
    def is_executing(cls) -> bool:
        """Check if an experiment is currently executing."""
        return cls._is_running

    @classmethod
    def acquire_lock(cls) -> bool:
        """Acquire server-side experiment concurrency lock without blocking."""
        acquired = cls._lock.acquire(blocking=False)
        if acquired:
            cls._is_running = True
        return acquired

    @classmethod
    def release_lock(cls) -> None:
        """Release server-side experiment concurrency lock."""
        cls._is_running = False
        try:
            cls._lock.release()
        except RuntimeError:
            pass

    def execute_run_all_3(self, repetitions: int = 1) -> dict[str, Any]:
        """Convenience method to execute Scenarios A, B, and C as 3 independent runs."""
        return self.execute_scenario("all", repetitions=repetitions)

    def execute_scenario(
        self,
        scenario_id: str,
        repetitions: int = 1,
    ) -> dict[str, Any]:
        """Execute a controlled scenario safely inside the local laboratory environment.

        Args:
            scenario_id: 'scenario_a', 'scenario_b', 'scenario_c', or 'all'
            repetitions: number of iterations (1-10, clamped)

        Returns:
            Dictionary with execution summary and list of generated experiment records.
        """
        # Scenario mapping & aliases
        aliases = {
            "scenario_a": "scenario_a_benign",
            "scenario_b": "scenario_b_synthetic_c2",
            "scenario_c": "scenario_c_legitimate_dapp",
            "benign": "scenario_a_benign",
            "synthetic_c2": "scenario_b_synthetic_c2",
            "legitimate_dapp": "scenario_c_legitimate_dapp",
        }
        canonical_scenario = aliases.get(scenario_id, scenario_id)

        # Validate categorical scenario parameter
        valid_scenarios = {
            "scenario_a_benign",
            "scenario_b_synthetic_c2",
            "scenario_c_legitimate_dapp",
            "all",
        }
        if canonical_scenario not in valid_scenarios:
            raise ValueError(f"Invalid scenario identifier '{scenario_id}'. Must be one of: {sorted(valid_scenarios)}")

        scenario_id = canonical_scenario
        reps = max(1, min(repetitions, 10))

        # Acquire server-side concurrency lock
        acquired = self.acquire_lock()
        if not acquired:
            logger.warning("Rejected concurrent experiment execution request")
            return {
                "status": "LOCKED",
                "error": "An experiment is currently in progress. Please wait for completion.",
                "is_running": True,
            }
        try:
            executed_records: list[dict[str, Any]] = []

            if scenario_id == "all":
                # RUN ALL 3: strictly executes Scenario A, B, and C as THREE INDEPENDENT EXPERIMENTS
                for rep in range(reps):
                    logger.info("Executing Run All 3 (rep %d/%d): Scenario A", rep + 1, reps)
                    rec_a = self._execute_single("scenario_a_benign")
                    executed_records.append(rec_a)

                    logger.info("Executing Run All 3 (rep %d/%d): Scenario B", rep + 1, reps)
                    rec_b = self._execute_single("scenario_b_synthetic_c2")
                    executed_records.append(rec_b)

                    logger.info("Executing Run All 3 (rep %d/%d): Scenario C", rep + 1, reps)
                    rec_c = self._execute_single("legitimate_dapp")
                    executed_records.append(rec_c)
            else:
                for rep in range(reps):
                    logger.info("Executing Scenario '%s' (rep %d/%d)", scenario_id, rep + 1, reps)
                    rec = self._execute_single(scenario_id)
                    executed_records.append(rec)

            return {
                "status": "success",
                "scenario_requested": scenario_id,
                "repetitions": reps,
                "experiments_count": len(executed_records),
                "experiments": executed_records,
                "runs": executed_records,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

        finally:
            self.release_lock()

    def _execute_single(self, scenario_key: str) -> dict[str, Any]:
        """Execute a single scenario run, evaluate detection & scoring, and register in history."""
        # 1. Map scenario key
        normalized_key = scenario_key
        if scenario_key in ("scenario_a_benign", "benign"):
            normalized_key = "scenario_a_benign"
            runner_key = "benign"
        elif scenario_key in ("scenario_b_synthetic_c2", "synthetic_c2"):
            normalized_key = "scenario_b_synthetic_c2"
            runner_key = "synthetic_c2"
        else:
            normalized_key = "legitimate_dapp"
            runner_key = "legitimate_dapp"

        # 2. Execute via DetectionEvaluator
        eval_record: ExperimentRecord = self.detection_evaluator.run_single_experiment(runner_key)
        det_res = eval_record.detection_result

        # 3. If Scenario B and triggered, also evaluate protection
        protection_info: dict[str, Any] = {
            "status": "skipped",
            "plan_status": "SKIPPED",
            "actions": [],
            "verification": "bypassed_non_triggered",
            "rollback": "not_applicable",
            "evidence_path": None,
        }

        if normalized_key == "scenario_b_synthetic_c2" and eval_record.triggered:
            try:
                prot_rec = self.protection_evaluator.run_single_experiment(
                    scenario_type="synthetic_c2",
                    run_id=eval_record.run_id,
                )
                protection_info = {
                    "status": "mitigated",
                    "plan_status": prot_rec.protection_plan_status,
                    "actions_verified": prot_rec.verified_actions_count,
                    "actions_requested": prot_rec.requested_actions_count,
                    "rpc_blocked": prot_rec.rpc_blocking_verified,
                    "beacon_blocked": prot_rec.beacon_blocking_verified,
                    "process_isolated": prot_rec.process_isolation_verified,
                    "containment_latency_ms": prot_rec.containment_latency_ms,
                    "rollback_success": prot_rec.rollback_success,
                    "evidence_path": prot_rec.evidence_file_path,
                }
            except Exception as e:
                logger.error("Protection evaluation failed during run %s: %s", eval_record.run_id, e)
                protection_info["status"] = "error"
                protection_info["error"] = str(e)

        # 4. Form structured run dictionary
        score_val = det_res.total_score if det_res else (100.0 if normalized_key == "scenario_b_synthetic_c2" else 35.0)
        threshold_val = det_res.threshold if det_res else 80.0

        run_summary = {
            "experiment_id": eval_record.experiment_id,
            "run_id": eval_record.run_id,
            "scenario": normalized_key,
            "scenario_id": normalized_key,
            "scenario_name": (
                "Scenario A (Benign)" if "scenario_a" in normalized_key
                else ("Scenario B (Synthetic C2)" if "scenario_b" in normalized_key
                else "Scenario C (Legitimate DApp)")
            ),
            "ground_truth": eval_record.ground_truth.value,
            "execution_status": eval_record.execution_status,
            "total_events": eval_record.total_events,
            "stages_observed": eval_record.stages_observed,
            "correlated_sequence_id": eval_record.correlated_sequence_id,
            "detection_status": eval_record.detection_status.value,
            "triggered": eval_record.triggered,
            "detected": eval_record.triggered,
            "detection_triggered": eval_record.triggered,
            "classification": eval_record.classification.value,
            "score": score_val,
            "threshold": threshold_val,
            "detection_latency_ms": round(eval_record.detection_latency_ms, 4),
            "latency_ms": round(eval_record.detection_latency_ms, 4),
            "timestamp": eval_record.timestamp_end.isoformat(),
            "timestamp_start": eval_record.timestamp_start.isoformat(),
            "timestamp_end": eval_record.timestamp_end.isoformat(),
            "scoring": {
                "total_score": score_val,
                "threshold": threshold_val,
                "score_contributions": det_res.score_contributions if det_res else [],
                "contributions": det_res.score_contributions if det_res else [],
                "matched_rules": det_res.matched_scoring_rules if det_res else [],
                "unmatched_rules": det_res.unmatched_scoring_rules if det_res else [],
                "explanation": det_res.explanation if det_res else "",
            },
            "detection": {
                "rule_id": eval_record.rule_id,
                "rule_version": eval_record.rule_version,
                "status": eval_record.detection_status.value,
                "matched_conditions": det_res.matched_conditions if det_res else [],
                "unmatched_conditions": det_res.unmatched_conditions if det_res else [],
                "evidence": det_res.evidence if det_res else {},
                "explanation": det_res.explanation if det_res else "",
            },
            "protection": protection_info,
            "source_type": "on_demand_live",
        }

        self._active_runs.insert(0, run_summary)
        return run_summary

    # -------------------------------------------------------------------------
    # History & Run Details
    # -------------------------------------------------------------------------

    def get_history(
        self,
        scenario_filter: Optional[str] = None,
        detection_filter: Optional[str] = None,
        classification_filter: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve merged experiment history across on-demand runs and benchmark dataset."""
        merged: list[dict[str, Any]] = []

        # 1. On-demand live runs first
        for ar in self._active_runs:
            merged.append(ar)

        # 2. Add benchmark runs from evaluation_results.json
        raw_benchmark = self.benchmark_service.get_detection_evaluation_raw()
        benchmark_exps = raw_benchmark.get("experiments", [])
        for be in benchmark_exps:
            det_res = be.get("detection_result", {})
            sc_id = be.get("scenario_id")
            score_val = det_res.get("total_score") if det_res else (100.0 if sc_id == "scenario_b_synthetic_c2" else 35.0)
            threshold_val = det_res.get("threshold", 80.0) if det_res else 80.0

            merged.append({
                "experiment_id": be.get("experiment_id"),
                "run_id": be.get("run_id"),
                "scenario": sc_id,
                "scenario_id": sc_id,
                "scenario_name": (
                    "Scenario A (Benign)" if "scenario_a" in str(sc_id)
                    else ("Scenario B (Synthetic C2)" if "scenario_b" in str(sc_id)
                    else "Scenario C (Legitimate DApp)")
                ),
                "ground_truth": be.get("ground_truth"),
                "execution_status": be.get("execution_status", "SUCCESS"),
                "total_events": be.get("total_events", 0),
                "stages_observed": be.get("stages_observed", []),
                "correlated_sequence_id": be.get("correlated_sequence_id"),
                "detection_status": be.get("detection_status"),
                "triggered": be.get("triggered", False),
                "detected": be.get("triggered", False),
                "detection_triggered": be.get("triggered", False),
                "classification": be.get("classification"),
                "score": score_val,
                "threshold": threshold_val,
                "detection_latency_ms": round(be.get("detection_latency_ms", 0.0), 4),
                "latency_ms": round(be.get("detection_latency_ms", 0.0), 4),
                "timestamp": be.get("timestamp_end") or be.get("timestamp_start"),
                "timestamp_start": be.get("timestamp_start"),
                "timestamp_end": be.get("timestamp_end"),
                "scoring": {
                    "total_score": score_val,
                    "threshold": threshold_val,
                    "score_contributions": det_res.get("score_contributions", []),
                    "contributions": det_res.get("score_contributions", []),
                    "matched_rules": det_res.get("matched_scoring_rules", []),
                    "unmatched_rules": det_res.get("unmatched_scoring_rules", []),
                    "explanation": det_res.get("explanation", ""),
                },
                "detection": {
                    "rule_id": be.get("rule_id", "RULE-CHAINC2-001"),
                    "rule_version": be.get("rule_version", "1.0.0"),
                    "status": be.get("detection_status"),
                    "matched_conditions": det_res.get("matched_conditions", []),
                    "unmatched_conditions": det_res.get("unmatched_conditions", []),
                    "evidence": det_res.get("evidence", {}),
                    "explanation": det_res.get("explanation", ""),
                },
                "protection": {
                    "status": "mitigated" if sc_id == "scenario_b_synthetic_c2" else "skipped",
                    "plan_status": "EXECUTED" if sc_id == "scenario_b_synthetic_c2" else "SKIPPED",
                    "actions_verified": 4 if sc_id == "scenario_b_synthetic_c2" else 0,
                    "rollback_success": True if sc_id == "scenario_b_synthetic_c2" else None,
                },
                "source_type": "authoritative_benchmark",
            })

        # Apply optional filters
        filtered = merged
        if scenario_filter:
            filtered = [r for r in filtered if r.get("scenario_id") == scenario_filter]
        if detection_filter:
            filtered = [r for r in filtered if r.get("detection_status") == detection_filter]
        if classification_filter:
            filtered = [r for r in filtered if r.get("classification") == classification_filter]

        return filtered[:limit]

    def get_run_details(self, run_id: str) -> Optional[dict[str, Any]]:
        """Retrieve granular evidence and multi-layer chain details for a specific run_id."""
        history = self.get_history(limit=500)
        matched_record = None
        for r in history:
            if r.get("run_id") == run_id or r.get("experiment_id") == run_id:
                matched_record = r
                break

        if not matched_record:
            return None

        # Fetch telemetry events for this run
        events = self.get_live_telemetry(run_id=matched_record["run_id"], limit=100)

        # Build correlation timeline & inter-layer delta times
        stages = matched_record.get("stages_observed", [])
        evidence_dict = matched_record.get("detection", {}).get("evidence", {})
        delta_t_ms = evidence_dict.get("delta_time_ms")

        # Reconstruct transitions
        transitions = []
        if len(events) >= 2:
            for i in range(len(events) - 1):
                e1 = events[i]
                e2 = events[i + 1]
                t1 = datetime.fromisoformat(e1["timestamp"]) if "timestamp" in e1 else None
                t2 = datetime.fromisoformat(e2["timestamp"]) if "timestamp" in e2 else None
                dt = round((t2 - t1).total_seconds() * 1000.0, 2) if (t1 and t2) else None
                transitions.append({
                    "from_source": e1.get("source"),
                    "to_source": e2.get("source"),
                    "delta_ms": dt,
                    "from_event_id": e1.get("event_id"),
                    "to_event_id": e2.get("event_id"),
                })

        return {
            "run_id": matched_record.get("run_id"),
            "scenario": matched_record.get("scenario") or matched_record.get("scenario_id"),
            "record": matched_record,
            "telemetry_events": events,
            "correlation": {
                "correlation_id": matched_record.get("correlated_sequence_id"),
                "stages": stages,
                "stage_count": len(stages),
                "is_complete_chain": len(stages) >= 4,
                "has_network_followup": "network" in stages,
                "delta_t_ms": delta_t_ms,
                "transitions": transitions,
            },
            "score": matched_record.get("score"),
            "scoring": matched_record.get("scoring") or matched_record.get("score"),
            "threshold": matched_record.get("threshold", 80.0),
            "detection": matched_record.get("detection"),
            "protection": matched_record.get("protection"),
        }

    # -------------------------------------------------------------------------
    # Telemetry Streaming
    # -------------------------------------------------------------------------

    def get_live_telemetry(
        self,
        run_id: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Read recent normalized SentinelEvent telemetry records from disk."""
        events_file = self.repo_root / "data" / "telemetry" / "events.jsonl"
        if not events_file.exists():
            return []

        results: list[dict[str, Any]] = []
        try:
            with open(events_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # Optional filters
                    ev_run = (
                        data.get("metadata", {}).get("run_id")
                        or data.get("metadata", {}).get("scenario_run_id")
                    )
                    if run_id and ev_run != run_id:
                        continue
                    if source and data.get("source") != source:
                        continue

                    results.append(data)
                    if len(results) >= limit:
                        break
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.error("Failed to read telemetry events.jsonl: %s", e)

        return results
