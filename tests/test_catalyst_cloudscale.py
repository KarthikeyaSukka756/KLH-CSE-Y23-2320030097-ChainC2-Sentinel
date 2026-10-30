# ChainC2 Sentinel — Zoho Catalyst CloudScale Unit & Integration Tests
"""Validates Catalyst budget management, storage adaptation, cron automation,
and dashboard endpoints.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.cloudscale.budget_manager import BudgetOperatingState, CatalystBudgetManager
from src.cloudscale.cron_handler import CatalystCronWorker, catalyst_cron_handler
from src.cloudscale.storage_adapter import CatalystStorageAdapter
from src.dashboard.app import create_app


class TestCatalystBudgetManager(unittest.TestCase):
    """Unit tests for the credit-aware budget safety manager."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "budget_state.json"
        self.mgr = CatalystBudgetManager(
            total_budget_usd=250.00, persistence_path=self.state_file
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_initial_state(self) -> None:
        """Verify initial budget is $250.00 with NORMAL operating state."""
        self.assertEqual(self.mgr.total_budget_usd, 250.00)
        self.assertEqual(self.mgr.get_consumed_cost_usd(), 0.0)
        self.assertEqual(self.mgr.get_remaining_budget_usd(), 250.00)
        self.assertEqual(self.mgr.get_percent_consumed(), 0.0)
        self.assertEqual(self.mgr.get_operating_state(), BudgetOperatingState.NORMAL)
        can_exec, _ = self.mgr.can_execute_experiment()
        self.assertTrue(can_exec)

    def test_progressive_safety_thresholds(self) -> None:
        """Verify operating state transitions: NORMAL -> WARNING -> PAUSE -> SHUTDOWN."""
        # 1. WARNING threshold (>= 75% -> $187.50)
        self.mgr.set_actual_billed_cost(190.00)
        self.assertEqual(self.mgr.get_operating_state(), BudgetOperatingState.WARNING)
        can_exec, _ = self.mgr.can_execute_experiment()
        self.assertTrue(can_exec)

        # 2. PAUSE_EXPERIMENTS threshold (>= 90% -> $225.00)
        self.mgr.set_actual_billed_cost(230.00)
        self.assertEqual(self.mgr.get_operating_state(), BudgetOperatingState.PAUSE_EXPERIMENTS)
        can_exec, reason = self.mgr.can_execute_experiment()
        self.assertFalse(can_exec)
        self.assertIn("PAUSED", reason)

        # 3. SAFE_SHUTDOWN threshold (>= 95% -> $237.50)
        self.mgr.set_actual_billed_cost(240.00)
        self.assertEqual(self.mgr.get_operating_state(), BudgetOperatingState.SAFE_SHUTDOWN)
        can_exec, reason = self.mgr.can_execute_experiment()
        self.assertFalse(can_exec)
        self.assertIn("SAFE_SHUTDOWN", reason)

    def test_state_persistence_and_reload(self) -> None:
        """Verify usage counters and actual costs survive manager reload."""
        self.mgr.record_function_invocation(duration_sec=2.0, memory_mb=512)
        self.mgr.record_datastore_operation(op_type="write", count=10)
        self.mgr.record_appsail_runtime(runtime_hours=5.0)

        # Reload from persistence path
        reloaded = CatalystBudgetManager(
            total_budget_usd=250.00, persistence_path=self.state_file
        )
        self.assertEqual(reloaded.usage.function_invocations, 1)
        self.assertEqual(reloaded.usage.datastore_writes, 10)
        self.assertEqual(reloaded.usage.appsail_hours, 5.0)
        self.assertGreater(reloaded.get_consumed_cost_usd(), 0.0)


class TestCatalystStorageAdapter(unittest.TestCase):
    """Unit tests for Catalyst storage adapter and deduplication."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.adapter = CatalystStorageAdapter(repo_root=Path(self.temp_dir.name))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_monitoring_cursor_lifecycle(self) -> None:
        """Verify cursor initializes, updates, and advances block numbers."""
        cursor = self.adapter.get_monitoring_cursor()
        self.assertEqual(cursor["chain_id"], 11155111)
        self.assertIsNone(cursor["last_block_number"])

        self.adapter.save_monitoring_cursor(last_block_number=12014200, total_txs_observed=15)
        updated = self.adapter.get_monitoring_cursor()
        self.assertEqual(updated["last_block_number"], 12014200)
        self.assertEqual(updated["total_observed_transactions"], 15)
        self.assertEqual(updated["total_polled_blocks"], 1)

    def test_transaction_deduplication(self) -> None:
        """Verify transaction records are deduplicated by hash (idempotent writes)."""
        tx = {
            "tx_hash": "0xaaaabbbbccccdddd1111222233334444555566667777888899990000aaaabbbb",
            "block_number": 12014201,
            "from_address": "0x1111111111111111111111111111111111111111",
            "to_address": "0x2222222222222222222222222222222222222222",
            "value_eth": 0.5,
        }
        # First write succeeds
        self.assertTrue(self.adapter.save_transaction(tx))
        # Second write of identical hash is rejected as duplicate
        self.assertFalse(self.adapter.save_transaction(tx))

        txs = self.adapter.get_transactions()
        self.assertEqual(len(txs), 1)

    def test_experiment_record_persistence(self) -> None:
        """Verify experiment records are stored and retrieved."""
        exp = {
            "run_id": "run-test-001",
            "scenario": "scenario_b_synthetic_c2",
            "ground_truth": "POSITIVE",
            "detection_score": 100.0,
            "is_detected": True,
            "mitigation_status": "VERIFIED",
        }
        self.adapter.save_experiment_record(exp)
        exps = self.adapter.get_experiments()
        self.assertEqual(len(exps), 1)
        self.assertEqual(exps[0]["run_id"], "run-test-001")


class TestCatalystCronWorker(unittest.TestCase):
    """Unit tests for the scheduled Catalyst Cron worker."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.budget_mgr = CatalystBudgetManager(
            total_budget_usd=250.00,
            persistence_path=root / "budget.json",
        )
        self.storage_adapter = CatalystStorageAdapter(repo_root=root)
        self.worker = CatalystCronWorker(
            repo_root=root,
            budget_manager=self.budget_mgr,
            storage_adapter=self.storage_adapter,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cron_cycle_execution(self) -> None:
        """Verify a cron cycle executes observation, updates cursor, and records budget."""
        self.worker.monitor = MagicMock()
        self.worker.monitor.check_connection.return_value = {
            "is_connected": True,
            "latest_block": 12014250,
        }
        self.worker.monitor.poll_latest_blocks.return_value = [
            {
                "tx_hash": "0x9999888877776666555544443333222211110000aaaabbbbccccddddeeeeffff",
                "block_number": 12014250,
                "from_address": "0x1111111111111111111111111111111111111111",
                "to_address": "0x2222222222222222222222222222222222222222",
                "value_eth": 1.25,
            }
        ]
        self.worker.monitor.observed_transactions = self.worker.monitor.poll_latest_blocks.return_value

        report = self.worker.run_cron_cycle(auto_trigger_experiment=False, block_scan_count=1)
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(report["blocks_polled"], 1)
        self.assertEqual(report["new_transactions"], 1)
        self.assertGreater(self.budget_mgr.usage.function_invocations, 0)

    def test_cron_cycle_shutdown_safe_halt(self) -> None:
        """Verify cron halts immediately when budget reaches SAFE_SHUTDOWN."""
        self.budget_mgr.set_actual_billed_cost(245.00)  # > 95%
        report = self.worker.run_cron_cycle(auto_trigger_experiment=True)
        self.assertEqual(report["status"], "SHUTDOWN_PAUSED")
        self.assertIn("SAFE_SHUTDOWN", report["messages"][0])


class TestCatalystDashboardEndpoints(unittest.TestCase):
    """Integration tests for CloudScale REST API routes."""

    def setUp(self) -> None:
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_api_cloudscale_budget(self) -> None:
        """Verify GET /api/cloudscale/budget returns 200 with structured budget data."""
        resp = self.client.get("/api/cloudscale/budget")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["authorized_budget_usd"], 250.00)
        self.assertIn("operating_state", data)
        self.assertIn("remaining_budget_usd", data)

    def test_api_cloudscale_status(self) -> None:
        """Verify GET /api/cloudscale/status returns 200 with cursor and budget."""
        resp = self.client.get("/api/cloudscale/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("budget", data)
        self.assertIn("cursor", data)
        self.assertEqual(data["version"], "2.0.0-catalyst")

    def test_api_cloudscale_cron_trigger(self) -> None:
        """Verify POST /api/cloudscale/cron/trigger executes a cycle."""
        resp = self.client.post("/api/cloudscale/cron/trigger")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("status", data)
        self.assertIn("operating_state", data)


if __name__ == "__main__":
    unittest.main()
