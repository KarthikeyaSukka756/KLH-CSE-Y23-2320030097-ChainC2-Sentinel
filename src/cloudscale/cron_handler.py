# ChainC2 Sentinel — Zoho Catalyst Scheduled Cron & Observer Worker
"""Autonomous background observer executing on Zoho Catalyst Cron schedule.

Handles:
1. Ethereum Sepolia network verification (Chain ID 11155111).
2. Incremental block polling and transaction enumeration.
3. Deduplication and idempotent persistence via CatalystStorageAdapter.
4. Credit-aware operation and budget threshold enforcement.
5. Autonomous research experiment triggering in accordance with the locked plan.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.blockchain.monitor import SepoliaMonitor
from src.cloudscale.budget_manager import BudgetOperatingState, CatalystBudgetManager
from src.cloudscale.storage_adapter import CatalystStorageAdapter

logger = logging.getLogger("chainc2_sentinel.cloudscale.cron")


class CatalystCronWorker:
    """Orchestrates periodic observation, autonomous experiment execution, and budget checks."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        budget_manager: Optional[CatalystBudgetManager] = None,
        storage_adapter: Optional[CatalystStorageAdapter] = None,
        monitor: Optional[SepoliaMonitor] = None,
    ) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent.parent
        self.budget_manager = budget_manager or CatalystBudgetManager(repo_root=self.repo_root)
        self.storage_adapter = storage_adapter or CatalystStorageAdapter(repo_root=self.repo_root)
        self.monitor = monitor or SepoliaMonitor.get_instance(repo_root=self.repo_root)

    def run_cron_cycle(
        self,
        auto_trigger_experiment: bool = True,
        block_scan_count: int = 1,
    ) -> dict[str, Any]:
        """Execute one complete cron observation and autonomous experiment cycle.

        Returns:
            Dictionary containing audit report of the cycle execution.
        """
        start_time = time.perf_counter()
        cycle_timestamp = datetime.now(timezone.utc).isoformat()
        cycle_result: dict[str, Any] = {
            "timestamp": cycle_timestamp,
            "status": "COMPLETED",
            "operating_state": self.budget_manager.get_operating_state().value,
            "blocks_polled": 0,
            "new_transactions": 0,
            "experiment_executed": None,
            "messages": [],
        }

        # Step 1: Evaluate Budget Safeguards
        state = self.budget_manager.get_operating_state()
        if state == BudgetOperatingState.SAFE_SHUTDOWN:
            msg = "Cron execution skipped: System is in SAFE_SHUTDOWN to prevent credit exhaustion."
            logger.warning(msg)
            cycle_result["status"] = "SHUTDOWN_PAUSED"
            cycle_result["messages"].append(msg)
            return cycle_result

        # Step 2: Read Monitoring Cursor
        cursor = self.storage_adapter.get_monitoring_cursor()
        last_block = cursor.get("last_block_number")

        # Step 3: Check Sepolia Connection and Chain ID
        conn_info = self.monitor.check_connection()
        if not conn_info.get("is_connected"):
            msg = f"Sepolia connection unavailable: {conn_info.get('last_poll_error')}"
            logger.warning(msg)
            cycle_result["status"] = "RPC_UNAVAILABLE"
            cycle_result["messages"].append(msg)
            elapsed_sec = time.perf_counter() - start_time
            self.budget_manager.record_function_invocation(duration_sec=round(elapsed_sec, 2), memory_mb=256)
            cycle_result["duration_sec"] = round(elapsed_sec, 3)
            cycle_result["remaining_budget_usd"] = self.budget_manager.get_remaining_budget_usd()
            return cycle_result

        latest_network_block = conn_info.get("latest_block")

        # Step 4: Bounded Block Observation
        new_txs_observed = []
        try:
            # Poll latest blocks
            new_txs_observed = self.monitor.poll_latest_blocks(
                block_count=block_scan_count, sample_limit_per_block=20
            )
            cycle_result["blocks_polled"] = block_scan_count
            cycle_result["new_transactions"] = len(new_txs_observed)

            # Persist transactions via storage adapter
            for tx in new_txs_observed:
                self.storage_adapter.save_transaction(tx)

            # Advance cursor
            if latest_network_block:
                self.storage_adapter.save_monitoring_cursor(
                    last_block_number=latest_network_block,
                    polled_at=cycle_timestamp,
                    total_txs_observed=max(self.monitor.cumulative_tx_count, len(self.monitor.observed_transactions)),
                )
        except Exception as e:
            msg = f"Block polling encountered error: {e}"
            logger.error(msg)
            cycle_result["messages"].append(msg)

        # Step 5: Autonomous Experiment Orchestration (if permitted by budget)
        can_exec, reason = self.budget_manager.can_execute_experiment()
        if auto_trigger_experiment and can_exec:
            # Execute alternating controlled experiment in accordance with research plan
            # (Scenario B positive C2 control to validate detection & mitigation)
            try:
                exp_record = self.monitor.execute_controlled_experiment("positive_c2")
                self.storage_adapter.save_experiment_record(exp_record)
                cycle_result["experiment_executed"] = {
                    "run_id": exp_record.get("run_id"),
                    "scenario": exp_record.get("scenario"),
                    "detection_score": exp_record.get("detection_score"),
                    "is_detected": exp_record.get("is_detected"),
                    "mitigation_status": exp_record.get("mitigation_status"),
                }
            except Exception as e:
                msg = f"Autonomous experiment execution encountered error: {e}"
                logger.error(msg)
                cycle_result["messages"].append(msg)
        else:
            cycle_result["messages"].append(f"Experiment execution skipped: {reason}")

        # Step 6: Record Resource Consumption for the Cron Invocation
        elapsed_sec = time.perf_counter() - start_time
        self.budget_manager.record_function_invocation(
            duration_sec=round(elapsed_sec, 2), memory_mb=256
        )
        self.budget_manager.record_datastore_operation(
            op_type="write", count=max(1, len(new_txs_observed))
        )

        cycle_result["duration_sec"] = round(elapsed_sec, 3)
        cycle_result["remaining_budget_usd"] = self.budget_manager.get_remaining_budget_usd()
        return cycle_result


def catalyst_cron_handler(event_data: Any = None, context: Any = None) -> dict[str, Any]:
    """Standard entry point for Zoho Catalyst Cron function execution."""
    worker = CatalystCronWorker()
    return worker.run_cron_cycle(auto_trigger_experiment=True)
