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
