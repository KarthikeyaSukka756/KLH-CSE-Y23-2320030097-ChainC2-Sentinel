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
        contract_address: str = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
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
        rpc_client: Optional[Any] = None,
        network: str = "localhost",
    ) -> None:
        super().__init__(
            run_id=run_id,
            event_store=event_store,
            host=host,
            rpc_proxy_url=rpc_proxy_url,
            upstream_url=upstream_url,
            rpc_client=rpc_client,
            network=network,
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

        from src.blockchain.rpc_client import (
            decode_uint256,
            decode_string,
            decode_address,
            encode_string,
        )

        vid = self.variant_id.upper()

        if vid == "A01":
            # getCount() via eth_call
            call_res = self.rpc_client.eth_call(to=self.contract_address, data="0xa87d942c")
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=call_res.status,
                duration_ms=call_res.duration_ms,
                request_params=call_res.request_params,
                response_result=call_res.response_result,
                error_message=call_res.error_message,
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A01"})
            self.record_event(rpc_event, step_name="rpc_get_count")
            cnt = decode_uint256(call_res.result or "0x0")
            return {
                "contract": "BenignDAppContract",
                "function": "getCount",
                "variant_id": "A01",
                "count": cnt,
                "network_calls_made": 0,
                "execution_status": "SUCCESS" if call_res.success else "FAILED",
            }

        elif vid == "A02":
            # message() public getter via eth_call
            call_res = self.rpc_client.eth_call(to=self.contract_address, data="0xe21f37ce")
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=call_res.status,
                duration_ms=call_res.duration_ms,
                request_params=call_res.request_params,
                response_result=call_res.response_result,
                error_message=call_res.error_message,
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A02"})
            self.record_event(rpc_event, step_name="rpc_get_message")
            msg_str = decode_string(call_res.result or "0x0")
            return {
                "contract": "BenignDAppContract",
                "function": "message",
                "variant_id": "A02",
                "message": msg_str,
                "network_calls_made": 0,
                "execution_status": "SUCCESS" if call_res.success else "FAILED",
            }

        elif vid == "A03":
            # deployer() address getter via eth_call
            call_res = self.rpc_client.eth_call(to=self.contract_address, data="0xd5f39488")
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=call_res.status,
                duration_ms=call_res.duration_ms,
                request_params=call_res.request_params,
                response_result=call_res.response_result,
                error_message=call_res.error_message,
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A03"})
            self.record_event(rpc_event, step_name="rpc_get_deployer")
            dep_addr = decode_address(call_res.result or "0x0")
            return {
                "contract": "BenignDAppContract",
                "function": "deployer",
                "variant_id": "A03",
                "deployer": dep_addr,
                "network_calls_made": 0,
                "execution_status": "SUCCESS" if call_res.success else "FAILED",
            }

        elif vid == "A05":
            # updateMessage(string) transaction
            new_msg = str(self.parameters.get("message", "Benign update telemetry message"))
            calldata = "0x1923be24" + encode_string(new_msg)
            tx_res = self.rpc_client.eth_send_transaction(
                to=self.contract_address,
                data=calldata,
            )
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status=tx_res.status,
                duration_ms=tx_res.duration_ms,
                request_params=tx_res.request_params,
                response_result=tx_res.response_result,
                error_message=tx_res.error_message,
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A05"})
            self.record_event(rpc_event, step_name="rpc_update_message")

            if tx_res.success:
                bc_event = self.blockchain_collector.collect(
                    contract_name="BenignDAppContract",
                    contract_address=self.contract_address,
                    function_name="updateMessage",
                    tx_hash=tx_res.tx_hash,
                    block_number=tx_res.block_number,
                    sender=tx_res.sender,
                    event_name="MessageUpdated",
                    event_args={"sender": tx_res.sender, "newMessage": new_msg},
                    event_type="contract_interaction",
                )
                bc_event.metadata.update({"dapp_category": "message_board", "variant_id": "A05"})
                self.record_event(bc_event, step_name="blockchain_message_updated")

            return {
                "contract": "BenignDAppContract",
                "function": "updateMessage",
                "message": new_msg,
                "variant_id": "A05",
                "network_calls_made": 0,
                "execution_status": "SUCCESS" if tx_res.success else "FAILED",
            }

        elif vid == "A06":
            # getCount -> increment -> getCount
            call1 = self.rpc_client.eth_call(to=self.contract_address, data="0xa87d942c")
            rpc_get1 = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=call1.status,
                duration_ms=call1.duration_ms,
                request_params=call1.request_params,
                response_result=call1.response_result,
                error_message=call1.error_message,
            )
            self.record_event(rpc_get1, step_name="rpc_pre_get_count")

            tx_res = self.rpc_client.eth_send_transaction(
                to=self.contract_address,
                data="0xd09de08a",
            )
            rpc_inc = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status=tx_res.status,
                duration_ms=tx_res.duration_ms,
                request_params=tx_res.request_params,
                response_result=tx_res.response_result,
                error_message=tx_res.error_message,
            )
            self.record_event(rpc_inc, step_name="rpc_increment")

            if tx_res.success:
                bc_inc = self.blockchain_collector.collect(
                    contract_name="BenignDAppContract",
                    contract_address=self.contract_address,
                    function_name="increment",
                    tx_hash=tx_res.tx_hash,
                    block_number=tx_res.block_number,
                    sender=tx_res.sender,
                    event_name="CountIncremented",
                    event_type="contract_interaction",
                )
                self.record_event(bc_inc, step_name="blockchain_count_incremented")

            call2 = self.rpc_client.eth_call(to=self.contract_address, data="0xa87d942c")
            rpc_get2 = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=call2.status,
                duration_ms=call2.duration_ms,
                request_params=call2.request_params,
                response_result=call2.response_result,
                error_message=call2.error_message,
            )
            self.record_event(rpc_get2, step_name="rpc_post_get_count")

            return {
                "contract": "BenignDAppContract",
                "workflow": "read_write_read",
                "variant_id": "A06",
                "network_calls_made": 0,
                "execution_status": "SUCCESS" if tx_res.success else "FAILED",
            }

        elif vid == "A07":
            # getCount burst polling
            burst_count = max(5, min(int(self.parameters.get("burst_count", 5)), 10))
            delay_ms = max(0.0, min(float(self.parameters.get("delay_ms", 2.0)), 10.0))
            all_success = True
            for i in range(burst_count):
                if i > 0 and delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                call_res = self.rpc_client.eth_call(to=self.contract_address, data="0xa87d942c")
                if not call_res.success:
                    all_success = False
                rpc_burst = self.rpc_collector.collect(
                    rpc_method="eth_call",
                    status=call_res.status,
                    duration_ms=call_res.duration_ms,
                    request_params=call_res.request_params,
                    response_result=call_res.response_result,
                    error_message=call_res.error_message,
                )
                self.record_event(rpc_burst, step_name=f"rpc_burst_call_{i+1}")
            return {
                "contract": "BenignDAppContract",
                "function": "getCount",
                "burst_count": burst_count,
                "variant_id": "A07",
                "network_calls_made": 0,
                "execution_status": "SUCCESS" if all_success else "FAILED",
            }

        elif vid in ("A08A", "A08_NONCE"):
            # Controlled invalid/stale nonce error simulation
            tx_res = self.rpc_client.eth_send_transaction(
                to=self.contract_address,
                data="0xd09de08a",
                nonce=0,  # Deliberately stale nonce (deployer nonce is >0)
            )
            rpc_err = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status=tx_res.status,
                error_message=tx_res.error_message or "Nonce too low",
                duration_ms=tx_res.duration_ms,
                request_params=tx_res.request_params,
                response_result=tx_res.response_result,
            )
            self.record_event(rpc_err, step_name="rpc_nonce_error")
            return {
                "contract": "BenignDAppContract",
                "variant_id": "A08a",
                "failure_type": "NONCE_TOO_LOW",
                "network_calls_made": 0,
                "execution_status": "FAILED" if not tx_res.success else "SUCCESS",
            }

        elif vid in ("A08B", "A08_GAS"):
            # Controlled gas_limit below intrinsic gas simulation
            tx_res = self.rpc_client.eth_send_transaction(
                to=self.contract_address,
                data="0xd09de08a",
                gas=15000,  # Below intrinsic gas 21000
            )
            rpc_err = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status=tx_res.status,
                error_message=tx_res.error_message or "intrinsic gas too low",
                duration_ms=tx_res.duration_ms,
                request_params=tx_res.request_params,
                response_result=tx_res.response_result,
            )
            self.record_event(rpc_err, step_name="rpc_gas_error")
            return {
                "contract": "BenignDAppContract",
                "variant_id": "A08b",
                "failure_type": "INSUFFICIENT_GAS",
                "network_calls_made": 0,
                "execution_status": "FAILED" if not tx_res.success else "SUCCESS",
            }

        else:
            # A04: increment() default baseline (genuine on-chain transaction)
            tx_res = self.rpc_client.eth_send_transaction(
                to=self.contract_address,
                data="0xd09de08a",  # increment() selector
            )
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status=tx_res.status,
                duration_ms=tx_res.duration_ms,
                request_params=tx_res.request_params,
                response_result=tx_res.response_result,
                error_message=tx_res.error_message,
            )
            rpc_event.metadata.update({"scenario": self.scenario_id, "variant_id": "A04"})
            self.record_event(rpc_event, step_name="rpc_transaction")

            if tx_res.success:
                blockchain_event = self.blockchain_collector.collect(
                    contract_name="BenignDAppContract",
                    contract_address=self.contract_address,
                    function_name="increment",
                    tx_hash=tx_res.tx_hash,
                    block_number=tx_res.block_number,
                    sender=tx_res.sender,
                    event_name="CountIncremented",
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
                "execution_status": "SUCCESS" if tx_res.success else "FAILED",
            }

    def teardown(self) -> None:
        """Teardown benign scenario."""
        logger.debug("Scenario A teardown complete")
