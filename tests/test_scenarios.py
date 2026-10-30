# ChainC2 Sentinel — Tests for Detection Scenarios
"""Unit tests for Phase 1 Milestone 4 controlled detection scenarios."""

import os
from pathlib import Path

import pytest

from src.http_target.server import LocalHttpTargetServer
from src.models.events import SentinelEvent, TelemetrySource
from src.normalizer.normalizer import EventStore
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.definitions.legitimate_dapp_scenario import LegitimateDAppScenario
from src.scenarios.payload import SyntheticC2Payload
from src.scenarios.runner import ScenarioRunner


@pytest.mark.unit
class TestSyntheticC2Payload:
    """Tests for payload safety validation and serialization."""

    def test_valid_payload(self):
        """Valid BEACON payload with local target passes validation."""
        payload = SyntheticC2Payload(
            target="http://127.0.0.1:8080/beacon",
            parameters={"test": "val"},
        )
        assert payload.command == "BEACON"
        assert payload.scenario == "synthetic_c2"
        assert "127.0.0.1" in payload.target

        # Check serialization round-trip
        serialized = payload.to_blockchain_string()
        parsed = SyntheticC2Payload.from_raw(serialized)
        assert parsed.command == "BEACON"
        assert parsed.target == payload.target
        assert parsed.request_id == payload.request_id

    def test_parse_with_prefix(self):
        """Payload parser handles optional SYNTHETIC_C2: prefix."""
        raw = 'SYNTHETIC_C2:{"command": "BEACON", "target": "http://127.0.0.1:9090/beacon"}'
        parsed = SyntheticC2Payload.from_raw(raw)
        assert parsed.command == "BEACON"
        assert parsed.target == "http://127.0.0.1:9090/beacon"

    def test_rejects_arbitrary_commands(self):
        """Any command other than BEACON must be strictly rejected."""
        unsafe_commands = ["EXEC", "DOWNLOAD", "SHELL", "POLL", "RUN", "DELETE", "PING"]
        for cmd in unsafe_commands:
            with pytest.raises(ValueError, match="is not permitted.*Only predefined safe actions"):
                SyntheticC2Payload(
                    command=cmd,
                    target="http://127.0.0.1:8080/beacon",
                )

    def test_rejects_external_or_public_targets(self):
        """Targets outside localhost / 127.0.0.1 must be strictly rejected."""
        unsafe_targets = [
            "http://example.com/c2",
            "http://192.168.1.100:8080/beacon",
            "http://10.0.0.1:8080/beacon",
            "http://evil-server.org/api",
            "https://google.com",
            "ftp://127.0.0.1:8080/beacon",
        ]
        for target in unsafe_targets:
            with pytest.raises(ValueError, match="Security rejection"):
                SyntheticC2Payload(
                    command="BEACON",
                    target=target,
                )


from unittest.mock import MagicMock
from src.blockchain.rpc_client import RpcCallResult, RpcTxResult, encode_string


def _create_test_rpc_client(get_beacon_url=None):
    mock = MagicMock()
    mock.network = "localhost"
    mock.expected_chain_id = "31337"
    mock.default_sender = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    mock.get_chain_id.return_value = "31337"
    mock.eth_get_code.return_value = "0x60806040"

    def _eth_call(to, data):
        if "4f5063c4" in str(data):
            target = get_beacon_url() if callable(get_beacon_url) else (get_beacon_url or "http://127.0.0.1:8080/beacon")
            payload = SyntheticC2Payload(
                command="BEACON",
                target=target,
            ).to_blockchain_string()
            return RpcCallResult(
                success=True,
                status="success",
                result="0x" + encode_string(payload),
                error_message=None,
                duration_ms=1.0,
                request_params={"to": to, "data": data},
            )
        return RpcCallResult(
            success=True,
            status="success",
            result="0x0000000000000000000000000000000000000000000000000000000000000001",
            error_message=None,
            duration_ms=1.0,
            request_params={"to": to, "data": data},
        )

    mock.eth_call.side_effect = _eth_call
    mock.eth_send_transaction.return_value = RpcTxResult(
        success=True,
        status="success",
        tx_hash="0x4a7e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a",
        block_number=101,
        gas_used=21000,
        sender=mock.default_sender,
        to="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        response_result={"receipt": {"status": "0x1"}},
    )
    return mock


@pytest.mark.unit
class TestBenignWeb3Scenario:
    """Tests for Scenario A (Benign Web3 Activity)."""

    def test_scenario_a_execution_and_negative_control(self):
        """Scenario A produces endpoint, RPC, and BenignDApp events, and ZERO network events."""
        scenario = BenignWeb3Scenario(run_id="run-benign-001", rpc_client=_create_test_rpc_client())
        result = scenario.run()

        assert result.success is True
        assert result.scenario_id == "scenario_a_benign"
        assert result.run_id == "run-benign-001"
        assert len(result.events) == 3

        # Event counts by source
        assert result.event_counts_by_source[TelemetrySource.ENDPOINT.value] == 1
        assert result.event_counts_by_source[TelemetrySource.RPC.value] == 1
        assert result.event_counts_by_source[TelemetrySource.BLOCKCHAIN.value] == 1

        # CRITICAL NEGATIVE CONTROL: Zero network activity
        assert result.event_counts_by_source[TelemetrySource.NETWORK.value] == 0

        # Verify event specifics
        for ev in result.events:
            assert isinstance(ev, SentinelEvent)
            assert ev.metadata["scenario_id"] == "scenario_a_benign"
            assert ev.metadata["run_id"] == "run-benign-001"

        blockchain_ev = next(e for e in result.events if e.source == TelemetrySource.BLOCKCHAIN)
        assert blockchain_ev.blockchain is not None
        assert blockchain_ev.blockchain.contract_name == "BenignDAppContract"
        assert blockchain_ev.blockchain.function_name == "increment"


@pytest.mark.unit
class TestSyntheticC2Scenario:
    """Tests for Scenario B (Synthetic Blockchain-Mediated C2-Like Activity)."""

    def test_scenario_b_execution_with_local_target(self):
        """Scenario B produces 4-layer telemetry chain (Endpoint -> RPC -> Blockchain -> Network)."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            scenario = SyntheticC2Scenario(
                target_server=target_srv,
                run_id="run-c2-001",
                rpc_client=_create_test_rpc_client(lambda: target_srv.beacon_url),
            )
            result = scenario.run()

            assert result.success is True
            assert result.scenario_id == "scenario_b_synthetic_c2"
            assert result.run_id == "run-c2-001"
            assert len(result.events) == 4

            # Verify all 4 sources are present
            assert result.event_counts_by_source[TelemetrySource.ENDPOINT.value] == 1
            assert result.event_counts_by_source[TelemetrySource.RPC.value] == 1
            assert result.event_counts_by_source[TelemetrySource.BLOCKCHAIN.value] == 1
            assert result.event_counts_by_source[TelemetrySource.NETWORK.value] == 1

            # Verify blockchain event is C2DataStore
            bc_ev = next(e for e in result.events if e.source == TelemetrySource.BLOCKCHAIN)
            assert bc_ev.blockchain is not None
            assert bc_ev.blockchain.contract_name == "C2DataStore"
            assert bc_ev.blockchain.function_name == "getLatestCommand"

            # Verify network event strictly targets local HTTP target
            net_ev = next(e for e in result.events if e.source == TelemetrySource.NETWORK)
            assert net_ev.network is not None
            assert net_ev.network.destination_host == "127.0.0.1"
            assert net_ev.network.destination_port == target_srv.port
            assert net_ev.network.protocol == "HTTP"
            assert net_ev.network.status_code == 200

            # Verify the target server actually received the POST beacon request
            assert len(target_srv.received_requests) == 1
            rec = target_srv.received_requests[0]
            assert rec["path"] == "/beacon"
            assert rec["method"] == "POST"

    def test_scenario_b_internal_managed_server(self):
        """Scenario B can self-manage an ephemeral local HTTP target if none is supplied."""
        scenario = SyntheticC2Scenario(
            run_id="run-c2-self-managed",
            rpc_client=_create_test_rpc_client(lambda: scenario.target_server.beacon_url if scenario.target_server else "http://127.0.0.1:8080/beacon"),
        )
        result = scenario.run()

        assert result.success is True
        assert len(result.events) == 4
        assert result.event_counts_by_source[TelemetrySource.NETWORK.value] == 1


@pytest.mark.unit
class TestLegitimateDAppScenario:
    """Tests for Scenario C (Legitimate DApp Baseline)."""

    def test_scenario_c_execution_and_negative_control(self):
        """Scenario C executes multi-step task lifecycle with zero outbound network events."""
        scenario = LegitimateDAppScenario(run_id="run-legit-test-001")
        result = scenario.run()

        assert result.success is True
        assert result.scenario_id == "legitimate_dapp"
        assert result.run_id == "run-legit-test-001"
        assert len(result.events) == 7
        assert result.event_counts_by_source[TelemetrySource.ENDPOINT.value] == 1
        assert result.event_counts_by_source[TelemetrySource.RPC.value] == 4
        assert result.event_counts_by_source[TelemetrySource.BLOCKCHAIN.value] == 2
        assert result.event_counts_by_source.get(TelemetrySource.NETWORK.value, 0) == 0

        # Details check
        assert result.details["contract"] == "LegitimateDAppContract"
        assert result.details["final_status"] == "Completed"
        assert result.details["network_calls_made"] == 0

        # Verify event ordering and metadata
        for ev in result.events:
            assert ev.metadata["scenario_id"] == "legitimate_dapp"
            assert ev.metadata["run_id"] == "run-legit-test-001"


@pytest.mark.unit
class TestScenarioRunner:
    """Tests for the ScenarioRunner orchestrator and JSONL persistence."""

    def test_run_all_with_jsonl_persistence(self, tmp_path: Path):
        """ScenarioRunner runs all three scenarios and persists valid events to JSONL."""
        output_file = str(tmp_path / "events.jsonl")

        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            mock_rpc = _create_test_rpc_client(lambda: target_srv.beacon_url)
            runner = ScenarioRunner(output_path=output_file, rpc_client=mock_rpc)
            results = runner.run_all(target_server=target_srv, rpc_client=mock_rpc)

        assert len(results) == 3
        summary = runner.summarize(results)

        assert summary["total_scenarios"] == 3
        # 3 (Scenario A) + 4 (Scenario B) + 7 (Scenario C) = 14 total events
        assert summary["total_events"] == 14
        assert summary["events_by_source"][TelemetrySource.ENDPOINT.value] == 3
        assert summary["events_by_source"][TelemetrySource.RPC.value] == 6
        assert summary["events_by_source"][TelemetrySource.BLOCKCHAIN.value] == 4
        assert summary["events_by_source"][TelemetrySource.NETWORK.value] == 1

        # Verify file on disk
        assert os.path.exists(output_file)
        store = EventStore(output_file)
        saved_events = store.load_events()
        assert len(saved_events) == 14

        # Verify every event is a valid SentinelEvent with proper metadata
        for ev in saved_events:
            assert isinstance(ev, SentinelEvent)
            assert "scenario_id" in ev.metadata
            assert "run_id" in ev.metadata
            assert "step" in ev.metadata
