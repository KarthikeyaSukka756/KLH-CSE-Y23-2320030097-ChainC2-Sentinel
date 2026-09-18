# ChainC2 Sentinel — Event Normalizer and Persistence
"""Event normalization and JSONL-based telemetry persistence.

EventNormalizer:
    Converts raw dict representations into validated SentinelEvents.
    Handles timestamp normalization and field validation.
    Reports structured errors for malformed input.

EventStore:
    Append-only JSONL file writer/reader for telemetry events.
    Each line is a complete JSON-serialized SentinelEvent.
    Interface is deliberately simple so it can be replaced later
    with PostgreSQL or another backend.

This module is part of the telemetry foundation.
It does NOT implement correlation, detection, or scoring.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import ValidationError

from src.models.events import SentinelEvent, TelemetrySource

logger = logging.getLogger("chainc2_sentinel.normalizer")


# ---------------------------------------------------------------------------
# Normalization result
# ---------------------------------------------------------------------------

class NormalizationResult:
    """Result of an event normalization attempt.

    Attributes:
        event: The validated SentinelEvent, or None if normalization failed.
        errors: List of error descriptions if normalization failed.
        success: Whether normalization succeeded.
    """

    def __init__(
        self,
        event: Optional[SentinelEvent] = None,
        errors: Optional[list[str]] = None,
    ) -> None:
        self.event = event
        self.errors = errors or []
        self.success = event is not None


# ---------------------------------------------------------------------------
# Event normalizer
# ---------------------------------------------------------------------------

class EventNormalizer:
    """Converts raw dictionaries into validated SentinelEvents.

    Performs:
    - Pydantic v2 model validation
    - Timestamp string → UTC datetime normalization (via model validator)
    - Required-field enforcement per source type
    - Structured error reporting for malformed input
    """

    # Required sub-model fields per source type
    _SOURCE_REQUIRED_SUBMODEL: dict[str, str] = {
        "endpoint": "process",
        "rpc": "rpc",
        "blockchain": "blockchain",
        "network": "network",
    }

    def normalize(self, raw: dict[str, Any]) -> NormalizationResult:
        """Normalize a raw dict into a validated SentinelEvent.

        Args:
            raw: A dictionary containing event data. Must include at
                 minimum: timestamp, source, event_type.

        Returns:
            A NormalizationResult with the validated event or errors.
        """
        errors: list[str] = []

        # Basic required-field check before Pydantic validation
        for field in ("timestamp", "source", "event_type"):
            if field not in raw:
                errors.append(f"Missing required field: '{field}'")

        if errors:
            return NormalizationResult(errors=errors)

        # Validate source value
        source_value = raw.get("source", "")
        if isinstance(source_value, str):
            try:
                source_enum = TelemetrySource(source_value)
            except ValueError:
                valid = [s.value for s in TelemetrySource]
                errors.append(
                    f"Invalid source: '{source_value}'. Must be one of {valid}"
                )
                return NormalizationResult(errors=errors)
        elif isinstance(source_value, TelemetrySource):
            source_enum = source_value
        else:
            errors.append(f"Invalid source type: {type(source_value)}")
            return NormalizationResult(errors=errors)

        # Check that the corresponding sub-model is present
        required_submodel = self._SOURCE_REQUIRED_SUBMODEL.get(
            source_enum.value
        )
        if required_submodel and raw.get(required_submodel) is None:
            errors.append(
                f"Source '{source_enum.value}' requires the "
                f"'{required_submodel}' sub-model to be populated"
            )
            return NormalizationResult(errors=errors)

        # Attempt Pydantic validation
        try:
            event = SentinelEvent.model_validate(raw)
        except ValidationError as e:
            for err in e.errors():
                loc = " → ".join(str(l) for l in err["loc"])
                errors.append(f"{loc}: {err['msg']}")
            return NormalizationResult(errors=errors)

        logger.debug(
            "Normalized event: id=%s source=%s type=%s",
            event.event_id,
            event.source.value,
            event.event_type,
        )

        return NormalizationResult(event=event)


# ---------------------------------------------------------------------------
# JSONL event store
# ---------------------------------------------------------------------------

class EventStore:
    """Append-only JSONL file-based event store.

    Each line in the output file is a complete JSON-serialized
    SentinelEvent. This format is simple, append-friendly, and
    easy to consume in later phases.

    The interface is deliberately minimal so it can be replaced
    with a database backend (e.g. PostgreSQL) without changing
    the collector/normalizer code.
    """

    def __init__(self, file_path: Union[str, Path]) -> None:
        """Initialize the event store.

        Args:
            file_path: Path to the JSONL output file.
                       Parent directories will be created if needed.
        """
        self._file_path = Path(file_path)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def file_path(self) -> Path:
        """The path to the JSONL file."""
        return self._file_path

    def append(self, event: SentinelEvent) -> None:
        """Append a single event to the store.

        Args:
            event: The SentinelEvent to persist.
        """
        line = json.dumps(event.model_dump(mode="json"), default=str)
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        logger.debug("Persisted event %s to %s", event.event_id, self._file_path)

    def append_many(self, events: list[SentinelEvent]) -> None:
        """Append multiple events to the store.

        Args:
            events: List of SentinelEvents to persist.
        """
        with open(self._file_path, "a", encoding="utf-8") as f:
            for event in events:
                line = json.dumps(event.model_dump(mode="json"), default=str)
                f.write(line + "\n")

    def load_events(self) -> list[SentinelEvent]:
        """Load all events from the store.

        Returns:
            List of validated SentinelEvents. Malformed lines are
            logged and skipped.
        """
        events: list[SentinelEvent] = []

        if not self._file_path.exists():
            return events

        with open(self._file_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    event = SentinelEvent.model_validate(raw)
                    events.append(event)
                except (json.JSONDecodeError, ValidationError) as e:
                    logger.warning(
                        "Skipping malformed line %d in %s: %s",
                        line_number,
                        self._file_path,
                        e,
                    )

        return events

    def count(self) -> int:
        """Count the number of events in the store.

        Returns:
            The number of valid JSONL lines in the file.
        """
        if not self._file_path.exists():
            return 0

        count = 0
        with open(self._file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def clear(self) -> None:
        """Clear all events from the store.

        Truncates the file to zero length.
        """
        with open(self._file_path, "w", encoding="utf-8") as f:
            pass
