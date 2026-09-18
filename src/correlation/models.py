# ChainC2 Sentinel — Correlation Data Models
"""Data structures representing correlated multi-layer behavioral sequences.

Provides explicit representation for:
- Layer transitions between chronologically adjacent events
- Correlated evidence chains preserving the underlying SentinelEvents
- Factual structural observations without subjective threat verdicts
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.events import SentinelEvent, TelemetrySource
from src.utils.identifiers import generate_correlation_id


class CorrelationRelationship(str, enum.Enum):
    """Categorizes the causal/structural relationship between two adjacent events."""

    PROCESS_TO_RPC = "process_to_rpc"
    RPC_TO_BLOCKCHAIN = "rpc_to_blockchain"
    BLOCKCHAIN_TO_NETWORK = "blockchain_to_network"
    INTRA_LAYER = "intra_layer"
    GENERIC_TRANSITION = "generic_transition"


class EventTransition(BaseModel):
    """Explicit link between two temporally adjacent telemetry events."""

    model_config = ConfigDict(extra="forbid")

    from_event_id: str = Field(..., description="ID of the earlier event")
    to_event_id: str = Field(..., description="ID of the subsequent event")
    from_source: TelemetrySource = Field(..., description="Source layer of earlier event")
    to_source: TelemetrySource = Field(..., description="Source layer of subsequent event")
    relationship: CorrelationRelationship = Field(
        ..., description="Structural relationship type between the layers"
    )
    time_delta_ms: float = Field(
        ..., description="Elapsed time in milliseconds between the two events"
    )
    shared_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Factual shared attributes (e.g. host, process name)",
    )


class CorrelatedSequence(BaseModel):
    """Correlated behavioral sequence / evidence chain across telemetry layers.

    Represents the unified timeline of events originating from the same
    execution context (e.g. scenario run or host/process window).

    This model is strictly factual: it does NOT contain threat scores,
    malicious/benign labels, or anomaly verdicts.
    """

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = Field(
        default_factory=generate_correlation_id,
        description="Unique correlation identifier (UUID4)",
    )
    run_id: Optional[str] = Field(
        default=None,
        description="Scenario execution run identifier (if present)",
    )
    scenario_id: Optional[str] = Field(
        default=None,
        description="Scenario definition identifier (if present)",
    )
    host: Optional[str] = Field(
        default=None,
        description="Host identifier for the correlated activity",
    )
    start_time: datetime = Field(
        ..., description="Timestamp of the earliest event in the sequence"
    )
    end_time: datetime = Field(
        ..., description="Timestamp of the latest event in the sequence"
    )
    duration_ms: float = Field(
        ..., description="Total elapsed duration in milliseconds"
    )
    events: list[SentinelEvent] = Field(
        default_factory=list,
        description="All correlated SentinelEvents in strict chronological order",
    )

    # Primary stage mappings (None if that layer is absent/incomplete)
    endpoint_event: Optional[SentinelEvent] = Field(
        default=None, description="Correlated endpoint process event"
    )
    rpc_event: Optional[SentinelEvent] = Field(
        default=None, description="Correlated JSON-RPC proxy event"
    )
    blockchain_event: Optional[SentinelEvent] = Field(
        default=None, description="Correlated smart contract interaction event"
    )
    network_event: Optional[SentinelEvent] = Field(
        default=None, description="Correlated network activity event"
    )

    # Explicit transitions between adjacent events in chronological order
    transitions: list[EventTransition] = Field(
        default_factory=list,
        description="Layer transitions linking events chronologically",
    )

    # Structural factual observations (NO verdicts or scores)
    is_complete_chain: bool = Field(
        default=False,
        description="True if all 4 layers (Endpoint, RPC, Blockchain, Network) are present in causal order",
    )
    has_network_followup: bool = Field(
        default=False,
        description="True if a network event follows smart-contract interaction",
    )
    contract_name: Optional[str] = Field(
        default=None,
        description="Name of the smart contract accessed (if present)",
    )
    function_name: Optional[str] = Field(
        default=None,
        description="Name of the contract function invoked (if present)",
    )
    blockchain_to_network_latency_ms: Optional[float] = Field(
        default=None,
        description="Time delta between blockchain interaction and network connection (if both exist)",
    )
    stages_present: list[str] = Field(
        default_factory=list,
        description="List of TelemetrySource names present in this sequence",
    )
