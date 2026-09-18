# ChainC2 Sentinel — Network Telemetry Collector
"""Converts controlled local network activity into SentinelEvents.

Initial implementation limited to controlled local HTTP/network
observations. Does NOT implement:
- Packet capture
- Kernel-level instrumentation
- Deep packet inspection
- Contact with real C2 infrastructure
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.models.events import (
    NetworkInfo,
    SentinelEvent,
    TelemetrySource,
)


class NetworkTelemetryCollector:
    """Converts network activity observations into SentinelEvents.

    Accepts explicit metadata about controlled local HTTP/network
    activity and produces normalized events.
    """

    def __init__(self, host: Optional[str] = None) -> None:
        """Initialize the network telemetry collector.

        Args:
            host: Host identifier for generated events.
        """
        self._host = host

    def collect(
        self,
        destination_host: str,
        destination_port: int,
        protocol: str,
        source_process: Optional[str] = None,
        request_type: Optional[str] = None,
        status_code: Optional[int] = None,
        response_size_bytes: Optional[int] = None,
        event_type: str = "network_connection",
        timestamp: Optional[datetime] = None,
    ) -> SentinelEvent:
        """Create a SentinelEvent from network activity metadata.

        Args:
            destination_host: Destination host or IP address.
            destination_port: Destination port number.
            protocol: Protocol name (e.g. "HTTP", "TCP").
            source_process: Source process name (if available).
            request_type: Request type (e.g. "GET", "POST").
            status_code: HTTP status code (if applicable).
            response_size_bytes: Response body size in bytes.
            event_type: Specific event type string.
            timestamp: Event timestamp (defaults to now UTC).

        Returns:
            A SentinelEvent with source=NETWORK and populated NetworkInfo.
        """
        network_info = NetworkInfo(
            destination_host=destination_host,
            destination_port=destination_port,
            protocol=protocol,
            source_process=source_process,
            request_type=request_type,
            status_code=status_code,
            response_size_bytes=response_size_bytes,
        )

        return SentinelEvent(
            timestamp=timestamp or datetime.now(timezone.utc),
            source=TelemetrySource.NETWORK,
            event_type=event_type,
            host=self._host,
            network=network_info,
        )
