# ChainC2 Sentinel — Tests for Rule-Based Weighted Scoring
"""Comprehensive tests for explainable rule-based weighted scoring and detection."""

from datetime import datetime, timezone, timedelta
from typing import Any
import pytest

from src.correlation import CrossLayerCorrelationEngine
from src.correlation.models import CorrelatedSequence
from src.detection.models import DetectionResult, DetectionStatus
from src.detection.rules import SyntheticC2SequenceRule
from src.detection.scoring import (
    RuleBasedScorer,
    ScoringResult,
    DEFAULT_WEIGHT_ENDPOINT_CONTEXT,
    DEFAULT_WEIGHT_RPC_INTERACTION,
    DEFAULT_WEIGHT_CONTRACT_INTERACTION,
    DEFAULT_WEIGHT_SUSPICIOUS_RETRIEVAL,
    DEFAULT_WEIGHT_C2_CONFIGURATION,
    DEFAULT_WEIGHT_NETWORK_FOLLOWUP,
    DEFAULT_DETECTION_THRESHOLD,
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
from src.protection.policy import DefensivePolicyEngine
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.definitions.legitimate_dapp_scenario import LegitimateDAppScenario


@pytest.fixture
def correlation_engine() -> CrossLayerCorrelationEngine:
    return CrossLayerCorrelationEngine()


@pytest.fixture
def scorer() -> RuleBasedScorer:
    return RuleBasedScorer()


@pytest.fixture
def detection_rule() -> SyntheticC2SequenceRule:
    return SyntheticC2SequenceRule()


@pytest.mark.unit
class TestScoringScenarios:
    """Evaluate scoring and detection across Scenario A, Scenario B, and Scenario C."""

    def test_scenario_a_benign_web3_scoring(self, correlation_engine, scorer, detection_rule):
        """Scenario A produces a low score (35.0) and NOT_TRIGGERED verdict."""
        scenario = BenignWeb3Scenario(run_id="run-scoring-benign")
        res = scenario.run()
        seq = correlation_engine.correlate(res.events)[0]

        scoring_res = scorer.score(seq)
        assert scoring_res.total_score == 35.0
        assert scoring_res.threshold == 80.0
        assert scoring_res.is_triggered is False
        assert set(scoring_res.matched_scoring_rules) == {
            "endpoint_context",
            "rpc_interaction",
            "contract_interaction",
        }
        assert set(scoring_res.unmatched_scoring_rules) == {
            "suspicious_retrieval",
            "c2_configuration",
            "network_followup",
        }

        det_res = detection_rule.evaluate(seq)
        assert det_res.status == DetectionStatus.NOT_TRIGGERED
        assert det_res.triggered is False
        assert det_res.total_score == 35.0

        # Verify zero protection plan generated for benign
        policy_engine = DefensivePolicyEngine()
        plan = policy_engine.create_defense_plan(det_res)
        assert plan.status.value == "skipped"
        assert len(plan.actions) == 0

    def test_scenario_c_legitimate_dapp_scoring(self, correlation_engine, scorer, detection_rule):
        """Scenario C produces a low score (35.0) and NOT_TRIGGERED verdict."""
        scenario = LegitimateDAppScenario(run_id="run-scoring-legit")
        res = scenario.run()
        seq = correlation_engine.correlate(res.events)[0]

        scoring_res = scorer.score(seq)
        assert scoring_res.total_score == 35.0
        assert scoring_res.threshold == 80.0
        assert scoring_res.is_triggered is False
        assert set(scoring_res.matched_scoring_rules) == {
            "endpoint_context",
            "rpc_interaction",
            "contract_interaction",
        }
        assert set(scoring_res.unmatched_scoring_rules) == {
            "suspicious_retrieval",
            "c2_configuration",
            "network_followup",
        }

        det_res = detection_rule.evaluate(seq)
        assert det_res.status == DetectionStatus.NOT_TRIGGERED
        assert det_res.triggered is False
        assert det_res.total_score == 35.0

        # Verify zero protection plan generated for legitimate DApp
        policy_engine = DefensivePolicyEngine()
        plan = policy_engine.create_defense_plan(det_res)
        assert plan.status.value == "skipped"
        assert len(plan.actions) == 0

    def test_scenario_b_synthetic_c2_scoring(self, correlation_engine, scorer, detection_rule):
        """Scenario B produces maximum score (100.0) and TRIGGERED verdict."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            scenario = SyntheticC2Scenario(target_server=target_srv, run_id="run-scoring-c2")
            res = scenario.run()
            seq = correlation_engine.correlate(res.events)[0]

            scoring_res = scorer.score(seq)
            assert scoring_res.total_score == 100.0
            assert scoring_res.threshold == 80.0
            assert scoring_res.is_triggered is True
            assert len(scoring_res.matched_scoring_rules) == 6
            assert len(scoring_res.unmatched_scoring_rules) == 0

            det_res = detection_rule.evaluate(seq)
            assert det_res.status == DetectionStatus.TRIGGERED
            assert det_res.triggered is True
            assert det_res.total_score == 100.0
            assert det_res.threshold == 80.0

            # Verify existing protection plan correctly triggers from this result
            policy_engine = DefensivePolicyEngine()
            plan = policy_engine.create_defense_plan(det_res)
            assert plan.status.value == "pending"
            assert len(plan.actions) == 4


@pytest.mark.unit
class TestNegativeControlsAndEdgeCases:
    """Evaluate isolated components and negative controls against the scoring model."""

    def test_rpc_only_negative_control(self, correlation_engine, scorer):
        """RPC interaction alone achieves only 10 points and fails threshold."""
        now = datetime.now(timezone.utc)
        rpc_ev = SentinelEvent(
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            host="127.0.0.1",
            timestamp=now,
            metadata={"run_id": "run-rpc-only"},
            rpc=RpcInfo(
                rpc_endpoint="http://127.0.0.1:8546",
                upstream_endpoint="http://127.0.0.1:8545",
                rpc_method="eth_blockNumber",
                status="success",
            ),
        )
        seq = correlation_engine.correlate([rpc_ev])[0]
        res = scorer.score(seq)
        assert res.total_score == 10.0
        assert res.is_triggered is False

    def test_blockchain_only_negative_control(self, correlation_engine, scorer):
        """Blockchain contract event alone achieves only 15 points and fails threshold."""
        now = datetime.now(timezone.utc)
        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_interaction",
            host="127.0.0.1",
            timestamp=now,
            metadata={"run_id": "run-bc-only"},
            blockchain=BlockchainInfo(
                contract_name="BenignDAppContract",
                function_name="increment",
            ),
        )
        seq = correlation_engine.correlate([bc_ev])[0]
        res = scorer.score(seq)
        assert res.total_score == 15.0
        assert res.is_triggered is False

    def test_suspicious_retrieval_without_network_followup(self, correlation_engine, scorer):
        """Endpoint + RPC + C2DataStore retrieval WITHOUT network activity yields 75.0 (< 80) and does not trigger."""
        t0 = datetime.now(timezone.utc)
        t1 = t0 + timedelta(milliseconds=10)
        t2 = t1 + timedelta(milliseconds=20)

        ep_ev = SentinelEvent(
            source=TelemetrySource.ENDPOINT,
            event_type="process_start",
            host="127.0.0.1",
            timestamp=t0,
            metadata={"run_id": "run-no-net"},
            process=ProcessInfo(process_name="c2_agent", pid=1234),
        )
        rpc_ev = SentinelEvent(
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            host="127.0.0.1",
            timestamp=t1,
            metadata={"run_id": "run-no-net"},
            rpc=RpcInfo(
                rpc_endpoint="http://127.0.0.1:8546",
                upstream_endpoint="http://127.0.0.1:8545",
                rpc_method="eth_call",
                status="success",
            ),
        )
        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_interaction",
            host="127.0.0.1",
            timestamp=t2,
            metadata={"run_id": "run-no-net", "command": "CMD:BEACON"},
            blockchain=BlockchainInfo(
                contract_name="C2DataStore",
                function_name="getLatestCommand",
                event_args={"command": "CMD:BEACON:127.0.0.1:8088"},
            ),
        )
        seq = correlation_engine.correlate([ep_ev, rpc_ev, bc_ev])[0]
        res = scorer.score(seq)
        # 10 (ep) + 10 (rpc) + 15 (bc) + 20 (retrieval) + 20 (c2_config) = 75.0
        assert res.total_score == 75.0
        assert res.threshold == 80.0
        assert res.is_triggered is False

    def test_network_without_blockchain(self, correlation_engine, scorer):
        """Endpoint + Network beacon without blockchain activity fails threshold."""
        t0 = datetime.now(timezone.utc)
        t1 = t0 + timedelta(milliseconds=15)
        ep_ev = SentinelEvent(
            source=TelemetrySource.ENDPOINT,
            event_type="process_start",
            host="127.0.0.1",
            timestamp=t0,
            metadata={"run_id": "run-net-only"},
            process=ProcessInfo(process_name="browser", pid=5678),
        )
        net_ev = SentinelEvent(
            source=TelemetrySource.NETWORK,
            event_type="network_connection",
            host="127.0.0.1",
            timestamp=t1,
            metadata={"run_id": "run-net-only"},
            network=NetworkInfo(
                destination_host="127.0.0.1",
                destination_port=8088,
                protocol="HTTP",
                status_code=200,
            ),
        )
        seq = correlation_engine.correlate([ep_ev, net_ev])[0]
        res = scorer.score(seq)
        # Endpoint=10, Network=0 (requires blockchain causal antecedent)
        assert res.total_score == 10.0
        assert res.is_triggered is False

    def test_out_of_order_causality_violation(self, correlation_engine, scorer):
        """Network activity preceding blockchain read fails network_followup and does not trigger."""
        t0 = datetime.now(timezone.utc)
        t_net = t0 + timedelta(milliseconds=10)
        t_bc = t0 + timedelta(milliseconds=50)  # Blockchain event occurs AFTER network event

        ep_ev = SentinelEvent(
            source=TelemetrySource.ENDPOINT,
            event_type="process_start",
            host="127.0.0.1",
            timestamp=t0,
            metadata={"run_id": "run-out-of-order"},
            process=ProcessInfo(process_name="client", pid=9999),
        )
        rpc_ev = SentinelEvent(
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            host="127.0.0.1",
            timestamp=t0 + timedelta(milliseconds=5),
            metadata={"run_id": "run-out-of-order"},
            rpc=RpcInfo(
                rpc_endpoint="http://127.0.0.1:8546",
                upstream_endpoint="http://127.0.0.1:8545",
                rpc_method="eth_call",
                status="success",
            ),
        )
        net_ev = SentinelEvent(
            source=TelemetrySource.NETWORK,
            event_type="network_connection",
            host="127.0.0.1",
            timestamp=t_net,
            metadata={"run_id": "run-out-of-order"},
            network=NetworkInfo(
                destination_host="127.0.0.1",
                destination_port=8088,
                protocol="HTTP",
                status_code=200,
            ),
        )
        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_interaction",
            host="127.0.0.1",
            timestamp=t_bc,
            metadata={"run_id": "run-out-of-order", "command": "CMD:BEACON"},
            blockchain=BlockchainInfo(
                contract_name="C2DataStore",
                function_name="getLatestCommand",
            ),
        )
        seq = correlation_engine.correlate([ep_ev, rpc_ev, net_ev, bc_ev])[0]
        res = scorer.score(seq)
        # Network followup condition fails because t_net < t_bc
        assert res.total_score == 75.0
        assert res.is_triggered is False
        assert "network_followup" in res.unmatched_scoring_rules

    def test_missing_layers(self, correlation_engine, scorer):
        """Missing endpoint, RPC, or blockchain layers lowers score below threshold."""
        t0 = datetime.now(timezone.utc)
        # Missing endpoint
        rpc_ev = SentinelEvent(
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            host="127.0.0.1",
            timestamp=t0,
            metadata={"run_id": "run-no-ep"},
            rpc=RpcInfo(
                rpc_endpoint="http://127.0.0.1:8546",
                upstream_endpoint="http://127.0.0.1:8545",
                rpc_method="eth_call",
                status="success",
            ),
        )
        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_interaction",
            host="127.0.0.1",
            timestamp=t0 + timedelta(milliseconds=5),
            metadata={"run_id": "run-no-ep", "command": "CMD:BEACON"},
            blockchain=BlockchainInfo(contract_name="C2DataStore", function_name="getLatestCommand"),
        )
        seq_no_ep = correlation_engine.correlate([rpc_ev, bc_ev])[0]
        res_no_ep = scorer.score(seq_no_ep)
        assert res_no_ep.total_score == 65.0
        assert res_no_ep.is_triggered is False

    def test_deterministic_repeated_scoring(self, correlation_engine, scorer):
        """Repeated scoring of identical inputs produces identical scores and rule matches."""
        scenario = BenignWeb3Scenario(run_id="run-det-repeat")
        res = scenario.run()
        seq = correlation_engine.correlate(res.events)[0]

        scores = [scorer.score(seq) for _ in range(10)]
        for s in scores:
            assert s.total_score == 35.0
            assert s.threshold == 80.0
            assert s.is_triggered is False
            assert s.matched_scoring_rules == scores[0].matched_scoring_rules

    def test_threshold_boundary_behavior(self, correlation_engine):
        """Custom threshold configures boundary triggering correctly."""
        scorer_70 = RuleBasedScorer(threshold=70.0)
        scorer_80 = RuleBasedScorer(threshold=80.0)

        t0 = datetime.now(timezone.utc)
        ep_ev = SentinelEvent(
            source=TelemetrySource.ENDPOINT,
            event_type="process_start",
            host="127.0.0.1",
            timestamp=t0,
            metadata={"run_id": "run-boundary"},
            process=ProcessInfo(process_name="c2_agent", pid=1234),
        )
        rpc_ev = SentinelEvent(
            source=TelemetrySource.RPC,
            event_type="rpc_call",
            host="127.0.0.1",
            timestamp=t0 + timedelta(milliseconds=5),
            metadata={"run_id": "run-boundary"},
            rpc=RpcInfo(
                rpc_endpoint="http://127.0.0.1:8546",
                upstream_endpoint="http://127.0.0.1:8545",
                rpc_method="eth_call",
                status="success",
            ),
        )
        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_interaction",
            host="127.0.0.1",
            timestamp=t0 + timedelta(milliseconds=10),
            metadata={"run_id": "run-boundary", "command": "CMD:BEACON"},
            blockchain=BlockchainInfo(contract_name="C2DataStore", function_name="getLatestCommand"),
        )
        seq = correlation_engine.correlate([ep_ev, rpc_ev, bc_ev])[0]

        # Score is 75.0
        res_70 = scorer_70.score(seq)
        assert res_70.total_score == 75.0
        assert res_70.is_triggered is True  # 75.0 >= 70.0

        res_80 = scorer_80.score(seq)
        assert res_80.total_score == 75.0
        assert res_80.is_triggered is False  # 75.0 < 80.0
