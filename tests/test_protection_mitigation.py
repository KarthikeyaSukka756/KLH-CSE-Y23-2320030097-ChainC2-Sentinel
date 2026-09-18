# ChainC2 Sentinel — Tests for Controlled Protection / Mitigation (Milestone 9)
"""Comprehensive unit and integration tests for Milestone 9 defensive responders,

handlers, verification routines, cooperative isolation, and rollback.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError

import pytest

from src.detection.models import DetectionConditionMatch, DetectionResult, DetectionStatus
from src.http_target.server import LocalHttpTargetServer
from src.protection.executor import DefenseExecutor
from src.protection.handlers.evidence_handler import EvidenceSnapshotHandler
from src.protection.handlers.network_handler import NetworkContainmentHandler
from src.protection.handlers.process_handler import ProcessIsolationHandler
from src.protection.handlers.rpc_handler import RpcFilterHandler
from src.protection.models import (
    DefenseExecutionRecord,
    DefensePlan,
    DefensePlanStatus,
    MitigationAction,
    MitigationStatus,
    MitigationType,
)
from src.protection.policy import DefensivePolicyEngine
from src.protection.process_registry import ScenarioWorkerRegistry
from src.rpc_proxy.proxy import RpcProxy, _extract_target_contract

C2_CONTRACT_ADDR = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
BENIGN_CONTRACT_ADDR = "0x5FbDB2315678afecb367f032d93F642f64180aa3"


@pytest.fixture
def sample_triggered_detection() -> DetectionResult:
    """Fixture representing a Scenario B candidate detection."""
    return DetectionResult(
        rule_id="RULE-CHAINC2-001",
        rule_name="Synthetic Blockchain-Mediated C2 Sequence Rule",
        rule_version="1.0.0",
        status=DetectionStatus.TRIGGERED,
        triggered=True,
        correlation_id="corr-c2-mitigation-001",
        run_id="run-c2-mitigation",
        scenario_id="scenario_b_synthetic_c2",
        observed_stages=["endpoint", "rpc", "blockchain", "network"],
        conditions=[
            DetectionConditionMatch(
                condition_id="cond_c2datastore",
                description="Synthetic C2DataStore smart contract",
                satisfied=True,
                evidence_detail=f"Contract: C2DataStore at {C2_CONTRACT_ADDR}",
            )
        ],
        matched_conditions=["cond_endpoint", "cond_rpc", "cond_blockchain", "cond_c2datastore", "cond_network", "cond_network_timing", "cond_causal_timeline"],
        unmatched_conditions=[],
        evidence={
            "contract_name": "C2DataStore",
            "contract_address": C2_CONTRACT_ADDR,
            "network_destination_host": "127.0.0.1",
            "network_destination_port": 8080,
            "process_name": "synthetic_c2_client",
            "process_pid": 4096,
        },
        explanation="Controlled detection candidate confirmed for synthetic C2 sequence.",
        evaluated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_benign_detection() -> DetectionResult:
    """Fixture representing a Scenario A negative control."""
    return DetectionResult(
        rule_id="RULE-CHAINC2-001",
        rule_name="Synthetic Blockchain-Mediated C2 Sequence Rule",
        rule_version="1.0.0",
        status=DetectionStatus.NOT_TRIGGERED,
        triggered=False,
        correlation_id="corr-benign-mitigation-001",
        run_id="run-benign-mitigation",
        scenario_id="scenario_a_benign",
        observed_stages=["endpoint", "rpc", "blockchain"],
        conditions=[],
        matched_conditions=["cond_endpoint", "cond_rpc"],
        unmatched_conditions=["cond_blockchain", "cond_c2datastore", "cond_network", "cond_network_timing", "cond_causal_timeline"],
        evidence={
            "contract_name": "BenignDAppContract",
            "contract_address": BENIGN_CONTRACT_ADDR,
        },
        explanation="Legitimate Web3 baseline: zero follow-up network activity observed.",
        evaluated_at=datetime.now(timezone.utc),
    )


@pytest.mark.unit
class TestControlledMitigation:
    """Milestone 9 validation suite for controlled protection and mitigation handlers."""

    def test_non_triggered_detection_skips_all_protection(
        self,
        sample_benign_detection: DetectionResult,
    ):
        """Scenario A negative control yields SKIPPED plan with zero mitigations executed."""
        policy_engine = DefensivePolicyEngine()
        plan = policy_engine.create_defense_plan(sample_benign_detection)

        assert plan.status == DefensePlanStatus.SKIPPED
        assert len(plan.actions) == 0

        executor = DefenseExecutor()
        record = executor.execute_plan(plan)

        assert record.overall_success is True
        assert record.actions_executed == 0
        assert record.actions_verified == 0
        assert record.actions_failed == 0
        assert record.plan.status == DefensePlanStatus.SKIPPED

    def test_triggered_detection_executes_protection_plan(
        self,
        sample_triggered_detection: DetectionResult,
        tmp_path: Path,
    ):
        """Scenario B candidate generates and successfully executes an ordered 4-layer defense plan."""
        policy_engine = DefensivePolicyEngine()
        plan = policy_engine.create_defense_plan(sample_triggered_detection)

        assert plan.status == DefensePlanStatus.PENDING
        assert len(plan.actions) == 4

        # Configure handlers with isolated test environments
        worker_registry = ScenarioWorkerRegistry()
        worker_registry.register_worker("synthetic_c2_client", 4096)

        proxy = RpcProxy()
        target_server = LocalHttpTargetServer(host="127.0.0.1", port=0)

        executor = DefenseExecutor(
            handlers={
                MitigationType.EVIDENCE_PRESERVATION: EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence")),
                MitigationType.RPC_FILTER: RpcFilterHandler(proxy=proxy),
                MitigationType.NETWORK_CONTAINMENT: NetworkContainmentHandler(target_server=target_server),
                MitigationType.PROCESS_ISOLATION: ProcessIsolationHandler(registry=worker_registry),
            }
        )

        record = executor.execute_plan(plan)

        assert record.overall_success is True
        assert record.actions_executed == 4
        assert record.actions_verified == 4
        assert record.actions_failed == 0
        assert plan.status == DefensePlanStatus.VERIFIED

        # Verify each action state
        for action in plan.actions:
            assert action.status == MitigationStatus.VERIFIED
            assert action.execution_timestamp is not None
            assert action.verification_timestamp is not None
            assert action.verification_details is not None

    def test_rpc_c2datastore_rejected_after_containment_and_benign_allowed(self):
        """RPC proxy rejects quarantined C2DataStore while allowing benign contract calls."""
        proxy = RpcProxy()
        handler = RpcFilterHandler(proxy=proxy)

        action = MitigationAction(
            mitigation_type=MitigationType.RPC_FILTER,
            target_layer="rpc",
            target_resource=C2_CONTRACT_ADDR,
            parameters={"contract_address": C2_CONTRACT_ADDR},
            verification_strategy="Probe proxy filter",
        )

        # Before mitigation: proxy is clean
        assert not proxy.is_contract_filtered(C2_CONTRACT_ADDR)
        assert not proxy.is_contract_filtered(BENIGN_CONTRACT_ADDR)

        # Execute mitigation
        assert handler.execute(action) is True
        assert handler.verify(action) is True
        assert action.status == MitigationStatus.VERIFIED

        # Target contract is filtered
        assert proxy.is_contract_filtered(C2_CONTRACT_ADDR)

        # Benign contract is NOT filtered and remains unaffected
        assert not proxy.is_contract_filtered(BENIGN_CONTRACT_ADDR)

        # Verify param extractor helper
        c2_params = [{"to": C2_CONTRACT_ADDR, "data": "0x1234"}]
        assert _extract_target_contract(c2_params) == C2_CONTRACT_ADDR.lower()

        benign_params = [{"to": BENIGN_CONTRACT_ADDR, "data": "0x5678"}]
        assert _extract_target_contract(benign_params) == BENIGN_CONTRACT_ADDR.lower()

    def test_local_beacon_rejected_after_network_containment_and_health_allowed(self):
        """LocalHttpTargetServer returns HTTP 403 on beacon while health endpoint remains healthy."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            handler = NetworkContainmentHandler(target_server=target_srv)

            # 1. Before containment: POST /beacon succeeds (200 OK)
            req = urllib_request.Request(
                target_srv.beacon_url,
                data=json.dumps({"test": "before"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib_request.urlopen(req) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode("utf-8"))
                assert data["status"] == "acknowledged"

            # 2. Execute containment
            action = MitigationAction(
                mitigation_type=MitigationType.NETWORK_CONTAINMENT,
                target_layer="network",
                target_resource="127.0.0.1",
                parameters={"destination_host": "127.0.0.1"},
                verification_strategy="Probe target /beacon",
            )
            assert handler.execute(action) is True
            assert handler.verify(action) is True
            assert action.status == MitigationStatus.VERIFIED

            # 3. After containment: POST /beacon is REJECTED with HTTP 403
            with pytest.raises(HTTPError) as exc_info:
                urllib_request.urlopen(req)
            assert exc_info.value.code == 403

            # 4. Unrelated GET /health endpoint remains functional (200 OK)
            with urllib_request.urlopen(target_srv.health_url) as resp:
                assert resp.status == 200
                h_data = json.loads(resp.read().decode("utf-8"))
                assert h_data["status"] == "healthy"

    def test_cooperative_process_isolation_and_arbitrary_process_refusal(self):
        """Cooperative isolation succeeds for registered workers and strictly refuses arbitrary processes."""
        registry = ScenarioWorkerRegistry()
        handler = ProcessIsolationHandler(registry=registry)

        # Register laboratory scenario worker
        registry.register_worker("synthetic_c2_client", 4096)
        assert registry.is_isolated("synthetic_c2_client", 4096) is False

        # Isolate registered worker
        action = MitigationAction(
            mitigation_type=MitigationType.PROCESS_ISOLATION,
            target_layer="process",
            target_resource="synthetic_c2_client",
            parameters={"process_name": "synthetic_c2_client", "pid": 4096},
            verification_strategy="Check registry state",
        )
        assert handler.execute(action) is True
        assert handler.verify(action) is True
        assert action.status == MitigationStatus.VERIFIED
        assert registry.is_isolated("synthetic_c2_client", 4096) is True

        # Attempt to isolate an arbitrary / unregistered host process
        unsafe_action = MitigationAction(
            mitigation_type=MitigationType.PROCESS_ISOLATION,
            target_layer="process",
            target_resource="arbitrary_system_process",
            parameters={"process_name": "arbitrary_system_process", "pid": 1},
            verification_strategy="Check registry state",
        )
        # MUST fail execution and refuse to touch arbitrary processes
        assert handler.execute(unsafe_action) is False
        assert unsafe_action.status == MitigationStatus.FAILED
        assert "not a registered laboratory worker" in unsafe_action.error_message

    def test_evidence_bundle_creation_and_integrity(
        self,
        sample_triggered_detection: DetectionResult,
        tmp_path: Path,
    ):
        """EvidenceSnapshotHandler serializes complete evidence bundle with valid SHA-256 checksum."""
        out_dir = tmp_path / "evidence_vault"
        handler = EvidenceSnapshotHandler(output_dir=str(out_dir))

        bundle_path_str = handler.preserve_evidence(sample_triggered_detection)
        bundle_path = Path(bundle_path_str)

        assert bundle_path.exists()
        assert bundle_path.stat().st_size > 0

        with open(bundle_path, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        assert bundle["correlation_id"] == sample_triggered_detection.correlation_id
        assert bundle["rule_id"] == "RULE-CHAINC2-001"
        assert bundle["detection_status"] == "triggered"
        assert bundle["triggered"] is True
        assert "sha256_checksum" in bundle
        assert "research_declaration" in bundle

        # Verify integrity of stored checksum
        stored_hash = bundle.pop("sha256_checksum")
        recomputed = hashlib.sha256(json.dumps(bundle, indent=2).encode("utf-8")).hexdigest()
        assert stored_hash == recomputed

    def test_rollback_restores_baseline(
        self,
        sample_triggered_detection: DetectionResult,
        tmp_path: Path,
    ):
        """Rollback cleanly reverts all reversible mitigations, restoring laboratory baseline."""
        policy_engine = DefensivePolicyEngine()
        plan = policy_engine.create_defense_plan(sample_triggered_detection)

        registry = ScenarioWorkerRegistry()
        registry.register_worker("synthetic_c2_client", 4096)
        proxy = RpcProxy()
        target_server = LocalHttpTargetServer(host="127.0.0.1", port=0)

        executor = DefenseExecutor(
            handlers={
                MitigationType.EVIDENCE_PRESERVATION: EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence")),
                MitigationType.RPC_FILTER: RpcFilterHandler(proxy=proxy),
                MitigationType.NETWORK_CONTAINMENT: NetworkContainmentHandler(target_server=target_server),
                MitigationType.PROCESS_ISOLATION: ProcessIsolationHandler(registry=registry),
            }
        )

        # 1. Execute plan
        record = executor.execute_plan(plan)
        assert record.overall_success is True

        # Mitigations are active
        assert proxy.is_contract_filtered(C2_CONTRACT_ADDR)
        assert target_server.is_containment_active()
        assert registry.is_isolated("synthetic_c2_client", 4096)

        # 2. Rollback plan
        rollback_success = executor.rollback_plan(plan)
        assert rollback_success is True
        assert plan.status == DefensePlanStatus.ROLLED_BACK

        # Mitigations are cleanly reverted
        assert not proxy.is_contract_filtered(C2_CONTRACT_ADDR)
        assert not target_server.is_containment_active()
        assert not registry.is_isolated("synthetic_c2_client", 4096)

    def test_failed_mitigation_is_recorded_as_failed(self):
        """Handler execution failure gracefully marks action and plan as FAILED."""
        action = MitigationAction(
            mitigation_type=MitigationType.PROCESS_ISOLATION,
            target_layer="process",
            target_resource="missing_process",
            parameters={"process_name": "missing_process", "pid": 9999},
            verification_strategy="Check registry state",
        )
        plan = DefensePlan(
            detection_correlation_id="corr-fail-test",
            rule_id="RULE-CHAINC2-001",
            status=DefensePlanStatus.PENDING,
            actions=[action],
            evidence_summary="Test plan with failing action.",
        )

        empty_registry = ScenarioWorkerRegistry()
        executor = DefenseExecutor(
            handlers={
                MitigationType.PROCESS_ISOLATION: ProcessIsolationHandler(registry=empty_registry),
                MitigationType.EVIDENCE_PRESERVATION: EvidenceSnapshotHandler(),
                MitigationType.RPC_FILTER: RpcFilterHandler(),
                MitigationType.NETWORK_CONTAINMENT: NetworkContainmentHandler(),
            }
        )

        record = executor.execute_plan(plan)

        assert record.overall_success is False
        assert record.actions_failed == 1
        assert record.actions_executed == 0
        assert action.status == MitigationStatus.FAILED
        assert plan.status == DefensePlanStatus.FAILED
