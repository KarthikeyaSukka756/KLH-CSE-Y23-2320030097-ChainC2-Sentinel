# ChainC2 Sentinel — Ethereum Sepolia Testnet Monitor & Experiment Tests
"""Tests for Ethereum Sepolia Testnet monitoring, public transaction observation,
cross-layer correlation, explainable detection, defensive mitigation, and dashboard endpoints.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.blockchain.monitor import SepoliaMonitor
from src.blockchain.rpc_client import SEPOLIA_CHAIN_ID, LocalRpcClient
from src.dashboard.app import create_app


class TestSepoliaMonitor(unittest.TestCase):
    """Unit tests for the SepoliaMonitor service."""

    def setUp(self) -> None:
        self.mock_rpc = MagicMock(spec=LocalRpcClient)
        self.mock_rpc.network = "sepolia"
        self.mock_rpc.rpc_url = "https://ethereum-sepolia-rpc.publicnode.com"
        self.mock_rpc.get_chain_id.return_value = SEPOLIA_CHAIN_ID
        self.mock_rpc.eth_block_number.return_value = 12014150
        self.monitor = SepoliaMonitor(rpc_client=self.mock_rpc)
        # Ensure fresh state per test to isolate from historical telemetry cache on disk
        self.monitor.latest_block = None
        self.monitor.last_ingested_block = None
        self.monitor.last_poll_time = None
        self.monitor.observed_transactions = []
        self.monitor._tx_hashes_seen = set()
        self.monitor.cumulative_tx_count = 0

    def test_sepolia_initialization_and_chain_id(self) -> None:
        """Verify monitor initializes with Sepolia chain ID 11155111 and correct network name."""
        self.assertEqual(str(self.monitor.chain_id), "11155111")
        self.assertEqual(self.monitor.network_name, "sepolia")
        self.assertIn("sepolia.etherscan.io", self.monitor.get_status_summary()["explorer_base"])

    def test_check_connection_success(self) -> None:
        """Verify check_connection updates connection status when RPC responds."""
        status = self.monitor.check_connection()
        self.assertTrue(status["is_connected"])
        self.assertEqual(status["connection_status"], "Connected")
        self.assertEqual(status["latest_block"], 12014150)
        self.assertEqual(str(status["chain_id"]), "11155111")

    def test_check_connection_chain_id_mismatch(self) -> None:
        """Verify monitor rejects non-Sepolia chain IDs."""
        self.mock_rpc.get_chain_id.return_value = 1  # Mainnet
        status = self.monitor.check_connection()
        self.assertFalse(status["is_connected"])
        self.assertEqual(status["connection_status"], "Incorrect chain")

    def test_poll_latest_blocks_normalization(self) -> None:
        """Verify public Sepolia block transactions are normalized and cached."""
        sample_tx = {
            "hash": "0xfeec00ffee00112233445566778899aabbccddeeff00112233445566778899aa",
            "from": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "to": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "value": "0xde0b6b3a7640000",  # 1 ETH
        }
        self.mock_rpc.eth_get_block_by_number.return_value = {
            "number": "0xb753a6",
            "timestamp": "0x66000000",
            "transactions": [sample_tx],
        }

        # Clear any seen hashes to ensure isolation
        self.monitor._tx_hashes_seen.discard(sample_tx["hash"])
        new_txs = self.monitor.poll_latest_blocks(block_count=1)
        self.assertEqual(len(new_txs), 1)
        tx = new_txs[0]
        self.assertEqual(tx["tx_hash"], sample_tx["hash"])
        self.assertEqual(tx["from_address"], sample_tx["from"])
        self.assertEqual(tx["to_address"], sample_tx["to"])
        self.assertEqual(tx["value_eth"], 1.0)
        self.assertIn("https://sepolia.etherscan.io/tx/", tx["explorer_url"])

    def test_positive_c2_experiment_execution(self) -> None:
        """Verify authoritative 9-stage Positive Synthetic C2 experiment on Sepolia."""
        res = self.monitor.execute_controlled_experiment("positive_c2")
        self.assertEqual(res["ground_truth"], "POSITIVE")
        self.assertEqual(res["classification"], "TRUE_POSITIVE")
        self.assertTrue(res["is_detected"])
        self.assertEqual(res["detection_score"], 100.0)
        self.assertEqual(res["threshold"], 80.0)
        self.assertIn(res["mitigation_status"], ("VERIFIED", "PARTIALLY_VERIFIED"))
        self.assertEqual(len(res["timeline"]), 9)
        self.assertEqual(res["timeline"][0]["stage"], 1)
        self.assertEqual(res["timeline"][-1]["stage"], 9)
        self.assertEqual(res["timeline"][-1]["status"], "SUCCESS")

    def test_benign_web3_control_experiment(self) -> None:
        """Verify Benign Web3 Control produces score 35.0, no detection, and SKIPPED mitigation."""
        res = self.monitor.execute_controlled_experiment("benign_web3")
        self.assertEqual(res["ground_truth"], "BENIGN")
        self.assertEqual(res["classification"], "TRUE_NEGATIVE")
        self.assertFalse(res["is_detected"])
        self.assertEqual(res["detection_score"], 35.0)
        self.assertEqual(res["mitigation_status"], "SKIPPED")

    def test_legitimate_dapp_control_experiment(self) -> None:
        """Verify Legitimate DApp Control produces score 35.0, no detection, and SKIPPED mitigation."""
        res = self.monitor.execute_controlled_experiment("legitimate_dapp")
        self.assertEqual(res["ground_truth"], "BENIGN")
        self.assertEqual(res["classification"], "TRUE_NEGATIVE")
        self.assertFalse(res["is_detected"])
        self.assertEqual(res["detection_score"], 35.0)
        self.assertEqual(res["mitigation_status"], "SKIPPED")

    def test_incomplete_sequence_control_experiment(self) -> None:
        """Verify Incomplete Sequence (no beacon) produces score 75.0 (<80.0 threshold) and no detection."""
        res = self.monitor.execute_controlled_experiment("incomplete_sequence")
        self.assertEqual(res["ground_truth"], "BENIGN")
        self.assertEqual(res["classification"], "TRUE_NEGATIVE")
        self.assertFalse(res["is_detected"])
        self.assertEqual(res["detection_score"], 75.0)
        self.assertEqual(res["mitigation_status"], "SKIPPED")

    def test_mitigation_rollback(self) -> None:
        """Verify rollback reverts active defensive mitigations."""
        self.monitor.execute_controlled_experiment("positive_c2")
        rb = self.monitor.rollback_mitigations()
        self.assertEqual(rb["status"], "ROLLBACK_SUCCESS")
        self.assertGreater(rb["actions_rolled_back"], 0)

    def test_continuous_monitoring_lifecycle_and_idempotency(self) -> None:
        """Verify starting/stopping continuous monitoring thread and idempotent duplicate start."""
        # Initial state should be stopped
        self.monitor.stop_continuous_monitoring()
        status_init = self.monitor.get_status_summary()
        self.assertFalse(status_init["monitoring_active"])
        self.assertFalse(status_init["continuous_monitoring_active"])
        self.assertEqual(status_init["daemon_status"], "IDLE")

        # Start monitoring daemon
        started = self.monitor.start_continuous_monitoring(poll_interval_seconds=60.0)
        self.assertTrue(started)
        status_running = self.monitor.get_status_summary()
        self.assertTrue(status_running["monitoring_active"])
        self.assertTrue(status_running["continuous_monitoring_active"])
        self.assertEqual(status_running["daemon_status"], "RUNNING")
        thread_ref = self.monitor._monitor_thread

        # Duplicate start call should be idempotent and not replace existing thread
        started_again = self.monitor.start_continuous_monitoring(poll_interval_seconds=60.0)
        self.assertTrue(started_again)
        self.assertIs(self.monitor._monitor_thread, thread_ref)

        # Stop monitoring daemon
        stopped = self.monitor.stop_continuous_monitoring()
        self.assertTrue(stopped)
        status_stopped = self.monitor.get_status_summary()
        self.assertFalse(status_stopped["monitoring_active"])
        self.assertFalse(status_stopped["continuous_monitoring_active"])
        self.assertEqual(status_stopped["daemon_status"], "IDLE")

    def test_monotonic_cursor_progression(self) -> None:
        """Verify ingestion cursor cannot regress when older or out-of-order blocks are queried."""
        self.monitor.last_ingested_block = 12014150

        # Query older blocks (e.g. 12014140, 12014145)
        self.mock_rpc.eth_get_block_by_number.return_value = {
            "number": hex(12014145),
            "timestamp": "0x66000000",
            "transactions": [],
        }
        self.monitor._ingest_blocks([12014140, 12014145])
        # Cursor MUST NOT regress below 12014150
        self.assertEqual(self.monitor.last_ingested_block, 12014150)

        # Query newer blocks (e.g. 12014155)
        self.mock_rpc.eth_get_block_by_number.return_value = {
            "number": hex(12014155),
            "timestamp": "0x66000000",
            "transactions": [],
        }
        self.monitor._ingest_blocks([12014155])
        # Cursor MUST advance to 12014155
        self.assertEqual(self.monitor.last_ingested_block, 12014155)

    def test_cursor_does_not_skip_unprocessed_blocks(self) -> None:
        """Verify cursor cannot skip past a failed block in a batch."""
        self.monitor.last_ingested_block = 12014150

        # Simulate block 12014151 succeeding, block 12014152 failing, block 12014153 present
        def mock_get_block(bn, full_transactions=True):
            if bn == 12014151:
                return {"number": hex(12014151), "timestamp": "0x66000000", "transactions": []}
            elif bn == 12014152:
                raise RuntimeError("Transient RPC timeout on block 12014152")
            elif bn == 12014153:
                return {"number": hex(12014153), "timestamp": "0x66000000", "transactions": []}
            return None

        self.mock_rpc.eth_get_block_by_number.side_effect = mock_get_block

        # Ingest batch
        self.monitor._ingest_blocks([12014151, 12014152, 12014153])

        # Cursor MUST be 12014151 (the last contiguous success); it must NOT have skipped to 12014153
        self.assertEqual(self.monitor.last_ingested_block, 12014151)
        self.mock_rpc.eth_get_block_by_number.side_effect = None

    def test_cumulative_observed_transactions_unbounded_by_buffer_cap(self) -> None:
        """Verify total_observed_transactions tracks cumulative count even when in-memory buffer is capped."""
        self.monitor.max_buffer_size = 3
        self.monitor.observed_transactions = []
        self.monitor._tx_hashes_seen = set()
        self.monitor.cumulative_tx_count = 0

        # Simulate block with 5 transactions
        txs = [
            {"hash": f"0x{i:064x}", "from": "0x1111", "to": "0x2222", "value": "0x1"}
            for i in range(1, 6)
        ]
        self.mock_rpc.eth_get_block_by_number.return_value = {
            "number": hex(12014160),
            "timestamp": "0x66000000",
            "transactions": txs,
        }
        self.monitor._ingest_blocks([12014160])

        # Buffer should be capped to max_buffer_size (3)
        self.assertEqual(len(self.monitor.observed_transactions), 3)
        status = self.monitor.get_status_summary()
        # Cumulative count must reflect all 5 ingested transactions
        self.assertEqual(status["total_observed_transactions"], 5)
        self.assertEqual(status["buffered_transactions_count"], 3)

    def test_cron_and_monitor_cursor_synchronization(self) -> None:
        """Verify SepoliaMonitor and CatalystStorageAdapter share synchronized cursor state."""
        self.monitor.latest_block = 12014200
        self.monitor.last_ingested_block = 12014198
        self.monitor._persist_cached_state()

        cache_dir = self.monitor._get_cache_dir()
        sep_cursor_path = cache_dir / "sepolia_cursor.json"
        cron_cursor_path = cache_dir / "monitoring_cursor.json"

        self.assertTrue(sep_cursor_path.exists())
        self.assertTrue(cron_cursor_path.exists())

        import json
        cron_data = json.loads(cron_cursor_path.read_text(encoding="utf-8"))
        self.assertEqual(cron_data.get("last_block_number"), 12014198)

    def test_complete_monitoring_lifecycle_with_recovery(self) -> None:
        """Test complete monitoring lifecycle: start -> running -> transient error -> recovery -> stop."""
        self.monitor.stop_continuous_monitoring()

        # Step 1: Start
        self.assertTrue(self.monitor.start_continuous_monitoring(poll_interval_seconds=60.0))
        self.assertTrue(self.monitor.get_status_summary()["continuous_monitoring_active"])

        # Step 2: Ingest blocks
        self.mock_rpc.eth_block_number.return_value = 12014155
        self.mock_rpc.eth_get_block_by_number.return_value = {
            "number": hex(12014155),
            "timestamp": "0x66000000",
            "transactions": [],
        }
        self.monitor.poll_latest_blocks(block_count=1)
        self.assertEqual(self.monitor.last_ingested_block, 12014155)

        # Step 3: Simulate transient RPC error
        self.mock_rpc.eth_block_number.side_effect = RuntimeError("503 Service Unavailable")
        self.monitor.check_connection(force=True)
        self.assertFalse(self.monitor.is_connected)
        self.assertEqual(self.monitor.connection_status, "Temporarily unavailable")
        # Worker thread must still be alive despite transient error
        self.assertTrue(self.monitor.get_status_summary()["continuous_monitoring_active"])

        # Step 4: Simulate RPC recovery
        self.mock_rpc.eth_block_number.side_effect = None
        self.mock_rpc.eth_block_number.return_value = 12014160
        self.monitor.check_connection(force=True)
        self.assertTrue(self.monitor.is_connected)
        self.assertEqual(self.monitor.connection_status, "Connected")
        self.assertEqual(self.monitor.latest_block, 12014160)

        # Step 5: Stop
        self.assertTrue(self.monitor.stop_continuous_monitoring())
        self.assertFalse(self.monitor.get_status_summary()["continuous_monitoring_active"])
        self.assertEqual(self.monitor.get_status_summary()["daemon_status"], "IDLE")


class TestSepoliaDashboardEndpoints(unittest.TestCase):
    """Integration tests for Sepolia dashboard API endpoints."""

    def setUp(self) -> None:
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_api_sepolia_status(self) -> None:
        """Verify GET /api/sepolia/status returns 200 with structured status."""
        resp = self.client.get("/api/sepolia/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(str(data["chain_id"]), "11155111")
        self.assertIn("network", data)
        self.assertIn("rpc_url", data)
        self.assertIn("continuous_monitoring_active", data)
        self.assertIn("daemon_status", data)

    def test_api_cache_control_headers(self) -> None:
        """Verify /api/ endpoints return no-store/no-cache headers to eliminate stale client caching."""
        resp = self.client.get("/api/sepolia/status")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("no-store", resp.headers.get("Cache-Control", ""))
        self.assertIn("no-cache", resp.headers.get("Cache-Control", ""))

    def test_api_sepolia_monitoring_start_stop(self) -> None:
        """Verify POST /api/sepolia/monitoring/start and stop endpoints control the daemon."""
        # Stop first to ensure clean baseline
        stop_resp = self.client.post("/api/sepolia/monitoring/stop")
        self.assertEqual(stop_resp.status_code, 200)

        # Start monitoring
        start_resp = self.client.post("/api/sepolia/monitoring/start?interval=30.0")
        self.assertEqual(start_resp.status_code, 200)
        start_data = start_resp.get_json()
        self.assertTrue(start_data["monitoring_active"])
        self.assertTrue(start_data["continuous_monitoring_active"])

        # Stop monitoring
        stop_resp2 = self.client.post("/api/sepolia/monitoring/stop")
        self.assertEqual(stop_resp2.status_code, 200)
        stop_data = stop_resp2.get_json()
        self.assertFalse(stop_data["monitoring_active"])

    def test_api_sepolia_transactions(self) -> None:
        """Verify GET /api/sepolia/transactions returns transactions list."""
        resp = self.client.get("/api/sepolia/transactions")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("transactions", data)
        self.assertIn("total_returned", data)

    def test_api_sepolia_execute_and_alerts(self) -> None:
        """Verify POST /api/sepolia/execute runs experiment and updates alerts."""
        resp = self.client.post("/api/sepolia/execute", json={"experiment_type": "positive_c2"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["experiment"]["detection_score"], 100.0)

        # Alerts should reflect the detection
        alerts_resp = self.client.get("/api/sepolia/alerts")
        self.assertEqual(alerts_resp.status_code, 200)
        alerts_data = alerts_resp.get_json()
        self.assertGreater(alerts_data["total_alerts"], 0)

    def test_api_sepolia_rollback(self) -> None:
        """Verify POST /api/sepolia/rollback reverts mitigations."""
        resp = self.client.post("/api/sepolia/rollback")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("status", data)


if __name__ == "__main__":
    unittest.main()
