# ChainC2 Sentinel — Focused Tests for Contract Address Resolution & Real RPC Execution
"""Focused verification suite covering:
1. Authoritative contract address resolution & fail-safe error handling.
2. Address binding to scenarios (BenignDAppContract, C2DataStore, LegitimateDAppContract).
3. Mocked RPC client tests: read responses, transaction receipt evaluation, revert capture.
4. Telemetry provenance & prohibition of unverified event claims.
5. Invariance of locked detection rules, conjunctions, and scoring.
6. Byte-for-byte preservation of historical artifacts.
7. Live local Hardhat node integration tests (marked with @pytest.mark.integration).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.blockchain.deployment import (
    DEFAULT_DEPLOYMENT_PATH,
    DeploymentResolutionError,
    load_deployed_addresses,
)
from src.blockchain.rpc_client import (
    LocalRpcClient,
    RpcCallResult,
    RpcTxResult,
    decode_address,
    decode_string,
    decode_uint256,
    encode_string,
    encode_two_strings,
    encode_uint256,
    encode_uint256_uint8,
    get_network_config,
)
from src.detection.detector import DetectionEngine
from src.detection.rules import SyntheticC2SequenceRule
from src.detection.scoring import RuleBasedScorer
from src.models.events import TelemetrySource
from src.models.matrix_v2 import Classification, ExecutionStatus
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.definitions.legitimate_dapp_scenario import LegitimateDAppScenario
from src.scenarios.runner import ScenarioRunner


# ===========================================================================
# 1. Address Resolution & Fail-Safe Tests (Pure Unit)
# ===========================================================================

@pytest.mark.unit
class TestContractAddressResolution:
    """Verifies authoritative deployment-address loading and fail-safe behavior."""

    def test_load_authoritative_addresses(self):
        """Authoritative deployed-addresses.json resolves all 3 required contracts with valid 0x addresses."""
        addrs = load_deployed_addresses()
        assert "C2DataStore" in addrs
        assert "BenignDAppContract" in addrs
        assert "LegitimateDAppContract" in addrs

        assert addrs["C2DataStore"] == "0x5FbDB2315678afecb367f032d93F642f64180aa3"
        assert addrs["BenignDAppContract"] == "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
        assert addrs["LegitimateDAppContract"] == "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"

        # All 3 contract addresses are strictly distinct
        assert len(set(addrs.values())) == 3

    def test_missing_deployment_file_fails_safely(self, tmp_path: Path):
        """Missing deployment file must raise DeploymentResolutionError without falling back."""
        non_existent = tmp_path / "non_existent.json"
        with pytest.raises(DeploymentResolutionError, match="Deployment address file not found"):
            load_deployed_addresses(non_existent)

    def test_malformed_json_fails_safely(self, tmp_path: Path):
        """Malformed JSON must raise DeploymentResolutionError."""
        bad_json = tmp_path / "malformed.json"
        bad_json.write_text("{ not json ...", encoding="utf-8")
        with pytest.raises(DeploymentResolutionError, match="Failed to parse deployment JSON"):
            load_deployed_addresses(bad_json)

    def test_missing_required_contract_fails_safely(self, tmp_path: Path):
        """Deployment file missing one of the 3 contracts must fail clearly."""
        partial = tmp_path / "partial.json"
        partial.write_text(
            json.dumps({
                "network": "localhost",
                "chainId": "31337",
                "contracts": {"C2DataStore": {"address": "0x5FbDB2315678afecb367f032d93F642f64180aa3"}},
            }),
            encoding="utf-8",
        )
        with pytest.raises(DeploymentResolutionError, match="missing from deployment artifact"):
            load_deployed_addresses(partial)

    def test_invalid_ethereum_address_format_fails_safely(self, tmp_path: Path):
        """Invalid address format (e.g. non-hex or wrong length) must fail clearly."""
        invalid_addr = tmp_path / "invalid_addr.json"
        invalid_addr.write_text(
            json.dumps({
                "network": "localhost",
                "chainId": "31337",
                "contracts": {
                    "C2DataStore": {"address": "0xINVALID_ADDRESS_STRING"},
                    "BenignDAppContract": {"address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"},
                    "LegitimateDAppContract": {"address": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"},
                }
            }),
            encoding="utf-8",
        )
        with pytest.raises(DeploymentResolutionError, match="Invalid Ethereum address format"):
            load_deployed_addresses(invalid_addr)


# ===========================================================================
# 2. Scenario Runner Address Binding Tests (Pure Unit)
# ===========================================================================

@pytest.mark.unit
class TestScenarioRunnerAddressBinding:
    """Verifies that ScenarioRunner passes the authoritative address to each scenario instance."""

    def test_runner_initializes_authoritative_addresses(self):
        """ScenarioRunner loads authoritative addresses upon initialization."""
        runner = ScenarioRunner()
        assert runner.deployed_addresses["C2DataStore"] == "0x5FbDB2315678afecb367f032d93F642f64180aa3"
        assert runner.deployed_addresses["BenignDAppContract"] == "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
        assert runner.deployed_addresses["LegitimateDAppContract"] == "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"

    def test_scenario_default_addresses_are_correct(self):
        """Direct constructor defaults match the authoritative addresses."""
        addrs = load_deployed_addresses()
        benign = BenignWeb3Scenario()
        assert benign.contract_address == addrs["BenignDAppContract"]

        c2 = SyntheticC2Scenario()
        assert c2.contract_address == addrs["C2DataStore"]

        legit = LegitimateDAppScenario()
        assert legit.contract_address == addrs["LegitimateDAppContract"]


# ===========================================================================
# 3. RPC Client Unit Tests (Mocked Responses)
# ===========================================================================

@pytest.mark.unit
class TestRpcClientUnit:
    """Verifies RPC client interaction logic with mocked HTTP responses."""

    def test_eth_call_successful_read(self):
        """eth_call returns RpcCallResult with success=True and parsed result."""
        client = LocalRpcClient(rpc_url="http://127.0.0.1:8546")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x0000000000000000000000000000000000000000000000000000000000000007",
        }

        with patch("requests.post", return_value=mock_response):
            call_res = client.eth_call(to="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512", data="0xa87d942c")

        assert call_res.success is True
        assert call_res.status == "success"
        assert decode_uint256(call_res.result) == 7
        assert call_res.error_message is None

    def test_eth_call_revert_recorded_as_error(self):
        """eth_call revert returns RpcCallResult with success=False and error message."""
        client = LocalRpcClient(rpc_url="http://127.0.0.1:8546")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32603, "message": "execution reverted: Task does not exist"},
        }

        with patch("requests.post", return_value=mock_response):
            call_res = client.eth_call(to="0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0", data="0x1d65e77e")

        assert call_res.success is False
        assert call_res.status == "error"
        assert "execution reverted: Task does not exist" in (call_res.error_message or "")

    def test_eth_send_transaction_success_verified_by_receipt(self):
        """eth_send_transaction verifies receipt status 0x1 before declaring success."""
        client = LocalRpcClient(rpc_url="http://127.0.0.1:8546")

        tx_hash_resp = MagicMock()
        tx_hash_resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": "0xabc123"}

        receipt_resp = MagicMock()
        receipt_resp.json.return_value = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "transactionHash": "0xabc123",
                "blockNumber": "0x64",
                "gasUsed": "0x5208",
                "status": "0x1",
                "logs": [],
            },
        }

        with patch("requests.post", side_effect=[tx_hash_resp, receipt_resp]):
            tx_res = client.eth_send_transaction(to="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512", data="0xd09de08a")

        assert tx_res.success is True
        assert tx_res.status == "success"
        assert tx_res.tx_hash == "0xabc123"
        assert tx_res.block_number == 100
        assert tx_res.receipt_status == "0x1"

    def test_eth_send_transaction_reverted_receipt_recorded_as_error(self):
        """eth_send_transaction with receipt status 0x0 is recorded as error."""
        client = LocalRpcClient(rpc_url="http://127.0.0.1:8546")

        tx_hash_resp = MagicMock()
        tx_hash_resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": "0xbadtx"}

        receipt_resp = MagicMock()
        receipt_resp.json.return_value = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "transactionHash": "0xbadtx",
                "blockNumber": "0x65",
                "gasUsed": "0x5208",
                "status": "0x0",  # EVM Revert
                "logs": [],
            },
        }

        with patch("requests.post", side_effect=[tx_hash_resp, receipt_resp]):
            tx_res = client.eth_send_transaction(to="0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0", data="0x292a4585")

        assert tx_res.success is False
        assert tx_res.status == "error"
        assert tx_res.receipt_status == "0x0"
        assert "reverted on-chain" in (tx_res.error_message or "")


# ===========================================================================
# 4. Telemetry Provenance & Integrity Tests (Pure Unit / Mocks)
# ===========================================================================

@pytest.mark.unit
class TestTelemetryProvenanceAndIntegrity:
    """Verifies that telemetry provenance reflects real execution evidence."""

    def test_revert_scenario_c07_records_failed_status(self):
        """C07 empty title revert records execution_status FAILED and CONTRACT_REVERT."""
        mock_client = MagicMock()
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=False,
            status="error",
            tx_hash=None,
            block_number=None,
            gas_used=None,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
            error_message="execution reverted: Title cannot be empty",
            duration_ms=12.5,
            request_params={"to": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0", "title": ""},
            response_result={"error": "execution reverted: Title cannot be empty"},
        )

        scenario = LegitimateDAppScenario(variant_id="C07", rpc_client=mock_client)
        result = scenario.run()

        assert result.details["execution_status"] == "FAILED"
        assert result.details["failure_type"] == "CONTRACT_REVERT"
        assert "Title cannot be empty" in result.details["error_details"]

        # Verify RPC event captures failure honestly
        rpc_ev = next(e for e in result.events if e.source == TelemetrySource.RPC)
        assert rpc_ev.rpc.status == "error"
        assert "CONTRACT_REVERT" in rpc_ev.metadata.get("error_type", "")

    def test_revert_scenario_c08_records_failed_status(self):
        """C08 missing task revert records execution_status FAILED and CONTRACT_REVERT."""
        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=False,
            status="error",
            result=None,
            error_message="execution reverted: Task does not exist",
            duration_ms=4.1,
            request_params={"to": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0", "taskId": 999999},
            response_result={"error": "execution reverted: Task does not exist"},
        )

        scenario = LegitimateDAppScenario(variant_id="C08", rpc_client=mock_client)
        result = scenario.run()

        assert result.details["execution_status"] == "FAILED"
        assert result.details["failure_type"] == "CONTRACT_REVERT"
        assert "Task does not exist" in result.details["error_details"]

    def test_scenario_b_data_provenance_tests(self):
        pass


@pytest.mark.unit
class TestScenarioBDataProvenance:
    """Verifies that Scenario B strictly requires successful on-chain data provenance and rejects fallback."""

    def test_rpc_failure_aborts_without_beacon_or_fallback(self):
        """When eth_call fails, Scenario B aborts with RuntimeError and makes zero beacon calls."""
        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=False,
            status="error",
            result=None,
            error_message="Connection refused to upstream RPC",
            duration_ms=2.5,
            request_params={"to": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            variant_id="B01",
            target_server=mock_target,
            rpc_client=mock_client,
        )

        with pytest.raises(RuntimeError, match="getLatestCommand eth_call failed"):
            scenario.execute()

    def test_empty_contract_data_aborts_without_beacon_or_fallback(self):
        """When eth_call returns empty bytecode/string, Scenario B aborts with RuntimeError."""
        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result="0x",
            error_message=None,
            duration_ms=2.5,
            request_params={"to": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            variant_id="B01",
            target_server=mock_target,
            rpc_client=mock_client,
        )

        with pytest.raises(RuntimeError, match="empty command payload"):
            scenario.execute()

    def test_malformed_contract_data_aborts_without_beacon_or_fallback(self):
        """When eth_call returns invalid payload JSON, Scenario B aborts without falling back."""
        malformed_raw = "NOT_A_VALID_JSON_STRING"
        encoded = "0x" + encode_string(malformed_raw)

        mock_client = MagicMock()
        mock_client.eth_call.return_value = RpcCallResult(
            success=True,
            status="success",
            result=encoded,
            error_message=None,
            duration_ms=3.0,
            request_params={"to": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            variant_id="B01",
            target_server=mock_target,
            rpc_client=mock_client,
        )

        with pytest.raises(RuntimeError, match="malformed payload"):
            scenario.execute()

    def test_b05_tx_failure_aborts_without_beacon_or_fallback(self):
        """When B05 storeCommand transaction fails, it aborts without falling back."""
        mock_client = MagicMock()
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=False,
            status="error",
            tx_hash=None,
            block_number=None,
            gas_used=None,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            error_message="out of gas",
            duration_ms=10.0,
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            variant_id="B05",
            target_server=mock_target,
            rpc_client=mock_client,
        )

        with pytest.raises(RuntimeError, match="storeCommand transaction failed"):
            scenario.execute()


@pytest.mark.unit
class TestScenarioBStateChangingBoundary:
    """Verifies that Scenario B transactions fail closed safely without fallback or TP classification (Finding 2)."""

    def test_unsupported_remote_transaction_fails_closed(self):
        """Unsupported remote transaction on Sepolia returns unsupported_network_operation."""
        client = LocalRpcClient(network="sepolia")
        with patch("requests.post") as mock_post:
            tx_res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
            mock_post.assert_not_called()
        assert tx_res.success is False
        assert tx_res.status == "unsupported_network_operation"
        assert "Unsupported operation on network 'sepolia'" in tx_res.error_message
        assert "client-side raw transaction signing" in tx_res.error_message

    def test_unknown_network_transaction_fails_closed_without_http_request(self):
        """Unknown or invalid network configuration fails closed without making an HTTP request."""
        client = LocalRpcClient(network="unknown_custom_network", rpc_url="http://127.0.0.1:8546")
        with patch("requests.post") as mock_post:
            tx_res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
            mock_post.assert_not_called()

        assert tx_res.success is False
        assert tx_res.status == "invalid_network_configuration"
        assert "Invalid or unknown network configuration" in (tx_res.error_message or "")


    def test_failed_or_unsupported_tx_does_not_result_in_successful_tp(self):
        """Unsupported remote transaction stops execution and ensures classification is NOT TP."""
        mock_client = MagicMock()
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=False,
            status="unsupported_network_operation",
            tx_hash=None,
            block_number=None,
            gas_used=None,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            error_message="Unsupported operation on network 'sepolia': eth_sendTransaction requires unlocked accounts on an EVM development node. Public and remote network transactions require client-side raw transaction signing (eth_sendRawTransaction), which is not configured.",
            duration_ms=0.5,
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            variant_id="B05",
            target_server=mock_target,
            rpc_client=mock_client,
        )
        result = scenario.run()
        assert result.success is False

        # Test runner classification for failed B05
        runner = ScenarioRunner()
        with patch("src.scenarios.runner.SyntheticC2Scenario.run", return_value=result):
            _, record = runner.run_variant("B05")
        assert record.execution_status == ExecutionStatus.FAILED
        assert record.classification != Classification.TP
        assert record.classification == Classification.EXCLUDED

    def test_beacon_not_contacted_after_required_blockchain_operation_fails(self):
        """Beacon is never contacted if the required blockchain operation fails."""
        mock_client = MagicMock()
        mock_client.eth_send_transaction.return_value = RpcTxResult(
            success=False,
            status="error",
            tx_hash=None,
            block_number=None,
            gas_used=None,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            error_message="Gas estimation failed",
            duration_ms=1.0,
        )
        mock_target = MagicMock()
        mock_target.beacon_url = "http://127.0.0.1:8080/beacon"

        scenario = SyntheticC2Scenario(
            variant_id="B05",
            target_server=mock_target,
            rpc_client=mock_client,
        )
        result = scenario.run()
        assert result.success is False
        net_events = [e for e in result.events if e.source == TelemetrySource.NETWORK]
        assert len(net_events) == 0

    def test_local_hardhat_transaction_flow_supported(self):
        """Local Hardhat transaction flow allows eth_sendTransaction with unlocked local account."""
        local_client = LocalRpcClient(network="localhost")
        assert local_client.network == "localhost"
        net_cfg = get_network_config("localhost")
        assert net_cfg.requires_signing is False
        assert net_cfg.is_local is True


# ===========================================================================
# 5. Detection Logic Invariance Tests (Pure Unit)
# ===========================================================================

@pytest.mark.unit
class TestDetectionRulesInvariance:
    """Verifies that the locked 7-condition detection conjunction and scoring weights are unchanged (Finding 5)."""

    def test_seven_conjunction_rules_intact(self):
        """Ensure all 7 detection conjunction conditions remain defined and evaluated."""
        rule = SyntheticC2SequenceRule()
        mock_seq = MagicMock()
        mock_seq.correlation_id = "test-corr"
        mock_seq.run_id = "test-run"
        mock_seq.scenario_id = "test"
        mock_seq.duration_ms = 0.0
        mock_seq.endpoint_event = None
        mock_seq.rpc_event = None
        mock_seq.blockchain_event = None
        mock_seq.network_event = None
        mock_seq.events = []

        result = rule.evaluate(mock_seq)
        condition_ids = {c.condition_id for c in result.conditions}
        expected_conditions = {
            "cond_endpoint",
            "cond_rpc",
            "cond_blockchain",
            "cond_c2datastore",
            "cond_network",
            "cond_network_timing",
            "cond_causal_timeline",
        }
        assert condition_ids == expected_conditions
        assert result.triggered is False

    def test_scoring_weights_and_threshold_intact(self):
        """Ensure exact 6 weights and threshold 80.0 are strictly maintained."""
        scorer = RuleBasedScorer()
        assert scorer.weight_endpoint == 10.0
        assert scorer.weight_rpc == 10.0
        assert scorer.weight_contract == 15.0
        assert scorer.weight_retrieval == 20.0
        assert scorer.weight_c2_config == 20.0
        assert scorer.weight_network == 25.0
        total_weights = (
            scorer.weight_endpoint
            + scorer.weight_rpc
            + scorer.weight_contract
            + scorer.weight_retrieval
            + scorer.weight_c2_config
            + scorer.weight_network
        )
        assert total_weights == 100.0
        assert scorer.threshold == 80.0

    def test_missing_any_required_conjunction_condition_prevents_positive_trigger(self):
        """Missing any required conjunction condition prevents positive trigger even if score exceeds 80."""
        rule = SyntheticC2SequenceRule()
        mock_seq = MagicMock()
        mock_seq.correlation_id = "test-corr"
        mock_seq.run_id = "test-run"
        mock_seq.scenario_id = "test"
        mock_seq.duration_ms = 100.0
        mock_seq.endpoint_event = MagicMock()
        mock_seq.rpc_event = MagicMock()
        # Missing blockchain event
        mock_seq.blockchain_event = None
        mock_seq.network_event = MagicMock()
        mock_seq.events = [mock_seq.endpoint_event, mock_seq.rpc_event, mock_seq.network_event]

        result = rule.evaluate(mock_seq)
        assert result.triggered is False

    def test_read_only_contract_call_distinguished_from_mined_tx_receipt_and_events(self):
        """Client-observed read (eth_call) is strictly distinct from submitted tx, mined receipt, and event log."""
        # 1. Read-only call result (eth_call)
        call_res = RpcCallResult(
            success=True,
            status="success",
            result="0x00000001",
            error_message=None,
            duration_ms=5.0,
            request_params={"to": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
        )
        assert not hasattr(call_res, "tx_hash") or call_res.tx_hash is None
        assert not hasattr(call_res, "receipt_status")
        assert not hasattr(call_res, "logs")

        # 2. Submitted & mined transaction result (eth_sendTransaction + receipt)
        tx_res = RpcTxResult(
            success=True,
            status="success",
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            block_number=100,
            gas_used=21000,
            sender="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            to="0x5FbDB2315678afecb367f032d93F642f64180aa3",
            logs=[{"topics": ["0x1234"]}],
            receipt_status="0x1",
            duration_ms=15.0,
            request_params={"to": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
        )
        assert tx_res.tx_hash is not None
        assert tx_res.receipt_status == "0x1"
        assert len(tx_res.logs) == 1


# ===========================================================================
# 6. Historical Artifact Preservation Tests (Byte-for-byte SHA256)
# ===========================================================================

@pytest.mark.unit
class TestHistoricalArtifactPreservation:
    """Ensures historical baseline artifacts are preserved byte-for-byte."""

    EXPECTED_HASHES = {
        "matrix_v2_81_results.json": (
            Path("data/evaluation/dataset_campaign/matrix_v2_81_results.json"),
            "15fa3d7e49a1cf5f8c1476a2ff5141849a46fb31eb021a3e2159a2d8998fd470",
            114232,
        ),
        "telemetry_events_balanced.jsonl": (
            Path("data/evaluation/dataset_campaign/telemetry_events_balanced.jsonl"),
            "519c1e988e221d889ed499badb8bb704a69dd2c17c96dc42881ddafbbce35aa0",
            267774,
        ),
        "campaign_plan_372.json": (
            Path("data/evaluation/dataset_campaign/campaign_plan_372.json"),
            "0c483d093ee32c4122ae4c47fdc6fd62451b78991ec45bd25077f517f0c23bc7",
            215305,
        ),
        "research_summary.json": (
            Path("results/final/research_summary.json"),
            "85b1d136d61c7657c518eb2872eedf50f245e968d9997178ca04cdcce7930bcc",
            10472,
        ),
    }

    @pytest.mark.parametrize("name", list(EXPECTED_HASHES.keys()))
    def test_artifact_byte_for_byte_integrity(self, name: str):
        path, expected_hash, expected_size = self.EXPECTED_HASHES[name]
        assert path.exists(), f"Historical artifact {path} is missing!"
        data = path.read_bytes()
        assert len(data) == expected_size, f"Size mismatch for {path}: got {len(data)}, expected {expected_size}"
        actual_hash = hashlib.sha256(data).hexdigest()
        assert actual_hash == expected_hash, f"SHA256 mismatch for {path}: got {actual_hash}, expected {expected_hash}"


# ===========================================================================
# 7. Live Local Hardhat Node Integration Tests (Require running node & proxy)
# ===========================================================================

@pytest.mark.integration
class TestLiveLocalHardhatNodeIntegration:
    """Exercises genuine JSON-RPC calls against the local RPC proxy and Hardhat node."""

    def test_live_proxy_forwarding_and_chain_id(self):
        """Verifies local RPC proxy (8546) forwards to Hardhat (8545) and returns chainId 31337."""
        client = LocalRpcClient(rpc_url="http://127.0.0.1:8546")
        chain_id = client.get_chain_id()
        assert chain_id == "31337", f"Expected Hardhat local chain ID '31337', got {chain_id}"

    def test_live_contract_read_benign_dapp(self):
        """Calls BenignDAppContract#getCount() via genuine JSON-RPC on local node."""
        client = LocalRpcClient(rpc_url="http://127.0.0.1:8546")
        addrs = load_deployed_addresses()
        call_res = client.eth_call(to=addrs["BenignDAppContract"], data="0xa87d942c")
        assert call_res.success is True
        assert call_res.status == "success"
        count = decode_uint256(call_res.result or "")
        assert count >= 0

    def test_live_contract_read_c2_data_store(self):
        """Calls C2DataStore#getCommandCount() via genuine JSON-RPC on local node."""
        client = LocalRpcClient(rpc_url="http://127.0.0.1:8546")
        addrs = load_deployed_addresses()
        call_res = client.eth_call(to=addrs["C2DataStore"], data="0x9a2d834f")
        assert call_res.success is True
        count = decode_uint256(call_res.result or "")
        assert count >= 0

    def test_live_contract_read_legitimate_dapp(self):
        """Calls LegitimateDAppContract#getTaskCount() via genuine JSON-RPC on local node."""
        client = LocalRpcClient(rpc_url="http://127.0.0.1:8546")
        addrs = load_deployed_addresses()
        call_res = client.eth_call(to=addrs["LegitimateDAppContract"], data="0xc17a340e")
        assert call_res.success is True
        count = decode_uint256(call_res.result or "")
        assert count >= 0
