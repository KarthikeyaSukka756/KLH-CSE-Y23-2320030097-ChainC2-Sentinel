# ChainC2 Sentinel — Regression Tests for Defects A, B, and C
"""Automated regression verification suite covering:
1. Defect A: Synthetic C2 scenario pre-seeding transaction validation and fail-closed setup.
2. Defect B: Missing transaction receipt handling and unconfirmed transaction classification.
3. Defect C: Bytecode verification enforcement in ScenarioRunner and alignment verification.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.blockchain.deployment import (
    DEFAULT_DEPLOYMENT_PATH,
    DeploymentResolutionError,
    verify_contract_bytecode,
    verify_rpc_and_registry_alignment,
)
from src.blockchain.rpc_client import (
    LocalRpcClient,
    RpcCallResult,
    RpcTxResult,
    encode_string,
)
from src.collectors.rpc_collector import RpcTelemetryCollector
from src.http_target.server import LocalHttpTargetServer
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.payload import SyntheticC2Payload
from src.scenarios.runner import ScenarioRunner


# ===========================================================================
# Defect A: Synthetic C2 Scenario Pre-Seeding Regression Tests
# ===========================================================================

@pytest.mark.unit
class TestDefectAPreSeedingVerification:
    """Verifies that SyntheticC2Scenario.setup() enforces strict transaction confirmation."""

    def test_defect_a_rpc_client_raises_exception_during_eth_call(self):
        """1. When querying C2DataStore state raises an RPC exception, setup fails closed."""
        mock_client = MagicMock()
        mock_client.eth_call.side_effect = RuntimeError("RPC connection refused")
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-1",
        )
        with pytest.raises(RuntimeError, match="Scenario B setup failed: error querying C2DataStore state"):
            scenario.setup()

    def test_defect_a_tx_submission_returns_success_false(self):
        """2. When pre-seeding transaction returns success=False, setup fails closed."""
        mock_client = MagicMock()
        # Contract currently empty or needs seed
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result="0x",
            error_message=None,
            duration_ms=1.0,
            request_params={},
        )
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=False,
            status="error",
            tx_hash=None,
            block_number=None,
            gas_used=None,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            error_message="Nonce too low",
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-2",
        )
        with pytest.raises(RuntimeError, match="pre-seeding transaction was not successful"):
            scenario.setup()

    def test_defect_a_tx_result_missing_tx_hash_fails_closed(self):
        """3b. When transaction result has success=True but tx_hash is None/empty, setup fails closed."""
        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result="0x",
            error_message=None,
            duration_ms=1.0,
            request_params={},
        )
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=True,
            status="success",
            tx_hash=None,
            block_number=None,
            gas_used=None,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            response_result={"receipt": {"status": "0x1"}},
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-3b",
        )
        with pytest.raises(RuntimeError, match="missing transaction hash"):
            scenario.setup()

    def test_defect_a_tx_result_has_no_confirmed_receipt(self):
        """3. When transaction receipt is unconfirmed (timed out), setup fails closed."""
        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result="0x",
            error_message=None,
            duration_ms=1.0,
            request_params={},
        )
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=False,
            status="unconfirmed",
            tx_hash="0x" + "a" * 64,
            block_number=None,
            gas_used=None,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            error_message="Receipt timed out",
            response_result={"tx_hash": "0x" + "a" * 64},
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-3",
        )
        with pytest.raises(RuntimeError, match="pre-seeding transaction was not successful"):
            scenario.setup()

    def test_defect_a_receipt_is_explicitly_failed(self):
        """4. When receipt status indicates on-chain revert (0x0), setup fails closed."""
        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result="0x",
            error_message=None,
            duration_ms=1.0,
            request_params={},
        )
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=False,
            status="error",
            tx_hash="0x" + "b" * 64,
            block_number=100,
            gas_used=21000,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            receipt_status="0x0",
            error_message="Transaction reverted on-chain (status 0x0)",
            response_result={"receipt": {"status": "0x0"}},
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-4",
        )
        with pytest.raises(RuntimeError, match="pre-seeding transaction was not successful"):
            scenario.setup()

    def test_defect_a_receipt_data_is_malformed(self):
        """5. When receipt object is malformed or not a dictionary, setup fails closed."""
        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result="0x",
            error_message=None,
            duration_ms=1.0,
            request_params={},
        )
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=True,
            status="success",
            tx_hash="0x" + "c" * 64,
            block_number=101,
            gas_used=21000,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            response_result={"receipt": "NOT_A_DICT"},
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-5",
        )
        with pytest.raises(RuntimeError, match="has no verified receipt data"):
            scenario.setup()

    def test_defect_a_valid_transaction_receipt_is_confirmed(self):
        """6. When pre-seeding transaction receipt has status 0x1, setup succeeds."""
        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result="0x",
            error_message=None,
            duration_ms=1.0,
            request_params={},
        )
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=True,
            status="success",
            tx_hash="0x" + "d" * 64,
            block_number=102,
            gas_used=21000,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            response_result={"receipt": {"status": "0x1"}},
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-6",
        )
        scenario.setup()
        assert mock_client.eth_send_transaction.call_count == 1

    def test_defect_a_existing_correct_state_avoids_unnecessary_seeding(self):
        """7. When on-chain state already holds the correct beacon target, seeding is skipped."""
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"
        payload = SyntheticC2Payload(command="BEACON", target=mock_target.beacon_url).to_blockchain_string()

        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result="0x" + encode_string(payload),
            error_message=None,
            duration_ms=1.0,
            request_params={},
        )

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-7",
        )
        scenario.setup()
        assert mock_client.eth_send_transaction.call_count == 0

    def test_defect_a_setup_failure_prevents_scenario_execution(self):
        """8. When setup fails, scenario.run() returns success=False and does not execute."""
        mock_client = MagicMock()
        mock_client.eth_call.side_effect = RuntimeError("Offline node")
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            target_server=mock_target,
            rpc_client=mock_client,
            run_id="run-defect-a-8",
        )
        result = scenario.run()
        assert result.success is False
        assert "Scenario B setup failed" in str(result.error)
        assert len(result.events) == 0


# ===========================================================================
# Defect B: Missing Transaction Receipt Classification Regression Tests
# ===========================================================================

@pytest.mark.unit
class TestDefectBTransactionReceiptClassification:
    """Verifies that LocalRpcClient.eth_send_transaction() never reports unconfirmed tx as success."""

    def test_defect_b_transaction_submission_failure(self):
        """1. When RPC returns an error object, success=False and status='error'."""
        client = LocalRpcClient(network="localhost")
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"error": {"code": -32000, "message": "insufficient funds"}}
            mock_post.return_value = mock_resp

            res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
            assert res.success is False
            assert res.status == "error"
            assert "insufficient funds" in res.error_message
            assert res.tx_hash is None

    def test_defect_b_missing_receipt_until_timeout(self):
        """2. When receipt polling returns None after retries, returns success=False and status='unconfirmed'."""
        client = LocalRpcClient(network="localhost")
        with patch("requests.post") as mock_post:
            tx_resp = MagicMock()
            tx_resp.json.return_value = {"result": "0x" + "e" * 64}
            # All receipt queries return None
            receipt_resp = MagicMock()
            receipt_resp.json.return_value = {"result": None}

            mock_post.side_effect = [tx_resp] + [receipt_resp] * 5

            res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
            assert res.success is False
            assert res.status == "unconfirmed"
            assert res.tx_hash == "0x" + "e" * 64
            assert "unconfirmed/timed out" in res.error_message

    def test_defect_b_receipt_polling_raises_exception(self):
        """3. When receipt polling encounters connection error, returns unconfirmed and preserves tx_hash."""
        client = LocalRpcClient(network="localhost")
        with patch("requests.post") as mock_post:
            tx_resp = MagicMock()
            tx_resp.json.return_value = {"result": "0x" + "f" * 64}
            mock_post.side_effect = [tx_resp, requests.exceptions.Timeout("Receipt timeout")]

            res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
            assert res.success is False
            assert res.status == "unconfirmed"
            assert res.tx_hash == "0x" + "f" * 64

    def test_defect_b_receipt_polling_returns_malformed_data(self):
        """4. When receipt is not a dict (e.g. integer or string), returns status='error'."""
        client = LocalRpcClient(network="localhost")
        with patch("requests.post") as mock_post:
            tx_resp = MagicMock()
            tx_resp.json.return_value = {"result": "0x" + "1" * 64}
            receipt_resp = MagicMock()
            receipt_resp.json.return_value = {"result": "MALFORMED_RECEIPT_STRING"}
            mock_post.side_effect = [tx_resp, receipt_resp]

            res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
            assert res.success is False
            assert res.status == "error"
            assert "Malformed transaction receipt" in res.error_message

    def test_defect_b_receipt_status_indicates_failure(self):
        """5. When receipt status is 0x0, returns success=False and status='error'."""
        client = LocalRpcClient(network="localhost")
        with patch("requests.post") as mock_post:
            tx_resp = MagicMock()
            tx_resp.json.return_value = {"result": "0x" + "2" * 64}
            receipt_resp = MagicMock()
            receipt_resp.json.return_value = {
                "result": {
                    "status": "0x0",
                    "blockNumber": "0x10",
                    "gasUsed": "0x5208",
                    "logs": [],
                }
            }
            mock_post.side_effect = [tx_resp, receipt_resp]

            res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
            assert res.success is False
            assert res.status == "error"
            assert "Transaction reverted" in res.error_message
            assert res.receipt_status == "0x0"
            assert res.block_number == 16
            assert res.gas_used == 21000

    def test_defect_b_receipt_status_indicates_success(self):
        """6. When receipt status is 0x1, returns success=True and status='success'."""
        client = LocalRpcClient(network="localhost")
        with patch("requests.post") as mock_post:
            tx_resp = MagicMock()
            tx_resp.json.return_value = {"result": "0x" + "3" * 64}
            receipt_resp = MagicMock()
            receipt_resp.json.return_value = {
                "result": {
                    "status": "0x1",
                    "blockNumber": "0x20",
                    "gasUsed": "0x7a120",
                    "logs": [{"address": "0x5FbDB2315678afecb367f032d93F642f64180aa3"}],
                }
            }
            mock_post.side_effect = [tx_resp, receipt_resp]

            res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
            assert res.success is True
            assert res.status == "success"
            assert res.receipt_status == "0x1"
            assert res.block_number == 32
            assert res.gas_used == 500000
            assert len(res.logs) == 1

    def test_defect_b_polling_respects_max_retries(self):
        """8. Receipt polling does not loop indefinitely and respects max_retries."""
        client = LocalRpcClient(network="localhost")
        with patch("requests.post") as mock_post:
            receipt_resp = MagicMock()
            receipt_resp.json.return_value = {"result": None}
            mock_post.return_value = receipt_resp

            receipt = client.get_transaction_receipt("0x" + "4" * 64, max_retries=3)
            assert receipt is None
            assert mock_post.call_count == 3

    def test_defect_b_rpc_collector_unconfirmed_status_normalized_to_error_with_diagnostic_preserved(self):
        """9. RpcTelemetryCollector normalizes 'unconfirmed' status to 'error' while preserving diagnostic context."""
        collector = RpcTelemetryCollector(
            rpc_endpoint="http://127.0.0.1:8546",
            upstream_endpoint="http://127.0.0.1:8545",
            host="127.0.0.1",
        )
        # Pass status="unconfirmed" with error_message
        event = collector.collect(
            rpc_method="eth_sendTransaction",
            status="unconfirmed",
            error_message="Transaction receipt unconfirmed/timed out for tx_hash: 0xabc",
            request_params={"to": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
            response_result={"tx_hash": "0xabc", "error": "timed out"},
        )
        assert event.rpc is not None
        assert event.rpc.status == "error"  # Pydantic schema expects 'error', not 'unconfirmed'
        assert "unconfirmed/timed out" in event.rpc.error_message
        assert event.rpc.response_result.get("tx_hash") == "0xabc"

        # Pass status="unconfirmed" without error_message to test fallback diagnostic string
        event2 = collector.collect(
            rpc_method="eth_sendTransaction",
            status="unconfirmed",
            error_message=None,
        )
        assert event2.rpc is not None
        assert event2.rpc.status == "error"
        assert event2.rpc.error_message == "RPC operation failed with status: unconfirmed"


# ===========================================================================
# Defect C: Bytecode Verification Enforcement Regression Tests
# ===========================================================================

@pytest.mark.unit
class TestDefectCBytecodeVerificationEnforcement:
    """Verifies that bytecode verification cannot be bypassed through ordinary runner or alignment paths."""

    def test_defect_c_contract_address_returns_0x_empty_bytecode(self):
        """1. When contract address returns '0x' bytecode, alignment fails closed."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        client.eth_get_code.return_value = "0x"

        with pytest.raises(DeploymentResolutionError, match="has no on-chain bytecode"):
            verify_rpc_and_registry_alignment(client, "localhost", verify_bytecode=True)

    def test_defect_c_contract_address_returns_valid_bytecode(self):
        """2. When contract addresses return valid bytecode, alignment succeeds."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        client.eth_get_code.return_value = "0x608060405234801561001057600080fd5b50"

        addresses = verify_rpc_and_registry_alignment(client, "localhost", verify_bytecode=True)
        assert len(addresses) == 3
        assert "C2DataStore" in addresses

    def test_defect_c_rpc_request_raises_exception_during_bytecode_check(self):
        """3. When eth_get_code query raises an RPC exception, verification fails closed."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        client.eth_get_code.side_effect = RuntimeError("RPC dropped connection")

        with pytest.raises(DeploymentResolutionError, match="RPC error querying bytecode"):
            verify_rpc_and_registry_alignment(client, "localhost", verify_bytecode=True)

    def test_defect_c_rpc_response_is_malformed_during_bytecode_check(self):
        """4. When eth_get_code returns malformed non-hex data, verification fails closed."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        client.eth_get_code.return_value = 12345  # Not a string starting with 0x

        with pytest.raises(DeploymentResolutionError, match="has no on-chain bytecode"):
            verify_rpc_and_registry_alignment(client, "localhost", verify_bytecode=True)

    def test_defect_c_chain_id_is_wrong(self):
        """5. When chain ID is wrong, alignment aborts before bytecode check."""
        client = MagicMock()
        client.get_chain_id.return_value = "1"  # Mainnet chain ID on local network

        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            verify_rpc_and_registry_alignment(client, "localhost", verify_bytecode=True)

    def test_defect_c_registry_metadata_is_inconsistent(self, tmp_path: Path):
        """6. Inconsistent registry metadata fails closed."""
        bad_reg = tmp_path / "bad_reg.json"
        bad_reg.write_text(json.dumps({
            "network": "localhost",
            "chainId": "9999",
            "contracts": {},
        }), encoding="utf-8")

        client = MagicMock()
        client.get_chain_id.return_value = "31337"

        with pytest.raises(DeploymentResolutionError, match="chain ID mismatch"):
            verify_rpc_and_registry_alignment(client, "localhost", deployment_path=str(bad_reg))

    def test_defect_c_one_required_contract_has_no_bytecode(self):
        """7. When one contract has valid bytecode but another has '0x', alignment fails closed."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"

        def _get_code(addr: str) -> str:
            # Let C2DataStore have bytecode, but BenignDApp have '0x'
            if addr == "0x5FbDB2315678afecb367f032d93F642f64180aa3":
                return "0x60806040"
            return "0x"

        client.eth_get_code.side_effect = _get_code

        with pytest.raises(DeploymentResolutionError, match="has no on-chain bytecode"):
            verify_rpc_and_registry_alignment(client, "localhost", verify_bytecode=True)

    def test_defect_c_verification_failure_prevents_scenario_execution(self):
        """8. Verification failure in validate_live_rpc_alignment() prevents scenario run."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        client.eth_get_code.return_value = "0x"  # Missing bytecode

        runner = ScenarioRunner(network="localhost", rpc_client=client)

        with pytest.raises(DeploymentResolutionError, match="has no on-chain bytecode"):
            runner.run_benign()

    def test_defect_c_valid_local_deployment_passes_alignment_verification(self):
        """9. Valid local deployment with deployed bytecode passes alignment verification cleanly."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        client.eth_get_code.return_value = "0x608060405234801561001057600080fd5b50"

        runner = ScenarioRunner(network="localhost", rpc_client=client)
        addrs = runner.validate_live_rpc_alignment()
        assert len(addrs) == 3
        assert addrs["C2DataStore"] == "0x5FbDB2315678afecb367f032d93F642f64180aa3"

    def test_defect_c_default_runner_path_does_not_silently_skip_bytecode_verification(self):
        """10. The default runner path strictly enforces verify_bytecode=True."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        # Provide client WITHOUT eth_get_code method
        del client.eth_get_code

        runner = ScenarioRunner(network="localhost", rpc_client=client)
        with pytest.raises(DeploymentResolutionError, match="does not support eth_get_code"):
            runner.validate_live_rpc_alignment()

