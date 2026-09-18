# ChainC2 Sentinel — Detection Data Models
"""Structured models representing factual detection results and rule evaluation evidence.

Safety and Research Integrity Declarations:
- Detection outcomes represent laboratory detection of predefined synthetic behavioral patterns.
- No subjective labels (e.g. "malicious", "threat actor") are used.
- No arbitrary threat scores or ungrounded ML outputs are produced.
- Blockchain interaction alone is NEVER classified as anomalous.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DetectionStatus(str, enum.Enum):
    """Categorical outcome of a detection rule evaluation."""

    TRIGGERED = "triggered"
    NOT_TRIGGERED = "not_triggered"


class DetectionConditionMatch(BaseModel):
    """Factual status of an individual observable condition within a detection rule."""

    model_config = ConfigDict(extra="forbid")

    condition_id: str = Field(..., description="Short identifier of the condition")
    description: str = Field(..., description="Human-readable description of the condition")
    satisfied: bool = Field(..., description="Whether this condition was observed")
    evidence_detail: Optional[str] = Field(
        default=None, description="Observable value or reason supporting satisfaction/failure"
    )


class DetectionResult(BaseModel):
    """Factual, explainable outcome of a detection rule evaluated against a CorrelatedSequence."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(..., description="Unique rule identifier (e.g. 'RULE-CHAINC2-001')")
    rule_name: str = Field(..., description="Descriptive rule name")
    rule_version: str = Field(..., description="Version of the detection rule")
    status: DetectionStatus = Field(..., description="Whether the rule triggered")
    triggered: bool = Field(..., description="Boolean flag indicating detection candidate")
    correlation_id: str = Field(..., description="ID of the evaluated CorrelatedSequence")
    run_id: Optional[str] = Field(default=None, description="Scenario run identifier if present")
    scenario_id: Optional[str] = Field(default=None, description="Scenario identifier if present")
    observed_stages: list[str] = Field(
        default_factory=list, description="Telemetry layers observed in the sequence"
    )
    conditions: list[DetectionConditionMatch] = Field(
        default_factory=list, description="Detailed breakdown of each condition evaluated"
    )
    matched_conditions: list[str] = Field(
        default_factory=list, description="List of condition_ids that were satisfied"
    )
    unmatched_conditions: list[str] = Field(
        default_factory=list, description="List of condition_ids that were NOT satisfied"
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Observable evidence dictionary (contract, destination, latency)"
    )
    explanation: str = Field(
        ..., description="Factual, transparent explanation of why the rule did or did not trigger"
    )
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when detection evaluation took place",
    )
