# ChainC2 Sentinel — Tests for Detection Layer
"""Unit tests for Phase 1 Milestone 6 explainable rule-based detection engine."""

from datetime import datetime, timedelta, timezone

import pytest

from src.correlation.engine import CrossLayerCorrelationEngine
from src.correlation.models import CorrelatedSequence
from src.detection.detector import DetectionEngine
from src.detection.models import DetectionResult, DetectionStatus
from src.detection.rules import SyntheticC2SequenceRule
from src.http_target.server import LocalHttpTargetServer
from src.models.events import (
    BlockchainInfo,
    NetworkInfo,
    ProcessInfo,
    RpcInfo,
    SentinelEvent,
    TelemetrySource,
)
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario


@pytest.mark.unit
class TestSyntheticC2SequenceRule:
    """Tests evaluating the 7 observable conditions of SyntheticC2SequenceRule."""

    def test_scenario_a_does_not_trigger_detection(self):
        """Scenario A (Benign Web3 Activity) must NEVER trigger detection (Negative Control)."""
        scen_a = BenignWeb3Scenario(run_id="run-det-benign-001")
        res_a = scen_a.run()
        assert res_a.success is True

        corr_engine = CrossLayerCorrelationEngine()
        sequences = corr_engine.correlate(res_a.events)
        assert len(sequences) == 1

        rule = SyntheticC2SequenceRule()
        result = rule.evaluate(sequences[0])

        assert result.triggered is False
        assert result.status == DetectionStatus.NOT_TRIGGERED
        assert result.rule_id == "RULE-CHAINC2-001"

        # Matched vs unmatched conditions
        assert "cond_endpoint" in result.matched_conditions
        assert "cond_rpc" in result.matched_conditions
        assert "cond_blockchain" in result.matched_conditions

        # Critical failure: contract is BenignDAppContract, and no network followup
        assert "cond_c2datastore" in result.unmatched_conditions
        assert "cond_network" in result.unmatched_conditions
        assert "cond_network_timing" in result.unmatched_conditions
        assert "cond_causal_timeline" in result.unmatched_conditions
        assert "BenignDAppContract" in result.explanation

    def test_scenario_b_triggers_detection(self):
        """Scenario B (Synthetic C2-like activity) satisfies all conditions and triggers detection."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            scen_b = SyntheticC2Scenario(
                target_server=target_srv,
                run_id="run-det-c2-001",
            )
            res_b = scen_b.run()
            assert res_b.success is True

        corr_engine = CrossLayerCorrelationEngine()
        sequences = corr_engine.correlate(res_b.events)
        assert len(sequences) == 1

        rule = SyntheticC2SequenceRule()
        result = rule.evaluate(sequences[0])

        assert result.triggered is True
        assert result.status == DetectionStatus.TRIGGERED
        assert len(result.unmatched_conditions) == 0
        assert len(result.matched_conditions) == 7

        # Observable evidence check
        assert result.evidence["contract_name"] == "C2DataStore"
        assert result.evidence["function_name"] == "getLatestCommand"
        assert "127.0.0.1" in result.evidence["network_destination"]
        assert result.evidence["blockchain_to_network_latency_ms"] >= 0.0
        assert "Detection candidate identified" in result.explanation

    def test_blockchain_interaction_without_network_does_not_trigger(self):
        """C2DataStore read without follow-up network activity must NOT trigger detection."""
        base_time = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            SentinelEvent(
                timestamp=base_time,
                source=TelemetrySource.ENDPOINT,
                event_type="process_start",
                process=ProcessInfo(process_name="test_proc", pid=101),
                metadata={"run_id": "no-net-run"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=50),
                source=TelemetrySource.RPC,
                event_type="rpc_call",
                rpc=RpcInfo(
                    rpc_endpoint="http://127.0.0.1:8546",
                    upstream_endpoint="http://127.0.0.1:8545",
                    rpc_method="eth_call",
                    status="success",
                ),
                metadata={"run_id": "no-net-run"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=100),
                source=TelemetrySource.BLOCKCHAIN,
                event_type="contract_read",
                blockchain=BlockchainInfo(
                    contract_name="C2DataStore",
                    function_name="getLatestCommand",
                ),
                metadata={"run_id": "no-net-run"},
            ),
        ]

        corr_engine = CrossLayerCorrelationEngine()
        seq = corr_engine.correlate(events)[0]

        rule = SyntheticC2SequenceRule()
        result = rule.evaluate(seq)

        assert result.triggered is False
        assert "cond_c2datastore" in result.matched_conditions
        assert "cond_network" in result.unmatched_conditions
        assert "no follow-up network activity observed" in result.explanation

    def test_network_without_blockchain_does_not_trigger(self):
        """Network connection without prior blockchain interaction must NOT trigger detection."""
        base_time = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            SentinelEvent(
                timestamp=base_time,
                source=TelemetrySource.ENDPOINT,
                event_type="process_start",
                process=ProcessInfo(process_name="normal_proc", pid=102),
                metadata={"run_id": "only-net-run"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=50),
                source=TelemetrySource.NETWORK,
                event_type="http_beacon",
                network=NetworkInfo(
                    destination_host="127.0.0.1",
                    destination_port=8080,
                    protocol="HTTP",
                ),
                metadata={"run_id": "only-net-run"},
            ),
        ]

        corr_engine = CrossLayerCorrelationEngine()
        seq = corr_engine.correlate(events)[0]

        rule = SyntheticC2SequenceRule()
        result = rule.evaluate(seq)

        assert result.triggered is False
        assert "cond_blockchain" in result.unmatched_conditions

    def test_benign_contract_followed_by_network_does_not_trigger(self):
        """BenignDAppContract interaction followed by network activity must NOT trigger detection."""
        base_time = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            SentinelEvent(
                timestamp=base_time,
                source=TelemetrySource.ENDPOINT,
                event_type="process_start",
                process=ProcessInfo(process_name="dapp_proc", pid=103),
                metadata={"run_id": "benign-plus-net"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=50),
                source=TelemetrySource.RPC,
                event_type="rpc_call",
                rpc=RpcInfo(
                    rpc_endpoint="http://127.0.0.1:8546",
                    upstream_endpoint="http://127.0.0.1:8545",
                    rpc_method="eth_sendTransaction",
                    status="success",
                ),
                metadata={"run_id": "benign-plus-net"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=100),
                source=TelemetrySource.BLOCKCHAIN,
                event_type="contract_interaction",
                blockchain=BlockchainInfo(
                    contract_name="BenignDAppContract",
                    function_name="increment",
                ),
                metadata={"run_id": "benign-plus-net"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=200),
                source=TelemetrySource.NETWORK,
                event_type="http_beacon",
                network=NetworkInfo(
                    destination_host="127.0.0.1",
                    destination_port=8080,
                    protocol="HTTP",
                ),
                metadata={"run_id": "benign-plus-net"},
            ),
        ]

        corr_engine = CrossLayerCorrelationEngine()
        seq = corr_engine.correlate(events)[0]

        rule = SyntheticC2SequenceRule()
        result = rule.evaluate(seq)

        # Fails because contract is NOT C2DataStore
        assert result.triggered is False
        assert "cond_c2datastore" in result.unmatched_conditions
        assert "is benign baseline" in result.explanation

    def test_network_occurring_before_blockchain_fails_timing(self):
        """Network event occurring BEFORE blockchain read must fail timing condition and not trigger."""
        base_time = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            SentinelEvent(
                timestamp=base_time,
                source=TelemetrySource.ENDPOINT,
                event_type="process_start",
                process=ProcessInfo(process_name="c2_proc", pid=104),
                metadata={"run_id": "timing-violation"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=100),
                source=TelemetrySource.NETWORK,
                event_type="http_beacon",
                network=NetworkInfo(
                    destination_host="127.0.0.1",
                    destination_port=8080,
                    protocol="HTTP",
                ),
                metadata={"run_id": "timing-violation"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=200),
                source=TelemetrySource.RPC,
                event_type="rpc_call",
                rpc=RpcInfo(
                    rpc_endpoint="http://127.0.0.1:8546",
                    upstream_endpoint="http://127.0.0.1:8545",
                    rpc_method="eth_call",
                    status="success",
                ),
                metadata={"run_id": "timing-violation"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=300),
                source=TelemetrySource.BLOCKCHAIN,
                event_type="contract_read",
                blockchain=BlockchainInfo(
                    contract_name="C2DataStore",
                    function_name="getLatestCommand",
                ),
                metadata={"run_id": "timing-violation"},
            ),
        ]

        corr_engine = CrossLayerCorrelationEngine()
        seq = corr_engine.correlate(events)[0]

        rule = SyntheticC2SequenceRule()
        result = rule.evaluate(seq)

        assert result.triggered is False
        assert "cond_network_timing" in result.unmatched_conditions
        assert "cond_causal_timeline" in result.unmatched_conditions

    def test_incomplete_sequence_missing_endpoint(self):
        """Sequence missing endpoint process fails cond_endpoint."""
        base_time = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            SentinelEvent(
                timestamp=base_time,
                source=TelemetrySource.RPC,
                event_type="rpc_call",
                rpc=RpcInfo(
                    rpc_endpoint="http://127.0.0.1:8546",
                    upstream_endpoint="http://127.0.0.1:8545",
                    rpc_method="eth_call",
                    status="success",
                ),
                metadata={"run_id": "missing-ep"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=50),
                source=TelemetrySource.BLOCKCHAIN,
                event_type="contract_read",
                blockchain=BlockchainInfo(
                    contract_name="C2DataStore",
                    function_name="getLatestCommand",
                ),
                metadata={"run_id": "missing-ep"},
            ),
            SentinelEvent(
                timestamp=base_time + timedelta(milliseconds=100),
                source=TelemetrySource.NETWORK,
                event_type="http_beacon",
                network=NetworkInfo(
                    destination_host="127.0.0.1",
                    destination_port=8080,
                    protocol="HTTP",
                ),
                metadata={"run_id": "missing-ep"},
            ),
        ]

        corr_engine = CrossLayerCorrelationEngine()
        seq = corr_engine.correlate(events)[0]

        rule = SyntheticC2SequenceRule()
        result = rule.evaluate(seq)

        assert result.triggered is False
        assert "cond_endpoint" in result.unmatched_conditions


@pytest.mark.unit
class TestDetectionEngine:
    """Tests for the DetectionEngine manager and multi-scenario evaluation."""

    def test_evaluate_mixed_stream_end_to_end(self):
        """End-to-end evaluation on mixed stream accurately distinguishes Scenario A and B."""
        scen_a = BenignWeb3Scenario(run_id="mixed-det-a")
        res_a = scen_a.run()

        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            scen_b = SyntheticC2Scenario(target_server=target_srv, run_id="mixed-det-b")
            res_b = scen_b.run()

        # Combine all events into one mixed list
        all_events = res_a.events + res_b.events

        detector = DetectionEngine()
        results = detector.evaluate_events(all_events)

        assert len(results) == 2
        res_by_run = {r.run_id: r for r in results}

        # Scenario A: NOT triggered
        assert res_by_run["mixed-det-a"].triggered is False
        assert res_by_run["mixed-det-a"].status == DetectionStatus.NOT_TRIGGERED

        # Scenario B: TRIGGERED
        assert res_by_run["mixed-det-b"].triggered is True
        assert res_by_run["mixed-det-b"].status == DetectionStatus.TRIGGERED

        # Check summary
        summary = detector.summarize(results)
        assert summary["total_evaluations"] == 2
        assert summary["triggered_candidates"] == 1
        assert summary["non_triggered"] == 1
        assert len(summary["candidates"]) == 1
        assert summary["candidates"][0]["run_id"] == "mixed-det-b"
