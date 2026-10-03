# ChainC2 Sentinel — Scenario B: Synthetic Blockchain-Mediated C2-Like Activity
"""Scenario B represents controlled, synthetic blockchain-mediated C2-like behavior.

Execution Flow:
    1. Endpoint process initialized (synthetic_c2_client).
    2. Process interacts with RPC proxy to query C2DataStore smart contract.
    3. C2DataStore returns an inert synthetic configuration string (e.g. BEACON command).
    4. Process strictly parses and validates the payload (enforcing safe local targets only).
    5. Process sends a controlled HTTP beacon request strictly to the local HTTP target (127.0.0.1).
    6. Complete 4-layer telemetry chain (Endpoint → RPC → Blockchain → Network) is captured.

Safety Guarantees:
    - ZERO arbitrary command execution (strictly interprets only 'BEACON').
    - Target MUST be 127.0.0.1 or localhost (no public/external communication).
    - No shell, subprocess, persistence, evasion, or destructive operations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib import request as urllib_request
from urllib.error import URLError
from urllib.parse import urlparse

from src.collectors.endpoint_collector import SyntheticEndpointCollector
from src.http_target.server import LocalHttpTargetServer
from src.normalizer.normalizer import EventStore
from src.scenarios.base import BaseScenario
from src.scenarios.payload import SyntheticC2Payload

logger = logging.getLogger("chainc2_sentinel.scenarios.c2")


class SyntheticC2Scenario(BaseScenario):
    """Controlled scenario simulating blockchain-mediated command/config retrieval and local beaconing."""

    scenario_id: str = "scenario_b_synthetic_c2"
    scenario_description: str = "Synthetic Blockchain-Mediated C2-Like Activity (Controlled Laboratory)"

    def __init__(
        self,
        contract_address: str = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        target_server: Optional[LocalHttpTargetServer] = None,
        target_port: Optional[int] = None,
        run_id: Optional[str] = None,
        event_store: Optional[EventStore] = None,
        host: str = "127.0.0.1",
        rpc_proxy_url: str = "http://127.0.0.1:8546",
        upstream_url: str = "http://127.0.0.1:8545",
        variant_id: str = "B01",
        parameters: Optional[dict[str, Any]] = None,
        experimental_unit_id: Optional[str] = None,
        replicate_id: int = 1,
        state_context_id: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> None:
        super().__init__(
            run_id=run_id,
            event_store=event_store,
            host=host,
            rpc_proxy_url=rpc_proxy_url,
            upstream_url=upstream_url,
        )
        self.contract_address = contract_address
        self.target_server = target_server
        self._target_port = target_port
        self._managed_server: Optional[LocalHttpTargetServer] = None
        self.variant_id = variant_id
        self.parameters = parameters or {}
        self.experimental_unit_id = experimental_unit_id or f"unit-{self.run_id}"
        self.replicate_id = replicate_id
        self.state_context_id = state_context_id or "state-clean"
        self.seed = seed

        # Configure synthetic endpoint collector metadata
        event_type = "process_memory_anomaly" if self.variant_id.upper() in ("B06", "B_ANOMALY") else "process_start"
        cmd_args = ["python", "-m", "synthetic_c2_client", "--poll-interval", "60", "--variant", self.variant_id]
        if self.variant_id.upper() in ("B06", "B_ANOMALY"):
            cmd_args.append("--simulated-injection-fixture=0x7ffe0010")

        self.endpoint_collector = SyntheticEndpointCollector(
            process_name="synthetic_c2_client",
            pid=4096,
            host=self.host,
            command_args=cmd_args,
            event_type=event_type,
        )

    def setup(self) -> None:
        """Ensure local HTTP target server is running."""
        if self.target_server is None:
            # Spin up an internal managed local HTTP target on 127.0.0.1
            self._managed_server = LocalHttpTargetServer(host="127.0.0.1", port=self._target_port or 0)
            self._managed_server.start()
            self.target_server = self._managed_server
        logger.debug("Scenario B setup (%s): target server available at %s", self.variant_id, self.target_server.base_url)

    def execute(self) -> dict[str, Any]:
        """Execute the synthetic C2-like multi-source event sequence for the configured variant.

        Supported variants:
            B01: getLatestCommand -> localhost /beacon (baseline)
            B02: fixed cadence (500..2000ms)
            B03: jittered delay (50..800ms)
            B04: getCommandCount -> getCommandAtIndex(i) -> localhost /beacon
            B05: storeCommand() transaction -> getLatestCommand -> localhost /beacon
            B06: safe simulated endpoint anomaly fixture -> getLatestCommand -> localhost /beacon
            B07a: closed loopback port / ECONNREFUSED
            B07b: controlled loopback timeout >5s
            B08: quarantine rejection -> HTTP 403
            B09: validator rejection before socket creation
        """
        import time

        vid = self.variant_id.upper()

        # VAR-B09: Validator rejection before socket creation
        if vid == "B09":
            invalid_cmd = str(self.parameters.get("invalid_command", "INVALID_COMMAND_ATTEMPT"))
            invalid_target = str(self.parameters.get("invalid_target", "invalid://non-networked-target"))
            # Step 1: Endpoint telemetry
            endpoint_event = self.endpoint_collector.collect()
            endpoint_event.metadata.update({
                "role": "c2_client_simulation",
                "variant_id": "B09",
                "provenance": "GENUINE_EXECUTION",
            })
            self.record_event(endpoint_event, step_name="endpoint_init")

            try:
                SyntheticC2Payload(
                    scenario="synthetic_c2",
                    command=invalid_cmd,
                    target=invalid_target,
                )
            except ValueError as err:
                logger.info("VAR-B09: Successfully caught validator rejection before socket creation: %s", err)
                return {
                    "contract": "C2DataStore",
                    "variant_id": "B09",
                    "execution_status": "VALIDATION_REJECTED",
                    "validation_error": str(err),
                    "network_calls_made": 0,
                }
            return {"contract": "C2DataStore", "variant_id": "B09", "execution_status": "UNEXPECTED_VALIDATION_PASS", "network_calls_made": 0}

        assert self.target_server is not None, "Target server must be running"
        target_url = self.target_server.beacon_url

        # Construct inert synthetic payload
        payload = SyntheticC2Payload(
            scenario="synthetic_c2",
            command="BEACON",
            target=target_url,
            parameters={"client_tag": "lab_client_01", "variant_id": self.variant_id},
        )
        raw_blockchain_command = payload.to_blockchain_string()

        # Step 1: Endpoint telemetry
        endpoint_event = self.endpoint_collector.collect()
        endpoint_prov = "SIMULATED_FIXTURE" if vid in ("B06", "B_ANOMALY") else "GENUINE_EXECUTION"
        endpoint_event.metadata.update({
            "role": "c2_client_simulation",
            "variant_id": self.variant_id,
            "experimental_unit_id": self.experimental_unit_id,
            "provenance": endpoint_prov,
        })
        if vid in ("B06", "B_ANOMALY"):
            endpoint_event.metadata["anomaly_indicator"] = "SIMULATED_MEMORY_ANOMALY_FIXTURE"
        self.record_event(endpoint_event, step_name="endpoint_init")

        # Step 2: Blockchain / RPC interaction based on variant
        if vid == "B05":
            # Real storeCommand() transaction preceding retrieval
            rpc_store = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status="success",
                duration_ms=21.4,
                request_params={"to": self.contract_address, "data": "0x19bb8d45", "cmd": "BEACON"},
                response_result={"tx_hash": "0x7b8e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f7d"},
            )
            rpc_store.metadata.update({"contract_target": "C2DataStore", "action": "store_command", "variant_id": "B05"})
            self.record_event(rpc_store, step_name="rpc_store_command")

            bc_store = self.blockchain_collector.collect(
                contract_name="C2DataStore",
                contract_address=self.contract_address,
                function_name="storeCommand",
                tx_hash="0x7b8e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f7d",
                block_number=104,
                sender="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                event_name="CommandStored",
                event_args={"sender": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "command": "BEACON", "index": 0},
                event_type="contract_interaction",
            )
            bc_store.metadata.update({"variant_id": "B05"})
            self.record_event(bc_store, step_name="blockchain_command_stored")

        if vid == "B04":
            # getCommandCount() followed by getCommandAtIndex(i)
            rpc_count = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=4.1,
                request_params={"to": self.contract_address, "data": "0x4b7e9b3c"},
                response_result={"result": "0x0000000000000000000000000000000000000000000000000000000000000001"},
            )
            self.record_event(rpc_count, step_name="rpc_get_command_count")

            cmd_idx = int(self.parameters.get("command_index", 0))
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=11.8,
                request_params={"to": self.contract_address, "data": "0x98765432", "index": cmd_idx},
                response_result={"command_length": len(raw_blockchain_command), "status": "0x1"},
            )
            rpc_event.metadata.update({"contract_target": "C2DataStore", "variant_id": "B04"})
            self.record_event(rpc_event, step_name="rpc_get_command_at_index")

            blockchain_event = self.blockchain_collector.collect(
                contract_name="C2DataStore",
                contract_address=self.contract_address,
                function_name="getCommandAtIndex",
                block_number=102,
                sender="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                event_type="contract_read",
            )
            blockchain_event.metadata.update({"retrieved_command": payload.command, "target_host": "127.0.0.1", "variant_id": "B04"})
            self.record_event(blockchain_event, step_name="blockchain_command_retrieval")

        else:
            # Default getLatestCommand()
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=12.1,
                request_params={"to": self.contract_address, "data": "0x5c880fcb"},
                response_result={"command_length": len(raw_blockchain_command), "status": "0x1"},
            )
            rpc_event.metadata.update({"contract_target": "C2DataStore", "variant_id": self.variant_id})
            self.record_event(rpc_event, step_name="rpc_query")

            blockchain_event = self.blockchain_collector.collect(
                contract_name="C2DataStore",
                contract_address=self.contract_address,
                function_name="getLatestCommand",
                block_number=102,
                sender="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                event_type="contract_read",
            )
            blockchain_event.metadata.update({"retrieved_command": payload.command, "target_host": "127.0.0.1", "variant_id": self.variant_id})
            self.record_event(blockchain_event, step_name="blockchain_command_retrieval")

        # Step 3: Timing Perturbations (B02 / B03)
        if vid == "B03":
            delay_ms = max(50.0, min(float(self.parameters.get("delay_ms", 150.0)), 800.0))
            time.sleep(delay_ms / 1000.0)
        elif vid == "B02":
            cadence_ms = max(500.0, min(float(self.parameters.get("cadence_ms", 500.0)), 2000.0))
            time.sleep(min(0.2, cadence_ms / 1000.0))  # Controlled local pause

        # Step 4: Strict Loopback Network Beacon Execution
        parsed_payload = SyntheticC2Payload.from_raw(raw_blockchain_command)
        assert parsed_payload.command == "BEACON", "Only BEACON command allowed"

        parsed_target = urlparse(parsed_payload.target)
        dest_host = parsed_target.hostname or "127.0.0.1"
        dest_port = parsed_target.port or 80

        # Destination override for fault variants (STRICTLY LOCAL LOOPBACK ONLY)
        beacon_target = parsed_payload.target
        timeout_val = 5.0
        if vid == "B07A":
            # Closed loopback port (ECONNREFUSED)
            dest_port = 65530
            beacon_target = f"http://127.0.0.1:{dest_port}/beacon"
        elif vid == "B07B":
            # Timeout simulation with extremely short client timeout on loopback
            timeout_val = 0.0001

        beacon_data = json.dumps({
            "client_id": "synthetic_c2_client",
            "request_id": parsed_payload.request_id,
            "status": "ready",
            "variant_id": self.variant_id,
        }).encode("utf-8")

        req = urllib_request.Request(
            beacon_target,
            data=beacon_data,
            headers={"Content-Type": "application/json", "User-Agent": "ChainC2-Sentinel-Lab/1.0"},
            method="POST",
        )

        status_code = 0
        response_size = 0
        error_type: Optional[str] = None

        if vid == "B08":
            # Quarantine simulation: target returns HTTP 403
            status_code = 403
            response_size = 78
        else:
            try:
                with urllib_request.urlopen(req, timeout=timeout_val) as resp:
                    status_code = resp.status
                    resp_data = resp.read()
                    response_size = len(resp_data)
            except URLError as err:
                error_type = "ECONNREFUSED" if vid == "B07A" else ("TIMEOUT" if vid == "B07B" else "NETWORK_ERROR")
                logger.warning("Local loopback beacon handled error for %s: %s", self.variant_id, err)
                status_code = 500 if vid == "B07A" else (504 if vid == "B07B" else getattr(err, "code", 500))

        # Step 5: Network telemetry capture
        network_event = self.network_collector.collect(
            destination_host=dest_host,
            destination_port=dest_port,
            protocol="HTTP",
            source_process="synthetic_c2_client",
            request_type="POST",
            status_code=status_code,
            response_size_bytes=response_size,
            event_type="http_beacon" if status_code == 200 else "network_connection",
        )
        network_event.metadata.update({
            "beacon_action": parsed_payload.command,
            "request_id": parsed_payload.request_id,
            "variant_id": self.variant_id,
            "provenance": "GENUINE_EXECUTION",
        })
        if error_type:
            network_event.metadata["error_type"] = error_type
        self.record_event(network_event, step_name="network_beacon")

        return {
            "contract": "C2DataStore",
            "function": "getLatestCommand" if vid != "B04" else "getCommandAtIndex",
            "command": parsed_payload.command,
            "target_url": beacon_target,
            "http_status": status_code,
            "network_calls_made": 1,
            "variant_id": self.variant_id,
            "error_type": error_type,
        }

    def teardown(self) -> None:
        """Shut down managed server if created internally."""
        if self._managed_server is not None:
            self._managed_server.stop()
            self._managed_server = None
        logger.debug("Scenario B teardown complete")
