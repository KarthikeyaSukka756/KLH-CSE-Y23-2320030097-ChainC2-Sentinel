# ChainC2 Sentinel — Investigation Defects & Edge Cases Verification Suite
"""Regression and verification tests covering:
1. Synthetic transaction anchoring defect repair (public Sepolia tx is not mutated).
2. Mitigation lifecycle and truthful verification (unattached handler reports UNVERIFIABLE).
3. Attached verification harness achieves VERIFIED.
4. Evidence bundle schema 2.1.0 and simulation provenance.
5. Telemetry, alert, experiment, and mitigation persistence across monitor restarts.
6. Sepolia transaction receipt independent audit and mismatch contradiction detection.
7. /openapi.json and /api/experiments HTTP 200 endpoint contracts.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.blockchain.monitor import SepoliaMonitor
from src.blockchain.rpc_client import SEPOLIA_CHAIN_ID, LocalRpcClient
from src.dashboard.app import create_app
from src.protection.executor import DefenseExecutor
from src.protection.handlers.evidence_handler import EvidenceSnapshotHandler
from src.protection.handlers.network_handler import NetworkContainmentHandler
from src.protection.handlers.process_handler import ProcessIsolationHandler
from src.protection.handlers.rpc_handler import RpcFilterHandler
from src.protection.models import (
    DefensePlan,
    DefensePlanStatus,
    MitigationAction,
    MitigationStatus,
    MitigationType,
)
from src.protection.process_registry import get_worker_registry


class TestInvestigationDefectsRepair(unittest.TestCase):
    """Test suite covering the 8 audit findings and verified engineering fixes."""

    def setUp(self) -> None:
        self.mock_rpc = MagicMock(spec=LocalRpcClient)
        self.mock_rpc.network = "sepolia"
        self.mock_rpc.rpc_url = "https://ethereum-sepolia-rpc.publicnode.com"
        self.mock_rpc.get_chain_id.return_value = SEPOLIA_CHAIN_ID
        self.mock_rpc.eth_block_number.return_value = 12020300

        self.monitor = SepoliaMonitor(rpc_client=self.mock_rpc)
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_public_sepolia_transaction_not_mutated_as_c2(self) -> None:
        """Defect 1 Repair: Public Sepolia transactions must never be falsely mutated as malicious C2."""
        public_tx = {
            "tx_hash": "0x83f0b7e2046901ed5bf3fd5e747d2a034416a83b4ee5f6b123b9e8c6a296dac7",
            "block_number": 12020227,
            "from_address": "0x511394b3c4314c99557faaa7faec93144a7f9b88",
            "to_address": "0x73798544e45c7eb3907cfaea412ff25a5874288b",
            "value_eth": 0.05,
            "classification": "Unclassified",
            "detection_status": "PENDING",
            "explorer_url": "https://sepolia.etherscan.io/tx/0x83f0b7e2046901ed5bf3fd5e747d2a034416a83b4ee5f6b123b9e8c6a296dac7",
        }
        self.monitor.observed_transactions = [public_tx]
        self.monitor._tx_hashes_seen = {public_tx["tx_hash"]}

        # Run controlled positive experiment
        res = self.monitor.execute_controlled_experiment("positive_c2")

        # The experiment itself detects synthetic C2
        self.assertEqual(res["ground_truth"], "POSITIVE")
        self.assertEqual(res["classification"], "TRUE_POSITIVE")

        # CRITICAL ASSERTION: The observed public transaction must NOT be mutated!
        self.assertEqual(public_tx["classification"], "Unclassified")
        self.assertEqual(public_tx["detection_status"], "PENDING")
        self.assertNotIn("is_positive_control", public_tx)

        # The experiment summary records ambient anchor reference and synthetic distinction
        self.assertEqual(res["ambient_reference_tx_hash"], public_tx["tx_hash"])
        self.assertEqual(res["tx_role"], "AMBIENT_LIVENESS_ANCHOR")
        self.assertEqual(res["receipt_verification_status"], "UNVERIFIED_CONTRACT_MAPPING")

    def test_mitigation_verification_unattached_handler_reports_unverifiable(self) -> None:
        """Defect 2 Repair: Handlers without attached targets report UNVERIFIABLE, not VERIFIED."""
        plan = DefensePlan(
            detection_correlation_id="corr-test-123",
            rule_id="RULE-CHAINC2-001",
            evidence_summary="Test detection trigger",
            actions=[
                MitigationAction(
                    mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
                    target_layer="evidence",
                    target_resource="corr-test-123",
                    verification_strategy="File existence check",
                ),
                MitigationAction(
                    mitigation_type=MitigationType.RPC_FILTER,
                    target_layer="rpc",
                    target_resource="0x5FbDB2315678afecb367f032d93F642f64180aa3",
                    verification_strategy="RPC proxy filter check",
                ),
                MitigationAction(
                    mitigation_type=MitigationType.NETWORK_CONTAINMENT,
                    target_layer="network",
                    target_resource="127.0.0.1:8080",
                    parameters={"destination_host": "127.0.0.1"},
                    verification_strategy="Target server containment check",
                ),
            ],
        )

        executor = DefenseExecutor()  # Default handlers (proxy=None, target_server=None)
        rec = executor.execute_plan(plan)

        # Evidence preservation is verified on disk
        self.assertEqual(plan.actions[0].status, MitigationStatus.VERIFIED)

        # RPC filter and Network containment are truthfully UNVERIFIABLE without target harnesses
        self.assertEqual(plan.actions[1].status, MitigationStatus.UNVERIFIABLE)
        self.assertIn("Independent verification mechanism not attached", plan.actions[1].verification_details or "")

        self.assertEqual(plan.actions[2].status, MitigationStatus.UNVERIFIABLE)
        self.assertIn("Independent verification mechanism not attached", plan.actions[2].verification_details or "")

        # Plan status must be PARTIALLY_VERIFIED, NOT falsely VERIFIED!
        self.assertEqual(plan.status, DefensePlanStatus.PARTIALLY_VERIFIED)
        self.assertEqual(rec.actions_verified, 1)
        self.assertEqual(rec.actions_unverifiable, 2)
        self.assertEqual(rec.actions_failed, 0)
        self.assertTrue(rec.overall_success)

    def test_mitigation_verification_attached_harness_achieves_verified(self) -> None:
        """Defect 2 Repair: Attached, effective harnesses achieve full VERIFIED status."""
        mock_proxy = MagicMock()
        mock_proxy.is_contract_filtered.return_value = True

        mock_target = MagicMock()
        mock_target.is_containment_active.return_value = True

        plan = DefensePlan(
            detection_correlation_id="corr-test-456",
            rule_id="RULE-CHAINC2-001",
            evidence_summary="Test detection trigger",
            actions=[
                MitigationAction(
                    mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
                    target_layer="evidence",
                    target_resource="corr-test-456",
                    verification_strategy="File existence check",
                ),
                MitigationAction(
                    mitigation_type=MitigationType.RPC_FILTER,
                    target_layer="rpc",
                    target_resource="0x5FbDB2315678afecb367f032d93F642f64180aa3",
                    verification_strategy="RPC proxy filter check",
                ),
                MitigationAction(
                    mitigation_type=MitigationType.NETWORK_CONTAINMENT,
                    target_layer="network",
                    target_resource="127.0.0.1:8080",
                    parameters={"destination_host": "127.0.0.1"},
                    verification_strategy="Target server containment check",
                ),
            ],
        )

        handlers = {
            MitigationType.EVIDENCE_PRESERVATION: EvidenceSnapshotHandler(),
            MitigationType.RPC_FILTER: RpcFilterHandler(proxy=mock_proxy),
            MitigationType.NETWORK_CONTAINMENT: NetworkContainmentHandler(target_server=mock_target),
            MitigationType.PROCESS_ISOLATION: ProcessIsolationHandler(),
        }
        executor = DefenseExecutor(handlers=handlers)
        rec = executor.execute_plan(plan)

        self.assertEqual(plan.actions[0].status, MitigationStatus.VERIFIED)
        self.assertEqual(plan.actions[1].status, MitigationStatus.VERIFIED)
        self.assertEqual(plan.actions[2].status, MitigationStatus.VERIFIED)
        self.assertEqual(plan.status, DefensePlanStatus.VERIFIED)
        self.assertEqual(rec.actions_verified, 3)
        self.assertEqual(rec.actions_unverifiable, 0)
        self.assertEqual(rec.actions_failed, 0)

    def test_evidence_bundle_version_and_simulation_provenance(self) -> None:
        """Defect 4 Repair: Evidence snapshots contain schema version 2.1.0 and lab simulation declaration."""
        handler = EvidenceSnapshotHandler(output_dir="data/evidence")
        action = MitigationAction(
            mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
            target_layer="evidence",
            target_resource="corr-schema-test",
            parameters={"correlation_id": "corr-schema-test", "run_id": "run-test-schema"},
            verification_strategy="File existence check",
        )
        self.assertTrue(handler.execute(action))
        self.assertTrue(handler.verify(action))

        snapshot_path = Path(action.parameters["snapshot_path"])
        self.assertTrue(snapshot_path.exists())

        bundle = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(bundle.get("schema_version"), "2.1.0")
        self.assertEqual(bundle.get("provenance_type"), "SIMULATED_LABORATORY_EVENT")
        self.assertFalse(bundle.get("blockchain_receipt_verification", {}).get("verified"))
        self.assertIn("Sepolia contract unconfigured", bundle.get("blockchain_receipt_verification", {}).get("reason", ""))

    def test_state_persistence_across_monitor_instances(self) -> None:
        """Defect 3 Repair: Alerts, experiments, and mitigations persist across monitor reloads."""
        # Ensure fresh state
        self.monitor.execute_controlled_experiment("positive_c2")
        initial_alert_count = len(self.monitor.alerts)
        initial_exp_count = len(self.monitor.experiment_records)
        initial_mit_count = len(self.monitor.mitigation_records)

        self.assertGreater(initial_alert_count, 0)
        self.assertGreater(initial_exp_count, 0)
        self.assertGreater(initial_mit_count, 0)

        # Create a completely separate monitor instance pointing to the same repo
        new_monitor = SepoliaMonitor(rpc_client=self.mock_rpc, repo_root=self.monitor.repo_root)

        # Must reload previous persisted state from disk
        self.assertEqual(len(new_monitor.alerts), initial_alert_count)
        self.assertEqual(len(new_monitor.experiment_records), initial_exp_count)
        self.assertEqual(len(new_monitor.mitigation_records), initial_mit_count)

    def test_sepolia_transaction_receipt_contradiction_detection(self) -> None:
        """Independent On-Chain Audit: Detect recipient mismatch between tx receipt and claimed contract."""
        # Mock receipt on Sepolia where recipient is 0x73798544... NOT 0x5FbDB...
        self.mock_rpc.get_transaction_receipt.return_value = {
            "transactionHash": "0x83f0b7e2046901ed5bf3fd5e747d2a034416a83b4ee5f6b123b9e8c6a296dac7",
            "blockNumber": "0xb76723",
            "from": "0x511394b3c4314c99557faaa7faec93144a7f9b88",
            "to": "0x73798544e45c7eb3907cfaea412ff25a5874288b",
            "status": "0x1",
        }

        # Query verification against C2DataStore target
        res = self.monitor.verify_transaction_on_sepolia(
            tx_hash="0x83f0b7e2046901ed5bf3fd5e747d2a034416a83b4ee5f6b123b9e8c6a296dac7",
            expected_contract="0x5FbDB2315678afecb367f032d93F642f64180aa3",
        )

        self.assertTrue(res["exists_on_sepolia"])
        self.assertFalse(res["contract_matches"])
        self.assertEqual(res["status"], "CONTRADICTED_CONTRACT_MISMATCH")
        self.assertIn("does not match expected target", res["details"])

    def test_openapi_json_returns_http_200(self) -> None:
        """Defect 7 Repair: /openapi.json returns HTTP 200 with OpenAPI 3.0.3 specification."""
        resp = self.client.get("/openapi.json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "application/json")
        data = resp.get_json()
        self.assertEqual(data.get("openapi"), "3.0.3")
        self.assertEqual(data.get("info", {}).get("title"), "ChainC2 Sentinel REST API")
        self.assertIn("/api/sepolia/status", data.get("paths", {}))
        self.assertIn("/api/experiments", data.get("paths", {}))
        self.assertIn("/api/sepolia/verify-tx/{tx_hash}", data.get("paths", {}))

    def test_api_experiments_alias_returns_http_200(self) -> None:
        """Defect 6 Repair: GET /api/experiments returns HTTP 200 JSON with experiment runs."""
        resp = self.client.get("/api/experiments")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "application/json")
        data = resp.get_json()
        self.assertIn("runs", data)
        self.assertIn("total_returned", data)
        self.assertIsInstance(data["runs"], list)

    def test_api_sepolia_verify_tx_endpoint(self) -> None:
        """Verify GET /api/sepolia/verify-tx/<tx_hash> endpoint."""
        expected_result = {
            "tx_hash": "0x83f0b7e2046901ed5bf3fd5e747d2a034416a83b4ee5f6b123b9e8c6a296dac7",
            "exists_on_sepolia": True,
            "block_number": 12020259,
            "actual_to": "0x73798544e45c7eb3907cfaea412ff25a5874288b",
            "expected_contract": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
            "contract_matches": False,
            "status": "CONTRADICTED_CONTRACT_MISMATCH",
            "details": "Receipt exists on Sepolia block 12020259, but recipient does not match expected target.",
        }
        with patch("src.dashboard.services.sepolia_service.SepoliaService.verify_transaction", return_value=expected_result):
            resp = self.client.get(
                "/api/sepolia/verify-tx/0x83f0b7e2046901ed5bf3fd5e747d2a034416a83b4ee5f6b123b9e8c6a296dac7"
                "?expected_contract=0x5FbDB2315678afecb367f032d93F642f64180aa3"
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["exists_on_sepolia"])
            self.assertFalse(data["contract_matches"])
            self.assertEqual(data["status"], "CONTRADICTED_CONTRACT_MISMATCH")

    def test_bounded_catch_up_and_lag_reduction(self) -> None:
        """Verify bounded catch-up and lag reduction with fast-forward for large gaps."""
        self.mock_rpc.eth_block_number.return_value = 12020500
        self.monitor.latest_block = 12020500
        self.monitor.last_ingested_block = 12014150  # 6350 blocks lag
        self.mock_rpc.eth_get_block_by_number.return_value = {
            "transactions": [],
            "timestamp": "0x67200000",
        }

        # Catch up
        res = self.monitor.catch_up(max_blocks=5)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["sync_status"], "RECOVERED_WINDOW")
        self.assertLessEqual(res["current_lag_blocks"], 5)
        self.assertEqual(self.monitor.last_ingested_block, 12020500)

        # GET /api/sepolia/status reflects sync
        status_resp = self.client.get("/api/sepolia/status")
        self.assertEqual(status_resp.status_code, 200)
        s_data = status_resp.get_json()
        self.assertIn("sync_status", s_data)
        self.assertIn("monitoring_lag_blocks", s_data)

    def test_telemetry_ingestion_endpoint(self) -> None:
        """Verify POST /api/telemetry/ingest accepts remote telemetry events."""
        events_file = Path("data/telemetry/events.jsonl")
        orig_content = events_file.read_bytes() if events_file.exists() else None

        try:
            event_payload = {
                "events": [
                    {
                        "event_id": "ev-test-endpoint-001",
                        "timestamp": "2026-10-29T20:00:00Z",
                        "source": "endpoint",
                        "event_type": "process_start",
                        "host": "127.0.0.1",
                        "process": {
                            "process_name": "synthetic_c2_client",
                            "pid": 5012,
                        },
                        "metadata": {"scenario_id": "scenario_b_synthetic_c2", "run_id": "run-ingest-test-1"},
                    },
                    {
                        "event_id": "ev-test-rpc-001",
                        "timestamp": "2026-10-29T20:00:01Z",
                        "source": "rpc",
                        "event_type": "eth_call",
                        "host": "127.0.0.1",
                        "rpc": {
                            "rpc_endpoint": "http://127.0.0.1:8546",
                            "upstream_endpoint": "https://ethereum-sepolia-rpc.publicnode.com",
                            "rpc_method": "eth_call",
                            "status": "success",
                        },
                        "metadata": {"scenario_id": "scenario_b_synthetic_c2", "run_id": "run-ingest-test-1"},
                    },
                    {
                        "event_id": "ev-test-bc-001",
                        "timestamp": "2026-10-29T20:00:02Z",
                        "source": "blockchain",
                        "event_type": "contract_read",
                        "host": "127.0.0.1",
                        "blockchain": {
                            "tx_hash": "0x1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
                            "block_number": 12020500,
                            "contract_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
                            "contract_name": "C2DataStore",
                            "chain_id": "11155111",
                            "network_name": "sepolia",
                        },
                        "metadata": {"scenario_id": "scenario_b_synthetic_c2", "run_id": "run-ingest-test-1"},
                    },
                    {
                        "event_id": "ev-test-net-001",
                        "timestamp": "2026-10-29T20:00:03Z",
                        "source": "network",
                        "event_type": "http_request",
                        "host": "127.0.0.1",
                        "network": {
                            "destination_host": "127.0.0.1",
                            "destination_port": 8080,
                            "protocol": "HTTP",
                            "request_type": "POST",
                            "status_code": 200,
                        },
                        "metadata": {"scenario_id": "scenario_b_synthetic_c2", "run_id": "run-ingest-test-1"},
                    },
                ]
            }
            resp = self.client.post(
                "/api/telemetry/ingest",
                json=event_payload,
                headers={"X-Sentinel-Ingest-Key": "sentinel-telemetry-sec-ingest-token-2026"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["status"], "PROCESSED")
            self.assertEqual(data["events_received"], 4)
            self.assertGreaterEqual(data["sequences_correlated"], 1)
        finally:
            if orig_content is not None:
                events_file.write_bytes(orig_content)

    def test_generator_status_and_step_endpoints(self) -> None:
        """Verify generator status disclosures and step execution."""
        events_file = Path("data/telemetry/events.jsonl")
        orig_content = events_file.read_bytes() if events_file.exists() else None

        try:
            status_resp = self.client.get("/api/generator/status")
            self.assertEqual(status_resp.status_code, 200)
            s_data = status_resp.get_json()
            self.assertIn("status", s_data)
            self.assertIn("prerequisites_status", s_data)
            self.assertIn("can_mutate_sepolia", s_data)
            self.assertEqual(s_data["vm_infrastructure_status"], "NO_EXTERNAL_VM_PROVISIONED")
            self.assertFalse(s_data["isolated_vm_mode"])

            # Verify bounded execution
            start_resp = self.client.post("/api/generator/start", json={"max_cycles": 1})
            self.assertIn(start_resp.status_code, [200, 403])

            step_resp = self.client.post("/api/generator/step")
            self.assertEqual(step_resp.status_code, 200)
            st_data = step_resp.get_json()
            self.assertEqual(st_data["status"], "STEP_COMPLETED")
            self.assertIn("result", st_data)
            self.assertIn("events_emitted", st_data["result"])
            self.assertIn("telemetry_summary", st_data["result"])
        finally:
            if orig_content is not None:
                events_file.write_bytes(orig_content)

    def test_explorer_url_construction_and_validation(self) -> None:
        """Verify Explorer URL is only constructed for valid Sepolia tx hashes."""
        # 1. Execute positive control experiment via client
        exec_resp = self.client.post("/api/sepolia/execute", json={"scenario": "positive_c2"})
        self.assertEqual(exec_resp.status_code, 200)

        # 2. Query investigations endpoint to ensure API returns valid URL
        invs_resp = self.client.get("/api/investigations")
        self.assertEqual(invs_resp.status_code, 200)
        invs_data = invs_resp.get_json()
        invs = invs_data.get("investigations", [])
        self.assertGreater(len(invs), 0)

        inv = invs[0]
        bc = inv.get("blockchain") or inv.get("transaction") or {}
        tx_hash = bc.get("tx_hash")

        if tx_hash and len(tx_hash) == 66 and tx_hash != "0x" + "0" * 64:
            self.assertIn("explorer_url", bc)
            self.assertEqual(bc["explorer_url"], f"https://sepolia.etherscan.io/tx/{tx_hash}")

    def test_investigation_blockchain_evidence_mapping_and_contradictions(self) -> None:
        """Verify investigation reflects truthful contract mapping and contradiction indicators."""
        invs = self.monitor.get_investigations(limit=5)
        self.assertGreater(len(invs), 0)

        for inv in invs:
            # Must contain both 'blockchain' and 'transaction'
            self.assertIn("blockchain", inv)
            self.assertIn("transaction", inv)
            bc = inv["blockchain"]

            # Must have receipt verification status
            self.assertIn("receipt_verification_status", bc)
            # Never convert unverified or contradiction into false verified on-chain
            if not bc.get("is_on_chain_verified"):
                self.assertNotEqual(bc.get("receipt_verification_status"), "VERIFIED_ON_CHAIN")

    def test_system_health_authoritative_connection_sync(self) -> None:
        """Verify /api/system/health provides synchronized connection state across components."""
        resp = self.client.get("/api/system/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        comps = data.get("components", {})

        self.assertIn("sepolia_monitor", comps)
        self.assertIn("ethereum_rpc", comps)
        self.assertIn("defense_readiness", comps)
        self.assertIn("detection_engine", comps)

        mon = comps["sepolia_monitor"]
        rpc = comps["ethereum_rpc"]

        # Ensure consistent connection state
        self.assertEqual(mon["is_connected"], rpc["is_connected"])
        self.assertEqual(mon["connected"], rpc["connected"])

    def test_defense_readiness_partial_enforcement(self) -> None:
        """Verify defense readiness truthfully reports partial enforcement rather than unconditional ready."""
        resp = self.client.get("/api/system/health")
        self.assertEqual(resp.status_code, 200)
        comps = resp.get_json().get("components", {})
        defense = comps.get("defense_readiness", {})

        self.assertEqual(defense.get("status"), "PARTIALLY_ACTIVE")
        self.assertEqual(defense.get("network_enforcement"), "UNVERIFIABLE")
        self.assertEqual(defense.get("local_enforcement"), "ACTIVE")

    def test_cloudscale_budget_consistency_precision(self) -> None:
        """Verify budget endpoint returns authoritative micro-consumption without roundoff truncation."""
        resp = self.client.get("/api/cloudscale/budget")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("authorized_budget_usd", data)
        self.assertIn("remaining_budget_usd", data)
        self.assertIn("consumed_cost_usd", data)

        # Authorized cap is $250.00
        self.assertEqual(data["authorized_budget_usd"], 250.0)
        # If consumed > 0, remaining must be less than 250.0
        if data["consumed_cost_usd"] > 0:
            self.assertLess(data["remaining_budget_usd"], 250.0)
            self.assertAlmostEqual(data["authorized_budget_usd"] - data["consumed_cost_usd"], data["remaining_budget_usd"], places=4)


if __name__ == "__main__":
    unittest.main()

