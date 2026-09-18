# ChainC2 Sentinel — Tests for Cross-Layer Correlation
"""Unit tests for Phase 1 Milestone 5 cross-layer correlation engine."""

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.correlation.engine import CrossLayerCorrelationEngine
from src.correlation.models import (
    CorrelatedSequence,
    CorrelationRelationship,
    EventTransition,
)
from src.http_target.server import LocalHttpTargetServer
from src.models.events import (
    BlockchainInfo,
    NetworkInfo,
    ProcessInfo,
    RpcInfo,
    SentinelEvent,
    TelemetrySource,
)
from src.normalizer.normalizer import EventStore
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario


@pytest.mark.unit
class TestCrossLayerCorrelationEngine:
    """Comprehensive test suite for CrossLayerCorrelationEngine."""

    def test_scenario_a_correlation(self):
        """Scenario A correlates into Endpoint -> RPC -> Blockchain with zero network followup."""
        scenario = BenignWeb3Scenario(run_id="run-corr-benign-001")
        res = scenario.run()
        assert res.success is True

        engine = CrossLayerCorrelationEngine()
        sequences = engine.correlate(res.events)

        assert len(sequences) == 1
        seq = sequences[0]

        # General attributes
        assert seq.run_id == "run-corr-benign-001"
        assert seq.scenario_id == "scenario_a_benign"
        assert len(seq.events) == 3
        assert seq.duration_ms >= 0.0

        # Stage mapping
        assert seq.endpoint_event is not None
        assert seq.rpc_event is not None
        assert seq.blockchain_event is not None
        assert seq.network_event is None

        # Factual characteristics (Negative Control)
        assert seq.is_complete_chain is False
        assert seq.has_network_followup is False
        assert seq.contract_name == "BenignDAppContract"
        assert seq.function_name == "increment"
        assert seq.blockchain_to_network_latency_ms is None
        assert seq.stages_present == ["endpoint", "rpc", "blockchain"]

        # Transitions
        assert len(seq.transitions) == 2
        assert seq.transitions[0].relationship == CorrelationRelationship.PROCESS_TO_RPC
        assert seq.transitions[1].relationship == CorrelationRelationship.RPC_TO_BLOCKCHAIN
        for trans in seq.transitions:
            assert trans.time_delta_ms >= 0.0

    def test_scenario_b_correlation(self):
        """Scenario B correlates into complete 4-layer evidence chain (Endpoint -> RPC -> Blockchain -> Network)."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            scenario = SyntheticC2Scenario(
                target_server=target_srv,
                run_id="run-corr-c2-001",
            )
            res = scenario.run()
            assert res.success is True

        engine = CrossLayerCorrelationEngine()
        sequences = engine.correlate(res.events)

        assert len(sequences) == 1
        seq = sequences[0]

        # General attributes
        assert seq.run_id == "run-corr-c2-001"
        assert seq.scenario_id == "scenario_b_synthetic_c2"
        assert len(seq.events) == 4

        # Stage mapping
        assert seq.endpoint_event is not None
        assert seq.rpc_event is not None
        assert seq.blockchain_event is not None
        assert seq.network_event is not None

        # Factual characteristics (Complete Chain)
        assert seq.is_complete_chain is True
        assert seq.has_network_followup is True
        assert seq.contract_name == "C2DataStore"
        assert seq.function_name == "getLatestCommand"
        assert seq.blockchain_to_network_latency_ms is not None
        assert seq.blockchain_to_network_latency_ms >= 0.0
        assert seq.stages_present == ["endpoint", "rpc", "blockchain", "network"]

        # Transitions
        assert len(seq.transitions) == 3
        assert seq.transitions[0].relationship == CorrelationRelationship.PROCESS_TO_RPC
        assert seq.transitions[1].relationship == CorrelationRelationship.RPC_TO_BLOCKCHAIN
        assert seq.transitions[2].relationship == CorrelationRelationship.BLOCKCHAIN_TO_NETWORK
        for trans in seq.transitions:
            assert trans.time_delta_ms >= 0.0

    def test_temporal_ordering_and_delta_calculation(self):
        """Events must be ordered chronologically and deltas computed accurately."""
        base_time = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)

        e1 = SentinelEvent(
            timestamp=base_time,
            source=TelemetrySource.ENDPOINT,
            event_type="process_start",
            process=ProcessInfo(process_name="proc_a", pid=100),
            metadata={"run_id": "test-order-001"},
        )
        e2 = SentinelEvent(
            timestamp=base_time + timedelta(milliseconds=150),
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            rpc=RpcInfo(
                rpc_endpoint="http://127.0.0.1:8546",
                upstream_endpoint="http://127.0.0.1:8545",
                rpc_method="eth_call",
                status="success",
            ),
            metadata={"run_id": "test-order-001"},
        )
        e3 = SentinelEvent(
            timestamp=base_time + timedelta(milliseconds=400),
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_read",
            blockchain=BlockchainInfo(contract_name="C2DataStore"),
            metadata={"run_id": "test-order-001"},
        )

        engine = CrossLayerCorrelationEngine()
        sequences = engine.correlate([e1, e2, e3])
        assert len(sequences) == 1
        seq = sequences[0]

        assert seq.duration_ms == 400.0
        assert len(seq.transitions) == 2
        assert seq.transitions[0].time_delta_ms == 150.0
        assert seq.transitions[1].time_delta_ms == 250.0

    def test_handles_out_of_order_ingestion(self):
        """Engine re-orders shuffled events into true chronological sequence."""
        base_time = datetime(2026, 9, 18, 14, 0, 0, tzinfo=timezone.utc)
        events = [
            SentinelEvent(
                timestamp=base_time + timedelta(seconds=i * 2),
                source=src,
                event_type=f"event_{i}",
                process=ProcessInfo(process_name="test", pid=1) if src == TelemetrySource.ENDPOINT else None,
                rpc=RpcInfo(
                    rpc_endpoint="http://127.0.0.1:8546",
                    upstream_endpoint="http://127.0.0.1:8545",
                    rpc_method="eth_call",
                    status="success",
                ) if src == TelemetrySource.RPC else None,
                metadata={"run_id": "shuffled-run-001"},
            )
            for i, src in enumerate([TelemetrySource.ENDPOINT, TelemetrySource.RPC])
        ]

        # Shuffle
        shuffled = list(events)
        shuffled.reverse()

        engine = CrossLayerCorrelationEngine()
        sequences = engine.correlate(shuffled)
        assert len(sequences) == 1
        seq = sequences[0]

        # Verify sorted order
        assert seq.events[0].timestamp < seq.events[1].timestamp
        assert seq.transitions[0].relationship == CorrelationRelationship.PROCESS_TO_RPC
        assert seq.transitions[0].time_delta_ms == 2000.0

    def test_incomplete_sequences_handled_gracefully(self):
        """Engine processes incomplete event chains without crashing."""
        base_time = datetime.now(timezone.utc)

        # Only RPC and Blockchain (no Endpoint, no Network)
        e_rpc = SentinelEvent(
            timestamp=base_time,
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            rpc=RpcInfo(
                rpc_endpoint="http://127.0.0.1:8546",
                upstream_endpoint="http://127.0.0.1:8545",
                rpc_method="eth_call",
                status="success",
            ),
            metadata={"run_id": "partial-run-001"},
        )
        e_bc = SentinelEvent(
            timestamp=base_time + timedelta(milliseconds=80),
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_read",
            blockchain=BlockchainInfo(contract_name="C2DataStore"),
            metadata={"run_id": "partial-run-001"},
        )

        engine = CrossLayerCorrelationEngine()
        sequences = engine.correlate([e_rpc, e_bc])

        assert len(sequences) == 1
        seq = sequences[0]
        assert seq.endpoint_event is None
        assert seq.rpc_event is not None
        assert seq.blockchain_event is not None
        assert seq.network_event is None
        assert seq.is_complete_chain is False
        assert len(seq.transitions) == 1
        assert seq.transitions[0].relationship == CorrelationRelationship.RPC_TO_BLOCKCHAIN

    def test_single_event_and_empty_list(self):
        """Engine handles edge cases: single event and empty input."""
        engine = CrossLayerCorrelationEngine()
        assert engine.correlate([]) == []

        single = SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type="process_snapshot",
            process=ProcessInfo(process_name="lone_proc", pid=999),
            metadata={"run_id": "single-001"},
        )
        sequences = engine.correlate([single])
        assert len(sequences) == 1
        seq = sequences[0]
        assert len(seq.events) == 1
        assert len(seq.transitions) == 0
        assert seq.duration_ms == 0.0

    def test_mixed_scenario_streams_separated(self):
        """Events from different runs are partitioned cleanly without leakage."""
        scen_a = BenignWeb3Scenario(run_id="mixed-run-a")
        res_a = scen_a.run()

        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            scen_b = SyntheticC2Scenario(target_server=target_srv, run_id="mixed-run-b")
            res_b = scen_b.run()

        # Interleave events
        mixed_events = []
        for e1, e2 in zip(res_a.events, res_b.events):
            mixed_events.extend([e1, e2])
        if len(res_b.events) > len(res_a.events):
            mixed_events.extend(res_b.events[len(res_a.events):])

        random.seed(42)
        random.shuffle(mixed_events)

        engine = CrossLayerCorrelationEngine()
        sequences = engine.correlate(mixed_events)

        assert len(sequences) == 2
        seq_a = next(s for s in sequences if s.run_id == "mixed-run-a")
        seq_b = next(s for s in sequences if s.run_id == "mixed-run-b")

        assert len(seq_a.events) == 3
        assert seq_a.is_complete_chain is False
        assert seq_a.has_network_followup is False

        assert len(seq_b.events) == 4
        assert seq_b.is_complete_chain is True
        assert seq_b.has_network_followup is True

    def test_correlate_from_event_store(self, tmp_path: Path):
        """Engine can ingest directly from JSONL EventStore."""
        jsonl_path = str(tmp_path / "events.jsonl")
        store = EventStore(jsonl_path)

        scenario = BenignWeb3Scenario(run_id="store-run-001", event_store=store)
        scenario.run()

        engine = CrossLayerCorrelationEngine()
        sequences = engine.correlate_from_store(store)

        assert len(sequences) == 1
        assert sequences[0].run_id == "store-run-001"
        assert len(sequences[0].events) == 3

    def test_sequence_model_serialization_round_trip(self):
        """CorrelatedSequence model serializes and deserializes without data loss."""
        now = datetime.now(timezone.utc)
        seq = CorrelatedSequence(
            run_id="run-ser-001",
            scenario_id="scenario_test",
            host="127.0.0.1",
            start_time=now,
            end_time=now + timedelta(seconds=1),
            duration_ms=1000.0,
            stages_present=["endpoint"],
        )
        data = seq.model_dump()
        restored = CorrelatedSequence(**data)

        assert restored.run_id == "run-ser-001"
        assert restored.scenario_id == "scenario_test"
        assert restored.duration_ms == 1000.0
