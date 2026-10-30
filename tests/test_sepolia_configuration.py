# ChainC2 Sentinel — Stage A Sepolia Isolated Configuration Tests
"""Strictly offline unit tests verifying Sepolia configuration isolation,

fail-safe handling of unconfigured contract registries, prevention of silent
network fallbacks, preservation of local Hardhat defaults, and absence of credentials.
"""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.blockchain.deployment import (
    DEFAULT_DEPLOYMENT_PATH,
    SEPOLIA_DEPLOYMENT_PATH,
    DeploymentResolutionError,
    get_deployment_path_for_network,
    load_deployed_addresses,
    verify_rpc_and_registry_alignment,
)
from src.blockchain.rpc_client import (
    DEFAULT_DEPLOYER,
    DEFAULT_RPC_URL,
    LOCAL_CHAIN_ID,
    LOCAL_CHAIN_ID_HEX,
    SEPOLIA_CHAIN_ID,
    SEPOLIA_CHAIN_ID_HEX,
    LocalRpcClient,
    get_network_config,
)
from src.scenarios.runner import ScenarioRunner


class TestSepoliaConfigurationIsolation:
    """Verifies that Sepolia configuration is isolated, local defaults are preserved,

    and missing configurations fail safely without network access.
    """

    def test_local_defaults_remain_unchanged(self):
        """Verifies that default invocations load local Hardhat settings and addresses."""
        # Deployment path defaults to local deployed-addresses.json
        assert get_deployment_path_for_network() == DEFAULT_DEPLOYMENT_PATH
        assert get_deployment_path_for_network("localhost") == DEFAULT_DEPLOYMENT_PATH
        assert get_deployment_path_for_network("hardhat") == DEFAULT_DEPLOYMENT_PATH

        # Default address loader resolves local addresses
        local_addrs = load_deployed_addresses()
        assert "C2DataStore" in local_addrs
        assert "BenignDAppContract" in local_addrs
        assert "LegitimateDAppContract" in local_addrs
        assert local_addrs["C2DataStore"].startswith("0x")

        # Network configuration defaults to localhost / 31337
        local_cfg = get_network_config()
        assert local_cfg.name == "localhost"
        assert local_cfg.chain_id == "31337"
        assert local_cfg.chain_id_hex == "0x7a69"
        assert local_cfg.rpc_url == DEFAULT_RPC_URL
        assert local_cfg.requires_signing is False
        assert local_cfg.is_local is True

        # RPC client defaults to localhost
        client = LocalRpcClient()
        assert client.rpc_url == DEFAULT_RPC_URL
        assert client.default_sender == DEFAULT_DEPLOYER
        assert client.network == "localhost"
        assert client.expected_chain_id is None

    def test_sepolia_configuration_is_isolated(self):
        """Verifies that Sepolia requires explicit opt-in and provides correct constants."""
        sepolia_cfg = get_network_config("sepolia")
        assert sepolia_cfg.name == "sepolia"
        assert sepolia_cfg.chain_id == "11155111"
        assert sepolia_cfg.chain_id_hex == "0xaa36a7"
        assert sepolia_cfg.requires_signing is True
        assert sepolia_cfg.is_local is False

        # Registry path for Sepolia is distinct from local path
        sepolia_path = get_deployment_path_for_network("sepolia")
        assert sepolia_path == SEPOLIA_DEPLOYMENT_PATH
        assert sepolia_path != DEFAULT_DEPLOYMENT_PATH
        assert sepolia_path.name == "deployed-addresses.sepolia.json"

    def test_unknown_network_rejection_prevents_silent_fallback(self):
        """Verifies that unknown network identifiers raise errors rather than falling back."""
        with pytest.raises(ValueError, match="Unknown network 'goerli'"):
            get_network_config("goerli")

        with pytest.raises(ValueError, match="Unknown network 'mainnet'"):
            get_network_config("mainnet")

        with pytest.raises(DeploymentResolutionError, match="Unknown network 'goerli'"):
            get_deployment_path_for_network("goerli")

    def test_unconfigured_sepolia_registry_fails_safely(self):
        """Verifies that attempting to load unconfigured Sepolia addresses raises DeploymentResolutionError."""
        assert SEPOLIA_DEPLOYMENT_PATH.is_file(), f"Missing {SEPOLIA_DEPLOYMENT_PATH}"

        with open(SEPOLIA_DEPLOYMENT_PATH, "r", encoding="utf-8") as f:
            registry_data = json.load(f)

        assert registry_data.get("network") == "sepolia"
        assert registry_data.get("status") == "UNCONFIGURED"
        assert registry_data.get("contracts") == {}

        with pytest.raises(DeploymentResolutionError) as exc_info:
            load_deployed_addresses(SEPOLIA_DEPLOYMENT_PATH)

        assert "UNCONFIGURED" in str(exc_info.value)
        assert "sepolia" in str(exc_info.value)

    def test_chain_id_validation_prevents_silent_cross_network_execution(self):
        """Verifies that get_chain_id strictly enforces expected_chain_id and prevents silent fallback."""
        client = LocalRpcClient(
            rpc_url="http://mock-rpc:8545",
            network="sepolia",
            expected_chain_id="11155111",
        )

        # Mock an RPC response returning 31337 (local) when client expects Sepolia (11155111)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"jsonrpc": "2.0", "result": "0x7a69", "id": 1}

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Chain ID mismatch for network 'sepolia'"):
                client.get_chain_id()

        # Mock an RPC network failure on Sepolia client: must raise, NEVER silently return "31337"
        with patch("requests.post", side_effect=ConnectionError("Mocked offline connection failure")):
            with pytest.raises(Exception):
                client.get_chain_id()

    def test_local_rpc_client_failure_raises_without_fallback_when_expected_chain_id_is_none(self):
        """Offline local RPC connection failure raises and never silently falls back to 31337 when expected_chain_id=None."""
        client = LocalRpcClient(network="localhost")  # implicit expected_chain_id=None
        with patch("requests.post", side_effect=ConnectionRefusedError("Connection refused")):
            with pytest.raises(ConnectionRefusedError):
                client.get_chain_id()

    def test_verify_rpc_and_registry_alignment_rejects_unavailable_local_rpc_with_implicit_chain_id(self):
        """verify_rpc_and_registry_alignment fails closed and refuses addresses when local RPC is unavailable."""
        client = LocalRpcClient(network="localhost")  # implicit expected_chain_id=None
        with patch("requests.post", side_effect=ConnectionRefusedError("Connection refused")):
            with pytest.raises(DeploymentResolutionError, match="Failed to query RPC chain ID for network 'localhost'"):
                verify_rpc_and_registry_alignment(client, "localhost")

    def test_local_rpc_client_successful_chain_id_retrieval(self):
        """LocalRpcClient successfully parses chain ID from responding local RPC."""
        client = LocalRpcClient(network="localhost")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"jsonrpc": "2.0", "result": "0x7a69", "id": 1}
        with patch("requests.post", return_value=mock_resp):
            cid = client.get_chain_id()
            assert cid == "31337"


    def test_no_credentials_required_or_embedded(self):
        """Verifies that no private keys, mnemonics, or credentials are hardcoded in the codebase."""
        # 1. Sepolia deployment registry
        with open(SEPOLIA_DEPLOYMENT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        assert "private" not in content.lower()
        assert "secret" not in content.lower()
        assert content.count("0x") <= 2  # Only chainIdHex and address regex if any

        # 2. Hardhat config inspection
        hardhat_config_path = Path(__file__).resolve().parent.parent / "src" / "blockchain" / "hardhat.config.js"
        assert hardhat_config_path.is_file()
        hardhat_text = hardhat_config_path.read_text(encoding="utf-8")
        assert "accounts: process.env.SEPOLIA_PRIVATE_KEY ? [process.env.SEPOLIA_PRIVATE_KEY] : []" in hardhat_text
        # Ensure no 64-char hex private key is hardcoded
        private_key_regex = re.compile(r"0x[0-9a-fA-F]{64}")
        assert not private_key_regex.search(hardhat_text), "Hardcoded private key found in hardhat.config.js"

        # 3. .env.example inspection
        env_example_path = Path(__file__).resolve().parent.parent / ".env.example"
        env_text = env_example_path.read_text(encoding="utf-8")
        assert "# SEPOLIA_PRIVATE_KEY=" in env_text
        assert not private_key_regex.search(env_text), "Hardcoded private key found in .env.example"

    def test_verify_rpc_and_registry_alignment_success(self):
        """Connected local node matching hardhat registry resolves addresses cleanly."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        client.eth_get_code.return_value = "0x60806040"
        addresses = verify_rpc_and_registry_alignment(client, "hardhat")
        assert addresses["C2DataStore"] == "0x5FbDB2315678afecb367f032d93F642f64180aa3"

    def test_verify_rpc_and_registry_alignment_chain_id_mismatch(self):
        """Cross-network mismatch aborts before contract address usage."""
        client = MagicMock()
        client.get_chain_id.return_value = "31337"  # Local RPC connected
        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            verify_rpc_and_registry_alignment(client, "sepolia")

    def test_verify_rpc_and_registry_alignment_sepolia_unconfigured(self):
        """Sepolia RPC matching chain ID aborts safely because registry is unconfigured."""
        client = MagicMock()
        client.get_chain_id.return_value = "11155111"  # Sepolia RPC
        with pytest.raises(DeploymentResolutionError, match="UNCONFIGURED"):
            verify_rpc_and_registry_alignment(client, "sepolia")

    def test_sepolia_telemetry_label_and_chain_id(self):
        """Scenario initialized for Sepolia records 'sepolia' and '11155111', NEVER 'hardhat' or '31337'."""
        from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
        scenario = SyntheticC2Scenario(network="sepolia")
        assert scenario.blockchain_collector._network_name == "sepolia"
        assert scenario.blockchain_collector._chain_id == "11155111"
        assert scenario.blockchain_collector._network_name != "hardhat"
        assert scenario.blockchain_collector._chain_id != "31337"


class TestScenarioRunnerNetworkAndRegistryEnforcement:
    """Exercises ScenarioRunner configuration, network resolution, and registry bypass prevention (Findings 1 & 3)."""

    def test_local_execution_resolves_local_endpoint_and_registry(self):
        """ScenarioRunner with localhost/hardhat network resolves local endpoint and registry."""
        runner = ScenarioRunner(network="localhost")
        assert runner.network == "localhost"
        assert runner.chain_id == "31337"
        assert runner.rpc_proxy_url == "http://127.0.0.1:8546"
        assert runner.upstream_url == "http://127.0.0.1:8545"
        assert runner.deployment_path == DEFAULT_DEPLOYMENT_PATH
        assert runner.deployed_addresses["C2DataStore"] == "0x5FbDB2315678afecb367f032d93F642f64180aa3"

    def test_sepolia_selection_resolves_sepolia_endpoint_and_registry(self):
        """ScenarioRunner with network='sepolia' resolves Sepolia RPC URL and Sepolia registry, failing closed on UNCONFIGURED."""
        with pytest.raises(DeploymentResolutionError, match="UNCONFIGURED"):
            ScenarioRunner(network="sepolia")

    def test_no_silent_fallback_to_localhost_when_sepolia_selected(self):
        """Selecting network='sepolia' never silently falls back to localhost endpoints or registry."""
        with pytest.raises(DeploymentResolutionError) as exc_info:
            ScenarioRunner(network="sepolia")
        assert "sepolia" in str(exc_info.value)
        assert "UNCONFIGURED" in str(exc_info.value)

    def test_missing_or_unknown_network_fails_closed(self):
        """Unknown or unconfigured networks fail closed immediately."""
        with pytest.raises(ValueError, match="Unknown network 'ropsten'"):
            ScenarioRunner(network="ropsten")
        with pytest.raises(ValueError, match="Unknown network 'mainnet'"):
            ScenarioRunner(network="mainnet")

    def test_empty_configured_rpc_endpoint_fails_closed(self, monkeypatch):
        """Empty SEPOLIA_RPC_URL environment variable fails closed."""
        monkeypatch.setenv("SEPOLIA_RPC_URL", "")
        with pytest.raises(ValueError, match="Configured SEPOLIA_RPC_URL is empty"):
            ScenarioRunner(network="sepolia")

    def test_explicit_local_registry_for_sepolia_runner_is_rejected(self):
        """Supplying local registry explicitly to a Sepolia runner cannot bypass validation."""
        with pytest.raises(DeploymentResolutionError, match="network mismatch"):
            ScenarioRunner(
                network="sepolia",
                deployment_path=str(DEFAULT_DEPLOYMENT_PATH),
            )

    def test_explicit_sepolia_registry_for_local_runner_is_rejected(self):
        """Supplying Sepolia registry explicitly to a local runner is rejected."""
        with pytest.raises(DeploymentResolutionError, match="(UNCONFIGURED|network mismatch)"):
            ScenarioRunner(
                network="localhost",
                deployment_path=str(SEPOLIA_DEPLOYMENT_PATH),
            )

    def test_registry_with_wrong_chain_id_is_rejected(self, tmp_path):
        """Registry metadata with wrong chain ID fails closed."""
        bad_reg = tmp_path / "bad_chain.json"
        bad_reg.write_text(
            json.dumps({
                "network": "localhost",
                "chainId": "99999",
                "status": "DEPLOYED",
                "contracts": {
                    "C2DataStore": {"address": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
                    "BenignDAppContract": {"address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"},
                    "LegitimateDAppContract": {"address": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"},
                },
            }),
            encoding="utf-8",
        )
        with pytest.raises(DeploymentResolutionError, match="chain ID mismatch"):
            ScenarioRunner(network="localhost", deployment_path=str(bad_reg))

    def test_registry_missing_or_malformed_metadata_is_rejected(self, tmp_path):
        """Registry with missing or empty network/chainId metadata fails closed."""
        bad_meta = tmp_path / "missing_meta.json"
        bad_meta.write_text(
            json.dumps({
                "status": "DEPLOYED",
                "contracts": {
                    "C2DataStore": {"address": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
                    "BenignDAppContract": {"address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"},
                    "LegitimateDAppContract": {"address": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"},
                },
            }),
            encoding="utf-8",
        )
        with pytest.raises(DeploymentResolutionError, match="Missing or malformed 'network' metadata"):
            ScenarioRunner(network="localhost", deployment_path=str(bad_meta))

    def test_chain_id_mismatch_prevents_scenario_execution_all_entrypoints(self):
        """Live RPC chain ID mismatch prevents actual scenario execution across all normal entry points."""
        runner = ScenarioRunner(network="localhost")
        mismatched_client = MagicMock()
        mismatched_client.get_chain_id.return_value = "11155111"  # Sepolia RPC on local runner (expected 31337)

        # 1. run_benign
        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            runner.run_benign(rpc_client=mismatched_client)

        # 2. run_legitimate_dapp
        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            runner.run_legitimate_dapp(rpc_client=mismatched_client)

        # 3. run_synthetic_c2
        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            runner.run_synthetic_c2(rpc_client=mismatched_client)

        # 4. run_variant
        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            runner.run_variant("A01", rpc_client=mismatched_client)

        # 5. run_all
        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            runner.run_all(rpc_client=mismatched_client)

    def test_injected_runner_rpc_client_mismatch_blocks_execution(self):
        """ScenarioRunner initialized with mismatched rpc_client blocks scenario execution."""
        mismatched_client = MagicMock()
        mismatched_client.get_chain_id.return_value = "11155111"
        runner = ScenarioRunner(network="localhost", rpc_client=mismatched_client)

        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            runner.run_benign()

    def test_live_rpc_alignment_caching_avoids_redundant_checks(self):
        """Live RPC alignment caches validated client/network/deployment tuples avoiding redundant calls."""
        runner = ScenarioRunner(network="localhost")
        aligned_client = MagicMock()
        aligned_client.get_chain_id.return_value = "31337"
        aligned_client.eth_get_code.return_value = "0x60806040"

        # Validate directly
        addrs1 = runner.validate_live_rpc_alignment(aligned_client)
        assert addrs1["C2DataStore"] == "0x5FbDB2315678afecb367f032d93F642f64180aa3"
        assert aligned_client.get_chain_id.call_count == 1

        # Second validation call with same client uses cached boundary and does not call get_chain_id again
        addrs2 = runner.validate_live_rpc_alignment(aligned_client)
        assert addrs2 == addrs1
        assert aligned_client.get_chain_id.call_count == 1

        # Force bypass cache
        addrs3 = runner.validate_live_rpc_alignment(aligned_client, force=True)
        assert addrs3 == addrs1
        assert aligned_client.get_chain_id.call_count == 2

    def test_registry_addresses_changed_after_runner_initialization(self, tmp_path):
        """Changes to registry file on disk after runner init are picked up and update runner.deployed_addresses."""
        reg_file = tmp_path / "dynamic_reg.json"
        initial_data = {
            "network": "localhost",
            "chainId": "31337",
            "status": "DEPLOYED",
            "contracts": {
                "C2DataStore": {"address": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
                "BenignDAppContract": {"address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"},
                "LegitimateDAppContract": {"address": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"},
            },
        }
        reg_file.write_text(json.dumps(initial_data), encoding="utf-8")

        runner = ScenarioRunner(network="localhost", deployment_path=str(reg_file))
        assert runner.deployed_addresses["BenignDAppContract"] == "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"

        # Update registry on disk with new contract address
        import time
        time.sleep(0.01)  # Ensure mtime changes
        new_addr = "0x1111111111111111111111111111111111111111"
        initial_data["contracts"]["BenignDAppContract"]["address"] = new_addr
        reg_file.write_text(json.dumps(initial_data), encoding="utf-8")

        aligned_client = MagicMock()
        aligned_client.get_chain_id.return_value = "31337"
        aligned_client.eth_get_code.return_value = "0x60806040"

        validated = runner.validate_live_rpc_alignment(aligned_client)
        assert validated["BenignDAppContract"] == new_addr
        assert runner.deployed_addresses["BenignDAppContract"] == new_addr

    def test_forced_revalidation_updates_deployed_addresses(self, tmp_path):
        """Forced revalidation (force=True) re-reads registry and updates runner.deployed_addresses."""
        reg_file = tmp_path / "reval_reg.json"
        data = {
            "network": "localhost",
            "chainId": "31337",
            "status": "DEPLOYED",
            "contracts": {
                "C2DataStore": {"address": "0x5FbDB2315678afecb367f032d93F642f64180aa3"},
                "BenignDAppContract": {"address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"},
                "LegitimateDAppContract": {"address": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"},
            },
        }
        reg_file.write_text(json.dumps(data), encoding="utf-8")
        runner = ScenarioRunner(network="localhost", deployment_path=str(reg_file))
        aligned_client = MagicMock()
        aligned_client.get_chain_id.return_value = "31337"
        aligned_client.eth_get_code.return_value = "0x60806040"

        runner.validate_live_rpc_alignment(aligned_client)

        # Update file on disk
        new_c2 = "0x2222222222222222222222222222222222222222"
        data["contracts"]["C2DataStore"]["address"] = new_c2
        reg_file.write_text(json.dumps(data), encoding="utf-8")

        revalidated = runner.validate_live_rpc_alignment(aligned_client, force=True)
        assert revalidated["C2DataStore"] == new_c2
        assert runner.deployed_addresses["C2DataStore"] == new_c2

    def test_validation_failure_after_previously_successful_validation(self):
        """Validation failure with a bad client raises and does not permit execution using stale addresses."""
        runner = ScenarioRunner(network="localhost")
        aligned_client = MagicMock()
        aligned_client.get_chain_id.return_value = "31337"
        aligned_client.eth_get_code.return_value = "0x60806040"
        runner.validate_live_rpc_alignment(aligned_client)

        failing_client = MagicMock()
        failing_client.get_chain_id.side_effect = RuntimeError("RPC disconnected")

        with pytest.raises(DeploymentResolutionError, match="Failed to query RPC chain ID"):
            runner.validate_live_rpc_alignment(failing_client)

    def test_distinct_rpc_clients_or_configurations_do_not_share_cached_validation(self):
        """Distinct client configurations do not share cached alignment entries."""
        runner = ScenarioRunner(network="localhost")

        client_a = MagicMock()
        client_a.rpc_url = "http://127.0.0.1:8546"
        client_a.get_chain_id.return_value = "31337"
        client_a.eth_get_code.return_value = "0x60806040"

        client_b = MagicMock()
        client_b.rpc_url = "http://127.0.0.1:8547"
        client_b.get_chain_id.return_value = "31337"
        client_b.eth_get_code.return_value = "0x60806040"

        runner.validate_live_rpc_alignment(client_a)
        assert client_a.get_chain_id.call_count == 1

        runner.validate_live_rpc_alignment(client_b)
        assert client_b.get_chain_id.call_count == 1

    def test_exact_rpc_client_identity_propagated_to_scenarios(self):
        """Scenario execution entry points propagate the exact validated RPC client instance."""
        injected_client = MagicMock()
        injected_client.get_chain_id.return_value = "31337"
        injected_client.eth_get_code.return_value = "0x60806040"

        runner = ScenarioRunner(network="localhost", rpc_client=injected_client)

        with patch("src.scenarios.runner.BenignWeb3Scenario") as mock_benign_cls:
            mock_inst = MagicMock()
            mock_benign_cls.return_value = mock_inst
            runner.run_benign()
            assert mock_benign_cls.call_count == 1
            assert mock_benign_cls.call_args.kwargs["rpc_client"] is injected_client

        with patch("src.scenarios.runner.LegitimateDAppScenario") as mock_legit_cls:
            mock_inst = MagicMock()
            mock_legit_cls.return_value = mock_inst
            runner.run_legitimate_dapp()
            assert mock_legit_cls.call_count == 1
            assert mock_legit_cls.call_args.kwargs["rpc_client"] is injected_client

        with patch("src.scenarios.runner.SyntheticC2Scenario") as mock_c2_cls:
            mock_inst = MagicMock()
            mock_c2_cls.return_value = mock_inst
            runner.run_synthetic_c2()
            assert mock_c2_cls.call_count == 1
            assert mock_c2_cls.call_args.kwargs["rpc_client"] is injected_client

        with patch("src.scenarios.runner.BenignWeb3Scenario") as mock_benign_cls:
            mock_inst = MagicMock()
            mock_inst.run.return_value = MagicMock(details={})
            mock_benign_cls.return_value = mock_inst
            runner.run_variant("A01")
            assert mock_benign_cls.call_count == 1
            assert mock_benign_cls.call_args.kwargs["rpc_client"] is injected_client

    def test_bytecode_verification_success_and_failure(self):
        """Bytecode verification via eth_get_code confirms contract code exists and rejects empty code."""
        from src.blockchain.deployment import verify_contract_bytecode

        client = MagicMock()
        client.get_chain_id.return_value = "31337"
        client.eth_get_code.return_value = "0x608060405234801561001057600080fd5b50"

        # Helper returns True when bytecode exists
        assert verify_contract_bytecode(client, "0x5FbDB2315678afecb367f032d93F642f64180aa3") is True

        # Helper returns False when bytecode is 0x
        client.eth_get_code.return_value = "0x"
        assert verify_contract_bytecode(client, "0x5FbDB2315678afecb367f032d93F642f64180aa3") is False

        # verify_rpc_and_registry_alignment succeeds when verify_bytecode=True and code exists
        client.eth_get_code.return_value = "0x60806040"
        addrs = verify_rpc_and_registry_alignment(client, "localhost", verify_bytecode=True)
        assert "C2DataStore" in addrs

        # verify_rpc_and_registry_alignment rejects when verify_bytecode=True and code is empty 0x
        client.eth_get_code.return_value = "0x"
        with pytest.raises(DeploymentResolutionError, match="has no on-chain bytecode"):
            verify_rpc_and_registry_alignment(client, "localhost", verify_bytecode=True)

    def test_local_rpc_client_eth_get_code_method(self):
        """LocalRpcClient.eth_get_code executes JSON-RPC call and parses result."""
        client = LocalRpcClient(network="localhost")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"jsonrpc": "2.0", "result": "0x60806040", "id": 1}

        with patch("requests.post", return_value=mock_resp):
            code = client.eth_get_code("0x5FbDB2315678afecb367f032d93F642f64180aa3")
            assert code == "0x60806040"





