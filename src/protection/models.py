# ChainC2 Sentinel — Defensive Response Data Models
"""Structured data models for Phase 2 — Protection (Milestone 8).

Defines formal models for defensive response planning, controlled mitigation
actions, audit records, and verification outcomes.

Safety and Research Integrity Declarations:
- Defensive responses are restricted entirely to controlled laboratory infrastructure.
- Responses can ONLY be initiated from factual, triggered DetectionResult objects.
- Zero modification to OS host firewalls, kernel tables, or arbitrary system processes.
- No interaction with public blockchains, external networks, or real-world infrastructure.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.detection.models import DetectionResult, DetectionStatus
from src.utils.identifiers import generate_event_id


class MitigationType(str, enum.Enum):
    """Categorical type of defensive mitigation action."""

    EVIDENCE_PRESERVATION = "evidence_preservation"  # Snapshotting and freezing evidence bundle
    RPC_FILTER = "rpc_filter"  # Application-layer RPC proxy filter / access restriction
    NETWORK_CONTAINMENT = "network_containment"  # Controlled local HTTP target beacon containment
    PROCESS_ISOLATION = "process_isolation"  # Controlled laboratory process containment signal


class MitigationStatus(str, enum.Enum):
    """Lifecycle status of an individual mitigation action."""

    REQUESTED = "requested"  # Action planned but not yet executed
    EXECUTED = "executed"    # Action executed by mitigation handler
    VERIFIED = "verified"    # Action independently verified as effective
    FAILED = "failed"        # Action execution or verification failed
    ROLLED_BACK = "rolled_back"  # Action reverted during clean-up or failure recovery


class DefensePlanStatus(str, enum.Enum):
    """Overall status of a defensive response plan."""

    PENDING = "pending"
    EXECUTED = "executed"
    VERIFIED = "verified"
    FAILED = "failed"
    SKIPPED = "skipped"  # When detection was not triggered (e.g. Scenario A negative control)
    ROLLED_BACK = "rolled_back"


class MitigationAction(BaseModel):
    """Atomic, auditable defensive mitigation action within a DefensePlan."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(
        default_factory=generate_event_id,
        description="Unique identifier for this mitigation action"
    )
    mitigation_type: MitigationType = Field(
        ..., description="Type of mitigation being applied"
    )
    target_layer: str = Field(
        ..., description="Target architectural layer ('evidence', 'rpc', 'network', 'process')"
    )
    target_resource: str = Field(
        ..., description="Resource being mitigated (e.g. contract address, local port, process name)"
    )
    status: MitigationStatus = Field(
        default=MitigationStatus.REQUESTED,
        description="Current lifecycle state of the mitigation action"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured action parameters (e.g. filter rules, port, process PID)"
    )
    verification_strategy: str = Field(
        ..., description="Description of the test used to verify mitigation efficacy"
    )
    is_reversible: bool = Field(
        default=True,
        description="Whether this action supports clean rollback to restore baseline"
    )
    execution_timestamp: Optional[datetime] = Field(
        default=None, description="Timestamp when action was executed"
    )
    verification_timestamp: Optional[datetime] = Field(
        default=None, description="Timestamp when action was verified"
    )
    verification_details: Optional[str] = Field(
        default=None, description="Observable verification outcome"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error diagnostics if execution or verification failed"
    )


class DefensePlan(BaseModel):
    """Factual, auditable defensive response plan derived from a DetectionResult."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(
        default_factory=generate_event_id,
        description="Unique identifier for the defense plan"
    )
    detection_correlation_id: str = Field(
        ..., description="Correlation ID of the trigger sequence"
    )
    run_id: Optional[str] = Field(
        default=None, description="Scenario run identifier"
    )
    scenario_id: Optional[str] = Field(
        default=None, description="Scenario identifier"
    )
    rule_id: str = Field(
        ..., description="Detection rule that triggered this response"
    )
    status: DefensePlanStatus = Field(
        default=DefensePlanStatus.PENDING,
        description="Current aggregate status of the response plan"
    )
    actions: list[MitigationAction] = Field(
        default_factory=list,
        description="Ordered sequence of defensive mitigation actions"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the defense plan was formulated"
    )
    evidence_summary: str = Field(
        ..., description="Factual summary of the detection evidence justifying the response"
    )
    safety_boundary_verified: bool = Field(
        default=True,
        description="Confirmed that actions strictly target controlled local laboratory resources"
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Auditing and research notes"
    )


class DefenseExecutionRecord(BaseModel):
    """Complete post-execution audit log documenting response execution and verification."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(
        default_factory=generate_event_id,
        description="Unique execution audit identifier"
    )
    plan: DefensePlan = Field(..., description="The planned defense response")
    overall_success: bool = Field(
        ..., description="Whether all planned actions executed and verified successfully"
    )
    actions_executed: int = Field(..., description="Count of successfully executed actions")
    actions_verified: int = Field(..., description="Count of successfully verified actions")
    actions_failed: int = Field(..., description="Count of failed actions")
    started_at: datetime = Field(..., description="Execution start timestamp")
    completed_at: datetime = Field(..., description="Execution completion timestamp")
    duration_ms: float = Field(..., description="Total execution duration in milliseconds")
    rollback_available: bool = Field(
        default=True, description="Whether all executed actions can be rolled back"
    )
    audit_telemetry: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological audit trail of each mitigation transition"
    )
