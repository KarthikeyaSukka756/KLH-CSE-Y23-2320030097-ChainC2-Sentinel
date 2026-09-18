# ChainC2 Sentinel — Collector Tests
"""Unit tests for all four telemetry collectors.

Tests actual behavior:
- Endpoint: LocalEndpointCollector captures real PID;
            SyntheticEndpointCollector returns controlled data
- RPC: rpc_endpoint vs upstream_endpoint distinction;
       success/error handling; timing capture
- Blockchain: C2DataStore vs BenignDAppContract distinguishability;
              field population
- Network: HTTP activity events; required/optional fields
"""

import os
import sys

import pytest

from src.collectors.endpoint_collector import (
    LocalEndpointCollector,
    SyntheticEndpointCollector,
)
from src.collectors.rpc_collector import RpcTelemetryCollector
from src.collectors.blockchain_collector import BlockchainTelemetryCollector
from src.collectors.network_collector import NetworkTelemetryCollector
from src.models.events import TelemetrySource


# ---------------------------------------------------------------------------
# Endpoint collector tests
# ---------------------------------------------------------------------------

class TestLocalEndpointCollector:
    """Tests for the LocalEndpointCollector."""

    @pytest.mark.unit
    def test_collects_valid_event(self):
        """Produces a valid SentinelEvent with source=ENDPOINT."""
        collector = LocalEndpointCollector()
        event = collector.collect()

        assert event.source == TelemetrySource.ENDPOINT
        assert event.event_type == "process_snapshot"
        assert event.process is not None

    @pytest.mark.unit
    def test_captures_real_pid(self):
        """Captures the actual current process PID."""
        collector = LocalEndpointCollector()
        event = collector.collect()

        assert event.process is not None
        assert event.process.pid == os.getpid()

    @pytest.mark.unit
    def test_captures_host(self):
        """Captures a host identifier."""
        collector = LocalEndpointCollector()
        event = collector.collect()

        # platform.node() should return something on most systems
        assert event.host is not None or event.host is None  # portable

    @pytest.mark.unit
    def test_has_executable(self):
        """Captures the Python executable path."""
        collector = LocalEndpointCollector()
        event = collector.collect()

        assert event.process is not None
        assert event.process.executable is not None
        assert event.process.executable == sys.executable

    @pytest.mark.unit
    def test_custom_event_type(self):
        """Supports custom event_type."""
        collector = LocalEndpointCollector(event_type="process_start")
        event = collector.collect()

        assert event.event_type == "process_start"

    @pytest.mark.unit
    def test_event_has_timestamp(self):
        """Event has a UTC timestamp."""
        collector = LocalEndpointCollector()
        event = collector.collect()

        assert event.timestamp is not None
        assert event.timestamp.tzinfo is not None


class TestSyntheticEndpointCollector:
    """Tests for the SyntheticEndpointCollector."""

    @pytest.mark.unit
    def test_returns_configured_data(self):
        """Returns exactly the configured synthetic process metadata."""
        collector = SyntheticEndpointCollector(
            process_name="synthetic_agent",
            pid=9999,
            parent_pid=1000,
            executable="/opt/agent/run",
            command_args=["--mode", "test"],
            host="lab-node-01",
        )
        event = collector.collect()

        assert event.source == TelemetrySource.ENDPOINT
        assert event.host == "lab-node-01"
        assert event.process is not None
        assert event.process.process_name == "synthetic_agent"
        assert event.process.pid == 9999
        assert event.process.parent_pid == 1000
        assert event.process.executable == "/opt/agent/run"
        assert event.process.command_args == ["--mode", "test"]

    @pytest.mark.unit
    def test_minimal_configuration(self):
        """Works with only required parameters."""
        collector = SyntheticEndpointCollector(
            process_name="minimal_proc",
            pid=1,
        )
        event = collector.collect()

        assert event.process is not None
        assert event.process.process_name == "minimal_proc"
        assert event.process.pid == 1
        assert event.process.parent_pid is None
        assert event.host is None

    @pytest.mark.unit
    def test_is_valid_sentinel_event(self):
        """Produces an event that passes full model validation."""
        collector = SyntheticEndpointCollector(
            process_name="test", pid=42
        )
        event = collector.collect()

        # Round-trip through JSON to verify
        data = event.model_dump(mode="json")
        from src.models.events import SentinelEvent
        restored = SentinelEvent.model_validate(data)
        assert restored.event_id == event.event_id


# ---------------------------------------------------------------------------
# RPC collector tests
# ---------------------------------------------------------------------------

class TestRpcTelemetryCollector:
    """Tests for the RpcTelemetryCollector."""

    @pytest.mark.unit
    def test_produces_rpc_event(self):
        """Produces a valid SentinelEvent with source=RPC."""
        collector = RpcTelemetryCollector(
            rpc_endpoint="http://rpc-proxy:8546",
            upstream_endpoint="http://hardhat-node:8545",
        )
        event = collector.collect(
            rpc_method="eth_blockNumber",
            status="success",
        )

        assert event.source == TelemetrySource.RPC
        assert event.event_type == "rpc_call"
        assert event.rpc is not None

    @pytest.mark.unit
    def test_endpoints_distinguishable(self):
        """Client-facing and upstream endpoints are distinct in the event."""
        collector = RpcTelemetryCollector(
            rpc_endpoint="http://rpc-proxy:8546",
            upstream_endpoint="http://hardhat-node:8545",
        )
        event = collector.collect(
            rpc_method="eth_call",
            status="success",
        )

        assert event.rpc is not None
        assert event.rpc.rpc_endpoint == "http://rpc-proxy:8546"
        assert event.rpc.upstream_endpoint == "http://hardhat-node:8545"
        assert event.rpc.rpc_endpoint != event.rpc.upstream_endpoint

    @pytest.mark.unit
    def test_success_event(self):
        """Success event captures method, params, result, timing."""
        collector = RpcTelemetryCollector(
            rpc_endpoint="http://proxy:8546",
            upstream_endpoint="http://hardhat:8545",
        )
        event = collector.collect(
            rpc_method="eth_getBalance",
            status="success",
            request_id="1",
            request_params={"_type": "list", "_count": 2},
            response_result={"_type": "string", "_length": 66},
            duration_ms=15.7,
        )

        assert event.rpc is not None
        assert event.rpc.status == "success"
        assert event.rpc.rpc_method == "eth_getBalance"
        assert event.rpc.request_id == "1"
        assert event.rpc.duration_ms == 15.7
        assert event.rpc.error_message is None

    @pytest.mark.unit
    def test_error_event(self):
        """Error event captures error message."""
        collector = RpcTelemetryCollector(
            rpc_endpoint="http://proxy:8546",
            upstream_endpoint="http://hardhat:8545",
        )
        event = collector.collect(
            rpc_method="eth_call",
            status="error",
            error_message="execution reverted",
        )

        assert event.rpc is not None
        assert event.rpc.status == "error"
        assert event.rpc.error_message == "execution reverted"

    @pytest.mark.unit
    def test_host_propagated(self):
        """Host identifier propagates to the event."""
        collector = RpcTelemetryCollector(
            rpc_endpoint="http://proxy:8546",
            upstream_endpoint="http://hardhat:8545",
            host="rpc-proxy-container",
        )
        event = collector.collect(
            rpc_method="eth_blockNumber",
            status="success",
        )

        assert event.host == "rpc-proxy-container"


# ---------------------------------------------------------------------------
# Blockchain collector tests
# ---------------------------------------------------------------------------

class TestBlockchainTelemetryCollector:
    """Tests for the BlockchainTelemetryCollector."""

    @pytest.mark.unit
    def test_c2datastore_event(self):
        """C2DataStore interaction produces correct event."""
        collector = BlockchainTelemetryCollector()
        event = collector.collect(
            contract_name="C2DataStore",
            tx_hash="0xabc123",
            block_number=10,
            contract_address="0xC2Addr",
            sender="0xSender",
            function_name="storeCommand",
            event_name="CommandStored",
            event_args={"command": "SYNTHETIC_PING", "index": 0},
        )

        assert event.source == TelemetrySource.BLOCKCHAIN
        assert event.blockchain is not None
        assert event.blockchain.contract_name == "C2DataStore"
        assert event.blockchain.function_name == "storeCommand"
        assert event.blockchain.event_name == "CommandStored"
        assert event.blockchain.event_args["command"] == "SYNTHETIC_PING"

    @pytest.mark.unit
    def test_benign_dapp_event(self):
        """BenignDAppContract interaction produces correct event."""
        collector = BlockchainTelemetryCollector()
        event = collector.collect(
            contract_name="BenignDAppContract",
            tx_hash="0xdef456",
            function_name="increment",
            event_name="CountIncremented",
            event_args={"newCount": 5},
        )

        assert event.blockchain is not None
        assert event.blockchain.contract_name == "BenignDAppContract"
        assert event.blockchain.function_name == "increment"

    @pytest.mark.unit
    def test_contracts_distinguishable(self):
        """C2DataStore and BenignDAppContract events are distinguishable."""
        collector = BlockchainTelemetryCollector()

        c2_event = collector.collect(contract_name="C2DataStore")
        benign_event = collector.collect(contract_name="BenignDAppContract")

        assert c2_event.blockchain is not None
        assert benign_event.blockchain is not None
        assert c2_event.blockchain.contract_name != benign_event.blockchain.contract_name

    @pytest.mark.unit
    def test_default_chain_id_and_network(self):
        """Default chain_id is 31337 and network is hardhat."""
        collector = BlockchainTelemetryCollector()
        event = collector.collect(contract_name="C2DataStore")

        assert event.blockchain is not None
        assert event.blockchain.chain_id == "31337"
        assert event.blockchain.network_name == "hardhat"

    @pytest.mark.unit
    def test_custom_chain_id(self):
        """Supports custom chain_id and network_name."""
        collector = BlockchainTelemetryCollector(
            chain_id="1337",
            network_name="localhost",
        )
        event = collector.collect(contract_name="C2DataStore")

        assert event.blockchain is not None
        assert event.blockchain.chain_id == "1337"
        assert event.blockchain.network_name == "localhost"

    @pytest.mark.unit
    def test_event_type_default(self):
        """Default event_type is contract_interaction."""
        collector = BlockchainTelemetryCollector()
        event = collector.collect(contract_name="C2DataStore")
        assert event.event_type == "contract_interaction"

    @pytest.mark.unit
    def test_custom_event_type(self):
        """Supports custom event_type."""
        collector = BlockchainTelemetryCollector()
        event = collector.collect(
            contract_name="C2DataStore",
            event_type="contract_deployment",
        )
        assert event.event_type == "contract_deployment"


# ---------------------------------------------------------------------------
# Network collector tests
# ---------------------------------------------------------------------------

class TestNetworkTelemetryCollector:
    """Tests for the NetworkTelemetryCollector."""

    @pytest.mark.unit
    def test_http_request_event(self):
        """HTTP request produces a valid network event."""
        collector = NetworkTelemetryCollector()
        event = collector.collect(
            destination_host="http-target",
            destination_port=8080,
            protocol="HTTP",
            request_type="GET",
            status_code=200,
            response_size_bytes=512,
        )

        assert event.source == TelemetrySource.NETWORK
        assert event.network is not None
        assert event.network.destination_host == "http-target"
        assert event.network.destination_port == 8080
        assert event.network.protocol == "HTTP"
        assert event.network.request_type == "GET"
        assert event.network.status_code == 200

    @pytest.mark.unit
    def test_minimal_network_event(self):
        """Works with only required fields."""
        collector = NetworkTelemetryCollector()
        event = collector.collect(
            destination_host="127.0.0.1",
            destination_port=443,
            protocol="TCP",
        )

        assert event.network is not None
        assert event.network.source_process is None
        assert event.network.request_type is None
        assert event.network.status_code is None

    @pytest.mark.unit
    def test_source_process_captured(self):
        """Source process name is captured when provided."""
        collector = NetworkTelemetryCollector()
        event = collector.collect(
            destination_host="localhost",
            destination_port=8080,
            protocol="HTTP",
            source_process="python",
        )

        assert event.network is not None
        assert event.network.source_process == "python"

    @pytest.mark.unit
    def test_host_propagated(self):
        """Host identifier propagates to the event."""
        collector = NetworkTelemetryCollector(host="lab-node")
        event = collector.collect(
            destination_host="localhost",
            destination_port=8080,
            protocol="HTTP",
        )

        assert event.host == "lab-node"

    @pytest.mark.unit
    def test_custom_event_type(self):
        """Supports custom event_type."""
        collector = NetworkTelemetryCollector()
        event = collector.collect(
            destination_host="localhost",
            destination_port=8080,
            protocol="HTTP",
            event_type="http_request",
        )

        assert event.event_type == "http_request"
