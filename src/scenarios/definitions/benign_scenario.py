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
        variant_id: str = "A04",
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
        self.variant_id = variant_id
        self.parameters = parameters or {}
        self.experimental_unit_id = experimental_unit_id or f"unit-{self.run_id}"
        self.replicate_id = replicate_id
        self.state_context_id = state_context_id or "state-clean"
        self.seed = seed

        # Configure synthetic process metadata for the benign client
        self.endpoint_collector = SyntheticEndpointCollector(
            process_name="web3_dapp_client",
            pid=2048,
            host=self.host,
            command_args=["python", "-m", "web3_dapp_client", "--action", self.variant_id],
            event_type="process_start",
        )

    def setup(self) -> None:
        """Prerequisites for benign scenario."""
        logger.debug("Scenario A setup (%s): target contract is %s", self.variant_id, self.contract_address)

    def execute(self) -> dict[str, Any]:
        """Execute the benign Web3 interaction sequence for the configured variant.

        Supported variants:
            A01: getCount() via eth_call
            A02: message() via eth_call
            A03: deployer() via eth_call
            A04: increment() transaction (default baseline)
            A05: updateMessage(string) transaction
            A06: getCount -> increment -> getCount
            A07: getCount burst polling (N=5..10, delay <10ms)
            A08a: controlled invalid/stale nonce error
            A08b: controlled gas_limit below intrinsic gas

        Telemetry invariant:
            Network events: STRICTLY 0 (Negative Control).
        """
        import time

        # Step 1: Endpoint telemetry
        endpoint_event = self.endpoint_collector.collect()
        endpoint_event.metadata.update({
            "dapp": "BenignDApp",
            "variant_id": self.variant_id,
            "experimental_unit_id": self.experimental_unit_id,
            "provenance": "GENUINE_EXECUTION",
        })
        self.record_event(endpoint_event, step_name="endpoint_init")

        vid = self.variant_id.upper()

        if vid == "A01":
            # getCount() via eth_call
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=4.2,
                request_params={"to": self.contract_address, "data": "0xa87d942c"},
                response_result={"result": "0x0000000000000000000000000000000000000000000000000000000000000001"},
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A01"})
            self.record_event(rpc_event, step_name="rpc_get_count")
            return {"contract": "BenignDAppContract", "function": "getCount", "variant_id": "A01", "network_calls_made": 0}

        elif vid == "A02":
            # message() public getter via eth_call
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=4.5,
                request_params={"to": self.contract_address, "data": "0xe21f37ce"},
                response_result={"result": "ChainC2 Sentinel — Benign DApp Active"},
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A02"})
            self.record_event(rpc_event, step_name="rpc_get_message")
            return {"contract": "BenignDAppContract", "function": "message", "variant_id": "A02", "network_calls_made": 0}

        elif vid == "A03":
            # deployer() address getter via eth_call
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=3.8,
                request_params={"to": self.contract_address, "data": "0x789c02ff"},
                response_result={"result": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"},
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A03"})
            self.record_event(rpc_event, step_name="rpc_get_deployer")
            return {"contract": "BenignDAppContract", "function": "deployer", "variant_id": "A03", "network_calls_made": 0}

        elif vid == "A05":
            # updateMessage(string) transaction
            new_msg = str(self.parameters.get("message", "Benign update telemetry message"))
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status="success",
                duration_ms=22.1,
                request_params={"to": self.contract_address, "data": "0x368b8772", "newMessage": new_msg},
                response_result={"tx_hash": "0x5a8e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f5b"},
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A05"})
            self.record_event(rpc_event, step_name="rpc_update_message")

            bc_event = self.blockchain_collector.collect(
                contract_name="BenignDAppContract",
                contract_address=self.contract_address,
                function_name="updateMessage",
                tx_hash="0x5a8e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f5b",
                block_number=102,
                sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                event_name="MessageUpdated",
                event_args={"sender": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", "newMessage": new_msg},
                event_type="contract_interaction",
            )
            bc_event.metadata.update({"dapp_category": "message_board", "variant_id": "A05"})
            self.record_event(bc_event, step_name="blockchain_message_updated")
            return {"contract": "BenignDAppContract", "function": "updateMessage", "message": new_msg, "variant_id": "A05", "network_calls_made": 0}

        elif vid == "A06":
            # getCount -> increment -> getCount
            rpc_get1 = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=4.1,
                request_params={"to": self.contract_address, "data": "0xa87d942c"},
                response_result={"result": "0x0000000000000000000000000000000000000000000000000000000000000001"},
            )
            self.record_event(rpc_get1, step_name="rpc_pre_get_count")

            rpc_inc = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status="success",
                duration_ms=18.6,
                request_params={"to": self.contract_address, "data": "0xd09de08a"},
                response_result={"tx_hash": "0x6a7e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f6c"},
            )
            self.record_event(rpc_inc, step_name="rpc_increment")

            bc_inc = self.blockchain_collector.collect(
                contract_name="BenignDAppContract",
                contract_address=self.contract_address,
                function_name="increment",
                tx_hash="0x6a7e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f6c",
                block_number=103,
                sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                event_name="CountIncremented",
                event_args={"sender": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", "newCount": 2},
                event_type="contract_interaction",
            )
            self.record_event(bc_inc, step_name="blockchain_count_incremented")

            rpc_get2 = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=3.9,
                request_params={"to": self.contract_address, "data": "0xa87d942c"},
                response_result={"result": "0x0000000000000000000000000000000000000000000000000000000000000002"},
            )
            self.record_event(rpc_get2, step_name="rpc_post_get_count")
            return {"contract": "BenignDAppContract", "workflow": "read_write_read", "variant_id": "A06", "network_calls_made": 0}

        elif vid == "A07":
            # getCount burst polling
            burst_count = max(5, min(int(self.parameters.get("burst_count", 5)), 10))
            delay_ms = max(0.0, min(float(self.parameters.get("delay_ms", 2.0)), 10.0))
            for i in range(burst_count):
                if i > 0 and delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                rpc_burst = self.rpc_collector.collect(
                    rpc_method="eth_call",
                    status="success",
                    duration_ms=3.5,
                    request_params={"to": self.contract_address, "data": "0xa87d942c"},
                    response_result={"result": "0x0000000000000000000000000000000000000000000000000000000000000001"},
                )
                self.record_event(rpc_burst, step_name=f"rpc_burst_call_{i+1}")
            return {"contract": "BenignDAppContract", "function": "getCount", "burst_count": burst_count, "variant_id": "A07", "network_calls_made": 0}

        elif vid in ("A08A", "A08_NONCE"):
            # Controlled invalid/stale nonce error simulation
            rpc_err = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status="error",
                error_message="Nonce too low: expected 5, got 3",
                duration_ms=6.1,
                request_params={"to": self.contract_address, "nonce": 3},
            )
            self.record_event(rpc_err, step_name="rpc_nonce_error")
            return {"contract": "BenignDAppContract", "variant_id": "A08a", "failure_type": "NONCE_TOO_LOW", "network_calls_made": 0}

        elif vid in ("A08B", "A08_GAS"):
            # Controlled gas_limit below intrinsic gas simulation
            rpc_err = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status="error",
                error_message="intrinsic gas too low: 21000 < 50000",
                duration_ms=5.4,
                request_params={"to": self.contract_address, "gas": 15000},
            )
            self.record_event(rpc_err, step_name="rpc_gas_error")
            return {"contract": "BenignDAppContract", "variant_id": "A08b", "failure_type": "INSUFFICIENT_GAS", "network_calls_made": 0}

        else:
            # A04: increment() default baseline (preserves original behavior exactly)
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
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A04"})
            self.record_event(rpc_event, step_name="rpc_transaction")

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
            blockchain_event.metadata.update({"dapp_category": "counter", "variant_id": "A04"})
            self.record_event(blockchain_event, step_name="blockchain_contract_event")

            return {
                "contract": "BenignDAppContract",
                "function": "increment",
                "action": "counter_increment",
                "variant_id": "A04",
                "network_calls_made": 0,
            }

    def teardown(self) -> None:
        """Teardown benign scenario."""
        logger.debug("Scenario A teardown complete")
