# ChainC2 Sentinel — Contract Deployment Resolution
"""Authoritative resolution and validation of locally deployed smart contracts.

Strictly validates contract addresses from deployed-addresses.json
to prevent silent configuration inversions or hardcoded address drift.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("chainc2_sentinel.blockchain.deployment")

ETH_ADDRESS_REGEX = re.compile(r"^0x[0-9a-fA-F]{40}$")
DEFAULT_DEPLOYMENT_PATH = Path(__file__).resolve().parent / "deployed-addresses.json"
SEPOLIA_DEPLOYMENT_PATH = Path(__file__).resolve().parent / "deployed-addresses.sepolia.json"

NETWORK_DEPLOYMENT_PATHS: dict[str, Path] = {
    "localhost": DEFAULT_DEPLOYMENT_PATH,
    "hardhat": DEFAULT_DEPLOYMENT_PATH,
    "hardhat_docker": DEFAULT_DEPLOYMENT_PATH,
    "sepolia": SEPOLIA_DEPLOYMENT_PATH,
}


class DeploymentResolutionError(RuntimeError):
    """Raised when contract deployment data is missing, malformed, or invalid."""
    pass


def get_deployment_path_for_network(network: str = "localhost") -> Path:
    """Resolve the authoritative deployment address registry path for a specified network.

    Args:
        network: Network identifier (e.g., 'localhost', 'hardhat', 'hardhat_docker', 'sepolia'). Defaults to 'localhost'.

    Returns:
        Path to the network's deployment JSON file.

    Raises:
        DeploymentResolutionError: If the network is unknown, preventing silent fallback.
    """
    norm = network.strip().lower()
    if norm not in NETWORK_DEPLOYMENT_PATHS:
        raise DeploymentResolutionError(
            f"Unknown network '{network}'. Known networks: {list(NETWORK_DEPLOYMENT_PATHS.keys())}"
        )
    return NETWORK_DEPLOYMENT_PATHS[norm]


def load_deployed_addresses(
    path: Optional[Path | str] = None,
    expected_network: Optional[str] = None,
    expected_chain_id: Optional[str | int] = None,
) -> dict[str, str]:
    """Load and strictly validate contract addresses from authoritative deployment JSON.

    Args:
        path: Optional path to deployed-addresses JSON. Defaults to src/blockchain/deployed-addresses.json
              unless expected_network is specified.
        expected_network: Optional expected network identifier to validate against registry metadata.
        expected_chain_id: Optional expected chain ID to validate against registry metadata.

    Returns:
        Mapping of contract name to validated Ethereum address string.

    Raises:
        DeploymentResolutionError: If file is missing, JSON is invalid, unconfigured, network/chain-ID mismatches,
                                   or required contracts/addresses are missing.
    """
    if path is not None:
        file_path = Path(path)
    elif expected_network is not None:
        file_path = get_deployment_path_for_network(expected_network)
    else:
        file_path = DEFAULT_DEPLOYMENT_PATH
    if not file_path.is_file():
        raise DeploymentResolutionError(
            f"Deployment address file not found: {file_path}. Ensure 'npm run deploy' was executed."
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise DeploymentResolutionError(
            f"Failed to parse deployment JSON at {file_path}: {e}"
        ) from e

    # Strict metadata presence validation
    if "network" not in data or not isinstance(data["network"], str) or not data["network"].strip():
        raise DeploymentResolutionError(f"Missing or malformed 'network' metadata in {file_path}")
    if "chainId" not in data or not str(data["chainId"]).strip():
        raise DeploymentResolutionError(f"Missing or malformed 'chainId' metadata in {file_path}")

    status = data.get("status")
    if status == "UNCONFIGURED":
        notice = data.get("notice", "Deployment not yet performed.")
        net = data.get("network", "unknown")
        raise DeploymentResolutionError(
            f"Deployment registry for network '{net}' at {file_path} is UNCONFIGURED. {notice}"
        )

    if expected_network is not None:
        actual_net = str(data.get("network", "")).strip().lower()
        exp_net = expected_network.strip().lower()
        local_nets = {"localhost", "hardhat", "hardhat_docker"}
        is_both_local = (actual_net in local_nets) and (exp_net in local_nets)
        if actual_net != exp_net and not is_both_local:
            raise DeploymentResolutionError(
                f"Deployment registry network mismatch in {file_path}: expected '{expected_network}', found '{actual_net}'"
            )

    if expected_chain_id is not None:
        actual_cid = str(data.get("chainId", "")).strip()
        if actual_cid != str(expected_chain_id).strip():
            raise DeploymentResolutionError(
                f"Deployment registry chain ID mismatch in {file_path}: expected '{expected_chain_id}', found '{actual_cid}'"
            )

    contracts = data.get("contracts")
    if not isinstance(contracts, dict):
        raise DeploymentResolutionError(
            f"Missing or invalid 'contracts' dictionary in {file_path}"
        )

    required_contracts = ["C2DataStore", "BenignDAppContract", "LegitimateDAppContract"]
    resolved: dict[str, str] = {}

    for name in required_contracts:
        if name not in contracts:
            raise DeploymentResolutionError(
                f"Required contract '{name}' missing from deployment artifact: {file_path}"
            )
        entry = contracts[name]
        if not isinstance(entry, dict) or "address" not in entry:
            raise DeploymentResolutionError(
                f"Contract '{name}' entry missing 'address' field in {file_path}"
            )
        addr = entry["address"]
        if not isinstance(addr, str) or not ETH_ADDRESS_REGEX.match(addr):
            raise DeploymentResolutionError(
                f"Invalid Ethereum address format for '{name}' in {file_path}: '{addr}'"
            )
        resolved[name] = addr

    logger.debug("Successfully resolved deployed contract addresses: %s", resolved)
    return resolved


def verify_contract_bytecode(
    rpc_client: Any,
    address: str,
) -> bool:
    """Verify that an address contains non-empty deployed bytecode via eth_getCode."""
    if not hasattr(rpc_client, "eth_get_code"):
        return False
    code = rpc_client.eth_get_code(address)
    return bool(code and code != "0x" and len(code) > 2)


def verify_rpc_and_registry_alignment(
    rpc_client: Any,
    expected_network: str,
    deployment_path: Optional[Union[str, Path]] = None,
    verify_bytecode: bool = False,
) -> dict[str, str]:
    """Verify that connected RPC chain ID matches expected network and registry metadata before using addresses.

    Args:
        rpc_client: LocalRpcClient or equivalent with get_chain_id() method.
        expected_network: Intended network ('localhost', 'hardhat', 'hardhat_docker', 'sepolia').
        deployment_path: Optional path to registry JSON.
        verify_bytecode: If True, asserts deployed bytecode exists at each contract address via eth_getCode.

    Returns:
        Mapping of contract names to validated addresses.

    Raises:
        DeploymentResolutionError: If chain ID, network, bytecode, or registry metadata fails verification.
    """
    from src.blockchain.rpc_client import NETWORK_CONFIGS
    norm_net = expected_network.strip().lower()
    if norm_net not in NETWORK_CONFIGS:
        raise DeploymentResolutionError(
            f"Unknown network '{expected_network}'. Allowed: {list(NETWORK_CONFIGS.keys())}"
        )
    cfg = NETWORK_CONFIGS[norm_net]
    expected_cid = str(cfg.chain_id)

    try:
        rpc_cid = str(rpc_client.get_chain_id())
    except Exception as e:
        raise DeploymentResolutionError(
            f"Failed to query RPC chain ID for network '{expected_network}': {e}"
        ) from e

    if rpc_cid != expected_cid:
        raise DeploymentResolutionError(
            f"RPC chain ID mismatch for network '{expected_network}': "
            f"expected {expected_cid}, but connected RPC returned {rpc_cid}. "
            f"Refusing to use contract addresses to prevent cross-network corruption."
        )

    target_path = deployment_path or get_deployment_path_for_network(norm_net)
    addresses = load_deployed_addresses(
        path=target_path,
        expected_network=norm_net,
        expected_chain_id=rpc_cid,
    )

    if verify_bytecode:
        if not hasattr(rpc_client, "eth_get_code"):
            raise DeploymentResolutionError(
                f"RPC client does not support eth_get_code for bytecode verification on network '{expected_network}'."
            )
        for name, addr in addresses.items():
            code = rpc_client.eth_get_code(addr)
            if not code or code == "0x" or len(code) <= 2:
                raise DeploymentResolutionError(
                    f"Contract '{name}' at {addr} has no on-chain bytecode on network '{expected_network}' (eth_getCode returned '{code}')."
                )

    return addresses

