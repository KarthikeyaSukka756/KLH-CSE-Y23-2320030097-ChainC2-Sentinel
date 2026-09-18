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


@pytest.mark.unit
class TestBenignWeb3Scenario:
    """Tests for Scenario A (Benign Web3 Activity)."""

    def test_scenario_a_execution_and_negative_control(self):
        """Scenario A produces endpoint, RPC, and BenignDApp events, and ZERO network events."""
        scenario = BenignWeb3Scenario(run_id="run-benign-001")
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
        scenario = SyntheticC2Scenario(run_id="run-c2-self-managed")
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
        runner = ScenarioRunner(output_path=output_file)

        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            results = runner.run_all(target_server=target_srv)

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
