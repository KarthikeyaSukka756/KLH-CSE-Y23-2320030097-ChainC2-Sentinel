# ChainC2 Sentinel — SentinelEvent Schema Tests
"""Comprehensive unit tests for the normalized SentinelEvent model.

Tests:
- SentinelEvent creation with each source type
- Sub-model validation (ProcessInfo, RpcInfo, BlockchainInfo, NetworkInfo)
- Required field enforcement
- Strict mode (extra="forbid") rejects unknown fields
- Timestamp handling (ISO-8601 strings, naive/aware datetimes)
- JSON serialization/deserialization round-trip
- TelemetrySource enum coverage
- Malformed event rejection
"""

import json
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from src.models.events import (
    BlockchainInfo,
    NetworkInfo,
    ProcessInfo,
    RpcInfo,
    SentinelEvent,
    TelemetrySource,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# TelemetrySource enum
# ---------------------------------------------------------------------------

class TestTelemetrySource:
    """Tests for the TelemetrySource enum."""

    @pytest.mark.unit
    def test_all_values_exist(self):
        """All four source types are defined."""
        assert TelemetrySource.ENDPOINT == "endpoint"
        assert TelemetrySource.RPC == "rpc"
        assert TelemetrySource.BLOCKCHAIN == "blockchain"
        assert TelemetrySource.NETWORK == "network"

    @pytest.mark.unit
    def test_enum_from_string(self):
        """Enum can be constructed from string values."""
        assert TelemetrySource("endpoint") is TelemetrySource.ENDPOINT
        assert TelemetrySource("rpc") is TelemetrySource.RPC
        assert TelemetrySource("blockchain") is TelemetrySource.BLOCKCHAIN
        assert TelemetrySource("network") is TelemetrySource.NETWORK

    @pytest.mark.unit
    def test_invalid_source_raises(self):
        """Invalid source string raises ValueError."""
        with pytest.raises(ValueError):
            TelemetrySource("invalid_source")

    @pytest.mark.unit
    def test_enum_count(self):
        """Exactly four source types are defined."""
        assert len(TelemetrySource) == 4


# ---------------------------------------------------------------------------
# ProcessInfo
# ---------------------------------------------------------------------------

class TestProcessInfo:
    """Tests for the ProcessInfo sub-model."""

    @pytest.mark.unit
    def test_required_fields(self):
        """process_name and pid are required."""
        info = ProcessInfo(process_name="python", pid=1234)
        assert info.process_name == "python"
        assert info.pid == 1234
        assert info.parent_pid is None
        assert info.executable is None
        assert info.command_args is None

    @pytest.mark.unit
    def test_all_fields(self):
        """All fields populate correctly."""
        info = ProcessInfo(
            process_name="test_proc",
            pid=100,
            parent_pid=50,
            executable="/usr/bin/python3",
            command_args=["script.py", "--verbose"],
        )
        assert info.parent_pid == 50
        assert info.executable == "/usr/bin/python3"
        assert info.command_args == ["script.py", "--verbose"]

    @pytest.mark.unit
    def test_missing_process_name_raises(self):
        """Missing process_name raises ValidationError."""
        with pytest.raises(Exception):
            ProcessInfo(pid=1234)  # type: ignore

    @pytest.mark.unit
    def test_missing_pid_raises(self):
        """Missing pid raises ValidationError."""
        with pytest.raises(Exception):
            ProcessInfo(process_name="test")  # type: ignore

    @pytest.mark.unit
    def test_extra_fields_rejected(self):
        """Extra fields are rejected by strict mode."""
        with pytest.raises(Exception):
            ProcessInfo(process_name="test", pid=1, unknown_field="bad")  # type: ignore


# ---------------------------------------------------------------------------
# RpcInfo
# ---------------------------------------------------------------------------

class TestRpcInfo:
    """Tests for the RpcInfo sub-model."""

    @pytest.mark.unit
    def test_required_fields(self):
        """rpc_endpoint, upstream_endpoint, rpc_method, status are required."""
        info = RpcInfo(
            rpc_endpoint="http://proxy:8546",
            upstream_endpoint="http://hardhat:8545",
            rpc_method="eth_blockNumber",
            status="success",
        )
        assert info.rpc_endpoint == "http://proxy:8546"
        assert info.upstream_endpoint == "http://hardhat:8545"
        assert info.rpc_method == "eth_blockNumber"
        assert info.status == "success"

    @pytest.mark.unit
    def test_endpoints_distinguishable(self):
        """Client-facing and upstream endpoints remain distinct."""
        info = RpcInfo(
            rpc_endpoint="http://rpc-proxy:8546",
            upstream_endpoint="http://hardhat-node:8545",
            rpc_method="eth_call",
            status="success",
        )
        assert info.rpc_endpoint != info.upstream_endpoint
        assert "8546" in info.rpc_endpoint
        assert "8545" in info.upstream_endpoint

    @pytest.mark.unit
    def test_error_status_with_message(self):
        """Error status includes error message."""
        info = RpcInfo(
            rpc_endpoint="http://proxy:8546",
            upstream_endpoint="http://hardhat:8545",
            rpc_method="eth_call",
            status="error",
            error_message="execution reverted",
        )
        assert info.status == "error"
        assert info.error_message == "execution reverted"

    @pytest.mark.unit
    def test_invalid_status_raises(self):
        """Invalid status value raises ValidationError."""
        with pytest.raises(Exception):
            RpcInfo(
                rpc_endpoint="http://proxy:8546",
                upstream_endpoint="http://hardhat:8545",
                rpc_method="eth_call",
                status="pending",  # not "success" or "error"
            )

    @pytest.mark.unit
    def test_optional_fields(self):
        """Optional fields default to None."""
        info = RpcInfo(
            rpc_endpoint="http://proxy:8546",
            upstream_endpoint="http://hardhat:8545",
            rpc_method="eth_call",
            status="success",
        )
        assert info.request_id is None
        assert info.request_params is None
        assert info.response_result is None
        assert info.error_message is None
        assert info.duration_ms is None

    @pytest.mark.unit
    def test_duration_ms(self):
        """Duration in milliseconds is captured."""
        info = RpcInfo(
            rpc_endpoint="http://proxy:8546",
            upstream_endpoint="http://hardhat:8545",
            rpc_method="eth_call",
            status="success",
            duration_ms=12.5,
        )
        assert info.duration_ms == 12.5


# ---------------------------------------------------------------------------
# BlockchainInfo
# ---------------------------------------------------------------------------

class TestBlockchainInfo:
    """Tests for the BlockchainInfo sub-model."""

    @pytest.mark.unit
    def test_all_optional(self):
        """All fields are optional — empty instance is valid."""
        info = BlockchainInfo()
        assert info.tx_hash is None
        assert info.contract_name is None

    @pytest.mark.unit
    def test_c2datastore_activity(self):
        """C2DataStore interactions populate correctly."""
        info = BlockchainInfo(
            tx_hash="0xabc123",
            block_number=42,
            contract_address="0xContract1",
            chain_id="31337",
            network_name="hardhat",
            sender="0xSender1",
            function_name="storeCommand",
            event_name="CommandStored",
            event_args={"command": "SYNTHETIC_PING", "index": 0},
            contract_name="C2DataStore",
        )
        assert info.contract_name == "C2DataStore"
        assert info.function_name == "storeCommand"
        assert info.event_name == "CommandStored"

    @pytest.mark.unit
    def test_benign_dapp_activity(self):
        """BenignDAppContract interactions populate correctly."""
        info = BlockchainInfo(
            tx_hash="0xdef456",
            block_number=43,
            contract_address="0xContract2",
            chain_id="31337",
            network_name="hardhat",
            sender="0xSender1",
            function_name="increment",
            event_name="CountIncremented",
            event_args={"newCount": 1},
            contract_name="BenignDAppContract",
        )
        assert info.contract_name == "BenignDAppContract"
        assert info.function_name == "increment"

    @pytest.mark.unit
    def test_contract_names_distinguishable(self):
        """C2DataStore and BenignDAppContract are distinguishable."""
        c2 = BlockchainInfo(contract_name="C2DataStore")
        benign = BlockchainInfo(contract_name="BenignDAppContract")
        assert c2.contract_name != benign.contract_name

    @pytest.mark.unit
    def test_extra_fields_rejected(self):
        """Extra fields are rejected."""
        with pytest.raises(Exception):
            BlockchainInfo(unknown="bad")  # type: ignore


# ---------------------------------------------------------------------------
# NetworkInfo
# ---------------------------------------------------------------------------

class TestNetworkInfo:
    """Tests for the NetworkInfo sub-model."""

    @pytest.mark.unit
    def test_required_fields(self):
        """destination_host, destination_port, protocol are required."""
        info = NetworkInfo(
            destination_host="127.0.0.1",
            destination_port=8080,
            protocol="HTTP",
        )
        assert info.destination_host == "127.0.0.1"
        assert info.destination_port == 8080
        assert info.protocol == "HTTP"

    @pytest.mark.unit
    def test_optional_fields(self):
        """Optional fields default to None."""
        info = NetworkInfo(
            destination_host="localhost",
            destination_port=443,
            protocol="HTTP",
        )
        assert info.source_process is None
        assert info.request_type is None
        assert info.status_code is None
        assert info.response_size_bytes is None

    @pytest.mark.unit
    def test_http_request(self):
        """HTTP request with all fields populated."""
        info = NetworkInfo(
            destination_host="http-target",
            destination_port=8080,
            protocol="HTTP",
            source_process="python",
            request_type="GET",
            status_code=200,
            response_size_bytes=1024,
        )
        assert info.request_type == "GET"
        assert info.status_code == 200

    @pytest.mark.unit
    def test_missing_required_raises(self):
        """Missing required field raises ValidationError."""
        with pytest.raises(Exception):
            NetworkInfo(destination_port=8080, protocol="HTTP")  # type: ignore


# ---------------------------------------------------------------------------
# SentinelEvent
# ---------------------------------------------------------------------------

class TestSentinelEvent:
    """Tests for the SentinelEvent normalized model."""

    @pytest.mark.unit
    def test_endpoint_event(self):
        """Create a valid endpoint event."""
        event = SentinelEvent(
            timestamp=_utc_now(),
            source=TelemetrySource.ENDPOINT,
            event_type="process_snapshot",
            host="lab-workstation",
            process=ProcessInfo(process_name="python", pid=1234),
        )
        assert event.source == TelemetrySource.ENDPOINT
        assert event.event_type == "process_snapshot"
        assert event.process is not None
        assert event.process.pid == 1234

    @pytest.mark.unit
    def test_rpc_event(self):
        """Create a valid RPC event."""
        event = SentinelEvent(
            timestamp=_utc_now(),
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            rpc=RpcInfo(
                rpc_endpoint="http://proxy:8546",
                upstream_endpoint="http://hardhat:8545",
                rpc_method="eth_blockNumber",
                status="success",
            ),
        )
        assert event.source == TelemetrySource.RPC
        assert event.rpc is not None
        assert event.rpc.rpc_method == "eth_blockNumber"

    @pytest.mark.unit
    def test_blockchain_event(self):
        """Create a valid blockchain event."""
        event = SentinelEvent(
            timestamp=_utc_now(),
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_interaction",
            blockchain=BlockchainInfo(
                contract_name="C2DataStore",
                function_name="storeCommand",
                tx_hash="0xabc",
            ),
        )
        assert event.source == TelemetrySource.BLOCKCHAIN
        assert event.blockchain is not None
        assert event.blockchain.contract_name == "C2DataStore"

    @pytest.mark.unit
    def test_network_event(self):
        """Create a valid network event."""
        event = SentinelEvent(
            timestamp=_utc_now(),
            source=TelemetrySource.NETWORK,
            event_type="http_request",
            network=NetworkInfo(
                destination_host="http-target",
                destination_port=8080,
                protocol="HTTP",
                request_type="GET",
                status_code=200,
            ),
        )
        assert event.source == TelemetrySource.NETWORK
        assert event.network is not None
        assert event.network.status_code == 200

    @pytest.mark.unit
    def test_event_id_auto_generated(self):
        """event_id is auto-generated as a valid UUID4."""
        event = SentinelEvent(
            timestamp=_utc_now(),
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        )
        # Should be a valid UUID
        parsed = uuid.UUID(event.event_id)
        assert parsed.version == 4

    @pytest.mark.unit
    def test_event_ids_unique(self):
        """Each event gets a unique event_id."""
        events = [
            SentinelEvent(
                timestamp=_utc_now(),
                source=TelemetrySource.ENDPOINT,
                event_type="test",
                process=ProcessInfo(process_name="test", pid=1),
            )
            for _ in range(10)
        ]
        ids = [e.event_id for e in events]
        assert len(set(ids)) == 10

    @pytest.mark.unit
    def test_timestamp_iso_string(self):
        """Timestamp can be provided as an ISO-8601 string."""
        event = SentinelEvent(
            timestamp="2026-09-18T10:30:00+00:00",
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        )
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    @pytest.mark.unit
    def test_timestamp_naive_assumed_utc(self):
        """Naive datetime is assumed to be UTC."""
        naive_dt = datetime(2026, 9, 18, 10, 30, 0)
        event = SentinelEvent(
            timestamp=naive_dt,
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        )
        assert event.timestamp.tzinfo == timezone.utc

    @pytest.mark.unit
    def test_timestamp_aware_preserved(self):
        """Timezone-aware datetime is preserved."""
        ist = timezone(timedelta(hours=5, minutes=30))
        aware_dt = datetime(2026, 9, 18, 16, 0, 0, tzinfo=ist)
        event = SentinelEvent(
            timestamp=aware_dt,
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        )
        # The offset should be preserved
        assert event.timestamp.utcoffset() == timedelta(hours=5, minutes=30)

    @pytest.mark.unit
    def test_missing_timestamp_raises(self):
        """Missing timestamp raises ValidationError."""
        with pytest.raises(Exception):
            SentinelEvent(
                source=TelemetrySource.ENDPOINT,
                event_type="test",
                process=ProcessInfo(process_name="test", pid=1),
            )  # type: ignore

    @pytest.mark.unit
    def test_missing_source_raises(self):
        """Missing source raises ValidationError."""
        with pytest.raises(Exception):
            SentinelEvent(
                timestamp=_utc_now(),
                event_type="test",
            )  # type: ignore

    @pytest.mark.unit
    def test_missing_event_type_raises(self):
        """Missing event_type raises ValidationError."""
        with pytest.raises(Exception):
            SentinelEvent(
                timestamp=_utc_now(),
                source=TelemetrySource.ENDPOINT,
            )  # type: ignore

    @pytest.mark.unit
    def test_extra_fields_rejected(self):
        """Extra fields on SentinelEvent are rejected."""
        with pytest.raises(Exception):
            SentinelEvent(
                timestamp=_utc_now(),
                source=TelemetrySource.ENDPOINT,
                event_type="test",
                process=ProcessInfo(process_name="test", pid=1),
                unknown_field="bad",  # type: ignore
            )

    @pytest.mark.unit
    def test_metadata_default_empty(self):
        """metadata defaults to an empty dict."""
        event = SentinelEvent(
            timestamp=_utc_now(),
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
        )
        assert event.metadata == {}

    @pytest.mark.unit
    def test_metadata_accepts_arbitrary_data(self):
        """metadata accepts arbitrary key-value data."""
        event = SentinelEvent(
            timestamp=_utc_now(),
            source=TelemetrySource.ENDPOINT,
            event_type="test",
            process=ProcessInfo(process_name="test", pid=1),
            metadata={"scenario": "benign_web3", "run_id": "abc-123"},
        )
        assert event.metadata["scenario"] == "benign_web3"

    @pytest.mark.unit
    def test_json_round_trip(self):
        """Serialization and deserialization preserves all data."""
        original = SentinelEvent(
            timestamp=_utc_now(),
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_interaction",
            host="lab-node",
            blockchain=BlockchainInfo(
                tx_hash="0xabc123def456",
                block_number=42,
                contract_address="0xContractAddr",
                chain_id="31337",
                network_name="hardhat",
                sender="0xSenderAddr",
                function_name="storeCommand",
                event_name="CommandStored",
                event_args={"command": "SYNTHETIC_PING", "index": 0},
                contract_name="C2DataStore",
            ),
            metadata={"scenario": "c2_simulation"},
        )

        # Serialize
        json_data = original.model_dump(mode="json")
        json_str = json.dumps(json_data)

        # Deserialize
        parsed = json.loads(json_str)
        restored = SentinelEvent.model_validate(parsed)

        assert restored.event_id == original.event_id
        assert restored.source == original.source
        assert restored.event_type == original.event_type
        assert restored.host == original.host
        assert restored.blockchain is not None
        assert restored.blockchain.tx_hash == "0xabc123def456"
        assert restored.blockchain.contract_name == "C2DataStore"
        assert restored.blockchain.event_args == {"command": "SYNTHETIC_PING", "index": 0}
        assert restored.metadata == {"scenario": "c2_simulation"}

    @pytest.mark.unit
    def test_json_round_trip_all_sources(self):
        """JSON round-trip works for all four source types."""
        events = [
            SentinelEvent(
                timestamp=_utc_now(),
                source=TelemetrySource.ENDPOINT,
                event_type="process_snapshot",
                process=ProcessInfo(process_name="python", pid=1234, parent_pid=1),
            ),
            SentinelEvent(
                timestamp=_utc_now(),
                source=TelemetrySource.RPC,
                event_type="rpc_call",
                rpc=RpcInfo(
                    rpc_endpoint="http://proxy:8546",
                    upstream_endpoint="http://hardhat:8545",
                    rpc_method="eth_call",
                    status="success",
                    duration_ms=5.2,
                ),
            ),
            SentinelEvent(
                timestamp=_utc_now(),
                source=TelemetrySource.BLOCKCHAIN,
                event_type="contract_interaction",
                blockchain=BlockchainInfo(contract_name="BenignDAppContract"),
            ),
            SentinelEvent(
                timestamp=_utc_now(),
                source=TelemetrySource.NETWORK,
                event_type="http_request",
                network=NetworkInfo(
                    destination_host="localhost",
                    destination_port=8080,
                    protocol="HTTP",
                ),
            ),
        ]

        for original in events:
            json_data = original.model_dump(mode="json")
            restored = SentinelEvent.model_validate(json_data)
            assert restored.event_id == original.event_id
            assert restored.source == original.source
            assert restored.event_type == original.event_type
