# ChainC2 Sentinel — Protection Evaluation Models
"""Structured Pydantic models for Milestone 10 Protection Evaluation.

Safety and Research Declarations:
- Measures laboratory performance of defensive containment handlers implemented in M8 and M9.
- Quantifies mitigation success, containment latency, RPC blocking, beacon blocking,
  cooperative process isolation, legitimate traffic preservation, and rollback integrity.
- Operates strictly against controlled synthetic scenarios; does not claim proof of
  real-world malware containment or universal blockchain security efficacy.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.detection.models import DetectionStatus
from src.protection.models import DefensePlanStatus


class ProtectionExperimentRecord(BaseModel):
    """Detailed audit record of a single defensive response experiment execution."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str = Field(..., description="Unique experiment identifier")
    run_id: str = Field(..., description="Scenario run identifier")
    scenario_id: str = Field(..., description="Scenario identifier ('scenario_a_benign', 'scenario_b_synthetic_c2', 'scenario_c_fault_injection')")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Execution timestamp")
    detection_status: DetectionStatus = Field(..., description="Detection verdict ('triggered' or 'not_triggered')")
    protection_plan_status: DefensePlanStatus = Field(..., description="Final DefensePlan status ('verified', 'skipped', 'failed', 'rolled_back')")
    
    # Action counts
    requested_actions_count: int = Field(default=0, description="Total mitigation actions requested in the plan")
    executed_actions_count: int = Field(default=0, description="Total mitigation actions executed")
    verified_actions_count: int = Field(default=0, description="Total mitigation actions independently verified")
    failed_actions_count: int = Field(default=0, description="Total mitigation actions that failed")

    # Protection measurement dimensions
    containment_latency_ms: Optional[float] = Field(
        default=None, description="Time from protection plan invocation to verified containment in milliseconds"
    )
    rpc_blocking_verified: Optional[bool] = Field(
        default=None, description="Whether synthetic C2DataStore RPC queries were verified blocked (None if not applicable)"
    )
    beacon_blocking_verified: Optional[bool] = Field(
        default=None, description="Whether synthetic /beacon HTTP requests were verified blocked with HTTP 403"
    )
    process_isolation_verified: Optional[bool] = Field(
        default=None, description="Whether cooperative isolation of registered scenario worker was verified"
    )
    legitimate_traffic_preserved: bool = Field(
        default=True, description="Whether legitimate Web3 contract calls and /health endpoints remained functional"
    )
    false_mitigation_applied: bool = Field(
        default=False, description="Whether any mitigation action was erroneously executed on a benign negative control"
    )
    evidence_preserved: Optional[bool] = Field(
        default=None, description="Whether immutable evidence bundle was verified saved with valid SHA-256 digest"
    )
    evidence_file_path: Optional[str] = Field(
        default=None, description="File path to the preserved evidence bundle if applicable"
    )
    rollback_success: Optional[bool] = Field(
        default=None, description="Whether rollback successfully restored baseline state while keeping evidence intact"
    )
    final_verdict: str = Field(
        ..., description="Experiment verdict ('SUCCESS', 'FAILED', 'BENIGN_PRESERVED', 'FAULT_HANDLED')"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional context, timing, or telemetry metadata"
    )


class ProtectionEvaluationMetrics(BaseModel):
    """Aggregate statistical metrics for defensive response evaluation with explicit denominators."""

    model_config = ConfigDict(extra="forbid")

    total_experiments: int = Field(..., description="Total number of evaluated protection experiments")
    successful_experiments: int = Field(..., description="Number of experiments meeting all expected protection criteria")
    failed_experiments: int = Field(..., description="Number of experiments failing protection criteria")
    experiment_success_rate: float = Field(..., description="Ratio of successful experiments to total [successful / total]")

    # Scenario distributions
    scenario_a_runs: int = Field(default=0, description="Total Scenario A (benign negative control) runs")
    scenario_b_runs: int = Field(default=0, description="Total Scenario B (synthetic C2 positive control) runs")
    fault_injection_runs: int = Field(default=0, description="Total fault-injection negative control runs")

    # Protection efficacy metrics (None when denominator is 0)
    mitigation_success_rate: Optional[float] = Field(
        default=None,
        description="Verified mitigation actions / requested mitigation actions across triggered plans",
    )
    rpc_blocking_rate: Optional[float] = Field(
        default=None,
        description="Successfully verified RPC blocks / runs where RPC filter was requested",
    )
    beacon_blocking_rate: Optional[float] = Field(
        default=None,
        description="Successfully verified beacon HTTP 403 blocks / runs where network containment was requested",
    )
    process_isolation_success_rate: Optional[float] = Field(
        default=None,
        description="Successfully verified cooperative worker isolations / runs where process isolation was requested",
    )
    legitimate_traffic_preservation_rate: float = Field(
        ...,
        description="Runs where legitimate contract calls & /health remained available / total evaluated runs",
    )
    false_mitigation_rate: float = Field(
        ...,
        description="Benign Scenario A runs with erroneous mitigation / total Scenario A runs",
    )
    rollback_success_rate: Optional[float] = Field(
        default=None,
        description="Successfully verified rollbacks / total attempted rollbacks",
    )
    evidence_preservation_rate: Optional[float] = Field(
        default=None,
        description="Verified evidence bundles with valid checksums / total triggered runs",
    )

    # Containment latency statistics (milliseconds)
    containment_latency_min_ms: Optional[float] = Field(default=None, description="Minimum measured containment latency in ms")
    containment_latency_max_ms: Optional[float] = Field(default=None, description="Maximum measured containment latency in ms")
    containment_latency_avg_ms: Optional[float] = Field(default=None, description="Average measured containment latency in ms")
    containment_latency_median_ms: Optional[float] = Field(default=None, description="Median measured containment latency in ms")

    # Explicit formulas documentation
    metric_formulas: dict[str, str] = Field(
        default_factory=dict, description="Dictionary documenting the exact mathematical formula and denominator for each metric"
    )


class AggregateProtectionEvaluationResult(BaseModel):
    """Container holding complete protection evaluation metadata, metrics, and individual experiment records."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(..., description="Unique evaluation suite identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Evaluation creation timestamp")
    rule_id: str = Field(default="RULE-CHAINC2-001", description="Associated detection rule")
    total_experiments: int = Field(..., description="Total evaluated experiments count")
    scenario_counts: dict[str, int] = Field(default_factory=dict, description="Breakdown of runs per scenario")
    metrics: ProtectionEvaluationMetrics = Field(..., description="Aggregate deterministic protection metrics")
    experiments: list[ProtectionExperimentRecord] = Field(default_factory=list, description="All individual experiment records")
    research_disclaimer: str = Field(
        default=(
            "Laboratory evaluation result only. Measures containment efficacy, latency, "
            "and baseline preservation of defensive mechanisms under controlled synthetic conditions. "
            "Does not assert real-world malware containment or universal blockchain security efficacy."
        ),
        description="Mandatory scientific research limitation declaration",
    )
