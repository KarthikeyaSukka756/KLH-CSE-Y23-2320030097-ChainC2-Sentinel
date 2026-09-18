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

        # Configure synthetic endpoint collector metadata
        self.endpoint_collector = SyntheticEndpointCollector(
            process_name="synthetic_c2_client",
            pid=4096,
            host=self.host,
            command_args=["python", "-m", "synthetic_c2_client", "--poll-interval", "60"],
            event_type="process_start",
        )

    def setup(self) -> None:
        """Ensure local HTTP target server is running."""
        if self.target_server is None:
            # Spin up an internal managed local HTTP target on 127.0.0.1
            self._managed_server = LocalHttpTargetServer(host="127.0.0.1", port=self._target_port or 0)
            self._managed_server.start()
            self.target_server = self._managed_server
        logger.debug("Scenario B target server available at %s", self.target_server.base_url)

    def execute(self) -> dict[str, Any]:
        """Execute the synthetic C2-like multi-source event sequence.

        Telemetry generated:
            - 1 Endpoint event (process start/snapshot)
            - 1 RPC event (eth_call query to proxy)
            - 1 Blockchain event (getLatestCommand from C2DataStore)
            - 1 Network event (HTTP POST beacon to local HTTP target)
        """
        assert self.target_server is not None, "Target server must be running"
        target_url = self.target_server.beacon_url

        # Construct the inert synthetic payload conforming to strict requirements
        payload = SyntheticC2Payload(
            scenario="synthetic_c2",
            command="BEACON",
            target=target_url,
            parameters={"client_tag": "lab_client_01"},
        )
        raw_blockchain_command = payload.to_blockchain_string()

        # Step 1: Endpoint telemetry
        endpoint_event = self.endpoint_collector.collect()
        endpoint_event.metadata.update({"role": "c2_client_simulation"})
        self.record_event(endpoint_event, step_name="endpoint_init")

        # Step 2: RPC telemetry (client queries C2DataStore via proxy)
        rpc_event = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=12.1,
            request_params={
                "to": self.contract_address,
                "data": "0x5c880fcb",  # getLatestCommand() selector
            },
            response_result={
                "command_length": len(raw_blockchain_command),
                "status": "0x1",
            },
        )
        rpc_event.metadata.update({"contract_target": "C2DataStore"})
        self.record_event(rpc_event, step_name="rpc_query")

        # Step 3: Blockchain interaction telemetry (retrieval of inert config)
        blockchain_event = self.blockchain_collector.collect(
            contract_name="C2DataStore",
            contract_address=self.contract_address,
            function_name="getLatestCommand",
            block_number=102,
            sender="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            event_type="contract_read",
        )
        blockchain_event.metadata.update({
            "retrieved_command": payload.command,
            "target_host": "127.0.0.1",
        })
        self.record_event(blockchain_event, step_name="blockchain_command_retrieval")

        # Step 4: Strict Payload Interpretation & Safe Beacon Execution
        # Strictly validate that only 'BEACON' is permitted and target is strictly local
        parsed_payload = SyntheticC2Payload.from_raw(raw_blockchain_command)
        assert parsed_payload.command == "BEACON", "Only BEACON command allowed"

        parsed_target = urlparse(parsed_payload.target)
        dest_host = parsed_target.hostname or "127.0.0.1"
        dest_port = parsed_target.port or 80

        # Execute safe local HTTP beacon
        beacon_data = json.dumps({
            "client_id": "synthetic_c2_client",
            "request_id": parsed_payload.request_id,
            "status": "ready",
        }).encode("utf-8")

        req = urllib_request.Request(
            parsed_payload.target,
            data=beacon_data,
            headers={"Content-Type": "application/json", "User-Agent": "ChainC2-Sentinel-Lab/1.0"},
            method="POST",
        )

        status_code = 0
        response_size = 0
        try:
            with urllib_request.urlopen(req, timeout=5.0) as resp:
                status_code = resp.status
                resp_data = resp.read()
                response_size = len(resp_data)
        except URLError as err:
            logger.warning("Local beacon failed: %s", err)
            status_code = getattr(err, "code", 500)

        # Step 5: Network telemetry capture
        network_event = self.network_collector.collect(
            destination_host=dest_host,
            destination_port=dest_port,
            protocol="HTTP",
            source_process="synthetic_c2_client",
            request_type="POST",
            status_code=status_code,
            response_size_bytes=response_size,
            event_type="http_beacon",
        )
        network_event.metadata.update({
            "beacon_action": parsed_payload.command,
            "request_id": parsed_payload.request_id,
        })
        self.record_event(network_event, step_name="network_beacon")

        return {
            "contract": "C2DataStore",
            "function": "getLatestCommand",
            "command": parsed_payload.command,
            "target_url": parsed_payload.target,
            "http_status": status_code,
            "network_calls_made": 1,
        }

    def teardown(self) -> None:
        """Shut down managed server if created internally."""
        if self._managed_server is not None:
            self._managed_server.stop()
            self._managed_server = None
        logger.debug("Scenario B teardown complete")
