# ChainC2 Sentinel — SentinelEvent Schema
"""Normalized telemetry event model for ChainC2 Sentinel.

Defines the common SentinelEvent representation and source-specific
sub-models using Pydantic v2 with strict validation.

Telemetry Sources:
    ENDPOINT   — local process metadata
    RPC        — JSON-RPC request/response pairs
    BLOCKCHAIN — synthetic smart-contract interactions
    NETWORK    — controlled HTTP/network activity

This module is the telemetry foundation. It does NOT contain
correlation logic, detection rules, or scoring — those belong
to later phases.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.utils.identifiers import generate_event_id


# ---------------------------------------------------------------------------
# Telemetry source enumeration
# ---------------------------------------------------------------------------

class TelemetrySource(str, enum.Enum):
    """Identifies the origin of a telemetry event."""

    ENDPOINT = "endpoint"
    RPC = "rpc"
    BLOCKCHAIN = "blockchain"
    NETWORK = "network"


# ---------------------------------------------------------------------------
# Source-specific sub-models
# ---------------------------------------------------------------------------

class ProcessInfo(BaseModel):
    """Endpoint process metadata.

    Captures safe, locally-available process information.
    Does NOT claim OS-wide process visibility — only what the
    Python runtime can observe about itself or what is explicitly
    provided by a synthetic adapter.
    """

    model_config = ConfigDict(extra="forbid")

    process_name: str = Field(..., description="Name of the process")
    pid: int = Field(..., description="Process ID")
    parent_pid: Optional[int] = Field(
        default=None, description="Parent process ID (if available)"
    )
    executable: Optional[str] = Field(
        default=None, description="Path to the executable"
    )
    command_args: Optional[list[str]] = Field(
        default=None, description="Command-line arguments"
    )


class RpcInfo(BaseModel):
    """JSON-RPC request/response metadata.

    IMPORTANT: rpc_endpoint and upstream_endpoint are distinct.
    - rpc_endpoint: the client-facing proxy address
    - upstream_endpoint: the Hardhat node address

    The RPC proxy is telemetry infrastructure, NOT C2.
    """

    model_config = ConfigDict(extra="forbid")

    rpc_endpoint: str = Field(
        ..., description="Client-facing RPC proxy address"
    )
    upstream_endpoint: str = Field(
        ..., description="Upstream Hardhat node address"
    )
    rpc_method: str = Field(..., description="JSON-RPC method name")
    request_id: Optional[str] = Field(
        default=None, description="JSON-RPC request ID"
    )
    request_params: Optional[dict[str, Any]] = Field(
        default=None, description="Safe summary of request parameters"
    )
    response_result: Optional[dict[str, Any]] = Field(
        default=None, description="Safe summary of response result"
    )
    status: str = Field(
        ..., description="Request status: 'success' or 'error'"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if status is 'error'"
    )
    duration_ms: Optional[float] = Field(
        default=None, description="Round-trip duration in milliseconds"
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Ensure status is one of the expected values."""
        allowed = {"success", "error"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}, got '{v}'")
        return v


class BlockchainInfo(BaseModel):
    """Synthetic blockchain interaction metadata.

    Represents activity from the local Hardhat environment only.
    Supports both C2DataStore and BenignDAppContract interactions.
    No public blockchain interaction.
    """

    model_config = ConfigDict(extra="forbid")

    tx_hash: Optional[str] = Field(
        default=None, description="Transaction hash"
    )
    block_number: Optional[int] = Field(
        default=None, description="Block number"
    )
    contract_address: Optional[str] = Field(
        default=None, description="Smart contract address"
    )
    chain_id: Optional[str] = Field(
        default=None, description="Chain/network identifier"
    )
    network_name: Optional[str] = Field(
        default=None, description="Network name (e.g. 'hardhat', 'localhost')"
    )
    sender: Optional[str] = Field(
        default=None, description="Transaction sender address"
    )
    function_name: Optional[str] = Field(
        default=None, description="Called function name"
    )
    event_name: Optional[str] = Field(
        default=None, description="Emitted event name"
    )
    event_args: Optional[dict[str, Any]] = Field(
        default=None, description="Event arguments"
    )
    contract_name: Optional[str] = Field(
        default=None,
        description="Contract name (e.g. 'C2DataStore', 'BenignDAppContract')",
    )


class NetworkInfo(BaseModel):
    """Controlled network activity metadata.

    Represents local HTTP/network observations only.
    No packet capture or kernel-level instrumentation.
    No contact with real C2 infrastructure.
    """

    model_config = ConfigDict(extra="forbid")

    destination_host: str = Field(
        ..., description="Destination host/IP address"
    )
    destination_port: int = Field(..., description="Destination port number")
    protocol: str = Field(
        ..., description="Protocol (e.g. 'HTTP', 'TCP')"
    )
    source_process: Optional[str] = Field(
        default=None, description="Source process name (if available)"
    )
    request_type: Optional[str] = Field(
        default=None, description="Request type (e.g. 'GET', 'POST')"
    )
    status_code: Optional[int] = Field(
        default=None, description="HTTP status code"
    )
    response_size_bytes: Optional[int] = Field(
        default=None, description="Response body size in bytes"
    )


# ---------------------------------------------------------------------------
# Normalized event model
# ---------------------------------------------------------------------------

class SentinelEvent(BaseModel):
    """Normalized telemetry event for ChainC2 Sentinel.

    This is the common event representation across all telemetry sources.
    Each event has exactly one source type and populates the corresponding
    sub-model (process, rpc, blockchain, or network).

    The metadata dict provides an extensible key-value store for
    additional context without schema changes.

    This model is the telemetry foundation. It does NOT contain
    correlation, detection, or scoring fields — those belong to
    later phases.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(
        default_factory=generate_event_id,
        description="Unique event identifier (UUID4)",
    )
    timestamp: datetime = Field(
        ..., description="Event timestamp in UTC"
    )
    source: TelemetrySource = Field(
        ..., description="Telemetry source type"
    )
    event_type: str = Field(
        ..., description="Specific event type within the source"
    )
    host: Optional[str] = Field(
        default=None, description="Host identifier"
    )

    # Source-specific sub-models (populate the one matching `source`)
    process: Optional[ProcessInfo] = Field(
        default=None, description="Endpoint process metadata"
    )
    rpc: Optional[RpcInfo] = Field(
        default=None, description="RPC request/response metadata"
    )
    blockchain: Optional[BlockchainInfo] = Field(
        default=None, description="Blockchain interaction metadata"
    )
    network: Optional[NetworkInfo] = Field(
        default=None, description="Network activity metadata"
    )

    # Extensible metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible key-value metadata",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v: Any) -> datetime:
        """Normalize timestamps to UTC-aware datetime objects.

        Accepts:
            - datetime objects (timezone-aware or naive)
            - ISO-8601 formatted strings

        Naive datetimes are assumed to be UTC.
        """
        if isinstance(v, str):
            # Parse ISO-8601 string
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError(
                f"timestamp must be a datetime or ISO-8601 string, got {type(v)}"
            )

        # Ensure timezone-aware (assume UTC for naive datetimes)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
