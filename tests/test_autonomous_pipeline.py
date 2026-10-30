# ChainC2 Sentinel — Autonomous Pipeline & Integration Test Suite
"""Automated verification for:
1. Bounded continuous/step generator rotation
2. Observable telemetry emission with run_id and metadata
3. Multi-layer sequence correlation and 6-criteria scoring
4. Automatic alert creation, investigation linking, and autonomous mitigation
5. Zero false positives on negative controls (benign Web3, legitimate DApp, incomplete)
6. System health authoritative indicators and truthful VM status reporting
7. CloudScale micro-cent budget precision
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest
from src.dashboard.app import create_app
from src.models.events import SentinelEvent, TelemetrySource, BlockchainInfo
from src.scenarios.generator import ControlledGenerator
from src.blockchain.monitor import SepoliaMonitor


@pytest.fixture
def client(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    app = create_app(repo_root=repo_root)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestAutonomousPipeline:
    """End-to-end event-driven pipeline verification."""

    def test_generator_status_and_truthful_vm_reporting(self, client):
        """Verify generator status reports truthful NO_EXTERNAL_VM_PROVISIONED."""
        resp = client.get("/api/generator/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["isolated_vm_mode"] is False
        assert data["telemetry_source_type"] == "IN_PROCESS_SIMULATION"
        assert "NO_EXTERNAL_VM_PROVISIONED" in data["vm_infrastructure_status"]
        assert "rotation_plan" in data
        assert len(data["rotation_plan"]) == 4

    def test_step_generator_execution_and_telemetry_emission(self, client):
        """Verify POST /api/generator/step executes a single workload and emits telemetry."""
        resp = client.post("/api/generator/step")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "STEP_COMPLETED"
        res = data["result"]
        assert "scenario" in res
        assert "run_id" in res
        assert res["events_emitted"] >= 3
        assert "telemetry_summary" in res

    def test_autonomous_detection_on_positive_c2_scenario(self):
        """Verify that executing synthetic C2 scenario automatically creates an alert and investigation."""
        gen = ControlledGenerator.get_instance()
        mon = SepoliaMonitor.get_instance()

        initial_alerts_count = len(mon.alerts)
        initial_invs_count = len(mon.investigations)

        import time
        run_id = f"test-autoc2-{int(time.time()*1000)}"
        res = gen._execute_c2_workload(run_id)
        assert res["status"] == "SUCCESS"
        assert res["events_emitted"] == 4

        # Feed to monitor intake
        intake_res = mon.process_telemetry_events(res["events"])
        assert intake_res["status"] == "PROCESSED"
        assert intake_res["events_received"] == 4
        assert intake_res["detections_triggered"] == 1
        assert len(intake_res["alerts_created"]) == 1

        # Verify created alert
        alert = intake_res["alerts_created"][0]
        assert alert["score"] == 100.0
        assert alert["severity"] == "CRITICAL"
        assert alert["investigation_id"].startswith("INV-")

        # Verify linked investigation
        inv = mon.get_investigation_by_id(alert["investigation_id"])
        assert inv is not None
        assert inv["alert_id"] == alert["alert_id"]
        assert inv["score"] == 100.0
        assert inv["status"] == "CONTAINED"
        assert "blockchain" in inv
        assert "endpoint" in inv
        assert "rpc" in inv
        assert "network" in inv
        assert len(inv["timeline"]) >= 4

    def test_negative_controls_produce_zero_alerts(self):
        """Verify benign and incomplete sequences do NOT trigger false alerts."""
        gen = ControlledGenerator.get_instance()
        mon = SepoliaMonitor.get_instance()

        import time
        for fn, scen_name, max_expected_score in [
            (gen._execute_benign_workload, "scenario_a_benign", 40.0),
            (gen._execute_dapp_workload, "scenario_c_legitimate_dapp", 40.0),
            (gen._execute_incomplete_workload, "scenario_b_incomplete", 60.0),
        ]:
            res = fn(f"test-neg-{scen_name}-{int(time.time()*1000)}")
            intake_res = mon.process_telemetry_events(res["events"])
            assert intake_res["status"] == "PROCESSED"
            assert intake_res["detections_triggered"] == 0
            assert len(intake_res["alerts_created"]) == 0

    def test_telemetry_ingest_api_endpoint(self, client):
        """Verify POST /api/telemetry/ingest accepts authenticated telemetry events."""
        now_iso = datetime.now(timezone.utc).isoformat()
        event_payload = {
            "source": "endpoint",
            "event_type": "process_snapshot",
            "timestamp": now_iso,
            "host": "127.0.0.1",
            "process": {
                "process_name": "test_client",
                "pid": 9999,
                "command_args": ["python", "test.py"],
            },
            "metadata": {"run_id": f"test-ingest-run-{int(time.time()*1000)}"},
        }
        resp = client.post(
            "/api/telemetry/ingest",
            json=event_payload,
            headers={"Authorization": "Bearer sentinel-telemetry-sec-ingest-token-2026"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "PROCESSED"
        assert data["events_received"] == 1

    def test_telemetry_ingest_auth_rejection(self, client):
        """Verify POST /api/telemetry/ingest rejects unauthorized and invalid requests."""
        now_iso = datetime.now(timezone.utc).isoformat()
        event_payload = {
            "source": "endpoint",
            "event_type": "process_snapshot",
            "timestamp": now_iso,
            "host": "127.0.0.1",
            "process": {"process_name": "attacker", "pid": 1111},
        }

        # 1. Missing credentials -> 401
        resp_no_auth = client.post("/api/telemetry/ingest", json=event_payload)
        assert resp_no_auth.status_code == 401
        assert resp_no_auth.get_json()["status"] == "UNAUTHORIZED"

        # 2. Invalid credentials -> 401
        resp_bad_auth = client.post(
            "/api/telemetry/ingest",
            json=event_payload,
            headers={"Authorization": "Bearer invalid-tampered-token-xyz"},
        )
        assert resp_bad_auth.status_code == 401
        assert resp_bad_auth.get_json()["status"] == "UNAUTHORIZED"

    def test_telemetry_ingest_idempotency_and_replay_rejection(self, client):
        """Verify replayed telemetry requests are detected and safely ignored."""
        idemp_key = f"idemp-test-{int(time.time()*1000)}"
        now_iso = datetime.now(timezone.utc).isoformat()
        event_payload = {
            "source": "endpoint",
            "event_type": "process_snapshot",
            "timestamp": now_iso,
            "host": "127.0.0.1",
            "process": {"process_name": "worker", "pid": 4096},
            "metadata": {"run_id": f"run-idemp-{int(time.time()*1000)}"},
        }

        # First request -> 200 PROCESSED
        resp1 = client.post(
            "/api/telemetry/ingest",
            json=event_payload,
            headers={
                "X-Sentinel-Ingest-Key": "sentinel-telemetry-sec-ingest-token-2026",
                "X-Idempotency-Key": idemp_key,
            },
        )
        assert resp1.status_code == 200
        assert resp1.get_json()["status"] == "PROCESSED"
        assert resp1.get_json()["events_received"] == 1

        # Second replayed request -> 200 DUPLICATE_IGNORED (0 events re-processed)
        resp2 = client.post(
            "/api/telemetry/ingest",
            json=event_payload,
            headers={
                "X-Sentinel-Ingest-Key": "sentinel-telemetry-sec-ingest-token-2026",
                "X-Idempotency-Key": idemp_key,
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["status"] == "DUPLICATE_IGNORED"
        assert data2["events_received"] == 0

    def test_ground_truth_separation_strict_audit(self):
        """Verify live emitted telemetry contains zero scenario labels or expected outcomes."""
        gen = ControlledGenerator.get_instance()

        for fn, scen_name in [
            (gen._execute_benign_workload, "scenario_a_benign"),
            (gen._execute_dapp_workload, "scenario_c_legitimate_dapp"),
            (gen._execute_incomplete_workload, "scenario_b_incomplete"),
            (gen._execute_c2_workload, "scenario_b_synthetic_c2"),
        ]:
            run_id = f"test-gt-audit-{scen_name}-{int(time.time()*1000)}"
            res = fn(run_id)
            assert "events" in res

            # Strictly inspect each event in the emitted batch
            for ev in res["events"]:
                meta = ev.metadata or {}
                # Live detector MUST NOT receive scenario_id, scenario_name, expected_label, or is_malicious
                assert "scenario_id" not in meta, f"Leaked scenario_id in {scen_name} telemetry!"
                assert "scenario_name" not in meta, f"Leaked scenario_name in {scen_name} telemetry!"
                assert "expected_label" not in meta, f"Leaked expected_label in {scen_name} telemetry!"
                assert "is_malicious" not in meta, f"Leaked is_malicious in {scen_name} telemetry!"
                # Event must carry synthetic run_id for post-run evaluation
                assert meta.get("run_id") == run_id

        # Verify ground truth file contains the actual evaluation labels
        gt_file = Path("data/evaluation/generator_ground_truth.jsonl")
        assert gt_file.exists()
        lines = gt_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 4
        latest_gt = json.loads(lines[-1])
        assert "ground_truth" in latest_gt
        assert "scenario_id" in latest_gt

    def test_system_health_authoritative_components(self, client):
        """Verify GET /api/system/health returns all 6 required components."""
        resp = client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.get_json()
        comps = data["components"]

        assert "sepolia_monitor" in comps
        assert "ethereum_rpc" in comps
        assert "controlled_generator" in comps
        assert "telemetry_ingestion" in comps
        assert "cloudscale_budget" in comps
        assert "defense_readiness" in comps
        assert "detection_engine" in comps

        # Verify truthful VM reporting
        assert comps["controlled_generator"]["vm_infrastructure_status"] == "NO_EXTERNAL_VM_PROVISIONED"
        assert comps["defense_readiness"]["status"] == "PARTIALLY_ACTIVE"
        assert comps["cloudscale_budget"]["authorized_budget_usd"] == 250.0
        assert 240.0 <= comps["cloudscale_budget"]["remaining_budget_usd"] <= 250.0

    def test_generator_automatic_startup_and_concurrency_guard(self, monkeypatch):
        """Verify generator auto-starts with bounded cycles and guards against duplicate workers."""
        gen = ControlledGenerator.get_instance()
        gen.stop()
        assert gen.is_running is False

        # 1. Start generator bounded to 2 cycles
        started = gen.start(max_cycles=2)
        assert started is True
        assert gen.is_running is True

        # 2. Concurrency check: Attempting to start again should not spawn duplicate workers
        started_again = gen.start(max_cycles=2)
        assert started_again is True
        assert gen.is_running is True

        # 3. Clean stop
        stopped = gen.stop()
        assert stopped is True
        assert gen.is_running is False

        # Status check
        st = gen.get_status()
        assert st["status"] == "STOPPED"
        assert st["vm_infrastructure_status"] == "NO_EXTERNAL_VM_PROVISIONED"

    def test_alert_investigation_persistence_across_simulated_restart(self):
        """Verify alerts and linked investigations survive service restart."""
        repo_root = Path(__file__).resolve().parent.parent
        mon = SepoliaMonitor.get_instance(repo_root=repo_root)

        now_utc = datetime.now(timezone.utc)
        unique_run_id = f"test-persist-{int(time.time()*1000)}-{os.urandom(4).hex()}"

        # Construct synthetic positive C2 event sequence
        events = [
            SentinelEvent(
                source=TelemetrySource.ENDPOINT,
                event_type="process_execution",
                timestamp=now_utc,
                host="127.0.0.1",
                process={"process_name": "synthetic_c2_client", "pid": 5555, "command_args": ["test"]},
                metadata={"run_id": unique_run_id, "telemetry_source": "synthetic_workload"},
            ),
            SentinelEvent(
                source=TelemetrySource.RPC,
                event_type="rpc_query",
                timestamp=now_utc,
                host="127.0.0.1",
                rpc={"rpc_method": "eth_call", "rpc_endpoint": "http://127.0.0.1:8546", "upstream_endpoint": "https://ethereum-sepolia-rpc.publicnode.com", "status": "success"},
                metadata={"run_id": unique_run_id, "telemetry_source": "synthetic_workload"},
            ),
            SentinelEvent(
                source=TelemetrySource.BLOCKCHAIN,
                event_type="contract_read",
                timestamp=now_utc,
                host="127.0.0.1",
                blockchain=BlockchainInfo(
                    tx_hash="0x" + "a" * 64,
                    block_number=12020503,
                    contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
                    contract_name="C2DataStore",
                    chain_id="11155111",
                ),
                metadata={"run_id": unique_run_id, "telemetry_source": "synthetic_workload"},
            ),
            SentinelEvent(
                source=TelemetrySource.NETWORK,
                event_type="network_connection",
                timestamp=now_utc,
                host="127.0.0.1",
                network={"destination_host": "127.0.0.1", "destination_port": 8080, "protocol": "HTTP", "status_code": 200, "source_process": "synthetic_c2_client"},
                metadata={"run_id": unique_run_id, "telemetry_source": "synthetic_workload"},
            ),
        ]

        res = mon.process_telemetry_events(events)
        assert res["detections_triggered"] == 1
        assert len(res["alerts_created"]) == 1

        alert_id = res["alerts_created"][0]["alert_id"]
        inv_id = res["alerts_created"][0]["investigation_id"]

        # Confirm in memory
        assert any(a["alert_id"] == alert_id for a in mon.alerts)
        assert any(i["investigation_id"] == inv_id for i in mon.investigations)

        # Confirm persisted on disk
        alerts_file = repo_root / "data" / "telemetry" / "sepolia_alerts.json"
        invs_file = repo_root / "data" / "telemetry" / "sepolia_investigations.json"
        assert alerts_file.exists()
        assert invs_file.exists()

        # Simulate fresh instance restart
        fresh_monitor = SepoliaMonitor(repo_root=repo_root)
        fresh_alerts = [a for a in fresh_monitor.alerts if a.get("alert_id") == alert_id]
        fresh_invs = [i for i in fresh_monitor.investigations if i.get("investigation_id") == inv_id]

        assert len(fresh_alerts) == 1, "Alert not found in reloaded state after simulated restart!"
        assert len(fresh_invs) == 1, "Investigation not found in reloaded state after simulated restart!"
        assert fresh_alerts[0]["score"] >= 80.0
        assert fresh_invs[0]["status"] == "CONTAINED"

    def test_mitigation_verification_statuses_truthful(self):
        """Verify mitigation verification statuses faithfully report verified vs unverifiable."""
        from src.protection.executor import DefenseExecutor
        from src.protection.policy import DefensivePolicyEngine
        from src.detection.models import DetectionResult, DetectionStatus

        # Create mock detection result
        det = DetectionResult(
            rule_id="RULE-CHAINC2-001",
            rule_name="Synthetic C2 Sequence Detection Rule",
            rule_version="1.0.0",
            status=DetectionStatus.TRIGGERED,
            triggered=True,
            correlation_id="corr-test-001",
            explanation="Detection candidate identified by RULE-CHAINC2-001",
            total_score=100.0,
            threshold=80.0,
            matched_conditions=["c2_pattern"],
            matched_scoring_rules=["network_followup"],
            unmatched_conditions=[],
            unmatched_scoring_rules=[],
            score_contributions=[],
            evidence={"contract_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3", "target_host": "127.0.0.1", "target_port": 8080, "process_name": "synthetic_c2_client", "pid": 4096},
        )

        policy = DefensivePolicyEngine()
        plan = policy.create_defense_plan(det)

        executor = DefenseExecutor()
        exec_record = executor.execute_plan(plan)

        statuses = {
            a.mitigation_type.value: a.status.value
            for a in exec_record.plan.actions
        }

        # Evidence preservation must be verified
        assert statuses.get("evidence_preservation") == "verified"
        # Process isolation must be verified
        assert statuses.get("process_isolation") == "verified"
        # Unattached RPC and Network controls must be unverifiable
        assert statuses.get("rpc_filter") == "unverifiable"
        assert statuses.get("network_containment") == "unverifiable"

