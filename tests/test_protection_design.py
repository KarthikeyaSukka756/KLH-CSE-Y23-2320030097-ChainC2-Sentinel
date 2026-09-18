# ChainC2 Sentinel — Tests for Defensive Response Design (Milestone 8)
"""Unit tests verifying the defensive response architecture, data models,

and policy engine.
"""

from datetime import datetime, timezone
import pytest

from src.detection.models import DetectionConditionMatch, DetectionResult, DetectionStatus
from src.protection.models import (
    DefenseExecutionRecord,
    DefensePlan,
    DefensePlanStatus,
    MitigationAction,
    MitigationStatus,
    MitigationType,
)
from src.protection.policy import DefensivePolicyEngine


@pytest.fixture
def policy_engine() -> DefensivePolicyEngine:
    return DefensivePolicyEngine()


@pytest.fixture
def triggered_detection_result() -> DetectionResult:
    """Fixture representing a factual Scenario B candidate detection."""
    return DetectionResult(
        rule_id="RULE-CHAINC2-001",
        rule_name="Synthetic Blockchain-Mediated C2 Sequence Rule",
        rule_version="1.0.0",
        status=DetectionStatus.TRIGGERED,
        triggered=True,
        correlation_id="corr-test-c2-001",
        run_id="run-c2-test",
        scenario_id="scenario_b_synthetic_c2",
        observed_stages=["endpoint", "rpc", "blockchain", "network"],
        conditions=[
            DetectionConditionMatch(
                condition_id="cond_c2datastore",
                description="Synthetic C2DataStore smart contract",
                satisfied=True,
                evidence_detail="Contract: C2DataStore at 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
            )
        ],
        matched_conditions=["cond_endpoint", "cond_rpc", "cond_blockchain", "cond_c2datastore", "cond_network", "cond_network_timing", "cond_causal_timeline"],
        unmatched_conditions=[],
        evidence={
            "contract_name": "C2DataStore",
            "contract_address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
            "network_destination_host": "127.0.0.1",
            "network_destination_port": 8080,
            "process_name": "synthetic_c2_client",
            "process_pid": 4096,
        },
        explanation="Synthetic C2 sequence detected with all 7 observable conditions satisfied.",
        evaluated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def non_triggered_detection_result() -> DetectionResult:
    """Fixture representing a Scenario A negative control."""
    return DetectionResult(
        rule_id="RULE-CHAINC2-001",
        rule_name="Synthetic Blockchain-Mediated C2 Sequence Rule",
        rule_version="1.0.0",
        status=DetectionStatus.NOT_TRIGGERED,
        triggered=False,
        correlation_id="corr-test-benign-001",
        run_id="run-benign-test",
        scenario_id="scenario_a_benign",
        observed_stages=["endpoint", "rpc", "blockchain"],
        conditions=[],
        matched_conditions=["cond_endpoint", "cond_rpc"],
        unmatched_conditions=["cond_blockchain", "cond_c2datastore", "cond_network", "cond_network_timing", "cond_causal_timeline"],
        evidence={
            "contract_name": "BenignDAppContract",
            "contract_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        },
        explanation="Legitimate Web3 baseline: zero follow-up network activity observed.",
        evaluated_at=datetime.now(timezone.utc),
    )


@pytest.mark.unit
class TestDefensiveResponseDesign:
    """Tests for Milestone 8 defensive response architecture and policy rules."""

    def test_benign_scenario_produces_no_defense_actions(
        self,
        policy_engine: DefensivePolicyEngine,
        non_triggered_detection_result: DetectionResult,
    ):
        """CRITICAL REQUIREMENT: Legitimate Web3 activity must NEVER trigger defensive response."""
        plan = policy_engine.create_defense_plan(non_triggered_detection_result)

        assert isinstance(plan, DefensePlan)
        assert plan.status == DefensePlanStatus.SKIPPED
        assert len(plan.actions) == 0
        assert plan.safety_boundary_verified is True
        assert "No defensive response required" in plan.evidence_summary

    def test_triggered_detection_produces_defense_plan(
        self,
        policy_engine: DefensivePolicyEngine,
        triggered_detection_result: DetectionResult,
    ):
        """Triggered detection candidate produces an ordered, layered defense plan."""
        plan = policy_engine.create_defense_plan(triggered_detection_result)

        assert isinstance(plan, DefensePlan)
        assert plan.status == DefensePlanStatus.PENDING
        assert plan.rule_id == "RULE-CHAINC2-001"
        assert plan.detection_correlation_id == "corr-test-c2-001"
        assert len(plan.actions) == 4

        # Verify Layer 1: Evidence Preservation
        a_ev = plan.actions[0]
        assert a_ev.mitigation_type == MitigationType.EVIDENCE_PRESERVATION
        assert a_ev.target_layer == "evidence"
        assert a_ev.status == MitigationStatus.REQUESTED
        assert a_ev.is_reversible is False  # Permanent audit trail

        # Verify Layer 2: RPC Access Filter
        a_rpc = plan.actions[1]
        assert a_rpc.mitigation_type == MitigationType.RPC_FILTER
        assert a_rpc.target_layer == "rpc"
        assert a_rpc.target_resource == "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
        assert a_rpc.is_reversible is True

        # Verify Layer 3: Network Beacon Containment
        a_net = plan.actions[2]
        assert a_net.mitigation_type == MitigationType.NETWORK_CONTAINMENT
        assert a_net.target_layer == "network"
        assert a_net.target_resource == "127.0.0.1:8080"
        assert a_net.is_reversible is True

        # Verify Layer 4: Process Containment Signal
        a_proc = plan.actions[3]
        assert a_proc.mitigation_type == MitigationType.PROCESS_ISOLATION
        assert a_proc.target_layer == "process"
        assert a_proc.target_resource == "synthetic_c2_client"
        assert a_proc.is_reversible is True

    def test_safety_boundary_rejection_external_ip(
        self,
        policy_engine: DefensivePolicyEngine,
        triggered_detection_result: DetectionResult,
    ):
        """Defense policy strictly rejects targeting external IPs outside the laboratory."""
        triggered_detection_result.evidence["network_destination_host"] = "192.168.1.50"

        with pytest.raises(ValueError, match="Safety violation: Destination host 192.168.1.50"):
            policy_engine.create_defense_plan(triggered_detection_result)

    def test_policy_selective_layer_configuration(
        self,
        triggered_detection_result: DetectionResult,
    ):
        """Policy engine can be selectively configured with specific defensive layers."""
        engine = DefensivePolicyEngine(
            enable_evidence_preservation=True,
            enable_rpc_filter=True,
            enable_network_containment=False,
            enable_process_isolation=False,
        )
        plan = engine.create_defense_plan(triggered_detection_result)

        assert len(plan.actions) == 2
        types = [a.mitigation_type for a in plan.actions]
        assert types == [MitigationType.EVIDENCE_PRESERVATION, MitigationType.RPC_FILTER]

    def test_defense_execution_record_model(
        self,
        policy_engine: DefensivePolicyEngine,
        triggered_detection_result: DetectionResult,
    ):
        """DefenseExecutionRecord accurately represents an auditable response log."""
        plan = policy_engine.create_defense_plan(triggered_detection_result)

        # Simulate execution
        for action in plan.actions:
            action.status = MitigationStatus.VERIFIED
            action.execution_timestamp = datetime.now(timezone.utc)
            action.verification_timestamp = datetime.now(timezone.utc)
            action.verification_details = "Containment verified by active probe."

        plan.status = DefensePlanStatus.VERIFIED

        record = DefenseExecutionRecord(
            plan=plan,
            overall_success=True,
            actions_executed=4,
            actions_verified=4,
            actions_failed=0,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_ms=2.45,
            rollback_available=True,
            audit_telemetry=[{"event": "mitigation_applied", "layer": "rpc"}],
        )

        assert record.overall_success is True
        assert record.actions_executed == 4
        assert record.plan.status == DefensePlanStatus.VERIFIED
        assert record.duration_ms == 2.45
