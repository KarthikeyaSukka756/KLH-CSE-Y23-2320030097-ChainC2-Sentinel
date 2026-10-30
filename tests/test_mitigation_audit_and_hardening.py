# ChainC2 Sentinel — Comprehensive Mitigation Audit & Hardening Test Suite
"""Validation suite for Milestone 9 defensive mitigation audit, verification hardening,
truthful status semantics, cooperative worker isolation, and rollback capabilities.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from src.protection.process_registry import ScenarioWorkerRegistry, get_worker_registry
from src.rpc_proxy.proxy import RpcProxy
from src.scenarios.generator import ControlledGenerator

C2_CONTRACT_ADDR = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
BENIGN_CONTRACT_ADDR = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"


@pytest.fixture
def c2_detection_result() -> DetectionResult:
    """Fixture producing a synthetic C2 detection result (Positive Control)."""
    return DetectionResult(
        rule_id="RULE-CHAINC2-001",
        rule_name="Synthetic Blockchain-Mediated C2 Sequence Rule",
        rule_version="1.0.0",
        status=DetectionStatus.TRIGGERED,
        triggered=True,
        correlation_id="corr-audit-c2-001",
        run_id="run-audit-c2-001",
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
        explanation="Controlled positive control confirmed for synthetic C2 sequence.",
        evaluated_at=datetime.now(timezone.utc),
    )


@pytest.mark.unit
class TestEvidencePreservationHardening:
    """Rigorous tests for evidence snapshot creation, independent SHA-256 verification, and corruption detection."""

    def test_evidence_snapshot_creates_valid_bundle_with_recomputed_hash(
        self,
        c2_detection_result: DetectionResult,
        tmp_path: Path,
    ):
        """Handler creates a valid snapshot and verify() confirms independent SHA-256 integrity."""
        handler = EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence"))

        action = MitigationAction(
            mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
            target_layer="data",
            target_resource=c2_detection_result.correlation_id,
            parameters={"correlation_id": c2_detection_result.correlation_id, "run_id": c2_detection_result.run_id},
            verification_strategy="File existence and cryptographic SHA-256 recomputation",
        )

        assert handler.execute(action) is True
        assert action.status == MitigationStatus.EXECUTED
        assert "snapshot_path" in action.parameters
        assert "sha256_checksum" in action.parameters

        # Verify confirms file existence and matches recomputed checksum
        assert handler.verify(action) is True
        assert action.status == MitigationStatus.VERIFIED
        assert "SHA-256" in action.verification_details
        assert "ephemeral" in action.verification_details.lower() or "local container" in action.verification_details.lower()

    def test_evidence_verification_detects_corrupted_json(self, tmp_path: Path):
        """Corrupted or truncated JSON file causes verify() to fail honestly."""
        handler = EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence"))
        corrupt_file = tmp_path / "evidence" / "evidence_corrupt.json"
        corrupt_file.parent.mkdir(parents=True, exist_ok=True)
        corrupt_file.write_text("{ this is not valid json! ", encoding="utf-8")

        action = MitigationAction(
            mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
            target_layer="data",
            target_resource="corr-corrupt-001",
            parameters={"snapshot_path": str(corrupt_file), "sha256_checksum": "0" * 64},
            verification_strategy="File existence and cryptographic SHA-256 recomputation",
        )

        assert handler.verify(action) is False
        assert action.status == MitigationStatus.FAILED
        assert "invalid or corrupted JSON" in action.verification_details

    def test_evidence_verification_detects_tampered_payload(self, tmp_path: Path):
        """Tampered bundle payload causes SHA-256 checksum mismatch and fails verification."""
        handler = EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence"))

        action = MitigationAction(
            mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
            target_layer="data",
            target_resource="corr-tamper-001",
            parameters={"correlation_id": "corr-tamper-001"},
            verification_strategy="Cryptographic verification",
        )

        assert handler.execute(action) is True
        path = Path(action.parameters["snapshot_path"])

        # Tamper with the file contents on disk
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tampered_field"] = "malicious_injection"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # verify() must catch the tampering and return False
        assert handler.verify(action) is False
        assert action.status == MitigationStatus.FAILED
        assert "Cryptographic integrity failure" in action.verification_details

    def test_evidence_verification_detects_missing_file(self, tmp_path: Path):
        """Missing snapshot path causes verify() to fail."""
        handler = EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence"))
        action = MitigationAction(
            mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
            target_layer="data",
            target_resource="corr-missing-001",
            parameters={"snapshot_path": str(tmp_path / "nonexistent.json")},
            verification_strategy="Cryptographic verification",
        )
        assert handler.verify(action) is False
        assert action.status == MitigationStatus.FAILED
        assert "not found" in action.verification_details

    def test_evidence_verification_detects_incorrect_parameter_checksum(self, tmp_path: Path):
        """Mismatched recorded checksum in action parameters causes verification to fail with FAILED."""
        handler = EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence"))
        action = MitigationAction(
            mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
            target_layer="data",
            target_resource="corr-bad-checksum-001",
            parameters={"correlation_id": "corr-bad-checksum-001"},
            verification_strategy="Cryptographic verification",
        )
        assert handler.execute(action) is True

        # Tamper with recorded parameter checksum
        action.parameters["sha256_checksum"] = "bad" * 21 + "a"
        assert handler.verify(action) is False
        assert action.status == MitigationStatus.FAILED
        assert action.status != MitigationStatus.VERIFIED
        assert "mismatch" in action.verification_details.lower()

    def test_evidence_verification_missing_checksum_field_fails(self, tmp_path: Path):
        """Bundle missing mandatory sha256_checksum field fails verification."""
        handler = EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence"))
        action = MitigationAction(
            mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
            target_layer="data",
            target_resource="corr-no-checksum-001",
            parameters={"correlation_id": "corr-no-checksum-001"},
            verification_strategy="Cryptographic verification",
        )
        assert handler.execute(action) is True
        path = Path(action.parameters["snapshot_path"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("sha256_checksum", None)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        assert handler.verify(action) is False
        assert action.status == MitigationStatus.FAILED
        assert action.status != MitigationStatus.VERIFIED
        assert "missing mandatory 'sha256_checksum'" in action.verification_details


@pytest.mark.unit
class TestSyntheticWorkerIsolation:
    """Tests for cooperative worker isolation, real event suppression, and rollback resumption."""

    def test_cooperative_isolation_and_activity_suppression(self, tmp_path: Path):
        """Isolated worker has real activity suppressed in generator cycles."""
        registry = get_worker_registry()
        registry.clear()

        # Step 1: Register and run active worker
        generator = ControlledGenerator(repo_root=tmp_path)
        generator.current_scenario_index = 2  # scenario_b_synthetic_c2

        res_before = generator._execute_c2_workload("run-before-isolation")
        assert res_before["status"] == "SUCCESS"
        assert res_before["events_emitted"] == 4

        # Step 2: Apply cooperative isolation
        handler = ProcessIsolationHandler(registry=registry)
        action = MitigationAction(
            mitigation_type=MitigationType.PROCESS_ISOLATION,
            target_layer="process",
            target_resource="synthetic_c2_client",
            parameters={"process_name": "synthetic_c2_client", "pid": 4096},
            verification_strategy="Check registry state and suppression",
        )
        assert handler.execute(action) is True
        assert handler.verify(action) is True
        assert action.status == MitigationStatus.VERIFIED
        assert registry.is_isolated("synthetic_c2_client", 4096) is True

        # Step 3: Run generator again — must be SUPPRESSED
        res_after = generator._execute_c2_workload("run-during-isolation")
        assert res_after["status"] == "SUPPRESSED"
        assert res_after["events_emitted"] == 0
        assert "ISOLATED" in res_after["telemetry_summary"]

        # Step 4: Rollback isolation — activity resumes
        assert handler.rollback(action) is True
        assert registry.is_isolated("synthetic_c2_client", 4096) is False

        res_resumed = generator._execute_c2_workload("run-resumed")
        assert res_resumed["status"] == "SUCCESS"
        assert res_resumed["events_emitted"] == 4

        registry.clear()

    def test_arbitrary_process_isolation_strictly_refused(self):
        """ProcessIsolationHandler strictly refuses to touch arbitrary un-whitelisted processes."""
        registry = ScenarioWorkerRegistry()
        handler = ProcessIsolationHandler(registry=registry)

        action = MitigationAction(
            mitigation_type=MitigationType.PROCESS_ISOLATION,
            target_layer="process",
            target_resource="host_system_daemon",
            parameters={"process_name": "host_system_daemon", "pid": 1},
            verification_strategy="Check registry state",
        )

        assert handler.execute(action) is False
        assert action.status == MitigationStatus.FAILED
        assert "not a registered laboratory worker" in action.error_message

    def test_unrelated_workloads_remain_untouched_during_isolation(self, tmp_path: Path):
        """When synthetic_c2_client is isolated, benign and dapp workloads continue running untouched."""
        registry = get_worker_registry()
        registry.clear()

        # Isolate synthetic_c2_client (PID 4096)
        handler = ProcessIsolationHandler(registry=registry)
        registry.register_worker("synthetic_c2_client", 4096)
        action = MitigationAction(
            mitigation_type=MitigationType.PROCESS_ISOLATION,
            target_layer="process",
            target_resource="synthetic_c2_client",
            parameters={"process_name": "synthetic_c2_client", "pid": 4096},
            verification_strategy="Check registry state and suppression",
        )
        assert handler.execute(action) is True
        assert registry.is_isolated("synthetic_c2_client", 4096) is True

        generator = ControlledGenerator(repo_root=tmp_path)

        # 1. Benign workload (Scenario A) runs completely unaffected
        res_a = generator._execute_benign_workload("run-audit-benign")
        assert res_a["status"] == "SUCCESS"
        assert res_a["events_emitted"] == 3

        # 2. Legitimate DApp workload (Scenario C) runs completely unaffected
        res_c = generator._execute_dapp_workload("run-audit-dapp")
        assert res_c["status"] == "SUCCESS"
        assert res_c["events_emitted"] == 3

        # 3. Isolated C2 workload is suppressed
        res_b = generator._execute_c2_workload("run-audit-c2")
        assert res_b["status"] == "SUPPRESSED"
        assert res_b["events_emitted"] == 0

        # Un-isolate and clear
        assert handler.rollback(action) is True
        registry.clear()

    def test_no_duplicate_workers_during_isolation_and_recovery(self):
        """Worker registry maintains exactly one record per worker key across multiple cycles."""
        registry = ScenarioWorkerRegistry()
        registry.clear()

        # Step 1: Initial registration
        k1 = registry.register_worker("synthetic_c2_client", 4096)
        assert len(registry._workers) == 1

        # Step 2: Isolation
        assert registry.isolate_worker("synthetic_c2_client", 4096) is True
        assert len(registry._workers) == 1
        assert registry.is_isolated("synthetic_c2_client", 4096) is True

        # Step 3: Re-registration attempt while isolated preserves isolation and avoids duplicates
        k2 = registry.register_worker("synthetic_c2_client", 4096)
        assert k1 == k2
        assert len(registry._workers) == 1
        assert registry.is_isolated("synthetic_c2_client", 4096) is True

        # Step 4: Recovery via rollback restores ACTIVE and keeps exactly 1 entry
        assert registry.rollback_worker("synthetic_c2_client", 4096) is True
        assert len(registry._workers) == 1
        assert registry.is_isolated("synthetic_c2_client", 4096) is False

    def test_unexecuted_or_incomplete_isolation_cannot_verify(self):
        """Unexecuted or incomplete isolation returns False on verify and sets FAILED."""
        registry = ScenarioWorkerRegistry()
        handler = ProcessIsolationHandler(registry=registry)

        # Worker never registered or isolated
        action = MitigationAction(
            mitigation_type=MitigationType.PROCESS_ISOLATION,
            target_layer="process",
            target_resource="unregistered_worker",
            parameters={"process_name": "unregistered_worker", "pid": 9999},
            verification_strategy="Check registry state",
        )

        # Calling verify() without successful execution must fail
        assert handler.verify(action) is False
        assert action.status == MitigationStatus.FAILED
        assert action.status != MitigationStatus.VERIFIED


@pytest.mark.unit
class TestTruthfulMitigationStatusSemantics:
    """Tests confirming truthful status distinction: VERIFIED, PARTIALLY_VERIFIED, and UNVERIFIABLE."""

    def test_unattached_proxy_and_network_yields_partially_verified_plan(
        self,
        c2_detection_result: DetectionResult,
        tmp_path: Path,
    ):
        """When proxy and network targets are unattached, plan reports PARTIALLY_VERIFIED honestly."""
        registry = ScenarioWorkerRegistry()
        registry.register_worker("synthetic_c2_client", 4096)

        policy_engine = DefensivePolicyEngine()
        plan = policy_engine.create_defense_plan(c2_detection_result)

        # Default executor without proxy and without local HTTP server
        executor = DefenseExecutor(
            handlers={
                MitigationType.EVIDENCE_PRESERVATION: EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence")),
                MitigationType.RPC_FILTER: RpcFilterHandler(proxy=None),  # Unattached
                MitigationType.NETWORK_CONTAINMENT: NetworkContainmentHandler(target_server=None),  # Unattached
                MitigationType.PROCESS_ISOLATION: ProcessIsolationHandler(registry=registry),
            }
        )

        record = executor.execute_plan(plan)

        # Plan status MUST be PARTIALLY_VERIFIED because 2 are VERIFIED and 2 are UNVERIFIABLE
        assert record.plan.status == DefensePlanStatus.PARTIALLY_VERIFIED
        assert record.actions_executed == 4
        assert record.actions_verified == 2
        assert record.actions_unverifiable == 2
        assert record.actions_failed == 0

        # Inspect individual action statuses
        evidence_act = next(a for a in plan.actions if a.mitigation_type == MitigationType.EVIDENCE_PRESERVATION)
        process_act = next(a for a in plan.actions if a.mitigation_type == MitigationType.PROCESS_ISOLATION)
        rpc_act = next(a for a in plan.actions if a.mitigation_type == MitigationType.RPC_FILTER)
        net_act = next(a for a in plan.actions if a.mitigation_type == MitigationType.NETWORK_CONTAINMENT)

        assert evidence_act.status == MitigationStatus.VERIFIED
        assert process_act.status == MitigationStatus.VERIFIED
        assert rpc_act.status == MitigationStatus.UNVERIFIABLE
        assert "Independent verification mechanism not attached" in rpc_act.verification_details
        assert net_act.status == MitigationStatus.UNVERIFIABLE
        assert "Independent verification mechanism not attached" in net_act.verification_details

    def test_fully_attached_harness_yields_verified_plan(
        self,
        c2_detection_result: DetectionResult,
        tmp_path: Path,
    ):
        """When all harnesses are attached, plan reports VERIFIED."""
        registry = ScenarioWorkerRegistry()
        registry.register_worker("synthetic_c2_client", 4096)
        proxy = RpcProxy()

        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            executor = DefenseExecutor(
                handlers={
                    MitigationType.EVIDENCE_PRESERVATION: EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence")),
                    MitigationType.RPC_FILTER: RpcFilterHandler(proxy=proxy),
                    MitigationType.NETWORK_CONTAINMENT: NetworkContainmentHandler(target_server=target_srv),
                    MitigationType.PROCESS_ISOLATION: ProcessIsolationHandler(registry=registry),
                }
            )

            policy_engine = DefensivePolicyEngine()
            plan = policy_engine.create_defense_plan(c2_detection_result)
            record = executor.execute_plan(plan)

            assert record.plan.status == DefensePlanStatus.VERIFIED
            assert record.actions_verified == 4
            assert record.actions_unverifiable == 0
            assert record.actions_failed == 0

    def test_partially_verified_plan_has_verified_false_in_record(
        self,
        c2_detection_result: DetectionResult,
        tmp_path: Path,
    ):
        """Partially verified defense plan strictly sets verified=False in summary record."""
        registry = ScenarioWorkerRegistry()
        registry.register_worker("synthetic_c2_client", 4096)

        policy_engine = DefensivePolicyEngine()
        plan = policy_engine.create_defense_plan(c2_detection_result)

        executor = DefenseExecutor(
            handlers={
                MitigationType.EVIDENCE_PRESERVATION: EvidenceSnapshotHandler(output_dir=str(tmp_path / "evidence")),
                MitigationType.RPC_FILTER: RpcFilterHandler(proxy=None),
                MitigationType.NETWORK_CONTAINMENT: NetworkContainmentHandler(target_server=None),
                MitigationType.PROCESS_ISOLATION: ProcessIsolationHandler(registry=registry),
            }
        )

        record = executor.execute_plan(plan)
        mitigation_status = record.plan.status.value.upper()

        mitigation_entry = {
            "mitigation_id": "MIT-test-001",
            "status": mitigation_status,
            "actions_executed": [
                a.mitigation_type.value
                for a in record.plan.actions
                if a.status in (MitigationStatus.EXECUTED, MitigationStatus.VERIFIED)
            ],
            "verified": (mitigation_status == "VERIFIED"),
        }

        assert mitigation_entry["status"] == "PARTIALLY_VERIFIED"
        assert mitigation_entry["verified"] is False
        assert len(mitigation_entry["actions_executed"]) == 2


