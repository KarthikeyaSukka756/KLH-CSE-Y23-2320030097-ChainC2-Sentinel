# ChainC2 Sentinel — Identifier Utilities
"""UUID-based identifier generation for telemetry events and laboratory runs.

Provides deterministic-format unique identifiers for:
- event_id: uniquely identifies each SentinelEvent
- run_id: uniquely identifies a scenario execution run
- correlation_id: links related events across sources (Milestone 5)
"""

import uuid


def generate_event_id() -> str:
    """Generate a unique event identifier (UUID4).

    Returns:
        A UUID4 string suitable for use as a SentinelEvent.event_id.
    """
    return str(uuid.uuid4())


def generate_run_id() -> str:
    """Generate a unique scenario execution run identifier (UUID4).

    Returns:
        A UUID4 string suitable for identifying a scenario execution run.
    """
    return str(uuid.uuid4())


def generate_correlation_id() -> str:
    """Generate a unique correlation identifier (UUID4).

    Correlation IDs are intended for linking related events across
    different telemetry sources in the future correlation engine.

    Returns:
        A UUID4 string suitable for use as a correlation identifier.
    """
    return str(uuid.uuid4())
