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

from src.blockchain.rpc_client import decode_uint256, encode_two_strings, encode_uint256, encode_uint256_uint8
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
    # Variant Helpers & Implementations (C01 - C08)
    # -------------------------------------------------------------------------

    def _create_task(self, title: str, description: str, step_prefix: str) -> tuple[int, bool]:
        """Send genuine createTask transaction, collect RPC and blockchain telemetry."""
        calldata = "0x292a4585" + encode_two_strings(title, description)
        tx_res = self.rpc_client.eth_send_transaction(to=self.contract_address, data=calldata)
        rpc_event = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status=tx_res.status,
            duration_ms=tx_res.duration_ms,
            request_params={"to": self.contract_address, "title": title, "description": description},
            response_result=tx_res.response_result,
            error_message=tx_res.error_message,
        )
        rpc_event.metadata.update({"operation": "create_task", "scenario": self.scenario_id, "variant_id": self.variant_id})
        self.record_event(rpc_event, step_name=f"{step_prefix}_rpc")

        # Query actual task count to obtain assigned task ID
        task_id = 1
        if tx_res.success:
            count_res = self.rpc_client.eth_call(to=self.contract_address, data="0xc17a340e")
            task_id = decode_uint256(count_res.result or "") if count_res.success else 1

        bc_event = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="createTask",
            tx_hash=tx_res.tx_hash or "",
            block_number=tx_res.block_number,
            sender=tx_res.sender,
            event_name="TaskCreated" if tx_res.success else None,
            event_args={"taskId": task_id, "creator": tx_res.sender, "title": title} if tx_res.success else {},
            event_type="contract_interaction",
        )
        bc_event.metadata.update({"task_id": task_id, "action": "task_created", "gas_used": tx_res.gas_used, "provenance": "GENUINE_EXECUTION"})
        self.record_event(bc_event, step_name=f"{step_prefix}_blockchain")
        return task_id, tx_res.success

    def _update_task_status(self, task_id: int, new_status: int, status_label: str, step_prefix: str) -> bool:
        """Send genuine updateTaskStatus transaction, collect RPC and blockchain telemetry."""
        calldata = "0xab9b6811" + encode_uint256_uint8(task_id, new_status)
        tx_res = self.rpc_client.eth_send_transaction(to=self.contract_address, data=calldata)
        rpc_event = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status=tx_res.status,
            duration_ms=tx_res.duration_ms,
            request_params={"to": self.contract_address, "taskId": task_id, "newStatus": new_status},
            response_result=tx_res.response_result,
            error_message=tx_res.error_message,
        )
        rpc_event.metadata.update({"operation": "update_task_status", "new_status": status_label, "scenario": self.scenario_id, "variant_id": self.variant_id})
        self.record_event(rpc_event, step_name=f"{step_prefix}_rpc")

        bc_event = self.blockchain_collector.collect(
            contract_name="LegitimateDAppContract",
            contract_address=self.contract_address,
            function_name="updateTaskStatus",
            tx_hash=tx_res.tx_hash or "",
            block_number=tx_res.block_number,
            sender=tx_res.sender,
            event_name="TaskStatusUpdated" if tx_res.success else None,
            event_args={"taskId": task_id, "newStatus": new_status} if tx_res.success else {},
            event_type="contract_interaction",
        )
        bc_event.metadata.update({"task_id": task_id, "status": status_label, "gas_used": tx_res.gas_used, "provenance": "GENUINE_EXECUTION"})
        self.record_event(bc_event, step_name=f"{step_prefix}_blockchain")
        return tx_res.success

    def _read_task(self, task_id: int, step_prefix: str) -> bool:
        """Execute genuine getTask call, collect RPC telemetry."""
        calldata = "0x1d65e77e" + encode_uint256(task_id)
        call_res = self.rpc_client.eth_call(to=self.contract_address, data=calldata)
        rpc_event = self.rpc_collector.collect(
            rpc_method="eth_call",
            status=call_res.status,
            duration_ms=call_res.duration_ms,
            request_params=call_res.request_params,
            response_result=call_res.response_result,
            error_message=call_res.error_message,
        )
        rpc_event.metadata.update({"operation": "read_task", "task_id": task_id, "scenario": self.scenario_id, "variant_id": self.variant_id})
        self.record_event(rpc_event, step_name=f"{step_prefix}_rpc")
        return call_res.success

    def _execute_c01_standard_lifecycle(self) -> dict[str, Any]:
        """C01: createTask -> getTask -> updateStatus(Completed) -> getTask."""
        task_id, s1 = self._create_task("Audit Telemetry Task", "Standard lifecycle verification", "rpc_create_task")
        self._read_task(task_id, "rpc_read_task_pending")
        self._update_task_status(task_id, 2, "Completed", "rpc_update_task")
        self._read_task(task_id, "rpc_read_task_completed")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C01",
            "task_id": task_id,
            "final_status": "Completed",
            "operations_executed": 4,
            "network_calls_made": 0,
            "execution_status": "SUCCESS" if s1 else "FAILED",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c02_interim_lifecycle(self) -> dict[str, Any]:
        """C02: createTask -> getTask -> updateStatus(InProgress) -> getTask."""
        task_id, s1 = self._create_task("Interim InProgress Workflow", "Testing interim state", "rpc_create_task")
        self._read_task(task_id, "rpc_get_task_pending")
        self._update_task_status(task_id, 1, "InProgress", "rpc_update_task_in_progress")
        self._read_task(task_id, "rpc_get_task_in_progress")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C02",
            "task_id": task_id,
            "final_status": "InProgress",
            "operations_executed": 4,
            "network_calls_made": 0,
            "execution_status": "SUCCESS" if s1 else "FAILED",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c03_batch_workflow(self) -> dict[str, Any]:
        """C03: Batch multi-task workflow (create and update 2..5 tasks)."""
        batch_size = int(self.parameters.get("batch_size", 3))
        batch_size = max(2, min(5, batch_size))

        tasks_created = []
        for i in range(1, batch_size + 1):
            t_id, _ = self._create_task(f"Batch Item #{i}", f"Batch item description {i}", f"batch_create_{i}")
            self._update_task_status(t_id, 2, "Completed", f"batch_update_{i}")
            tasks_created.append(t_id)

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
        call_count = self.rpc_client.eth_call(to=self.contract_address, data="0xc17a340e")
        count_rpc = self.rpc_collector.collect(
            rpc_method="eth_call",
            status=call_count.status,
            duration_ms=call_count.duration_ms,
            request_params={"to": self.contract_address, "function": "getTaskCount()"},
            response_result=call_count.response_result,
            error_message=call_count.error_message,
        )
        count_rpc.metadata.update({"operation": "getTaskCount", "variant_id": self.variant_id})
        self.record_event(count_rpc, step_name="rpc_get_task_count")
        count_val = decode_uint256(call_count.result or "") if call_count.success else 0

        if count_val == 0:
            t_id, _ = self._create_task("Seed Task for Polling", "Seed task", "seed_task")
            count_val = t_id

        reads_done = []
        for i in range(1, read_count + 1):
            target_id = ((i - 1) % max(1, count_val)) + 1
            self._read_task(target_id, f"rpc_read_task_{i}")
            reads_done.append(target_id)

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
        task_id, s1 = self._create_task("Cancellable Workflow", "Task to be cancelled", "rpc_create_task")
        self._update_task_status(task_id, 3, "Cancelled", "rpc_update_task_cancelled")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C05",
            "task_id": task_id,
            "final_status": "Cancelled",
            "network_calls_made": 0,
            "execution_status": "SUCCESS" if s1 else "FAILED",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c06_nonlinear_transition(self) -> dict[str, Any]:
        """C06: createTask -> Completed -> InProgress (contract-valid non-linear)."""
        task_id, s1 = self._create_task("Non-linear Transition Task", "Testing atypical transition", "rpc_create_task")
        self._update_task_status(task_id, 2, "Completed", "rpc_update_to_completed")
        self._update_task_status(task_id, 1, "InProgress", "rpc_update_reopened_to_in_progress")

        return {
            "contract": "LegitimateDAppContract",
            "variant_id": "C06",
            "task_id": task_id,
            "final_status": "InProgress",
            "transition": "Pending -> Completed -> InProgress",
            "semantically_atypical": True,
            "network_calls_made": 0,
            "execution_status": "SUCCESS" if s1 else "FAILED",
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c07_empty_title_revert(self) -> dict[str, Any]:
        """C07: createTask("", desc) -> controlled contract revert 'Title cannot be empty'."""
        calldata = "0x292a4585" + encode_two_strings("", "Empty title test")
        tx_res = self.rpc_client.eth_send_transaction(to=self.contract_address, data=calldata)

        rpc_error = self.rpc_collector.collect(
            rpc_method="eth_sendTransaction",
            status=tx_res.status,
            duration_ms=tx_res.duration_ms,
            request_params={"to": self.contract_address, "title": "", "description": "Empty title test"},
            response_result=tx_res.response_result,
            error_message=tx_res.error_message,
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
            "error_details": tx_res.error_message or "execution reverted: Title cannot be empty",
            "network_calls_made": 0,
            "provenance": "GENUINE_EXECUTION",
        }

    def _execute_c08_missing_task_revert(self) -> dict[str, Any]:
        """C08: getTask(999999) -> controlled revert 'Task does not exist'."""
        missing_id = int(self.parameters.get("missing_task_id", 999999))
        calldata = "0x1d65e77e" + encode_uint256(missing_id)
        call_res = self.rpc_client.eth_call(to=self.contract_address, data=calldata)

        rpc_error = self.rpc_collector.collect(
            rpc_method="eth_call",
            status=call_res.status,
            duration_ms=call_res.duration_ms,
            request_params={"to": self.contract_address, "function": "getTask(uint256)", "taskId": missing_id},
            response_result=call_res.response_result,
            error_message=call_res.error_message,
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
            "error_details": call_res.error_message or "execution reverted: Task does not exist",
            "missing_id": missing_id,
            "network_calls_made": 0,
            "provenance": "GENUINE_EXECUTION",
        }

    def teardown(self) -> None:
        """Teardown legitimate DApp scenario."""
        logger.debug("Scenario C teardown complete for variant %s", self.variant_id)
