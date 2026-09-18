# ChainC2 Sentinel — Scenario A: Benign Web3 Activity
"""Scenario A represents legitimate decentralized application usage.

Execution Flow:
    1. Endpoint process initialized (web3_dapp_client).
    2. Web3 client makes an RPC call via the RPC proxy.
    3. Smart contract interaction executes on BenignDAppContract (e.g. increment counter).
    4. Follow-up network activity: NONE.

Research Principle:
    Blockchain interaction alone must NEVER be classified as malicious.
    This scenario serves as a negative control baseline.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.collectors.endpoint_collector import SyntheticEndpointCollector
from src.normalizer.normalizer import EventStore
from src.scenarios.base import BaseScenario

logger = logging.getLogger("chainc2_sentinel.scenarios.benign")


class BenignWeb3Scenario(BaseScenario):
    """Controlled scenario executing legitimate BenignDAppContract interactions."""

    scenario_id: str = "scenario_a_benign"
    scenario_description: str = "Benign Web3 Activity Baseline (Negative Control)"

    def __init__(
        self,
        contract_address: str = "0x5FbDB2315678afecb367f032d93F642f64180aa3",
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

        # Configure synthetic process metadata for the benign client
        self.endpoint_collector = SyntheticEndpointCollector(
            process_name="web3_dapp_client",
            pid=2048,
            host=self.host,
            command_args=["python", "-m", "web3_dapp_client", "--action", "increment"],
            event_type="process_start",
        )

    def setup(self) -> None:
        """Prerequisites for benign scenario."""
        logger.debug("Scenario A setup: target contract is %s", self.contract_address)

    def execute(self) -> dict[str, Any]:
        """Execute the benign Web3 interaction sequence.

        Telemetry generated:
            - 1 Endpoint event (process snapshot)
            - 1 RPC event (eth_sendTransaction to proxy)
            - 1 Blockchain event (increment on BenignDAppContract)
            - 0 Network events (negative control)
        """
        # Step 1: Endpoint telemetry
        endpoint_event = self.endpoint_collector.collect()
        endpoint_event.metadata.update({"dapp": "BenignDApp"})
        self.record_event(endpoint_event, step_name="endpoint_init")

        # Step 2: RPC interaction telemetry
        rpc_event = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=18.4,
            request_params={
                "to": self.contract_address,
                "data": "0xd09de08a",  # increment() selector
            },
            response_result={
                "tx_hash": "0x4a7e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a",
            },
        )
        rpc_event.metadata.update({"scenario": self.scenario_id})
        self.record_event(rpc_event, step_name="rpc_transaction")

        # Step 3: Blockchain interaction telemetry
        blockchain_event = self.blockchain_collector.collect(
            contract_name="BenignDAppContract",
            contract_address=self.contract_address,
            function_name="increment",
            tx_hash="0x4a7e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a",
            block_number=101,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="CountIncremented",
            event_args={"sender": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", "newCount": 1},
            event_type="contract_interaction",
        )
        blockchain_event.metadata.update({"dapp_category": "counter"})
        self.record_event(blockchain_event, step_name="blockchain_contract_event")

        # Step 4: Follow-up Network Activity: NONE
        # Legitimate Web3 activity does NOT initiate out-of-band network connections.

        return {
            "contract": "BenignDAppContract",
            "function": "increment",
            "action": "counter_increment",
            "network_calls_made": 0,
        }

    def teardown(self) -> None:
        """Teardown benign scenario."""
        logger.debug("Scenario A teardown complete")
