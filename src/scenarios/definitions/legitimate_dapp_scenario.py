# ChainC2 Sentinel — Scenario C: Legitimate DApp Baseline
"""Scenario C represents realistic, multi-step decentralized application activity.

Workload:
    1. Endpoint process initialized (dapp_task_manager).
    2. Web3 client sends RPC transaction: createTask("Audit Log", "Record entry").
    3. Smart contract interaction executes on LegitimateDAppContract (TaskCreated event emitted).
    4. Web3 client queries state via RPC: eth_call getTask(taskId=1).
    5. Web3 client updates state via RPC transaction: updateTaskStatus(taskId=1, status=Completed).
    6. Smart contract executes update (TaskStatusUpdated event emitted).
    7. Web3 client queries updated state via RPC: eth_call getTask(taskId=1).
    8. Follow-up network activity: NONE.

Research Principle:
    A realistic multi-step decentralized application workload involves complex state
    mutations, read queries, and structured events. Even with extensive multi-step
    blockchain interaction, absence of dead-drop C2 interpretation and subsequent
    out-of-band network communication means this must NOT be detected as C2.
    Serves as an advanced negative control baseline.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.collectors.endpoint_collector import SyntheticEndpointCollector
from src.normalizer.normalizer import EventStore
from src.scenarios.base import BaseScenario

logger = logging.getLogger("chainc2_sentinel.scenarios.legitimate_dapp")


class LegitimateDAppScenario(BaseScenario):
    """Controlled scenario executing multi-step LegitimateDAppContract operations."""

    scenario_id: str = "legitimate_dapp"
    scenario_description: str = "Scenario C — Legitimate DApp Baseline"

    def __init__(
        self,
        contract_address: str = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
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

        # Configure synthetic process metadata for the legitimate DApp client
        self.endpoint_collector = SyntheticEndpointCollector(
            process_name="dapp_task_manager",
            pid=3072,
            host=self.host,
            command_args=["python", "-m", "dapp_task_manager", "--workflow", "task_lifecycle"],
            event_type="process_start",
        )

    def setup(self) -> None:
        """Prerequisites for legitimate DApp scenario."""
        logger.debug("Scenario C setup: target contract is %s", self.contract_address)

    def execute(self) -> dict[str, Any]:
        """Execute the multi-step legitimate DApp interaction sequence.

        Telemetry generated:
            - 1 Endpoint event (process snapshot)
            - 4 RPC events (transactions and query calls)
            - 2 Blockchain events (TaskCreated, TaskStatusUpdated on LegitimateDAppContract)
            - 0 Network events (negative control baseline)
        """
        # Step 1: Endpoint telemetry
        endpoint_event = self.endpoint_collector.collect()
        endpoint_event.metadata.update({"dapp": "LegitimateTaskRegistry", "scenario": self.scenario_id})
        self.record_event(endpoint_event, step_name="endpoint_init")

        # Step 2: RPC transaction — createTask
        rpc_create_tx = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=21.5,
            request_params={
                "to": self.contract_address,
                "data": "0x12345678",  # createTask selector + args
            },
            response_result={
                "tx_hash": "0x1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            },
        )
        rpc_create_tx.metadata.update({"operation": "create_task", "scenario": self.scenario_id})
        self.record_event(rpc_create_tx, step_name="rpc_create_task")

        # Step 3: Blockchain interaction — TaskCreated event
        bc_create_event = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="createTask",
            tx_hash="0x1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            block_number=105,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskCreated",
            event_args={
                "taskId": 1,
                "creator": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                "title": "Audit Telemetry Task",
            },
            event_type="contract_interaction",
        )
        bc_create_event.metadata.update({"task_id": 1, "action": "task_created"})
        self.record_event(bc_create_event, step_name="blockchain_task_created")

        # Step 4: RPC state query — readTask (eth_call)
        rpc_read_call = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=4.2,
            request_params={
                "to": self.contract_address,
                "data": "0x87654321",  # getTask(1)
            },
            response_result={
                "data": "0x0000000000000000000000000000000000000000000000000000000000000001",
            },
        )
        rpc_read_call.metadata.update({"operation": "read_task", "scenario": self.scenario_id})
        self.record_event(rpc_read_call, step_name="rpc_read_task_pending")

        # Step 5: RPC transaction — updateTaskStatus
        rpc_update_tx = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=19.8,
            request_params={
                "to": self.contract_address,
                "data": "0xabcdef12",  # updateTaskStatus(1, Completed)
            },
            response_result={
                "tx_hash": "0x222233334444555566667777888899990000aaaabbbbccccddddeeeeffff1111",
            },
        )
        rpc_update_tx.metadata.update({"operation": "update_task_status", "scenario": self.scenario_id})
        self.record_event(rpc_update_tx, step_name="rpc_update_task")

        # Step 6: Blockchain interaction — TaskStatusUpdated event
        bc_update_event = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="updateTaskStatus",
            tx_hash="0x222233334444555566667777888899990000aaaabbbbccccddddeeeeffff1111",
            block_number=106,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskStatusUpdated",
            event_args={
                "taskId": 1,
                "oldStatus": 0,
                "newStatus": 2,
            },
            event_type="contract_interaction",
        )
        bc_update_event.metadata.update({"task_id": 1, "status": "Completed"})
        self.record_event(bc_update_event, step_name="blockchain_task_updated")

        # Step 7: RPC state query — readTask (eth_call) verify completion
        rpc_read_final = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=3.9,
            request_params={
                "to": self.contract_address,
                "data": "0x87654321",  # getTask(1)
            },
            response_result={
                "data": "0x0000000000000000000000000000000000000000000000000000000000000002",
            },
        )
        rpc_read_final.metadata.update({"operation": "read_task_final", "scenario": self.scenario_id})
        self.record_event(rpc_read_final, step_name="rpc_read_task_completed")

        # Step 8: Follow-up Network Activity: NONE
        # Legitimate decentralized application activity does not perform C2-like beaconing.

        return {
            "contract": "LegitimateDAppContract",
            "task_id": 1,
            "final_status": "Completed",
            "operations_executed": 4,
            "network_calls_made": 0,
        }

    def teardown(self) -> None:
        """Teardown legitimate DApp scenario."""
        logger.debug("Scenario C teardown complete")
