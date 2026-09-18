# ChainC2 Sentinel — Cross-Layer Correlation Engine
"""Correlation engine for reconstructing multi-layer evidence chains.

Answers structural and relational questions:
1. Which telemetry events belong to the same execution context?
2. What is the chronological ordering of the events?
3. What process initiated the RPC interaction?
4. Which blockchain contract/function was accessed?
5. Was synthetic configuration retrieved?
6. Did network activity occur after that blockchain interaction?
7. What evidence links the events together?

BOUNDARY NOTICE:
This engine performs CORRELATION ONLY.
It does NOT assign threat scores, malicious verdicts, or alert classifications.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.correlation.models import (
    CorrelatedSequence,
    CorrelationRelationship,
    EventTransition,
)
from src.models.events import SentinelEvent, TelemetrySource
from src.normalizer.normalizer import EventStore

logger = logging.getLogger("chainc2_sentinel.correlation")


class CrossLayerCorrelationEngine:
    """Engine that correlates events from multiple telemetry layers into evidence chains."""

    def __init__(self, time_window_seconds: float = 60.0) -> None:
        """Initialize correlation engine.

        Args:
            time_window_seconds: Temporal window for fallback grouping when run_id is absent.
        """
        self.time_window_seconds = time_window_seconds

    def correlate(self, events: list[SentinelEvent]) -> list[CorrelatedSequence]:
        """Correlate a list of SentinelEvents into chronological behavioral sequences.

        Args:
            events: Telemetry events from any combination of sources and runs.

        Returns:
            List of CorrelatedSequence objects, one per execution group.
        """
        if not events:
            return []

        # Pass 1: Partition events into execution groups
        groups = self._partition_events(events)

        # Pass 2: Reconstruct evidence chains for each group
        correlated_sequences: list[CorrelatedSequence] = []
        for group in groups:
            sequence = self._build_sequence(group)
            correlated_sequences.append(sequence)

        # Sort sequences deterministically by their start time
        correlated_sequences.sort(key=lambda s: s.start_time)
        return correlated_sequences

    def correlate_from_store(self, store: EventStore) -> list[CorrelatedSequence]:
        """Load events from a JSONL EventStore and correlate them.

        Args:
            store: EventStore instance pointing to events.jsonl.

        Returns:
            List of CorrelatedSequence objects.
        """
        events = store.load_events()
        return self.correlate(events)

    def _partition_events(self, events: list[SentinelEvent]) -> list[list[SentinelEvent]]:
        """Group events by run_id or by temporal/host fallback."""
        by_run_id: dict[str, list[SentinelEvent]] = {}
        unassigned: list[SentinelEvent] = []

        for event in events:
            run_id = event.metadata.get("run_id")
            if run_id:
                by_run_id.setdefault(str(run_id), []).append(event)
            else:
                unassigned.append(event)

        groups: list[list[SentinelEvent]] = list(by_run_id.values())

        # Fallback grouping for events lacking run_id
        if unassigned:
            fallback_groups = self._temporal_fallback_partition(unassigned)
            groups.extend(fallback_groups)

        return groups

    def _temporal_fallback_partition(
        self, events: list[SentinelEvent]
    ) -> list[list[SentinelEvent]]:
        """Partition unassigned events by host and sliding time window."""
        # Sort chronologically first
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        partitions: list[list[SentinelEvent]] = []

        for event in sorted_events:
            event_host = event.host or "unknown"
            assigned = False
            for part in partitions:
                last_event = part[-1]
                part_host = last_event.host or "unknown"
                time_delta = (event.timestamp - last_event.timestamp).total_seconds()

                if event_host == part_host and 0.0 <= time_delta <= self.time_window_seconds:
                    part.append(event)
                    assigned = True
                    break

            if not assigned:
                partitions.append([event])

        return partitions

    def _build_sequence(self, group: list[SentinelEvent]) -> CorrelatedSequence:
        """Reconstruct the evidence chain from a chronologically ordered group of events."""
        # Ensure strict chronological ordering
        sorted_events = sorted(group, key=lambda e: e.timestamp)
        start_time = sorted_events[0].timestamp
        end_time = sorted_events[-1].timestamp
        duration_ms = max(0.0, (end_time - start_time).total_seconds() * 1000.0)

        run_id = sorted_events[0].metadata.get("run_id")
        scenario_id = sorted_events[0].metadata.get("scenario_id")
        host = sorted_events[0].host

        # Map primary event stages
        endpoint_event = next((e for e in sorted_events if e.source == TelemetrySource.ENDPOINT), None)
        rpc_event = next((e for e in sorted_events if e.source == TelemetrySource.RPC), None)
        blockchain_event = next((e for e in sorted_events if e.source == TelemetrySource.BLOCKCHAIN), None)
        network_event = next((e for e in sorted_events if e.source == TelemetrySource.NETWORK), None)

        # Build chronological layer transitions
        transitions: list[EventTransition] = []
        for i in range(len(sorted_events) - 1):
            e_from = sorted_events[i]
            e_to = sorted_events[i + 1]
            delta_ms = max(0.0, (e_to.timestamp - e_from.timestamp).total_seconds() * 1000.0)
            rel = self._classify_transition(e_from.source, e_to.source)

            context: dict[str, Any] = {
                "from_event_type": e_from.event_type,
                "to_event_type": e_to.event_type,
            }
            if e_from.host and e_to.host and e_from.host == e_to.host:
                context["shared_host"] = e_from.host

            transitions.append(
                EventTransition(
                    from_event_id=e_from.event_id,
                    to_event_id=e_to.event_id,
                    from_source=e_from.source,
                    to_source=e_to.source,
                    relationship=rel,
                    time_delta_ms=round(delta_ms, 3),
                    shared_context=context,
                )
            )

        # Extract contract and function names if blockchain event is present
        contract_name: Optional[str] = None
        function_name: Optional[str] = None
        if blockchain_event and blockchain_event.blockchain:
            contract_name = blockchain_event.blockchain.contract_name
            function_name = blockchain_event.blockchain.function_name

        # Calculate blockchain to network latency if both exist
        blockchain_to_network_ms: Optional[float] = None
        has_network_followup = False
        if blockchain_event and network_event:
            net_delta = (network_event.timestamp - blockchain_event.timestamp).total_seconds() * 1000.0
            if net_delta >= 0:
                has_network_followup = True
                blockchain_to_network_ms = round(net_delta, 3)

        # Check for complete causal chain: Endpoint -> RPC -> Blockchain -> Network
        is_complete_chain = False
        if (
            endpoint_event is not None
            and rpc_event is not None
            and blockchain_event is not None
            and network_event is not None
        ):
            if (
                endpoint_event.timestamp <= rpc_event.timestamp
                and rpc_event.timestamp <= blockchain_event.timestamp
                and blockchain_event.timestamp <= network_event.timestamp
            ):
                is_complete_chain = True

        stages_present = list(dict.fromkeys(e.source.value for e in sorted_events))

        return CorrelatedSequence(
            run_id=str(run_id) if run_id else None,
            scenario_id=str(scenario_id) if scenario_id else None,
            host=host,
            start_time=start_time,
            end_time=end_time,
            duration_ms=round(duration_ms, 3),
            events=sorted_events,
            endpoint_event=endpoint_event,
            rpc_event=rpc_event,
            blockchain_event=blockchain_event,
            network_event=network_event,
            transitions=transitions,
            is_complete_chain=is_complete_chain,
            has_network_followup=has_network_followup,
            contract_name=contract_name,
            function_name=function_name,
            blockchain_to_network_latency_ms=blockchain_to_network_ms,
            stages_present=stages_present,
        )

    @staticmethod
    def _classify_transition(
        from_source: TelemetrySource, to_source: TelemetrySource
    ) -> CorrelationRelationship:
        """Map layer transitions to explicit relationship types."""
        if from_source == to_source:
            return CorrelationRelationship.INTRA_LAYER
        if from_source == TelemetrySource.ENDPOINT and to_source == TelemetrySource.RPC:
            return CorrelationRelationship.PROCESS_TO_RPC
        if from_source == TelemetrySource.RPC and to_source == TelemetrySource.BLOCKCHAIN:
            return CorrelationRelationship.RPC_TO_BLOCKCHAIN
        if from_source == TelemetrySource.BLOCKCHAIN and to_source == TelemetrySource.NETWORK:
            return CorrelationRelationship.BLOCKCHAIN_TO_NETWORK

        return CorrelationRelationship.GENERIC_TRANSITION
