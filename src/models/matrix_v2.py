# ChainC2 Sentinel — Matrix v2 Execution Record Schema & Registry
"""Formal data model for the frozen ChainC2 Sentinel Experimental Matrix v2.

Defines:
- MatrixV2ExecutionRecord Pydantic model with strict validation.
- Enums for ExecutionStatus, GroundTruth, Provenance, and Classification.
- Deterministic seed computation: int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16)
- Authoritative 27-variant registry with ground truth and detection hypotheses.
"""

from __future__ import annotations

import enum
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Deterministic Seed Function (LOCKED FORMULA)
# ---------------------------------------------------------------------------

def compute_deterministic_seed(run_id: str) -> int:
    """Compute deterministic PRNG seed from run_id using SHA-256.

    Formula locked by research specification:
        int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16)
    """
    return int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExecutionStatus(str, enum.Enum):
    """Execution status of an experimental run."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    VALIDATION_REJECTED = "VALIDATION_REJECTED"


class GroundTruth(str, enum.Enum):
    """Ground-truth scientific class of an experimental run."""
    BENIGN = "BENIGN"
    SYNTHETIC_C2 = "SYNTHETIC_C2"
    LEGITIMATE_DAPP = "LEGITIMATE_DAPP"
    INVALID_EXECUTION = "INVALID_EXECUTION"


class Provenance(str, enum.Enum):
    """Data provenance classification."""
    GENUINE_EXECUTION = "GENUINE_EXECUTION"
    SIMULATED_FIXTURE = "SIMULATED_FIXTURE"
    RECONSTRUCTED_FALLBACK = "RECONSTRUCTED_FALLBACK"
    ILLUSTRATIVE = "ILLUSTRATIVE"


class Classification(str, enum.Enum):
    """Evaluation classification outcome."""
    TP = "TP"
    TN = "TN"
    FP = "FP"
    FN = "FN"
    EXCLUDED = "EXCLUDED"


# ---------------------------------------------------------------------------
# Execution Record Model (Matrix v2)
# ---------------------------------------------------------------------------

class MatrixV2ExecutionRecord(BaseModel):
    """Execution record for Matrix v2 experimental campaigns.

    Conforms strictly to the 27-variant frozen specification.
    """

    model_config = ConfigDict(extra="forbid")

    # Identifiers & Experimental Unit Structure
    run_id: str = Field(..., description="Unique execution run ID")
    experiment_id: str = Field(..., description="Unique experiment ID")
    experimental_unit_id: str = Field(..., description="Isolated experimental unit identifier")
    workload_variant_id: str = Field(..., description="Variant identifier (e.g. A01..C08)")
    replicate_id: int = Field(..., description="Replicate index within stratum")
    state_context_id: str = Field(..., description="State context tracking clean vs accumulated state")

    # Scenario & Behavior Taxonomy
    scenario: str = Field(..., description="Scenario identifier: scenario_a, scenario_b, or scenario_c")
    behavior_family: str = Field(..., description="Behavior family (e.g. A-RO, B-STD, C-LIFE)")
    variant_id: str = Field(..., description="Variant code (A01, B01, etc.)")

    # Parameters & Reproducibility
    parameters: dict[str, Any] = Field(default_factory=dict, description="Sampled parameter dimensions")
    seed: int = Field(..., description="Deterministic seed derived from run_id")
    timestamp_start: str = Field(..., description="Start timestamp (ISO-8601 UTC)")
    timestamp_end: str = Field(..., description="End timestamp (ISO-8601 UTC)")

    # Status & Scientific Ground Truth
    execution_status: ExecutionStatus = Field(..., description="Execution outcome")
    ground_truth: GroundTruth = Field(..., description="Factual ground truth")
    detection_hypothesis: str = Field(..., description="Pre-execution detection hypothesis")
    provenance: Provenance = Field(..., description="Data provenance classification")

    # Telemetry Event Counts
    endpoint_event_count: int = Field(default=0, description="Endpoint layer event count")
    rpc_event_count: int = Field(default=0, description="RPC layer event count")
    blockchain_event_count: int = Field(default=0, description="Blockchain layer event count")
    network_event_count: int = Field(default=0, description="Network layer event count")
    total_events: int = Field(default=0, description="Sum of events across all 4 layers")

    # Detector Evaluation (Observed Post-Execution)
    detector_score: float = Field(default=0.0, description="Composite weighted indicator score")
    detector_threshold: float = Field(default=80.0, description="Configured detector threshold")
    rule_conjunction_triggered: bool = Field(default=False, description="Whether 7-condition conjunction passed")
    score_threshold_met: bool = Field(default=False, description="Whether detector_score >= detector_threshold")
    triggered: bool = Field(default=False, description="Authoritative detection outcome (from rule conjunction)")
    classification: Classification = Field(default=Classification.EXCLUDED, description="Performance classification")
    detection_latency_ms: float = Field(default=0.0, description="Detection evaluation latency in milliseconds")

    # Optional Mitigation & Error Context
    mitigation_result: Optional[str] = Field(default=None, description="Mitigation status if applicable")
    mitigation_latency_ms: Optional[float] = Field(default=None, description="Containment latency in milliseconds")
    failure_type: Optional[str] = Field(default=None, description="Failure category if execution failed")
    failure_stage: Optional[str] = Field(default=None, description="Stage where failure occurred")
    error_details: Optional[str] = Field(default=None, description="Exception or error message")


# ---------------------------------------------------------------------------
# Authoritative 27-Variant Specification Registry
# ---------------------------------------------------------------------------

VARIANT_REGISTRY: dict[str, dict[str, Any]] = {
    # SCENARIO A: BENIGN WEB3 (9 variants)
    "A01": {
        "scenario": "scenario_a",
        "behavior_family": "A-RO",
        "name": "getCount() via eth_call",
        "ground_truth": GroundTruth.BENIGN,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: network event (C5) and C2 contract (C4) absent.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "A02": {
        "scenario": "scenario_a",
        "behavior_family": "A-RO",
        "name": "message() via eth_call",
        "ground_truth": GroundTruth.BENIGN,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: network event (C5) and C2 contract (C4) absent.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "A03": {
        "scenario": "scenario_a",
        "behavior_family": "A-RO",
        "name": "deployer() via eth_call",
        "ground_truth": GroundTruth.BENIGN,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: network event (C5) and C2 contract (C4) absent.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "A04": {
        "scenario": "scenario_a",
        "behavior_family": "A-MUT",
        "name": "increment() transaction",
        "ground_truth": GroundTruth.BENIGN,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: network event (C5) and C2 contract (C4) absent.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "A05": {
        "scenario": "scenario_a",
        "behavior_family": "A-MUT",
        "name": "updateMessage(string) transaction",
        "ground_truth": GroundTruth.BENIGN,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: network event (C5) and C2 contract (C4) absent.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "A06": {
        "scenario": "scenario_a",
        "behavior_family": "A-MIX",
        "name": "getCount -> increment -> getCount",
        "ground_truth": GroundTruth.BENIGN,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: network event (C5) and C2 contract (C4) absent.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "A07": {
        "scenario": "scenario_a",
        "behavior_family": "A-BURST",
        "name": "getCount burst polling (N=5..10, delay <10ms)",
        "ground_truth": GroundTruth.BENIGN,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: network event (C5) and C2 contract (C4) absent.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "A08a": {
        "scenario": "scenario_a",
        "behavior_family": "A-FAIL",
        "name": "Controlled invalid/stale nonce error",
        "ground_truth": GroundTruth.INVALID_EXECUTION,
        "detection_hypothesis": "RPC error state. Expected not to satisfy rule conjunction: transaction rejected before mining.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "A08b": {
        "scenario": "scenario_a",
        "behavior_family": "A-FAIL",
        "name": "Controlled gas_limit below intrinsic gas",
        "ground_truth": GroundTruth.INVALID_EXECUTION,
        "detection_hypothesis": "RPC error state. Expected not to satisfy rule conjunction: EVM execution aborted.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },

    # SCENARIO B: SYNTHETIC C2-LIKE ACTIVITY (10 variants)
    "B01": {
        "scenario": "scenario_b",
        "behavior_family": "B-STD",
        "name": "getLatestCommand -> localhost /beacon",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Expected to satisfy rule conjunction if all temporal (C6, C7) and cross-layer events align.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "B02": {
        "scenario": "scenario_b",
        "behavior_family": "B-CADENCE",
        "name": "Fixed cadence polling (500..2000ms)",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Expected to satisfy rule conjunction across repeated cycles if Δt >= 0 is preserved.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "B03": {
        "scenario": "scenario_b",
        "behavior_family": "B-CADENCE",
        "name": "Jittered delay polling (50..800ms)",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Expected to satisfy rule conjunction if delay remains within correlation window (<60s).",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "B04": {
        "scenario": "scenario_b",
        "behavior_family": "B-INDEX",
        "name": "getCommandCount -> getCommandAtIndex(i) -> localhost /beacon",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Expected to satisfy rule conjunction: multi-RPC queries bind to target contract C2DataStore (C4).",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "B05": {
        "scenario": "scenario_b",
        "behavior_family": "B-STORE",
        "name": "storeCommand() transaction -> getLatestCommand -> localhost /beacon",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Expected to satisfy rule conjunction: genuine on-chain staging followed by loopback beacon.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "B06": {
        "scenario": "scenario_b",
        "behavior_family": "B-ANOMALY",
        "name": "Safe simulated endpoint anomaly fixture -> getLatestCommand -> localhost /beacon",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Expected to satisfy rule conjunction: anomaly binds to C2DataStore and loopback beacon by PID.",
        "provenance": Provenance.SIMULATED_FIXTURE,
    },
    "B07a": {
        "scenario": "scenario_b",
        "behavior_family": "B-FAIL",
        "name": "Closed loopback port / ECONNREFUSED",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Expected to satisfy rule conjunction: network event captured with status_code=500 (ECONNREFUSED).",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "B07b": {
        "scenario": "scenario_b",
        "behavior_family": "B-FAIL",
        "name": "Controlled loopback timeout >5s",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Controlled loopback socket timeout (>5.0s delay). Expected to satisfy C1-C7 if timeout event logs.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "B08": {
        "scenario": "scenario_b",
        "behavior_family": "B-FAIL",
        "name": "Quarantine rejection -> HTTP 403",
        "ground_truth": GroundTruth.SYNTHETIC_C2,
        "detection_hypothesis": "Expected to satisfy rule conjunction; target returns HTTP 403 (quarantine mitigation active).",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "B09": {
        "scenario": "scenario_b",
        "behavior_family": "B-FAIL",
        "name": "Validator rejection before socket creation",
        "ground_truth": GroundTruth.INVALID_EXECUTION,
        "detection_hypothesis": "Rejected by SyntheticC2Payload validator. Aborts prior to socket creation; 0 network events.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },

    # SCENARIO C: LEGITIMATE DAPP (8 variants)
    "C01": {
        "scenario": "scenario_c",
        "behavior_family": "C-LIFE",
        "name": "createTask -> getTask -> updateStatus(Completed) -> getTask",
        "ground_truth": GroundTruth.LEGITIMATE_DAPP,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: network event (C5) and C2 contract (C4) absent.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "C02": {
        "scenario": "scenario_c",
        "behavior_family": "C-LIFE",
        "name": "createTask -> getTask -> updateStatus(InProgress) -> getTask",
        "ground_truth": GroundTruth.LEGITIMATE_DAPP,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: legitimate task progression without C2 events.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "C03": {
        "scenario": "scenario_c",
        "behavior_family": "C-BATCH",
        "name": "Batch multi-task workflow (2..5 tasks)",
        "ground_truth": GroundTruth.LEGITIMATE_DAPP,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: multi-transaction sequence without network calls.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "C04": {
        "scenario": "scenario_c",
        "behavior_family": "C-READ",
        "name": "getTaskCount -> repeated getTask reads",
        "ground_truth": GroundTruth.LEGITIMATE_DAPP,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: read-dominated DApp queries without network calls.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "C05": {
        "scenario": "scenario_c",
        "behavior_family": "C-CANCEL",
        "name": "createTask -> cancellation",
        "ground_truth": GroundTruth.LEGITIMATE_DAPP,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: terminal cancelled state without network events.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "C06": {
        "scenario": "scenario_c",
        "behavior_family": "C-EDGE",
        "name": "createTask -> Completed -> InProgress (contract-valid non-linear)",
        "ground_truth": GroundTruth.LEGITIMATE_DAPP,
        "detection_hypothesis": "Expected not to satisfy rule conjunction: unusual but contract-valid state transition without C2.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "C07": {
        "scenario": "scenario_c",
        "behavior_family": "C-FAIL",
        "name": "createTask(\"\", desc) -> empty-title revert",
        "ground_truth": GroundTruth.INVALID_EXECUTION,
        "detection_hypothesis": "Contract revert: 'Title cannot be empty'. RPC error response; 0 blockchain/network events.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
    "C08": {
        "scenario": "scenario_c",
        "behavior_family": "C-FAIL",
        "name": "getTask(999) -> missing-task-ID revert",
        "ground_truth": GroundTruth.INVALID_EXECUTION,
        "detection_hypothesis": "Contract revert: 'Task does not exist'. RPC error response; 0 blockchain/network events.",
        "provenance": Provenance.GENUINE_EXECUTION,
    },
}
