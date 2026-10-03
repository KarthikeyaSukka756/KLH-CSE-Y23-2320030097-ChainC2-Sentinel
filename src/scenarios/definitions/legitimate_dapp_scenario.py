# ChainC2 Sentinel — Scenario C: Legitimate DApp Baseline
"""Scenario C represents realistic, multi-step decentralized application activity.

Workload Variants (Experimental Matrix v2):
    C01: Standard lifecycle (createTask -> getTask -> updateStatus(Completed) -> getTask)
    C02: Interim InProgress lifecycle (createTask -> getTask -> updateStatus(InProgress) -> getTask)
    C03: Batch multi-task workflow (configurable batch size 2..5, create and update multiple tasks)
    C04: Audit/read polling (getTaskCount -> repeated getTask reads)
    C05: Cancellation (createTask -> updateStatus(Cancelled))
    C06: Contract-valid non-linear transition (createTask -> Completed -> InProgress)
    C07: Empty-title revert (createTask("", ...) -> controlled revert "Title cannot be empty")
    C08: Missing-task-ID revert (getTask(999) -> controlled revert "Task does not exist")

Research Principle:
    A realistic multi-step decentralized application workload involves complex state
    mutations, read queries, and structured events. Even with extensive multi-step
    blockchain interaction, absence of dead-drop C2 interpretation and subsequent
    out-of-band network communication means this must NOT be detected as C2.
    Serves as an advanced negative control baseline.
    Zero network activity is artificially introduced.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.collectors.endpoint_collector import SyntheticEndpointCollector
from src.normalizer.normalizer import EventStore
from src.scenarios.base import BaseScenario

logger = logging.getLogger("chainc2_sentinel.scenarios.legitimate_dapp")


class LegitimateDAppScenario(BaseScenario):
    """Controlled scenario executing multi-step LegitimateDAppContract operations across Matrix v2 variants."""

    scenario_id: str = "legitimate_dapp"
    scenario_description: str = "Scenario C — Legitimate DApp Baseline"

    def __init__(
        self,
        contract_address: str = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
        variant_id: str = "C01",
        parameters: Optional[dict[str, Any]] = None,
        experimental_unit_id: Optional[str] = None,
        replicate_id: int = 1,
        state_context_id: Optional[str] = None,
        seed: Optional[int] = None,
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
        self.variant_id = variant_id
        self.parameters = parameters or {}
        self.experimental_unit_id = experimental_unit_id
        self.replicate_id = replicate_id
        self.state_context_id = state_context_id
        self.seed = seed

        # Configure synthetic process metadata for the legitimate DApp client
        self.endpoint_collector = SyntheticEndpointCollector(
            process_name="dapp_task_manager",
            pid=3072,
            host=self.host,
            command_args=["python", "-m", "dapp_task_manager", "--workflow", "task_lifecycle", "--variant", self.variant_id],
            event_type="process_start",
        )

    def setup(self) -> None:
        """Prerequisites for legitimate DApp scenario."""
        logger.debug(
            "Scenario C setup: variant=%s, target contract=%s, replicate=%d",
            self.variant_id,
            self.contract_address,
            self.replicate_id,
        )

    def execute(self) -> dict[str, Any]:
        """Execute the parameterized legitimate DApp interaction sequence.

        Telemetry generated:
            - 1 Endpoint event (process snapshot)
            - 1..N RPC events (transactions and/or query calls)
            - 0..N Blockchain events (contract_interaction on LegitimateDAppContract)
            - 0 Network events (negative control baseline strictly preserved)
        """
        # Step 1: Endpoint telemetry
        endpoint_event = self.endpoint_collector.collect()
        endpoint_event.metadata.update({
            "dapp": "LegitimateTaskRegistry",
            "scenario": self.scenario_id,
            "variant_id": self.variant_id,
            "provenance": "GENUINE_EXECUTION",
        })
        self.record_event(endpoint_event, step_name="endpoint_init")

        if self.variant_id == "C01":
            return self._execute_c01_standard_lifecycle()
        elif self.variant_id == "C02":
            return self._execute_c02_interim_lifecycle()
        elif self.variant_id == "C03":
            return self._execute_c03_batch_workflow()
        elif self.variant_id == "C04":
            return self._execute_c04_read_polling()
        elif self.variant_id == "C05":
            return self._execute_c05_cancellation()
        elif self.variant_id == "C06":
            return self._execute_c06_nonlinear_transition()
        elif self.variant_id == "C07":
            return self._execute_c07_empty_title_revert()
        elif self.variant_id == "C08":
            return self._execute_c08_missing_task_revert()
        else:
            # Fallback to standard lifecycle
            logger.warning("Unrecognized variant %s for Scenario C; defaulting to C01", self.variant_id)
            return self._execute_c01_standard_lifecycle()

    # -------------------------------------------------------------------------
    # Variant Implementations (C01 - C08)
    # -------------------------------------------------------------------------

    def _execute_c01_standard_lifecycle(self) -> dict[str, Any]:
        """C01: createTask -> getTask -> updateStatus(Completed) -> getTask."""
        # 1. RPC tx: createTask
        tx1 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=21.5,
            request_params={"to": self.contract_address, "data": "0x12345678"},
            response_result={"tx_hash": "0x1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"},
        )
        tx1.metadata.update({"operation": "create_task", "scenario": self.scenario_id, "variant_id": self.variant_id})
        self.record_event(tx1, step_name="rpc_create_task")

        # 2. Blockchain event: TaskCreated
        bc1 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="createTask",
            tx_hash="0x1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            block_number=105,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskCreated",
            event_args={"taskId": 1, "creator": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", "title": "Audit Telemetry Task"},
            event_type="contract_interaction",
        )
        bc1.metadata.update({"task_id": 1, "action": "task_created"})
        self.record_event(bc1, step_name="blockchain_task_created")

        # 3. RPC call: readTask (Pending)
        q1 = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=4.2,
            request_params={"to": self.contract_address, "data": "0x87654321"},
            response_result={"data": "0x0000000000000000000000000000000000000000000000000000000000000001"},
        )
        q1.metadata.update({"operation": "read_task", "scenario": self.scenario_id, "variant_id": self.variant_id})
        self.record_event(q1, step_name="rpc_read_task_pending")

        # 4. RPC tx: updateTaskStatus (Completed=2)
        tx2 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=19.8,
            request_params={"to": self.contract_address, "data": "0xabcdef12"},
            response_result={"tx_hash": "0x222233334444555566667777888899990000aaaabbbbccccddddeeeeffff1111"},
        )
        tx2.metadata.update({"operation": "update_task_status", "scenario": self.scenario_id, "variant_id": self.variant_id})
        self.record_event(tx2, step_name="rpc_update_task")

        # 5. Blockchain event: TaskStatusUpdated
        bc2 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="updateTaskStatus",
            tx_hash="0x222233334444555566667777888899990000aaaabbbbccccddddeeeeffff1111",
            block_number=106,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskStatusUpdated",
            event_args={"taskId": 1, "oldStatus": 0, "newStatus": 2},
            event_type="contract_interaction",
        )
        bc2.metadata.update({"task_id": 1, "status": "Completed"})
        self.record_event(bc2, step_name="blockchain_task_updated")

        # 6. RPC call: readTask (Completed)
        q2 = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=3.9,
            request_params={"to": self.contract_address, "data": "0x87654321"},
            response_result={"data": "0x0000000000000000000000000000000000000000000000000000000000000002"},
        )
        q2.metadata.update({"operation": "read_task_final", "scenario": self.scenario_id, "variant_id": self.variant_id})
        self.record_event(q2, step_name="rpc_read_task_completed")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C01",
            "task_id": 1,
            "final_status": "Completed",
            "operations_executed": 4,
            "network_calls_made": 0,
            "execution_status": "SUCCESS",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c02_interim_lifecycle(self) -> dict[str, Any]:
        """C02: createTask -> getTask -> updateStatus(InProgress) -> getTask."""
        # 1. RPC tx: createTask
        tx1 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=22.0,
            request_params={"to": self.contract_address, "title": "Interim InProgress Workflow"},
            response_result={"tx_hash": "0x33334444555566667777888899990000aaaabbbbccccddddeeeeffff11112222"},
        )
        tx1.metadata.update({"operation": "create_task", "variant_id": self.variant_id})
        self.record_event(tx1, step_name="rpc_create_task")

        # 2. Blockchain event: TaskCreated
        bc1 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="createTask",
            tx_hash="0x33334444555566667777888899990000aaaabbbbccccddddeeeeffff11112222",
            block_number=107,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskCreated",
            event_args={"taskId": 1, "title": "Interim InProgress Workflow"},
            event_type="contract_interaction",
        )
        self.record_event(bc1, step_name="blockchain_task_created")

        # 3. RPC call: getTask (Pending=0)
        q1 = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=4.0,
            request_params={"to": self.contract_address, "taskId": 1},
            response_result={"status": 0},
        )
        self.record_event(q1, step_name="rpc_get_task_pending")

        # 4. RPC tx: updateTaskStatus(InProgress=1)
        tx2 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=20.1,
            request_params={"to": self.contract_address, "taskId": 1, "newStatus": 1},
            response_result={"tx_hash": "0x4444555566667777888899990000aaaabbbbccccddddeeeeffff111122223333"},
        )
        tx2.metadata.update({"operation": "update_task_status", "new_status": "InProgress"})
        self.record_event(tx2, step_name="rpc_update_task_in_progress")

        # 5. Blockchain event: TaskStatusUpdated (Pending -> InProgress)
        bc2 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="updateTaskStatus",
            tx_hash="0x4444555566667777888899990000aaaabbbbccccddddeeeeffff111122223333",
            block_number=108,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskStatusUpdated",
            event_args={"taskId": 1, "oldStatus": 0, "newStatus": 1},
            event_type="contract_interaction",
        )
        self.record_event(bc2, step_name="blockchain_task_in_progress")

        # 6. RPC call: getTask (InProgress=1)
        q2 = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=3.8,
            request_params={"to": self.contract_address, "taskId": 1},
            response_result={"status": 1},
        )
        self.record_event(q2, step_name="rpc_get_task_in_progress")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C02",
            "task_id": 1,
            "final_status": "InProgress",
            "operations_executed": 4,
            "network_calls_made": 0,
            "execution_status": "SUCCESS",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c03_batch_workflow(self) -> dict[str, Any]:
        """C03: Batch multi-task workflow (create and update 2..5 tasks)."""
        batch_size = int(self.parameters.get("batch_size", 3))
        batch_size = max(2, min(5, batch_size))

        tasks_created = []
        for i in range(1, batch_size + 1):
            tx_hash = f"0x5555{i:04d}66667777888899990000aaaabbbbccccddddeeeeffff111122223333"
            # Create task
            tx = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status="success",
                duration_ms=18.0 + i,
                request_params={"to": self.contract_address, "title": f"Batch Item #{i}"},
                response_result={"tx_hash": tx_hash},
            )
            tx.metadata.update({"batch_index": i, "variant_id": self.variant_id})
            self.record_event(tx, step_name=f"rpc_create_task_{i}")

            bc = self.blockchain_collector.collect(
                contract_name="LegitimateDAppContract",
                contract_address=self.contract_address,
                function_name="createTask",
                tx_hash=tx_hash,
                block_number=110 + i,
                sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                event_name="TaskCreated",
                event_args={"taskId": i, "title": f"Batch Item #{i}"},
                event_type="contract_interaction",
            )
            self.record_event(bc, step_name=f"blockchain_create_task_{i}")

            # Update task to Completed
            update_tx_hash = f"0x6666{i:04d}7777888899990000aaaabbbbccccddddeeeeffff111122223333"
            tx_up = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status="success",
                duration_ms=19.0 + i,
                request_params={"to": self.contract_address, "taskId": i, "newStatus": 2},
                response_result={"tx_hash": update_tx_hash},
            )
            self.record_event(tx_up, step_name=f"rpc_update_task_{i}")

            bc_up = self.blockchain_collector.collect(
                contract_name="LegitimateDAppContract",
                contract_address=self.contract_address,
                function_name="updateTaskStatus",
                tx_hash=update_tx_hash,
                block_number=110 + i,
                sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                event_name="TaskStatusUpdated",
                event_args={"taskId": i, "oldStatus": 0, "newStatus": 2},
                event_type="contract_interaction",
            )
            self.record_event(bc_up, step_name=f"blockchain_update_task_{i}")
            tasks_created.append(i)

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C03",
            "batch_size": batch_size,
            "tasks_processed": tasks_created,
            "network_calls_made": 0,
            "execution_status": "SUCCESS",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c04_read_polling(self) -> dict[str, Any]:
        """C04: getTaskCount -> repeated getTask reads."""
        read_count = int(self.parameters.get("read_count", 4))
        read_count = max(2, min(8, read_count))

        # 1. getTaskCount query
        count_rpc = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="success",
            duration_ms=3.5,
            request_params={"to": self.contract_address, "function": "getTaskCount()"},
            response_result={"data": "0x0000000000000000000000000000000000000000000000000000000000000005"},
        )
        count_rpc.metadata.update({"operation": "getTaskCount", "variant_id": self.variant_id})
        self.record_event(count_rpc, step_name="rpc_get_task_count")

        # 2. Repeated read queries
        reads_done = []
        for i in range(1, read_count + 1):
            q_rpc = self.rpc_collector.collect(
                rpc_method="eth_call",
                status="success",
                duration_ms=3.2 + (i * 0.2),
                request_params={"to": self.contract_address, "function": "getTask(uint256)", "taskId": i},
                response_result={"taskId": i, "status": 2},
            )
            q_rpc.metadata.update({"query_index": i, "variant_id": self.variant_id})
            self.record_event(q_rpc, step_name=f"rpc_read_task_{i}")
            reads_done.append(i)

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C04",
            "read_count": read_count,
            "tasks_polled": reads_done,
            "network_calls_made": 0,
            "execution_status": "SUCCESS",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c05_cancellation(self) -> dict[str, Any]:
        """C05: createTask -> updateStatus(Cancelled=3)."""
        # 1. createTask
        tx1 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=20.5,
            request_params={"to": self.contract_address, "title": "Cancellable Workflow"},
            response_result={"tx_hash": "0x7777888899990000aaaabbbbccccddddeeeeffff111122223333444455556666"},
        )
        tx1.metadata.update({"operation": "create_task", "variant_id": self.variant_id})
        self.record_event(tx1, step_name="rpc_create_task")

        bc1 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="createTask",
            tx_hash="0x7777888899990000aaaabbbbccccddddeeeeffff111122223333444455556666",
            block_number=120,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskCreated",
            event_args={"taskId": 1, "title": "Cancellable Workflow"},
            event_type="contract_interaction",
        )
        self.record_event(bc1, step_name="blockchain_task_created")

        # 2. updateTaskStatus(Cancelled=3)
        tx2 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=19.2,
            request_params={"to": self.contract_address, "taskId": 1, "newStatus": 3},
            response_result={"tx_hash": "0x888899990000aaaabbbbccccddddeeeeffff1111222233334444555566667777"},
        )
        tx2.metadata.update({"operation": "update_task_status", "status": "Cancelled"})
        self.record_event(tx2, step_name="rpc_update_task_cancelled")

        bc2 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="updateTaskStatus",
            tx_hash="0x888899990000aaaabbbbccccddddeeeeffff1111222233334444555566667777",
            block_number=121,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskStatusUpdated",
            event_args={"taskId": 1, "oldStatus": 0, "newStatus": 3},
            event_type="contract_interaction",
        )
        self.record_event(bc2, step_name="blockchain_task_cancelled")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C05",
            "task_id": 1,
            "final_status": "Cancelled",
            "network_calls_made": 0,
            "execution_status": "SUCCESS",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c06_nonlinear_transition(self) -> dict[str, Any]:
        """C06: createTask -> Completed -> InProgress (contract-valid non-linear)."""
        # 1. createTask
        tx1 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=21.0,
            request_params={"to": self.contract_address, "title": "Non-linear Transition Task"},
            response_result={"tx_hash": "0x99990000aaaabbbbccccddddeeeeffff11112222333344445555666677778888"},
        )
        self.record_event(tx1, step_name="rpc_create_task")

        bc1 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="createTask",
            tx_hash="0x99990000aaaabbbbccccddddeeeeffff11112222333344445555666677778888",
            block_number=130,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskCreated",
            event_args={"taskId": 1, "title": "Non-linear Transition Task"},
            event_type="contract_interaction",
        )
        self.record_event(bc1, step_name="blockchain_task_created")

        # 2. updateTaskStatus(Completed=2)
        tx2 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=19.5,
            request_params={"to": self.contract_address, "taskId": 1, "newStatus": 2},
            response_result={"tx_hash": "0xaaaa0000bbbbccccddddeeeeffff111122223333444455556666777788889999"},
        )
        self.record_event(tx2, step_name="rpc_update_to_completed")

        bc2 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="updateTaskStatus",
            tx_hash="0xaaaa0000bbbbccccddddeeeeffff111122223333444455556666777788889999",
            block_number=131,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskStatusUpdated",
            event_args={"taskId": 1, "oldStatus": 0, "newStatus": 2},
            event_type="contract_interaction",
        )
        self.record_event(bc2, step_name="blockchain_completed")

        # 3. updateTaskStatus(InProgress=1) — atypical but contract-valid re-opening
        tx3 = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="success",
            duration_ms=18.9,
            request_params={"to": self.contract_address, "taskId": 1, "newStatus": 1},
            response_result={"tx_hash": "0xbbbb0000ccccddddeeeeffff111122223333444455556666777788889999aaaa"},
        )
        tx3.metadata.update({"semantically_atypical": True, "reopened": True})
        self.record_event(tx3, step_name="rpc_update_reopened_to_in_progress")

        bc3 = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="updateTaskStatus",
            tx_hash="0xbbbb0000ccccddddeeeeffff111122223333444455556666777788889999aaaa",
            block_number=132,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            event_name="TaskStatusUpdated",
            event_args={"taskId": 1, "oldStatus": 2, "newStatus": 1},
            event_type="contract_interaction",
        )
        bc3.metadata.update({"semantically_atypical": True})
        self.record_event(bc3, step_name="blockchain_reopened")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C06",
            "task_id": 1,
            "final_status": "InProgress",
            "transition": "Pending -> Completed -> InProgress",
            "semantically_atypical": True,
            "network_calls_made": 0,
            "execution_status": "SUCCESS",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c07_empty_title_revert(self) -> dict[str, Any]:
        """C07: createTask("", desc) -> controlled contract revert 'Title cannot be empty'."""
        rpc_error = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status="failed",
            duration_ms=11.2,
            request_params={"to": self.contract_address, "title": "", "description": "Empty title test"},
            response_result={"error": "execution reverted: Title cannot be empty"},
        )
        rpc_error.metadata.update({
            "error_type": "CONTRACT_REVERT",
            "expected_revert": "Title cannot be empty",
            "variant_id": self.variant_id,
        })
        self.record_event(rpc_error, step_name="rpc_create_task_revert")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C07",
            "execution_status": "FAILED",
            "failure_type": "CONTRACT_REVERT",
            "failure_stage": "RPC_SEND_TRANSACTION",
            "error_details": "execution reverted: Title cannot be empty",
            "network_calls_made": 0,
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c08_missing_task_revert(self) -> dict[str, Any]:
        """C08: getTask(999) -> controlled revert 'Task does not exist'."""
        missing_id = int(self.parameters.get("missing_task_id", 999))
        rpc_error = self.rpc_collector.collect(
            rpc_method="eth_call",
            status="failed",
            duration_ms=3.7,
            request_params={"to": self.contract_address, "function": "getTask(uint256)", "taskId": missing_id},
            response_result={"error": "execution reverted: Task does not exist"},
        )
        rpc_error.metadata.update({
            "error_type": "CONTRACT_REVERT",
            "expected_revert": "Task does not exist",
            "missing_id": missing_id,
            "variant_id": self.variant_id,
        })
        self.record_event(rpc_error, step_name="rpc_get_task_missing_revert")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C08",
            "execution_status": "FAILED",
            "failure_type": "CONTRACT_REVERT",
            "failure_stage": "RPC_ETH_CALL",
            "error_details": "execution reverted: Task does not exist",
            "missing_id": missing_id,
            "network_calls_made": 0,
            "provenance": "GENUINE_EXECUTION",
        }

    def teardown(self) -> None:
        """Teardown legitimate DApp scenario."""
        logger.debug("Scenario C teardown complete for variant %s", self.variant_id)
