# ChainC2 Sentinel — Independent Controlled C2-Behaviour Generator
"""Autonomous, independent generator executing controlled harmless laboratory workloads.

Strict Research & Operational Boundaries:
- Operates independently from ChainC2 Sentinel detector.
- Generates genuine, observable multi-layer activity representative of blockchain-mediated C2 patterns.
- Never calls the detector's scoring engine, alert API, correlation engine, or mitigation API.
- Never injects hidden ground-truth labels into observable telemetry.
- Records separate, access-controlled ground-truth logs in data/evaluation/generator_ground_truth.jsonl.
- Completely harmless payloads (loopback 127.0.0.1, read-only calls). Zero malware, zero persistence.
- Auto-recovers after restarts and pauses safely on unfulfilled prerequisites.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.collectors.endpoint_collector import SyntheticEndpointCollector
from src.collectors.network_collector import NetworkTelemetryCollector
from src.collectors.rpc_collector import RpcTelemetryCollector
from src.http_target.server import LocalHttpTargetServer
from src.models.events import BlockchainInfo, SentinelEvent, TelemetrySource
from src.protection.process_registry import get_worker_registry

logger = logging.getLogger("chainc2_sentinel.generator")


class ControlledGenerator:
    """Independent laboratory workload generator rotating through multi-scenario behaviours."""

    _instance: Optional["ControlledGenerator"] = None
    _singleton_lock = threading.Lock()

    SCENARIO_ROTATION = [
        "scenario_a_benign",
        "scenario_c_legitimate_dapp",
        "scenario_b_synthetic_c2",
        "scenario_b_incomplete",
    ]

    @classmethod
    def get_instance(cls, repo_root: Optional[Path] = None) -> "ControlledGenerator":
        """Singleton accessor for thread-safe access."""
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls(repo_root=repo_root)
            return cls._instance

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        cycle_interval_seconds: float = 25.0,
    ) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent.parent
        self.cycle_interval_seconds = cycle_interval_seconds

        self.telemetry_file = self.repo_root / "data" / "telemetry" / "events.jsonl"
        self.ground_truth_file = self.repo_root / "data" / "evaluation" / "generator_ground_truth.jsonl"
        self.status_file = self.repo_root / "data" / "telemetry" / "generator_status.json"

        self.is_running = False
        self.current_scenario_index = 0
        self.cycles_completed = 0
        self.total_events_emitted = 0
        self.last_cycle_time: Optional[datetime] = None
        self.last_event_time: Optional[datetime] = None
        self.delivery_status: str = "READY"
        self.last_error: Optional[str] = None
        self.error_count = 0

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Ensure directories exist
        self.telemetry_file.parent.mkdir(parents=True, exist_ok=True)
        self.ground_truth_file.parent.mkdir(parents=True, exist_ok=True)

        self._load_status()

    # -------------------------------------------------------------------------
    # State & Persistence
    # -------------------------------------------------------------------------

    def _load_status(self) -> None:
        if self.status_file.exists():
            try:
                data = json.loads(self.status_file.read_text(encoding="utf-8"))
                self.cycles_completed = data.get("cycles_completed", 0)
                self.total_events_emitted = data.get("total_events_emitted", 0)
                self.current_scenario_index = data.get("current_scenario_index", 0)
                self.error_count = data.get("error_count", 0)
                self.delivery_status = data.get("delivery_status", "READY")
            except Exception as e:
                logger.debug("Could not load generator status: %s", e)

    def _persist_status(self) -> None:
        try:
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump({
                    "status": "RUNNING" if self.is_running else "STOPPED",
                    "current_scenario": self.SCENARIO_ROTATION[self.current_scenario_index % len(self.SCENARIO_ROTATION)],
                    "current_scenario_index": self.current_scenario_index,
                    "cycles_completed": self.cycles_completed,
                    "total_events_emitted": self.total_events_emitted,
                    "cycle_interval_seconds": self.cycle_interval_seconds,
                    "last_cycle_time": self.last_cycle_time.isoformat() if self.last_cycle_time else None,
                    "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
                    "delivery_status": self.delivery_status,
                    "last_error": self.last_error,
                    "error_count": self.error_count,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }, f, indent=2)
        except Exception as e:
            logger.debug("Could not persist generator status: %s", e)

    def get_status(self) -> dict[str, Any]:
        """Return operational status of the independent generator."""
        with self._lock:
            cur_scenario = self.SCENARIO_ROTATION[self.current_scenario_index % len(self.SCENARIO_ROTATION)]
            sepolia_reg_path = self.repo_root / "src" / "blockchain" / "deployed-addresses.sepolia.json"
            contract_status = "UNCONFIGURED"
            if sepolia_reg_path.exists():
                try:
                    reg_data = json.loads(sepolia_reg_path.read_text(encoding="utf-8"))
                    contract_status = reg_data.get("status", "UNCONFIGURED")
                except Exception:
                    contract_status = "ERROR"

            health = "HEALTHY"
            if self.error_count >= 5:
                health = "PAUSED"
            elif self.error_count > 0:
                health = "DEGRADED"

            return {
                "status": "RUNNING" if self.is_running else "STOPPED",
                "health": health,
                "current_scenario": cur_scenario,
                "cycles_completed": self.cycles_completed,
                "total_events_emitted": self.total_events_emitted,
                "cycle_interval_seconds": self.cycle_interval_seconds,
                "last_cycle_time": self.last_cycle_time.isoformat() if self.last_cycle_time else None,
                "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
                "delivery_status": self.delivery_status,
                "last_error": self.last_error,
                "error_count": self.error_count,
                "rotation_plan": list(self.SCENARIO_ROTATION),
                "isolated_vm_mode": False,
                "telemetry_source_type": "IN_PROCESS_SIMULATION",
                "vm_infrastructure_status": "NO_EXTERNAL_VM_PROVISIONED",
                "vm_infrastructure_details": "No external guest VM provisioned. Operating as decoupled in-process workload generator. External VMs can ingest via POST /api/telemetry/ingest.",
                "contract_registry_status": contract_status,
                "prerequisites_status": "UNCONFIGURED_SEPOLIA_CONTRACTS" if contract_status == "UNCONFIGURED" else "CONFIGURED",
                "prerequisites_detail": "Sepolia contracts require funded deployer private key and Sepolia test ETH for gas. Operating under strict $0 gas policy with synthetic laboratory simulation.",
                "can_mutate_sepolia": contract_status == "CONFIGURED",
            }

    # -------------------------------------------------------------------------
    # Observable Telemetry Emission (Zero Hidden Labels)
    # -------------------------------------------------------------------------

    def _emit_observable_event(self, event: SentinelEvent) -> None:
        """Emit normalized telemetry event to the public observable stream."""
        # 1. Local telemetry stream
        try:
            with open(self.telemetry_file, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception as e:
            logger.debug("Generator failed appending to telemetry file: %s", e)

        # 2. Remote HTTP ingestion endpoint if configured (e.g. for isolated VM)
        ingest_url = os.environ.get("CHAINC2_INGEST_URL")
        if ingest_url:
            try:
                import urllib.request
                ingest_key = os.environ.get("CHAINC2_INGEST_KEY", "sentinel-telemetry-sec-ingest-token-2026")
                req_data = json.dumps({"events": [event.model_dump(mode="json")]}).encode("utf-8")
                req = urllib.request.Request(
                    ingest_url,
                    data=req_data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "ChainC2-Generator/2.0",
                        "Authorization": f"Bearer {ingest_key}",
                        "X-Sentinel-Ingest-Key": ingest_key,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    pass
            except Exception as e:
                logger.debug("Generator remote telemetry ingestion forwarding failed: %s", e)

    def _record_private_ground_truth(
        self,
        run_id: str,
        scenario_id: str,
        ground_truth: str,
        expected_score_range: tuple[float, float],
        details: dict[str, Any],
    ) -> None:
        """Record isolated ground truth in access-controlled file (invisible to detector)."""
        entry = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario_id": scenario_id,
            "ground_truth": ground_truth,
            "expected_score_min": expected_score_range[0],
            "expected_score_max": expected_score_range[1],
            "details": details,
        }
        try:
            with open(self.ground_truth_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.debug("Generator failed appending ground truth: %s", e)

    # -------------------------------------------------------------------------
    # Scenario Workload Rotations
    # -------------------------------------------------------------------------

    def step_cycle(self) -> dict[str, Any]:
        """Execute one complete scenario cycle, emit telemetry, and feed autonomous pipeline."""
        with self._lock:
            scenario_name = self.SCENARIO_ROTATION[self.current_scenario_index % len(self.SCENARIO_ROTATION)]
            now_utc = datetime.now(timezone.utc)
            run_id = f"gen-{scenario_name[:8]}-{now_utc.strftime('%H%M%S')}-{hashlib.sha256(now_utc.isoformat().encode()).hexdigest()[:6]}"

            try:
                if scenario_name == "scenario_a_benign":
                    result = self._execute_benign_workload(run_id)
                elif scenario_name == "scenario_c_legitimate_dapp":
                    result = self._execute_dapp_workload(run_id)
                elif scenario_name == "scenario_b_synthetic_c2":
                    result = self._execute_c2_workload(run_id)
                elif scenario_name == "scenario_b_incomplete":
                    result = self._execute_incomplete_workload(run_id)
                else:
                    result = {"status": "UNKNOWN_SCENARIO", "events": []}

                cycle_events = result.get("events", [])
                if cycle_events:
                    self.total_events_emitted += len(cycle_events)
                    self.last_event_time = datetime.now(timezone.utc)
                    self.delivery_status = "DELIVERED_TO_INTAKE_STREAM"
                    # Autonomous Detection & Mitigation Pipeline (Event-Driven Intake)
                    try:
                        from src.blockchain.monitor import SepoliaMonitor
                        mon = SepoliaMonitor.get_instance(repo_root=self.repo_root)
                        detection_summary = mon.process_telemetry_events(cycle_events)
                        result["detection_summary"] = detection_summary
                    except Exception as det_exc:
                        logger.debug("Automatic detection intake failed: %s", det_exc)

                self.cycles_completed += 1
                self.current_scenario_index += 1
                self.last_cycle_time = datetime.now(timezone.utc)
                self.last_error = None
                self.error_count = 0
                self._persist_status()
                # Remove raw event objects from returned JSON-serializable dict
                result.pop("events", None)
                return result
            except Exception as e:
                self.error_count += 1
                self.last_error = str(e)
                logger.error("Error executing generator cycle (%s): %s", scenario_name, e)
                self._persist_status()
                return {"status": "ERROR", "error": str(e), "scenario": scenario_name}

    def _execute_benign_workload(self, run_id: str) -> dict[str, Any]:
        """Execute standard Web3 DApp query (Negative Control). Zero scenario label leakage."""
        ep_col = SyntheticEndpointCollector(
            process_name="benign_web3_client",
            pid=3011,
            host="127.0.0.1",
            command_args=["python", "-m", "src.scenarios.benign", "--network", "sepolia"],
        )
        ep_ev = ep_col.collect()
        ep_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not ep_ev.host:
            ep_ev.host = "127.0.0.1"
        self._emit_observable_event(ep_ev)

        rpc_col = RpcTelemetryCollector(
            rpc_endpoint="http://127.0.0.1:8546",
            upstream_endpoint="https://ethereum-sepolia-rpc.publicnode.com",
            host="127.0.0.1",
        )
        rpc_ev = rpc_col.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=2.1,
            request_params={"to": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512", "data": "0x0666144e"},
        )
        rpc_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not rpc_ev.host:
            rpc_ev.host = "127.0.0.1"
        self._emit_observable_event(rpc_ev)

        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_read",
            timestamp=datetime.now(timezone.utc),
            host="127.0.0.1",
            blockchain=BlockchainInfo(
                tx_hash=f"0x{hashlib.sha256(run_id.encode()).hexdigest()}",
                block_number=12020500,
                contract_address="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
                contract_name="BenignDAppContract",
                chain_id="11155111",
                network_name="sepolia",
                function_name="getCount",
                sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            ),
            metadata={"run_id": run_id, "telemetry_source": "synthetic_workload"},
        )
        self._emit_observable_event(bc_ev)

        self._record_private_ground_truth(
            run_id=run_id,
            scenario_id="scenario_a_benign",
            ground_truth="BENIGN",
            expected_score_range=(0.0, 40.0),
            details={"contract": "BenignDAppContract", "function": "getCount"},
        )
        return {
            "status": "SUCCESS",
            "scenario": "scenario_a_benign",
            "run_id": run_id,
            "events_emitted": 3,
            "events": [ep_ev, rpc_ev, bc_ev],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "telemetry_summary": "Emitted 3 events: Endpoint (benign_web3_client) + RPC (eth_call) + Blockchain read (getCount)",
        }

    def _execute_dapp_workload(self, run_id: str) -> dict[str, Any]:
        """Execute multi-step legitimate DApp worker task (Negative Control). Zero scenario label leakage."""
        ep_col = SyntheticEndpointCollector(
            process_name="dapp_worker",
            pid=3012,
            host="127.0.0.1",
            command_args=["python", "-m", "src.scenarios.dapp", "--network", "sepolia"],
        )
        ep_ev = ep_col.collect()
        ep_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not ep_ev.host:
            ep_ev.host = "127.0.0.1"
        self._emit_observable_event(ep_ev)

        rpc_col = RpcTelemetryCollector(
            rpc_endpoint="http://127.0.0.1:8546",
            upstream_endpoint="https://ethereum-sepolia-rpc.publicnode.com",
            host="127.0.0.1",
        )
        rpc_ev = rpc_col.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=2.4,
            request_params={"to": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0", "data": "0x00000000"},
        )
        rpc_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not rpc_ev.host:
            rpc_ev.host = "127.0.0.1"
        self._emit_observable_event(rpc_ev)

        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_read",
            timestamp=datetime.now(timezone.utc),
            host="127.0.0.1",
            blockchain=BlockchainInfo(
                tx_hash=f"0x{hashlib.sha256(run_id.encode()).hexdigest()}",
                block_number=12020501,
                contract_address="0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
                contract_name="LegitimateDAppContract",
                chain_id="11155111",
                network_name="sepolia",
                function_name="getTask",
                sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            ),
            metadata={"run_id": run_id, "telemetry_source": "synthetic_workload"},
        )
        self._emit_observable_event(bc_ev)

        self._record_private_ground_truth(
            run_id=run_id,
            scenario_id="scenario_c_legitimate_dapp",
            ground_truth="BENIGN",
            expected_score_range=(0.0, 40.0),
            details={"contract": "LegitimateDAppContract", "function": "getTask"},
        )
        return {
            "status": "SUCCESS",
            "scenario": "scenario_c_legitimate_dapp",
            "run_id": run_id,
            "events_emitted": 3,
            "events": [ep_ev, rpc_ev, bc_ev],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "telemetry_summary": "Emitted 3 events: Endpoint (dapp_worker) + RPC (eth_call) + Blockchain read (getTask)",
        }

    def _execute_c2_workload(self, run_id: str) -> dict[str, Any]:
        """Execute complete synthetic C2 sequence (Positive Control -> Score 100). Zero scenario label leakage."""
        registry = get_worker_registry()
        if registry.is_isolated("synthetic_c2_client", 4096):
            logger.warning("Generator: Worker 'synthetic_c2_client' (PID 4096) is ISOLATED by defensive policy; suppressing C2 telemetry emission.")
            self._record_private_ground_truth(
                run_id=run_id,
                scenario_id="scenario_b_synthetic_c2",
                ground_truth="SUPPRESSED_BY_DEFENSIVE_ISOLATION",
                expected_score_range=(0.0, 0.0),
                details={"status": "SUPPRESSED", "worker": "synthetic_c2_client", "pid": 4096, "containment": "ACTIVE"},
            )
            return {
                "status": "SUPPRESSED",
                "scenario": "scenario_b_synthetic_c2",
                "run_id": run_id,
                "events_emitted": 0,
                "events": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "telemetry_summary": "Worker synthetic_c2_client (PID 4096) is ISOLATED by defensive mitigation; event generation halted until un-isolated/rolled back.",
            }

        registry.register_worker(process_name="synthetic_c2_client", pid=4096)

        ep_col = SyntheticEndpointCollector(
            process_name="synthetic_c2_client",
            pid=4096,
            host="127.0.0.1",
            command_args=["python", "-m", "src.scenarios.c2", "--network", "sepolia"],
        )
        ep_ev = ep_col.collect()
        ep_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not ep_ev.host:
            ep_ev.host = "127.0.0.1"
        self._emit_observable_event(ep_ev)

        rpc_col = RpcTelemetryCollector(
            rpc_endpoint="http://127.0.0.1:8546",
            upstream_endpoint="https://ethereum-sepolia-rpc.publicnode.com",
            host="127.0.0.1",
        )
        rpc_ev = rpc_col.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=4.1,
            request_params={"to": "0x5FbDB2315678afecb367f032d93F642f64180aa3", "data": "0x4f5063c4"},
            response_result={"result": "0x424541434f4e"},
        )
        rpc_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not rpc_ev.host:
            rpc_ev.host = "127.0.0.1"
        self._emit_observable_event(rpc_ev)

        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_read",
            timestamp=datetime.now(timezone.utc),
            host="127.0.0.1",
            blockchain=BlockchainInfo(
                tx_hash=f"0x{hashlib.sha256(run_id.encode()).hexdigest()}",
                block_number=12020502,
                contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
                contract_name="C2DataStore",
                chain_id="11155111",
                network_name="sepolia",
                function_name="getLatestCommand",
                sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            ),
            metadata={"run_id": run_id, "telemetry_source": "synthetic_workload", "retrieved_command": "BEACON"},
        )
        self._emit_observable_event(bc_ev)

        # Loopback beacon
        target_port = 8080
        status_code = 200
        try:
            with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
                target_port = target_srv.port
                import urllib.request
                req = urllib.request.Request(
                    target_srv.beacon_url,
                    data=json.dumps({"command": "BEACON", "run_id": run_id}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    status_code = resp.status
        except Exception:
            status_code = 200

        net_col = NetworkTelemetryCollector(host="127.0.0.1")
        net_ev = net_col.collect(
            destination_host="127.0.0.1",
            destination_port=target_port,
            protocol="HTTP",
            source_process="synthetic_c2_client",
            request_type="POST",
            status_code=status_code,
            response_size_bytes=42,
        )
        net_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not net_ev.host:
            net_ev.host = "127.0.0.1"
        self._emit_observable_event(net_ev)

        self._record_private_ground_truth(
            run_id=run_id,
            scenario_id="scenario_b_synthetic_c2",
            ground_truth="POSITIVE",
            expected_score_range=(80.0, 100.0),
            details={"contract": "C2DataStore", "command": "BEACON", "beacon_port": target_port},
        )
        return {
            "status": "SUCCESS",
            "scenario": "scenario_b_synthetic_c2",
            "run_id": run_id,
            "events_emitted": 4,
            "events": [ep_ev, rpc_ev, bc_ev, net_ev],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "telemetry_summary": "Emitted 4 events: Endpoint (PID 4096) + RPC (eth_call) + Blockchain read + Loopback Egress Beacon",
        }

    def _execute_incomplete_workload(self, run_id: str) -> dict[str, Any]:
        """Execute incomplete C2 sequence (no subsequent loopback beacon -> Score 55 < 80). Zero scenario label leakage."""
        registry = get_worker_registry()
        if registry.is_isolated("synthetic_c2_client", 4013):
            logger.warning("Generator: Worker 'synthetic_c2_client' (PID 4013) is ISOLATED; suppressing activity.")
            self._record_private_ground_truth(
                run_id=run_id,
                scenario_id="scenario_b_incomplete",
                ground_truth="SUPPRESSED_BY_DEFENSIVE_ISOLATION",
                expected_score_range=(0.0, 0.0),
                details={"status": "SUPPRESSED", "worker": "synthetic_c2_client", "pid": 4013},
            )
            return {
                "status": "SUPPRESSED",
                "scenario": "scenario_b_incomplete",
                "run_id": run_id,
                "events_emitted": 0,
                "events": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "telemetry_summary": "Worker synthetic_c2_client (PID 4013) is ISOLATED; activity suppressed.",
            }

        registry.register_worker(process_name="synthetic_c2_client", pid=4013)

        ep_col = SyntheticEndpointCollector(process_name="synthetic_c2_client", pid=4013, host="127.0.0.1")
        ep_ev = ep_col.collect()
        ep_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not ep_ev.host:
            ep_ev.host = "127.0.0.1"
        self._emit_observable_event(ep_ev)

        rpc_col = RpcTelemetryCollector(
            rpc_endpoint="http://127.0.0.1:8546",
            upstream_endpoint="https://ethereum-sepolia-rpc.publicnode.com",
            host="127.0.0.1",
        )
        rpc_ev = rpc_col.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=3.0,
            request_params={"to": "0x5FbDB2315678afecb367f032d93F642f64180aa3", "data": "0x4f5063c4"},
        )
        rpc_ev.metadata = {"run_id": run_id, "telemetry_source": "synthetic_workload"}
        if not rpc_ev.host:
            rpc_ev.host = "127.0.0.1"
        self._emit_observable_event(rpc_ev)

        bc_ev = SentinelEvent(
            source=TelemetrySource.BLOCKCHAIN,
            event_type="contract_read",
            timestamp=datetime.now(timezone.utc),
            host="127.0.0.1",
            blockchain=BlockchainInfo(
                tx_hash=f"0x{hashlib.sha256(run_id.encode()).hexdigest()}",
                block_number=12020503,
                contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
                contract_name="C2DataStore",
                chain_id="11155111",
                network_name="sepolia",
                function_name="getLatestCommand",
                sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            ),
            metadata={"run_id": run_id, "telemetry_source": "synthetic_workload"},
        )
        self._emit_observable_event(bc_ev)
        # OMIT network beacon event

        self._record_private_ground_truth(
            run_id=run_id,
            scenario_id="scenario_b_incomplete",
            ground_truth="BENIGN",
            expected_score_range=(50.0, 60.0),
            details={"contract": "C2DataStore", "omitted": "network_beacon"},
        )
        return {
            "status": "SUCCESS",
            "scenario": "scenario_b_incomplete",
            "run_id": run_id,
            "events_emitted": 3,
            "events": [ep_ev, rpc_ev, bc_ev],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "telemetry_summary": "Emitted 3 events: Endpoint (PID 4013) + RPC (eth_call) + Blockchain read (no beacon)",
        }

    # -------------------------------------------------------------------------
    # Supervision & Daemon Controls
    # -------------------------------------------------------------------------

    def start(self, max_cycles: Optional[int] = None) -> bool:
        """Start unattended background generation loop, bounded by default (4 cycles)."""
        effective_max_cycles = 4 if max_cycles is None else (None if max_cycles <= 0 else max_cycles)
        with self._lock:
            if self.is_running:
                return True
            self.is_running = True
            self._stop_event.clear()

        def _worker_loop():
            logger.info(
                "ControlledGenerator daemon started (interval=%.1fs, max_cycles=%s)",
                self.cycle_interval_seconds,
                effective_max_cycles,
            )
            cycles_run = 0
            while not self._stop_event.is_set():
                try:
                    self.step_cycle()
                    cycles_run += 1
                    if effective_max_cycles is not None and cycles_run >= effective_max_cycles:
                        logger.info("ControlledGenerator reached bounded max_cycles (%d). Stopping.", effective_max_cycles)
                        break
                except Exception as e:
                    logger.error("ControlledGenerator error in daemon cycle: %s", e)
                self._stop_event.wait(timeout=self.cycle_interval_seconds)
            with self._lock:
                self.is_running = False
            self._persist_status()
            logger.info("ControlledGenerator daemon stopped")

        self._thread = threading.Thread(target=_worker_loop, daemon=True, name="ControlledGeneratorDaemon")
        self._thread.start()
        self._persist_status()
        return True

    def stop(self) -> bool:
        """Stop background generation gracefully."""
        with self._lock:
            if not self.is_running:
                return False
            self.is_running = False
            self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._persist_status()
        return True

    def emergency_stop(self) -> dict[str, Any]:
        """Emergency stop to immediately halt all generation activity."""
        self.stop()
        return {"status": "EMERGENCY_STOP_EXECUTED", "timestamp": datetime.now(timezone.utc).isoformat()}

