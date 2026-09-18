# ChainC2 Sentinel — Endpoint Telemetry Collector
"""Safe local endpoint telemetry collection.

Provides two implementations behind a common abstraction:

1. LocalEndpointCollector — captures the current Python process's own
   metadata using standard-library calls (os, sys, platform).
   Does NOT claim OS-wide process visibility.

2. SyntheticEndpointCollector — accepts explicit process metadata for
   testing and cross-platform portability.

NOT implemented at this stage:
- OS-wide process enumeration
- ETW / eBPF instrumentation
- Process tree walking
"""

from __future__ import annotations

import abc
import os
import platform
import sys
from datetime import datetime, timezone
from typing import Optional

from src.models.events import (
    ProcessInfo,
    SentinelEvent,
    TelemetrySource,
)


class EndpointCollector(abc.ABC):
    """Abstract base for endpoint telemetry collectors."""

    @abc.abstractmethod
    def collect(self) -> SentinelEvent:
        """Collect a single endpoint telemetry event.

        Returns:
            A SentinelEvent with source=ENDPOINT and populated ProcessInfo.
        """


class LocalEndpointCollector(EndpointCollector):
    """Collects metadata about the current Python process.

    Uses only safe, portable standard-library calls:
    - os.getpid()
    - os.getppid() (may not be available on all platforms)
    - sys.executable
    - sys.argv
    - platform.node()

    This collector captures a snapshot of the *current* process,
    not an enumeration of all running processes.
    """

    def __init__(self, event_type: str = "process_snapshot") -> None:
        """Initialize the local endpoint collector.

        Args:
            event_type: The event_type string for generated events.
        """
        self._event_type = event_type

    def collect(self) -> SentinelEvent:
        """Collect a snapshot of the current process.

        Returns:
            A SentinelEvent describing the current Python process.
        """
        # parent_pid: os.getppid() is available on Unix and Windows ≥ 3.2
        parent_pid: Optional[int] = None
        try:
            parent_pid = os.getppid()
        except (AttributeError, OSError):
            pass  # Not available on this platform

        process_info = ProcessInfo(
            process_name=_get_process_name(),
            pid=os.getpid(),
            parent_pid=parent_pid,
            executable=sys.executable or None,
            command_args=sys.argv[:] if sys.argv else None,
        )

        return SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type=self._event_type,
            host=platform.node() or None,
            process=process_info,
        )


class SyntheticEndpointCollector(EndpointCollector):
    """Generates controlled synthetic endpoint events for testing.

    Accepts explicit process metadata parameters so tests are
    deterministic and platform-independent.
    """

    def __init__(
        self,
        process_name: str,
        pid: int,
        parent_pid: Optional[int] = None,
        executable: Optional[str] = None,
        command_args: Optional[list[str]] = None,
        host: Optional[str] = None,
        event_type: str = "process_snapshot",
    ) -> None:
        """Initialize the synthetic endpoint collector.

        Args:
            process_name: Name of the synthetic process.
            pid: Synthetic process ID.
            parent_pid: Synthetic parent process ID.
            executable: Synthetic executable path.
            command_args: Synthetic command arguments.
            host: Synthetic host name.
            event_type: Event type string.
        """
        self._process_name = process_name
        self._pid = pid
        self._parent_pid = parent_pid
        self._executable = executable
        self._command_args = command_args
        self._host = host
        self._event_type = event_type

    def collect(self) -> SentinelEvent:
        """Generate a synthetic endpoint event.

        Returns:
            A SentinelEvent with the configured synthetic process metadata.
        """
        process_info = ProcessInfo(
            process_name=self._process_name,
            pid=self._pid,
            parent_pid=self._parent_pid,
            executable=self._executable,
            command_args=self._command_args,
        )

        return SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type=self._event_type,
            host=self._host,
            process=process_info,
        )


def _get_process_name() -> str:
    """Derive a human-readable process name.

    Uses the basename of sys.argv[0] if available, falling back
    to the basename of sys.executable.

    Returns:
        A string representing the process name.
    """
    if sys.argv and sys.argv[0]:
        return os.path.basename(sys.argv[0])
    if sys.executable:
        return os.path.basename(sys.executable)
    return "python"
