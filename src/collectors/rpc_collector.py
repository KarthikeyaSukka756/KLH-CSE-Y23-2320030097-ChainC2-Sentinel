# ChainC2 Sentinel — RPC Telemetry Collector
"""Converts raw JSON-RPC request/response records into SentinelEvents.

IMPORTANT architectural distinction:
    rpc_endpoint     = client-facing proxy address (telemetry infrastructure)
    upstream_endpoint = Hardhat node address (blockchain backend)

The RPC proxy is telemetry infrastructure, NOT C2.
This collector only normalizes captured metadata into the common schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from src.models.events import (
    RpcInfo,
    SentinelEvent,
    TelemetrySource,
)


class RpcTelemetryCollector:
    """Converts raw RPC metadata into normalized SentinelEvents.

    Can be used by:
    - The RPC proxy to produce events in real time
    - Offline normalization of saved RPC logs
    """

    def __init__(
        self,
        rpc_endpoint: str,
        upstream_endpoint: str,
        host: Optional[str] = None,
    ) -> None:
        """Initialize the RPC telemetry collector.

        Args:
            rpc_endpoint: Client-facing RPC proxy address
                          (e.g. "http://rpc-proxy:8546").
            upstream_endpoint: Upstream Hardhat node address
                               (e.g. "http://hardhat-node:8545").
            host: Host identifier for generated events.
        """
        self._rpc_endpoint = rpc_endpoint
        self._upstream_endpoint = upstream_endpoint
        self._host = host

    def collect(
        self,
        rpc_method: str,
        status: str,
        request_id: Optional[str] = None,
        request_params: Optional[dict[str, Any]] = None,
        response_result: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> SentinelEvent:
        """Create a SentinelEvent from RPC request/response metadata.

        Args:
            rpc_method: JSON-RPC method name (e.g. "eth_call").
            status: "success" or "error".
            request_id: JSON-RPC request ID.
            request_params: Safe summary of request parameters.
            response_result: Safe summary of response result.
            error_message: Error message if status is "error".
            duration_ms: Round-trip duration in milliseconds.
            timestamp: Event timestamp (defaults to now UTC).

        Returns:
            A SentinelEvent with source=RPC and populated RpcInfo.
        """
        rpc_info = RpcInfo(
            rpc_endpoint=self._rpc_endpoint,
            upstream_endpoint=self._upstream_endpoint,
            rpc_method=rpc_method,
            request_id=request_id,
            request_params=request_params,
            response_result=response_result,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
        )

        return SentinelEvent(
            timestamp=timestamp or datetime.now(timezone.utc),
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            host=self._host,
            rpc=rpc_info,
        )
