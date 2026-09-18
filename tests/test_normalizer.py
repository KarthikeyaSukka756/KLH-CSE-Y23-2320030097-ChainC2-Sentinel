# ChainC2 Sentinel — Normalizer and Persistence Tests
"""Unit tests for the EventNormalizer and EventStore.

Tests:
- Raw dict → SentinelEvent normalization for each source type
- Timestamp string normalization
- Malformed input rejection with structured errors
- EventStore JSONL write/read round-trip
- EventStore empty file handling
- EventStore count and clear operations
"""

import json
from datetime import datetime, timezone

import pytest

from src.models.events import (
    BlockchainInfo,
    NetworkInfo,
    ProcessInfo,
    RpcInfo,
    SentinelEvent,
    TelemetrySource,
)
from src.normalizer.normalizer import EventNormalizer, EventStore, NormalizationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_endpoint() -> dict:
    """Create a raw dict for an endpoint event."""
    return {
        "timestamp": "2026-09-18T10:00:00+00:00",
        "source": "endpoint",
        "event_type": "process_snapshot",
        "host": "lab-node",
        "process": {
            "process_name": "python",
            "pid": 1234,
            "parent_pid": 1,
        },
    }


def _make_raw_rpc() -> dict:
    """Create a raw dict for an RPC event."""
    return {
        "timestamp": "2026-09-18T10:00:01+00:00",
        "source": "rpc",
        "event_type": "rpc_call",
        "rpc": {
            "rpc_endpoint": "http://rpc-proxy:8546",
            "upstream_endpoint": "http://hardhat-node:8545",
            "rpc_method": "eth_blockNumber",
            "status": "success",
        },
    }


def _make_raw_blockchain() -> dict:
    """Create a raw dict for a blockchain event."""
    return {
        "timestamp": "2026-09-18T10:00:02+00:00",
        "source": "blockchain",
        "event_type": "contract_interaction",
        "blockchain": {
            "contract_name": "C2DataStore",
            "function_name": "storeCommand",
            "tx_hash": "0xabc",
            "chain_id": "31337",
        },
    }


def _make_raw_network() -> dict:
    """Create a raw dict for a network event."""
    return {
        "timestamp": "2026-09-18T10:00:03+00:00",
        "source": "network",
        "event_type": "http_request",
        "network": {
            "destination_host": "http-target",
            "destination_port": 8080,
            "protocol": "HTTP",
            "request_type": "GET",
            "status_code": 200,
        },
    }


# ---------------------------------------------------------------------------
# EventNormalizer tests
# ---------------------------------------------------------------------------

class TestEventNormalizer:
    """Tests for the EventNormalizer."""

    @pytest.mark.unit
    def test_normalize_endpoint(self):
        """Normalizes a valid endpoint event."""
        normalizer = EventNormalizer()
        result = normalizer.normalize(_make_raw_endpoint())

        assert result.success
        assert result.event is not None
        assert result.event.source == TelemetrySource.ENDPOINT
        assert result.event.process is not None
        assert result.event.process.pid == 1234

    @pytest.mark.unit
    def test_normalize_rpc(self):
        """Normalizes a valid RPC event."""
        normalizer = EventNormalizer()
        result = normalizer.normalize(_make_raw_rpc())

        assert result.success
        assert result.event is not None
        assert result.event.source == TelemetrySource.RPC
        assert result.event.rpc is not None
        assert result.event.rpc.rpc_endpoint == "http://rpc-proxy:8546"
        assert result.event.rpc.upstream_endpoint == "http://hardhat-node:8545"

    @pytest.mark.unit
    def test_normalize_blockchain(self):
        """Normalizes a valid blockchain event."""
        normalizer = EventNormalizer()
        result = normalizer.normalize(_make_raw_blockchain())

        assert result.success
        assert result.event is not None
        assert result.event.source == TelemetrySource.BLOCKCHAIN
        assert result.event.blockchain is not None
        assert result.event.blockchain.contract_name == "C2DataStore"

    @pytest.mark.unit
    def test_normalize_network(self):
        """Normalizes a valid network event."""
        normalizer = EventNormalizer()
        result = normalizer.normalize(_make_raw_network())

        assert result.success
        assert result.event is not None
        assert result.event.source == TelemetrySource.NETWORK
        assert result.event.network is not None
        assert result.event.network.destination_host == "http-target"

    @pytest.mark.unit
    def test_timestamp_string_normalized(self):
        """Timestamp strings are normalized to datetime objects."""
        normalizer = EventNormalizer()
        result = normalizer.normalize(_make_raw_endpoint())

        assert result.event is not None
        assert isinstance(result.event.timestamp, datetime)
        assert result.event.timestamp.tzinfo is not None

    @pytest.mark.unit
    def test_missing_timestamp_rejected(self):
        """Missing timestamp produces structured error."""
        normalizer = EventNormalizer()
        raw = _make_raw_endpoint()
        del raw["timestamp"]

        result = normalizer.normalize(raw)

        assert not result.success
        assert result.event is None
        assert any("timestamp" in e for e in result.errors)

    @pytest.mark.unit
    def test_missing_source_rejected(self):
        """Missing source produces structured error."""
        normalizer = EventNormalizer()
        raw = _make_raw_endpoint()
        del raw["source"]

        result = normalizer.normalize(raw)

        assert not result.success
        assert any("source" in e for e in result.errors)

    @pytest.mark.unit
    def test_missing_event_type_rejected(self):
        """Missing event_type produces structured error."""
        normalizer = EventNormalizer()
        raw = _make_raw_endpoint()
        del raw["event_type"]

        result = normalizer.normalize(raw)

        assert not result.success
        assert any("event_type" in e for e in result.errors)

    @pytest.mark.unit
    def test_invalid_source_rejected(self):
        """Invalid source value produces structured error."""
        normalizer = EventNormalizer()
        raw = _make_raw_endpoint()
        raw["source"] = "invalid_source"

        result = normalizer.normalize(raw)

        assert not result.success
        assert any("Invalid source" in e for e in result.errors)

    @pytest.mark.unit
    def test_missing_submodel_rejected(self):
        """Source without its required sub-model is rejected."""
        normalizer = EventNormalizer()
        raw = {
            "timestamp": "2026-09-18T10:00:00+00:00",
            "source": "endpoint",
            "event_type": "test",
            # Missing "process" sub-model
        }

        result = normalizer.normalize(raw)

        assert not result.success
        assert any("process" in e for e in result.errors)

    @pytest.mark.unit
    def test_extra_fields_rejected(self):
        """Extra fields in the raw dict are rejected by strict mode."""
        normalizer = EventNormalizer()
        raw = _make_raw_endpoint()
        raw["unknown_field"] = "bad"

        result = normalizer.normalize(raw)

        assert not result.success
        assert len(result.errors) > 0

    @pytest.mark.unit
    def test_normalization_result_structure(self):
        """NormalizationResult has correct attributes."""
        # Success case
        normalizer = EventNormalizer()
        result = normalizer.normalize(_make_raw_endpoint())
        assert result.success is True
        assert result.event is not None
        assert result.errors == []

        # Failure case
        result = normalizer.normalize({})
        assert result.success is False
        assert result.event is None
        assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# EventStore tests
# ---------------------------------------------------------------------------

class TestEventStore:
    """Tests for the JSONL EventStore."""

    @pytest.mark.unit
    def test_write_and_read_single_event(self, tmp_path):
        """Single event write-read round-trip."""
        store = EventStore(tmp_path / "events.jsonl")

        event = SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        )
        store.append(event)

        loaded = store.load_events()
        assert len(loaded) == 1
        assert loaded[0].event_id == event.event_id
        assert loaded[0].source == event.source

    @pytest.mark.unit
    def test_write_and_read_multiple_events(self, tmp_path):
        """Multiple events write-read round-trip."""
        store = EventStore(tmp_path / "events.jsonl")

        events = [
            SentinelEvent(
                timestamp=datetime.now(timezone.utc),
                source=TelemetrySource.ENDPOINT,
                event_type="test",
                process=ProcessInfo(process_name=f"proc_{i}", pid=i),
            )
            for i in range(5)
        ]
        store.append_many(events)

        loaded = store.load_events()
        assert len(loaded) == 5
        for i, loaded_event in enumerate(loaded):
            assert loaded_event.process is not None
            assert loaded_event.process.process_name == f"proc_{i}"

    @pytest.mark.unit
    def test_append_incremental(self, tmp_path):
        """Appending is incremental — doesn't overwrite."""
        store = EventStore(tmp_path / "events.jsonl")

        for i in range(3):
            event = SentinelEvent(
                timestamp=datetime.now(timezone.utc),
                source=TelemetrySource.ENDPOINT,
                event_type="test",
                process=ProcessInfo(process_name=f"proc_{i}", pid=i),
            )
            store.append(event)

        loaded = store.load_events()
        assert len(loaded) == 3

    @pytest.mark.unit
    def test_empty_file_returns_empty_list(self, tmp_path):
        """Loading from a non-existent file returns empty list."""
        store = EventStore(tmp_path / "nonexistent.jsonl")
        loaded = store.load_events()
        assert loaded == []

    @pytest.mark.unit
    def test_count(self, tmp_path):
        """Count returns the number of events."""
        store = EventStore(tmp_path / "events.jsonl")

        assert store.count() == 0

        for i in range(3):
            store.append(SentinelEvent(
                timestamp=datetime.now(timezone.utc),
                source=TelemetrySource.ENDPOINT,
                event_type="test",
                process=ProcessInfo(process_name="test", pid=i),
            ))

        assert store.count() == 3

    @pytest.mark.unit
    def test_clear(self, tmp_path):
        """Clear removes all events."""
        store = EventStore(tmp_path / "events.jsonl")

        store.append(SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        ))
        assert store.count() == 1

        store.clear()
        assert store.count() == 0
        assert store.load_events() == []

    @pytest.mark.unit
    def test_mixed_source_types(self, tmp_path):
        """Store handles events from all source types."""
        store = EventStore(tmp_path / "events.jsonl")

        events = [
            SentinelEvent(
                timestamp=datetime.now(timezone.utc),
                source=TelemetrySource.ENDPOINT,
                event_type="process_snapshot",
                process=ProcessInfo(process_name="python", pid=1),
            ),
            SentinelEvent(
                timestamp=datetime.now(timezone.utc),
                source=TelemetrySource.RPC,
                event_type="rpc_call",
                rpc=RpcInfo(
                    rpc_endpoint="http://proxy:8546",
                    upstream_endpoint="http://hardhat:8545",
                    rpc_method="eth_call",
                    status="success",
                ),
            ),
            SentinelEvent(
                timestamp=datetime.now(timezone.utc),
                source=TelemetrySource.BLOCKCHAIN,
                event_type="contract_interaction",
                blockchain=BlockchainInfo(
                    contract_name="C2DataStore",
                ),
            ),
            SentinelEvent(
                timestamp=datetime.now(timezone.utc),
                source=TelemetrySource.NETWORK,
                event_type="http_request",
                network=NetworkInfo(
                    destination_host="localhost",
                    destination_port=8080,
                    protocol="HTTP",
                ),
            ),
        ]
        store.append_many(events)

        loaded = store.load_events()
        assert len(loaded) == 4

        sources = {e.source for e in loaded}
        assert sources == {
            TelemetrySource.ENDPOINT,
            TelemetrySource.RPC,
            TelemetrySource.BLOCKCHAIN,
            TelemetrySource.NETWORK,
        }

    @pytest.mark.unit
    def test_jsonl_format(self, tmp_path):
        """Each line in the file is valid JSON."""
        store = EventStore(tmp_path / "events.jsonl")

        store.append(SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        ))

        with open(store.file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert "event_id" in parsed
        assert "timestamp" in parsed
        assert "source" in parsed

    @pytest.mark.unit
    def test_parent_directory_created(self, tmp_path):
        """Parent directories are created automatically."""
        nested_path = tmp_path / "deep" / "nested" / "events.jsonl"
        store = EventStore(nested_path)

        store.append(SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        ))

        assert nested_path.exists()
        assert store.count() == 1
