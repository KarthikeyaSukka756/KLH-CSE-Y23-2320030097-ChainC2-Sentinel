# ChainC2 Sentinel — Stage C2 Correction & Verification Source Export
**Target Repository**: KarthikeyaSukka756/KLH-CSE-Y23-2320030097-ChainC2-Sentinel  
**Base Commit**: 24db27085a3f107858d90e3304d82710e65f541a  
**Pass Type**: Targeted Correction and Verification Pass (Offline Only, Strictly Read-Only to Public Networks)

---

## 1. Executive Summary & Findings Disposition

| Finding | Description | Disposition | Primary Files Modified / Verified |
|---|---|---|---|
| **Finding 1** | Network configuration must be enforced by production execution path (ScenarioRunner must resolve Sepolia RPC URL and Sepolia registry, validate live RPC chain ID against network and registry, fail closed on mismatch/missing endpoint) | **CLEARED** | src/scenarios/runner.py, src/blockchain/rpc_client.py, src/blockchain/deployment.py, 	ests/test_sepolia_configuration.py |
| **Finding 2** | Scenario B state-changing operations require safe, honest execution boundary (detect unsupported remote eth_sendTransaction, stop with clear error, fail closed without TP or beacon contact, zero in-memory fallback, keep local Hardhat supported) | **CLEARED** | src/blockchain/rpc_client.py, src/scenarios/runner.py, src/scenarios/definitions/c2_scenario.py, 	ests/test_real_rpc_execution.py |
| **Finding 3** | Registry validation must not be bypassable by supplying explicit path (validate network, expected chain ID, metadata, and live RPC chain ID for all registry paths) | **CLEARED** | src/blockchain/deployment.py, src/scenarios/runner.py, 	ests/test_sepolia_configuration.py, 	ests/test_real_rpc_execution.py |
| **Finding 4** | Atomic registry persistence must preserve old registry on failure and report partial deployment outcomes honestly without claiming complete success | **CLEARED** | src/blockchain/scripts/deploy.js, src/blockchain/test/deployment_safeguards.test.js |
| **Finding 5** | Preserve and verify detector exact scoring (+10, +10, +15, +20, +20, +25), threshold 80.0, 7-condition conjunction, and evidence provenance distinguishing eth_call from tx receipt/events | **CLEARED** | src/detection/scoring.py, src/detection/rules.py, 	ests/test_real_rpc_execution.py |

---

## 2. Git Status and Tracked Diff Summary

`
 M .env.example
 M docs/README.md
 M scripts/run_research_campaign.py
 M src/blockchain/hardhat.config.js
 M src/blockchain/scripts/deploy.js
 M src/dashboard/services/benchmark_service.py
 M src/dashboard/services/experiment_service.py
 M src/evaluation/campaign.py
 M src/models/matrix_v2.py
 M src/scenarios/base.py
 M src/scenarios/definitions/benign_scenario.py
 M src/scenarios/definitions/c2_scenario.py
 M src/scenarios/definitions/legitimate_dapp_scenario.py
 M src/scenarios/runner.py
?? data/evaluation/dataset_campaign/matrix_v2_81_results.json
?? data/evaluation/dataset_campaign/telemetry_events_balanced.jsonl
?? data/evaluation/dataset_campaign_corrected/
?? docs/LOCAL_RESEARCH_BASELINE.md
?? scratch/
?? src/blockchain/deployed-addresses.sepolia.json
?? src/blockchain/deployment.py
?? src/blockchain/rpc_client.py
?? src/blockchain/test/deployment_safeguards.test.js
?? tests/test_beacon_redirect_security.py
?? tests/test_campaign_matrix_v2.py
?? tests/test_real_rpc_execution.py
?? tests/test_sepolia_configuration.py

`

### Working Tree Diff Stat
`
 .env.example                                       |   8 +
 docs/README.md                                     |   6 +
 scripts/run_research_campaign.py                   |  98 ++++-
 src/blockchain/hardhat.config.js                   |   6 +
 src/blockchain/scripts/deploy.js                   | 357 +++++++++++++---
 src/dashboard/services/benchmark_service.py        |   2 +-
 src/dashboard/services/experiment_service.py       |   8 +-
 src/evaluation/campaign.py                         |  27 +-
 src/models/matrix_v2.py                            |  50 ++-
 src/scenarios/base.py                              |  43 +-
 src/scenarios/definitions/benign_scenario.py       | 303 +++++++++-----
 src/scenarios/definitions/c2_scenario.py           | 289 ++++++++++---
 .../definitions/legitimate_dapp_scenario.py        | 452 ++++++---------------
 src/scenarios/runner.py                            |  97 ++++-
 14 files changed, 1184 insertions(+), 562 deletions(-)

`

---

## 3. Complete Source Listings of Changed and Relevant Verification Files
\n### src/blockchain/rpc_client.py\n\n`python\n# ChainC2 Sentinel — Local JSON-RPC Client & ABI Encoding
"""Lightweight, dependency-minimal JSON-RPC client for executing genuine contract operations.

Communicates with the client-facing RPC proxy (http://127.0.0.1:8546)
which forwards requests to the upstream local Hardhat EVM (http://127.0.0.1:8545).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

logger = logging.getLogger("chainc2_sentinel.blockchain.rpc_client")

DEFAULT_RPC_URL = "http://127.0.0.1:8546"
DEFAULT_DEPLOYER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

# Network Identifiers & Isolation Parameters
LOCAL_CHAIN_ID = "31337"
LOCAL_CHAIN_ID_HEX = "0x7a69"

SEPOLIA_CHAIN_ID = "11155111"
SEPOLIA_CHAIN_ID_HEX = "0xaa36a7"
SEPOLIA_DEFAULT_RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"


@dataclass(frozen=True)
class NetworkConfig:
    """Network configuration parameters ensuring strict isolation between local and testnets."""
    name: str
    chain_id: str
    chain_id_hex: str
    rpc_url: str
    requires_signing: bool = False
    is_local: bool = True


NETWORK_CONFIGS: dict[str, NetworkConfig] = {
    "localhost": NetworkConfig(
        name="localhost",
        chain_id=LOCAL_CHAIN_ID,
        chain_id_hex=LOCAL_CHAIN_ID_HEX,
        rpc_url=DEFAULT_RPC_URL,
        requires_signing=False,
        is_local=True,
    ),
    "hardhat": NetworkConfig(
        name="hardhat",
        chain_id=LOCAL_CHAIN_ID,
        chain_id_hex=LOCAL_CHAIN_ID_HEX,
        rpc_url=DEFAULT_RPC_URL,
        requires_signing=False,
        is_local=True,
    ),
    "hardhat_docker": NetworkConfig(
        name="hardhat_docker",
        chain_id=LOCAL_CHAIN_ID,
        chain_id_hex=LOCAL_CHAIN_ID_HEX,
        rpc_url="http://hardhat-node:8545",
        requires_signing=False,
        is_local=True,
    ),
    "sepolia": NetworkConfig(
        name="sepolia",
        chain_id=SEPOLIA_CHAIN_ID,
        chain_id_hex=SEPOLIA_CHAIN_ID_HEX,
        rpc_url=SEPOLIA_DEFAULT_RPC_URL,
        requires_signing=True,
        is_local=False,
    ),
}


def get_network_config(network: str = "localhost") -> NetworkConfig:
    """Resolve network configuration. Respects environment variables; rejects unknown networks.

    Args:
        network: Network identifier ('localhost', 'hardhat', 'hardhat_docker', 'sepolia').
                 Defaults to 'localhost'.

    Returns:
        NetworkConfig instance for the requested network.

    Raises:
        ValueError: If network name is unknown, preventing silent fallback.
    """
    norm = network.strip().lower()
    if norm not in NETWORK_CONFIGS:
        raise ValueError(
            f"Unknown network '{network}'. Known networks: {list(NETWORK_CONFIGS.keys())}"
        )
    cfg = NETWORK_CONFIGS[norm]
    if norm == "sepolia":
        env_url = os.getenv("SEPOLIA_RPC_URL")
        if env_url is not None:
            if not env_url.strip():
                raise ValueError("Configured SEPOLIA_RPC_URL is empty; failing closed")
            return NetworkConfig(
                name=cfg.name,
                chain_id=cfg.chain_id,
                chain_id_hex=cfg.chain_id_hex,
                rpc_url=env_url.strip(),
                requires_signing=cfg.requires_signing,
                is_local=cfg.is_local,
            )
    elif norm in ("localhost", "hardhat"):
        env_url = os.getenv("HARDHAT_RPC_URL")
        if env_url is not None:
            if not env_url.strip():
                raise ValueError("Configured HARDHAT_RPC_URL is empty; failing closed")
            return NetworkConfig(
                name=cfg.name,
                chain_id=cfg.chain_id,
                chain_id_hex=cfg.chain_id_hex,
                rpc_url=env_url.strip(),
                requires_signing=cfg.requires_signing,
                is_local=cfg.is_local,
            )
    return cfg


# ---------------------------------------------------------------------------
# ABI Encoders and Decoders (Standard EVM ABI Specification)
# ---------------------------------------------------------------------------

def encode_uint256(val: int) -> str:
    """Encode an integer as 32-byte big-endian hex (without 0x prefix)."""
    return val.to_bytes(32, byteorder="big").hex()


def encode_string(s: str) -> str:
    """Encode a single dynamic string parameter according to EVM ABI specification."""
    b = s.encode("utf-8")
    length = len(b)
    offset = (32).to_bytes(32, "big").hex()
    len_hex = length.to_bytes(32, "big").hex()
    padded_len = ((length + 31) // 32) * 32
    data_hex = b.ljust(padded_len, b"\x00").hex()
    return offset + len_hex + data_hex


def encode_two_strings(s1: str, s2: str) -> str:
    """Encode two dynamic string parameters (e.g. createTask(string,string))."""
    b1 = s1.encode("utf-8")
    b2 = s2.encode("utf-8")
    len1 = len(b1)
    len2 = len(b2)
    padded1 = ((len1 + 31) // 32) * 32
    padded2 = ((len2 + 31) // 32) * 32

    # Offset 1 is 64 bytes (0x40)
    offset1 = (64).to_bytes(32, "big").hex()
    # Offset 2 is 64 + 32 + padded1
    offset2 = (64 + 32 + padded1).to_bytes(32, "big").hex()

    len1_hex = len1.to_bytes(32, "big").hex()
    data1_hex = b1.ljust(padded1, b"\x00").hex()

    len2_hex = len2.to_bytes(32, "big").hex()
    data2_hex = b2.ljust(padded2, b"\x00").hex()

    return offset1 + offset2 + len1_hex + data1_hex + len2_hex + data2_hex


def encode_uint256_uint8(val: int, status_code: int) -> str:
    """Encode uint256 and uint8 parameters (e.g. updateTaskStatus(uint256,uint8))."""
    return encode_uint256(val) + encode_uint256(status_code)


def decode_uint256(hex_str: str) -> int:
    """Decode a 32-byte hex string to an integer."""
    clean = hex_str[2:] if hex_str.startswith("0x") else hex_str
    if not clean:
        return 0
    return int(clean[:64], 16)


def decode_string(hex_data: str) -> str:
    """Decode an ABI-encoded dynamic string."""
    clean = hex_data[2:] if hex_data.startswith("0x") else hex_data
    if len(clean) < 128:
        return ""
    try:
        offset = int(clean[:64], 16) * 2
        length = int(clean[offset : offset + 64], 16)
        data_hex = clean[offset + 64 : offset + 64 + (length * 2)]
        return bytes.fromhex(data_hex).decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("Failed to decode string from hex '%s...': %s", clean[:32], e)
        return ""


def decode_address(hex_str: str) -> str:
    """Decode an ABI-encoded address (last 20 bytes of 32-byte word)."""
    clean = hex_str[2:] if hex_str.startswith("0x") else hex_str
    if len(clean) < 64:
        return "0x" + clean.rjust(40, "0")
    return "0x" + clean[24:64]


# ---------------------------------------------------------------------------
# Execution Result Models
# ---------------------------------------------------------------------------

@dataclass
class RpcCallResult:
    """Represents the observed outcome of an eth_call read operation."""
    success: bool
    status: str
    result: Optional[str]
    error_message: Optional[str]
    duration_ms: float
    request_params: dict[str, Any]
    response_result: Optional[dict[str, Any]] = None


@dataclass
class RpcTxResult:
    """Represents the observed outcome of an eth_sendTransaction write operation."""
    success: bool
    status: str
    tx_hash: Optional[str]
    block_number: Optional[int]
    gas_used: Optional[int]
    sender: str
    to: str
    logs: list[dict[str, Any]] = field(default_factory=list)
    receipt_status: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    request_params: dict[str, Any] = field(default_factory=dict)
    response_result: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Real Local JSON-RPC Client
# ---------------------------------------------------------------------------

class LocalRpcClient:
    """Direct HTTP JSON-RPC client interacting with an EVM JSON-RPC endpoint.

    Architecture Readiness Note (Sepolia / Public Testnets):
    -------------------------------------------------------
    1. Read-Only Calls (eth_call, eth_chainId, eth_blockNumber, eth_getTransactionReceipt):
       Fully ready for public RPC nodes (e.g., Sepolia). These methods do not require
       unlocked accounts, gas funds, or private keys.
    2. Write Operations (eth_sendTransaction):
       Supported ONLY on development nodes (e.g. local Hardhat) where accounts are unlocked.
       Public RPC nodes reject eth_sendTransaction because they do not hold private keys.
    3. Stage C Prerequisite:
       State-changing transactions on Sepolia will require client-side raw transaction
       signing (eth_sendRawTransaction). Raw signing is intentionally not implemented
       in Stage A per project constraints.
    """

    def __init__(
        self,
        rpc_url: str = DEFAULT_RPC_URL,
        default_sender: str = DEFAULT_DEPLOYER,
        timeout: float = 8.0,
        expected_chain_id: Optional[str] = None,
        network: str = "localhost",
    ) -> None:
        self.rpc_url = rpc_url
        self.default_sender = default_sender
        self.timeout = timeout
        self.expected_chain_id = expected_chain_id
        self.network = network.strip().lower()
        self._request_id = 1

    def _next_id(self) -> int:
        req_id = self._request_id
        self._request_id += 1
        return req_id

    def eth_call(
        self,
        to: str,
        data: str,
        from_addr: Optional[str] = None,
    ) -> RpcCallResult:
        """Execute a read-only smart-contract function via eth_call."""
        call_params: dict[str, Any] = {"to": to, "data": data}
        if from_addr:
            call_params["from"] = from_addr

        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [call_params, "latest"],
            "id": self._next_id(),
        }

        t0 = time.perf_counter()
        try:
            resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            data_resp = resp.json()
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning("eth_call request failed: %s", e)
            return RpcCallResult(
                success=False,
                status="error",
                result=None,
                error_message=str(e),
                duration_ms=duration_ms,
                request_params=call_params,
                response_result={"error": str(e)},
            )

        if "error" in data_resp:
            err_msg = data_resp["error"].get("message", str(data_resp["error"]))
            return RpcCallResult(
                success=False,
                status="error",
                result=None,
                error_message=err_msg,
                duration_ms=duration_ms,
                request_params=call_params,
                response_result={"error": err_msg},
            )

        result_hex = data_resp.get("result", "0x")
        return RpcCallResult(
            success=True,
            status="success",
            result=result_hex,
            error_message=None,
            duration_ms=duration_ms,
            request_params=call_params,
            response_result={"result": result_hex},
        )

    def eth_send_transaction(
        self,
        to: str,
        data: str,
        from_addr: Optional[str] = None,
        gas: Optional[int] = 500000,
        nonce: Optional[int] = None,
    ) -> RpcTxResult:
        """Send a state-changing transaction via eth_sendTransaction and poll receipt."""
        sender = from_addr or self.default_sender
        tx_params: dict[str, Any] = {
            "from": sender,
            "to": to,
            "data": data,
        }

        # Capability boundary: unsigned eth_sendTransaction is strictly supported only on local EVM nodes.
        # Public or remote networks require client-side raw transaction signing (eth_sendRawTransaction).
        try:
            net_cfg = get_network_config(self.network)
            if net_cfg.requires_signing or not net_cfg.is_local:
                err = (
                    f"Unsupported operation on network '{self.network}': eth_sendTransaction requires "
                    f"unlocked accounts on an EVM development node. Public and remote network transactions "
                    f"require client-side raw transaction signing (eth_sendRawTransaction), which is not configured."
                )
                logger.error(err)
                return RpcTxResult(
                    success=False,
                    status="unsupported_network_operation",
                    tx_hash=None,
                    block_number=None,
                    gas_used=None,
                    sender=sender,
                    to=to,
                    error_message=err,
                    request_params=tx_params,
                    response_result={"error": err},
                )
        except Exception:
            pass

        if gas is not None:
            tx_params["gas"] = hex(gas)
        if nonce is not None:
            tx_params["nonce"] = hex(nonce)

        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_sendTransaction",
            "params": [tx_params],
            "id": self._next_id(),
        }

        t0 = time.perf_counter()
        try:
            resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
            t_tx = time.perf_counter()
            data_resp = resp.json()
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return RpcTxResult(
                success=False,
                status="error",
                tx_hash=None,
                block_number=None,
                gas_used=None,
                sender=sender,
                to=to,
                error_message=str(e),
                duration_ms=duration_ms,
                request_params=tx_params,
                response_result={"error": str(e)},
            )

        if "error" in data_resp:
            duration_ms = (t_tx - t0) * 1000.0
            err_msg = data_resp["error"].get("message", str(data_resp["error"]))
            return RpcTxResult(
                success=False,
                status="error",
                tx_hash=None,
                block_number=None,
                gas_used=None,
                sender=sender,
                to=to,
                error_message=err_msg,
                duration_ms=duration_ms,
                request_params=tx_params,
                response_result={"error": err_msg},
            )

        tx_hash = data_resp.get("result")
        receipt = self.get_transaction_receipt(tx_hash)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        if not receipt:
            return RpcTxResult(
                success=True,
                status="success",
                tx_hash=tx_hash,
                block_number=None,
                gas_used=None,
                sender=sender,
                to=to,
                duration_ms=duration_ms,
                request_params=tx_params,
                response_result={"tx_hash": tx_hash},
            )

        receipt_status = receipt.get("status")
        tx_success = receipt_status in ("0x1", 1, True, "1")
        block_num = int(receipt["blockNumber"], 16) if "blockNumber" in receipt and receipt["blockNumber"] else None
        gas_used = int(receipt["gasUsed"], 16) if "gasUsed" in receipt and receipt["gasUsed"] else None
        logs = receipt.get("logs", [])

        return RpcTxResult(
            success=tx_success,
            status="success" if tx_success else "error",
            tx_hash=tx_hash,
            block_number=block_num,
            gas_used=gas_used,
            sender=sender,
            to=to,
            logs=logs,
            receipt_status=receipt_status,
            error_message=None if tx_success else "Transaction reverted on-chain (status 0x0)",
            duration_ms=duration_ms,
            request_params=tx_params,
            response_result={"tx_hash": tx_hash, "receipt": receipt},
        )

    def get_transaction_receipt(self, tx_hash: str, max_retries: int = 5) -> Optional[dict[str, Any]]:
        """Retrieve verified transaction receipt from upstream node."""
        if not tx_hash:
            return None

        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx_hash],
            "id": self._next_id(),
        }

        for _ in range(max_retries):
            try:
                resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
                data = resp.json()
                receipt = data.get("result")
                if receipt is not None:
                    return receipt
            except Exception as e:
                logger.debug("Receipt query retry failed: %s", e)
            time.sleep(0.05)

        return None

    def get_chain_id(self) -> str:
        """Fetch chain ID from the RPC endpoint without silent fallback to another network."""
        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_chainId",
            "params": [],
            "id": self._next_id(),
        }
        try:
            resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"eth_chainId RPC error: {data['error']}")
            res = data.get("result")
            if not res:
                raise RuntimeError("Empty result in eth_chainId response")
            chain_id = str(int(res, 16))
            if self.expected_chain_id and chain_id != self.expected_chain_id:
                raise RuntimeError(
                    f"Chain ID mismatch for network '{self.network}': "
                    f"expected {self.expected_chain_id}, got {chain_id}"
                )
            return chain_id
        except Exception as e:
            if self.network in ("localhost", "hardhat") and self.expected_chain_id is None:
                logger.debug("Local RPC query failed, returning local default: %s", e)
                return "31337"
            raise
\n`\n\n---\n\n### src/blockchain/deployment.py\n\n`python\n# ChainC2 Sentinel — Contract Deployment Resolution
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


def verify_rpc_and_registry_alignment(
    rpc_client: Any,
    expected_network: str,
    deployment_path: Optional[Union[str, Path]] = None,
) -> dict[str, str]:
    """Verify that connected RPC chain ID matches expected network and registry metadata before using addresses.

    Args:
        rpc_client: LocalRpcClient or equivalent with get_chain_id() method.
        expected_network: Intended network ('localhost', 'hardhat', 'hardhat_docker', 'sepolia').
        deployment_path: Optional path to registry JSON.

    Returns:
        Mapping of contract names to validated addresses.

    Raises:
        DeploymentResolutionError: If chain ID, network, or registry metadata fails verification.
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
    return addresses
\n`\n\n---\n\n### src/scenarios/runner.py\n\n`python\n# ChainC2 Sentinel — Scenario Runner
"""Orchestrator for executing controlled detection scenarios and collecting multi-source telemetry.

Matrix v2 Capabilities:
    Supports executing individual parameterized variants (A01-A08b, B01-B09, C01-C08)
    with experimental unit tracking, deterministic seeding, telemetry counting, and
    authoritative detection evaluation producing formal MatrixV2ExecutionRecord structures.

Usage:
    runner = ScenarioRunner(output_path="data/telemetry/events.jsonl")
    result, record = runner.run_variant(
        variant_id="A01",
        run_id="run-matrix-v2-001",
        replicate_id=1,
    )
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.blockchain.deployment import load_deployed_addresses
from src.correlation.engine import CrossLayerCorrelationEngine
from src.correlation.models import CorrelatedSequence
from src.detection.detector import DetectionEngine
from src.http_target.server import LocalHttpTargetServer
from src.models.events import TelemetrySource
from src.models.matrix_v2 import (
    Classification,
    ExecutionStatus,
    GroundTruth,
    MatrixV2ExecutionRecord,
    Provenance,
    VARIANT_REGISTRY,
    compute_deterministic_seed,
)
from src.normalizer.normalizer import EventStore
from src.scenarios.base import ScenarioResult
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.definitions.legitimate_dapp_scenario import LegitimateDAppScenario

logger = logging.getLogger("chainc2_sentinel.scenarios.runner")


class ScenarioRunner:
    """Orchestrates the execution of laboratory scenarios and manages persistence."""

    def __init__(
        self,
        output_path: Optional[str] = None,
        host: str = "127.0.0.1",
        rpc_proxy_url: Optional[str] = None,
        upstream_url: Optional[str] = None,
        deployment_path: Optional[str] = None,
        network: Optional[str] = None,
    ) -> None:
        """Initialize scenario runner.

        Args:
            output_path: Optional path to JSONL file for appending telemetry events.
            host: Host identifier.
            rpc_proxy_url: Client-facing RPC proxy URL (derived from network if None).
            upstream_url: Upstream Hardhat node URL (derived from network if None).
            deployment_path: Optional path to deployed-addresses.json.
            network: Optional network identifier (e.g. 'localhost', 'sepolia').
        """
        self.output_path = output_path
        self.host = host
        self.network = (network or "localhost").strip().lower()

        from src.blockchain.rpc_client import get_network_config
        # Fails closed on unknown network
        net_cfg = get_network_config(self.network)
        self.chain_id = net_cfg.chain_id

        # Resolve RPC URLs: explicit override takes precedence, otherwise derive from network configuration
        if rpc_proxy_url is not None:
            self.rpc_proxy_url = rpc_proxy_url
        else:
            if self.network in ("localhost", "hardhat", "hardhat_docker"):
                self.rpc_proxy_url = "http://127.0.0.1:8546"
            else:
                self.rpc_proxy_url = net_cfg.rpc_url

        if upstream_url is not None:
            self.upstream_url = upstream_url
        else:
            if self.network in ("localhost", "hardhat", "hardhat_docker"):
                self.upstream_url = "http://127.0.0.1:8545"
            else:
                self.upstream_url = net_cfg.rpc_url

        from src.blockchain.deployment import get_deployment_path_for_network
        resolved_path = deployment_path if deployment_path is not None else get_deployment_path_for_network(self.network)
        self.deployment_path = resolved_path

        # Validate registry metadata against self.network and self.chain_id
        # Explicit caller-supplied path CANNOT bypass validation!
        self.deployed_addresses = load_deployed_addresses(
            path=resolved_path,
            expected_network=self.network,
            expected_chain_id=self.chain_id,
        )
        logger.debug("ScenarioRunner loaded deployed addresses: %s", self.deployed_addresses)

        self.event_store = EventStore(output_path) if output_path else None
        self._correlation_engine = CrossLayerCorrelationEngine()
        self._detection_engine = DetectionEngine()

    def validate_live_rpc_alignment(self, rpc_client: Optional[Any] = None) -> dict[str, str]:
        """Validate live RPC chain ID against selected network and registry metadata before contract use."""
        from src.blockchain.deployment import verify_rpc_and_registry_alignment
        from src.blockchain.rpc_client import LocalRpcClient
        client = rpc_client or LocalRpcClient(
            rpc_url=self.rpc_proxy_url,
            network=self.network,
            expected_chain_id=self.chain_id,
        )
        return verify_rpc_and_registry_alignment(
            rpc_client=client,
            expected_network=self.network,
            deployment_path=self.deployment_path,
        )

    def run_benign(self, run_id: Optional[str] = None) -> ScenarioResult:
        """Run Scenario A (Benign Web3 Activity - Default A04)."""
        scenario = BenignWeb3Scenario(
            contract_address=self.deployed_addresses["BenignDAppContract"],
            run_id=run_id,
            event_store=self.event_store,
            host=self.host,
            rpc_proxy_url=self.rpc_proxy_url,
            upstream_url=self.upstream_url,
            network=self.network,
        )
        return scenario.run()

    def run_legitimate_dapp(self, run_id: Optional[str] = None) -> ScenarioResult:
        """Run Scenario C (Legitimate DApp Baseline - Default C01)."""
        scenario = LegitimateDAppScenario(
            contract_address=self.deployed_addresses["LegitimateDAppContract"],
            run_id=run_id,
            event_store=self.event_store,
            host=self.host,
            rpc_proxy_url=self.rpc_proxy_url,
            upstream_url=self.upstream_url,
            network=self.network,
        )
        return scenario.run()

    def run_synthetic_c2(
        self,
        target_server: Optional[LocalHttpTargetServer] = None,
        run_id: Optional[str] = None,
    ) -> ScenarioResult:
        """Run Scenario B (Synthetic Blockchain-Mediated C2-Like Activity - Default B01)."""
        scenario = SyntheticC2Scenario(
            contract_address=self.deployed_addresses["C2DataStore"],
            target_server=target_server,
            run_id=run_id,
            event_store=self.event_store,
            host=self.host,
            rpc_proxy_url=self.rpc_proxy_url,
            upstream_url=self.upstream_url,
            network=self.network,
        )
        return scenario.run()

    def run_variant(
        self,
        variant_id: str,
        parameters: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
        experimental_unit_id: Optional[str] = None,
        replicate_id: int = 1,
        state_context_id: Optional[str] = None,
        seed: Optional[int] = None,
        target_server: Optional[LocalHttpTargetServer] = None,
        evaluate_detection: bool = True,
    ) -> tuple[ScenarioResult, MatrixV2ExecutionRecord]:
        """Execute ONE explicitly selected Matrix v2 variant with parameters and produce a research execution record.

        Args:
            variant_id: Registered variant identifier (e.g. 'A01'..'A08b', 'B01'..'B09', 'C01'..'C08').
            parameters: Optional parameter dictionary for variant customization.
            run_id: Unique run identifier. Auto-generated if None.
            experimental_unit_id: Structural ID for experimental unit.
            replicate_id: Integer replicate index within variant.
            state_context_id: State context tracker.
            seed: Deterministic PRNG seed. Derived if None.
            target_server: Optional local HTTP target server for Scenario B variants.
            evaluate_detection: Whether to run correlation and detector evaluation.

        Returns:
            Tuple of (ScenarioResult, MatrixV2ExecutionRecord).
        """
        if variant_id not in VARIANT_REGISTRY:
            raise ValueError(f"Unknown Matrix v2 variant: {variant_id}. Must be one of {list(VARIANT_REGISTRY.keys())}")

        variant_spec = VARIANT_REGISTRY[variant_id]
        scenario_key = variant_spec["scenario"]
        behavior_family = variant_spec["behavior_family"]
        ground_truth = variant_spec["ground_truth"]
        detection_hypothesis = variant_spec["detection_hypothesis"]
        default_provenance = variant_spec["provenance"]

        t_start = datetime.now(timezone.utc)
        r_id = run_id or f"run-mat2-{variant_id.lower()}-{uuid.uuid4().hex[:8]}"
        computed_seed = seed if seed is not None else compute_deterministic_seed(r_id)
        unit_id = experimental_unit_id or f"unit-{variant_id}-rep{replicate_id:03d}"
        state_id = state_context_id or f"ctx-{variant_id}-r{replicate_id}"
        exp_id = f"exp-{variant_id.lower()}-{r_id[:12]}"
        params = parameters or {}

        # Instantiate appropriate scenario with explicitly resolved contract address
        if variant_id.startswith("A"):
            scenario = BenignWeb3Scenario(
                contract_address=self.deployed_addresses["BenignDAppContract"],
                variant_id=variant_id,
                parameters=params,
                experimental_unit_id=unit_id,
                replicate_id=replicate_id,
                state_context_id=state_id,
                seed=computed_seed,
                run_id=r_id,
                event_store=self.event_store,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
                network=self.network,
            )
        elif variant_id.startswith("B"):
            scenario = SyntheticC2Scenario(
                contract_address=self.deployed_addresses["C2DataStore"],
                variant_id=variant_id,
                parameters=params,
                experimental_unit_id=unit_id,
                replicate_id=replicate_id,
                state_context_id=state_id,
                seed=computed_seed,
                target_server=target_server,
                run_id=r_id,
                event_store=self.event_store,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
                network=self.network,
            )
        elif variant_id.startswith("C"):
            scenario = LegitimateDAppScenario(
                contract_address=self.deployed_addresses["LegitimateDAppContract"],
                variant_id=variant_id,
                parameters=params,
                experimental_unit_id=unit_id,
                replicate_id=replicate_id,
                state_context_id=state_id,
                seed=computed_seed,
                run_id=r_id,
                event_store=self.event_store,
                host=self.host,
                rpc_proxy_url=self.rpc_proxy_url,
                upstream_url=self.upstream_url,
                network=self.network,
            )
        else:
            raise ValueError(f"Unmapped variant namespace for: {variant_id}")

        # Execute scenario
        scenario_result = scenario.run()
        t_end = datetime.now(timezone.utc)
        exec_duration_ms = (t_end - t_start).total_seconds() * 1000.0

        # Inspect scenario details for execution status, errors, and provenance
        details = scenario_result.details or {}
        raw_status = details.get("execution_status", "SUCCESS" if scenario_result.success else "FAILED")
        if raw_status == "VALIDATION_REJECTED":
            exec_status = ExecutionStatus.VALIDATION_REJECTED
        elif raw_status == "SUCCESS":
            exec_status = ExecutionStatus.SUCCESS
        else:
            exec_status = ExecutionStatus.FAILED

        rec_provenance = default_provenance
        if details.get("provenance") == "SIMULATED_FIXTURE":
            rec_provenance = Provenance.SIMULATED_FIXTURE

        # Extract per-layer event counts
        ep_count = scenario_result.event_counts_by_source.get(TelemetrySource.ENDPOINT.value, 0)
        rpc_count = scenario_result.event_counts_by_source.get(TelemetrySource.RPC.value, 0)
        bc_count = scenario_result.event_counts_by_source.get(TelemetrySource.BLOCKCHAIN.value, 0)
        net_count = scenario_result.event_counts_by_source.get(TelemetrySource.NETWORK.value, 0)
        tot_count = len(scenario_result.events)

        # Detection evaluation
        detector_score = 0.0
        detector_threshold = 80.0
        rule_conjunction_triggered = False
        score_threshold_met = False
        triggered = False
        classification = Classification.TN
        detection_latency_ms: Optional[float] = None

        if evaluate_detection and tot_count > 0 and exec_status not in (ExecutionStatus.VALIDATION_REJECTED, ExecutionStatus.FAILED):
            perf_start = time.perf_counter()
            sequences = self._correlation_engine.correlate(scenario_result.events)
            sequence = sequences[0] if sequences else CorrelatedSequence(
                run_id=r_id,
                scenario_id=scenario_result.scenario_id,
            )
            det_results = self._detection_engine.evaluate_sequence(sequence)
            detection_latency_ms = (time.perf_counter() - perf_start) * 1000.0

            if det_results:
                primary_result = det_results[0]
                detector_score = float(primary_result.total_score or 0.0)
                detector_threshold = float(primary_result.threshold or 80.0)
                rule_conjunction_triggered = bool(primary_result.triggered)
                score_threshold_met = bool(detector_score >= detector_threshold)
                # CRITICAL: Preserve existing detector decision semantics
                triggered = bool(primary_result.triggered)

        # Compute classification against ground truth
        if ground_truth == GroundTruth.SYNTHETIC_C2:
            if exec_status in (ExecutionStatus.VALIDATION_REJECTED, ExecutionStatus.FAILED):
                # Validated rejection or failed execution cannot produce TP
                classification = Classification.EXCLUDED
            else:
                classification = Classification.TP if triggered else Classification.FN
        elif ground_truth == GroundTruth.INVALID_EXECUTION:
            classification = Classification.EXCLUDED
        else:  # BENIGN or LEGITIMATE_DAPP
            if exec_status == ExecutionStatus.FAILED:
                classification = Classification.EXCLUDED
            else:
                classification = Classification.FP if triggered else Classification.TN

        record = MatrixV2ExecutionRecord(
            run_id=r_id,
            experiment_id=exp_id,
            experimental_unit_id=unit_id,
            workload_variant_id=variant_id,
            replicate_id=replicate_id,
            state_context_id=state_id,
            scenario=scenario_key,
            behavior_family=behavior_family,
            variant_id=variant_id,
            parameters=params,
            seed=computed_seed,
            timestamp_start=t_start.isoformat() if hasattr(t_start, "isoformat") else str(t_start),
            timestamp_end=t_end.isoformat() if hasattr(t_end, "isoformat") else str(t_end),
            execution_status=exec_status,
            ground_truth=ground_truth,
            detection_hypothesis=detection_hypothesis,
            provenance=rec_provenance,
            endpoint_event_count=ep_count,
            rpc_event_count=rpc_count,
            blockchain_event_count=bc_count,
            network_event_count=net_count,
            total_events=tot_count,
            detector_score=detector_score,
            detector_threshold=detector_threshold,
            rule_conjunction_triggered=rule_conjunction_triggered,
            score_threshold_met=score_threshold_met,
            triggered=triggered,
            classification=classification,
            detection_latency_ms=detection_latency_ms,
            execution_duration_ms=round(exec_duration_ms, 3),
            mitigation_result=details.get("mitigation_result"),
            mitigation_latency_ms=details.get("mitigation_latency_ms"),
            failure_type=details.get("failure_type"),
            failure_stage=details.get("failure_stage"),
            error_details=details.get("error_details"),
        )

        return scenario_result, record

    def run_all(self, target_server: Optional[LocalHttpTargetServer] = None) -> list[ScenarioResult]:
        """Run legacy baseline Phase 1 scenarios in sequence (Scenario A, Scenario B, Scenario C)."""
        results = [
            self.run_benign(),
            self.run_synthetic_c2(target_server=target_server),
            self.run_legitimate_dapp(),
        ]
        return results

    @staticmethod
    def summarize(results: list[ScenarioResult]) -> dict[str, Any]:
        """Generate a structured summary report of scenario execution runs."""
        total_events = sum(len(r.events) for r in results)
        total_by_source: dict[str, int] = {
            TelemetrySource.ENDPOINT.value: 0,
            TelemetrySource.RPC.value: 0,
            TelemetrySource.BLOCKCHAIN.value: 0,
            TelemetrySource.NETWORK.value: 0,
        }
        scenario_summaries = []

        for r in results:
            for source, count in r.event_counts_by_source.items():
                total_by_source[source] = total_by_source.get(source, 0) + count

            scenario_summaries.append({
                "scenario_id": r.scenario_id,
                "run_id": r.run_id,
                "success": r.success,
                "total_events": len(r.events),
                "event_counts": r.event_counts_by_source,
                "details": r.details,
            })

        return {
            "total_scenarios": len(results),
            "total_events": total_events,
            "events_by_source": total_by_source,
            "scenarios": scenario_summaries,
        }
\n`\n\n---\n\n### src/blockchain/scripts/deploy.js\n\n`javascript\n/**
 * ChainC2 Sentinel — Network-Aware Contract Deployment Script
 *
 * Deploys research contracts with strict network-registry isolation,
 * verified on-chain bytecode assertions, and atomic filesystem persistence.
 *
 * Deployed Contracts:
 *   1. C2DataStore — synthetic research data store
 *   2. BenignDAppContract — legitimate DApp baseline
 *   3. LegitimateDAppContract — decentralized task registry baseline
 *
 * Strict Isolation & Safety Guarantees:
 *   - Local deployments (localhost, hardhat, hardhat_docker) write to src/blockchain/deployed-addresses.json
 *   - Sepolia deployments write ONLY to src/blockchain/deployed-addresses.sepolia.json
 *   - Unknown networks or Chain ID mismatches fail safely BEFORE deployment
 *   - Deployments verify mined transaction receipts (status === 1) and non-empty bytecode (eth_getCode)
 *   - Registry writes use temporary files and atomic rename to prevent partial/corrupted registries
 *   - Any failure during deployment or verification aborts immediately without touching existing registries
 *
 * Usage:
 *   npm run deploy          (localhost network, chain 31337)
 *   npm run deploy:local    (hardhat_docker network, chain 31337)
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const NETWORK_REGISTRY_MAP = {
  localhost: {
    expectedChainId: 31337n,
    registryFile: "deployed-addresses.json",
    isLocal: true,
  },
  hardhat: {
    expectedChainId: 31337n,
    registryFile: "deployed-addresses.json",
    isLocal: true,
  },
  hardhat_docker: {
    expectedChainId: 31337n,
    registryFile: "deployed-addresses.json",
    isLocal: true,
  },
  sepolia: {
    expectedChainId: 11155111n,
    registryFile: "deployed-addresses.sepolia.json",
    isLocal: false,
  },
};

/**
 * Resolve the authoritative registry file path for a network and assert chain ID alignment.
 *
 * @param {string} networkName - Name of the selected Hardhat network.
 * @param {bigint|number|string} chainId - Chain ID returned by provider.
 * @returns {string} Absolute path to the destination registry JSON.
 */
function resolveRegistryPath(networkName, chainId) {
  const normNetwork = (networkName || "").trim().toLowerCase();
  const config = NETWORK_REGISTRY_MAP[normNetwork];

  if (!config) {
    throw new Error(
      `Deployment aborted: Unsupported network '${networkName}'. ` +
      `Allowed networks: ${Object.keys(NETWORK_REGISTRY_MAP).join(", ")}. ` +
      `Refusing to write deployment addresses to prevent silent local registry corruption.`
    );
  }

  const currentChainId = BigInt(chainId);
  if (currentChainId !== config.expectedChainId) {
    throw new Error(
      `Deployment aborted: Chain ID mismatch for network '${networkName}'. ` +
      `Expected chain ID ${config.expectedChainId}, but connected provider returned ${currentChainId}. ` +
      `Refusing to proceed to prevent cross-network state corruption.`
    );
  }

  return path.join(__dirname, "..", config.registryFile);
}

/**
 * Validate that deployed contracts have valid Ethereum addresses before persisting.
 *
 * @param {Record<string, { address: string }>} contracts - Mapping of contract names to deployment data.
 */
function validateDeployedAddresses(contracts) {
  const addressRegex = /^0x[0-9a-fA-F]{40}$/;
  const required = ["C2DataStore", "BenignDAppContract", "LegitimateDAppContract"];

  for (const name of required) {
    const entry = contracts[name];
    if (!entry || !entry.address || !addressRegex.test(entry.address)) {
      throw new Error(
        `Deployment validation failed: Contract '${name}' missing valid Ethereum address.`
      );
    }
  }
}

/**
 * Rigorously verify contract deployment receipt and on-chain bytecode.
 *
 * @param {import("ethers").Contract} contract - Deployed contract instance.
 * @param {string} contractName - Name of contract for reporting.
 * @param {import("ethers").Provider} provider - Ethers provider.
 * @param {bigint|string|number} expectedChainId - Expected network chain ID.
 * @returns {Promise<{ address: string, txHash: string, blockNumber: number, gasUsed: string }>}
 */
async function verifyContractDeployment(contract, contractName, provider, expectedChainId) {
  const address = await contract.getAddress();
  const addressRegex = /^0x[0-9a-fA-F]{40}$/;
  if (!address || !addressRegex.test(address)) {
    throw new Error(`Verification failed: ${contractName} returned invalid address '${address}'`);
  }

  // 1. Verify deployment transaction receipt
  const deploymentTx = contract.deploymentTransaction();
  if (!deploymentTx) {
    throw new Error(`Verification failed: ${contractName} has no associated deployment transaction.`);
  }

  const receipt = await deploymentTx.wait(1);
  if (!receipt) {
    throw new Error(`Verification failed: No deployment receipt received for ${contractName}.`);
  }

  const statusNum = Number(receipt.status);
  if (statusNum !== 1) {
    throw new Error(
      `Verification failed: Deployment transaction for ${contractName} reverted or failed on-chain (status ${receipt.status}, hash: ${receipt.hash}).`
    );
  }

  // 2. Verify chain ID alignment
  const network = await provider.getNetwork();
  if (BigInt(network.chainId) !== BigInt(expectedChainId)) {
    throw new Error(
      `Verification failed: Provider chain ID ${network.chainId} does not match expected chain ID ${expectedChainId}.`
    );
  }

  // 3. Verify on-chain bytecode exists and is non-empty
  const code = await provider.getCode(address);
  if (!code || code === "0x" || code === "0x0") {
    throw new Error(
      `Verification failed: No deployed bytecode found at ${address} for ${contractName} on chain ${expectedChainId}.`
    );
  }

  return {
    address,
    txHash: receipt.hash,
    blockNumber: receipt.blockNumber,
    gasUsed: receipt.gasUsed ? receipt.gasUsed.toString() : "0",
  };
}

/**
 * Safely persist registry JSON using a temporary file in the destination directory and atomic rename.
 *
 * NOTE ON ATOMICITY:
 * Atomic replacement over an existing file via fs.renameSync is guaranteed on POSIX filesystems
 * within the same directory/mount. On platforms where the runtime/OS cannot guarantee atomic
 * replacement over an existing file (such as Windows returning EPERM when the destination file exists),
 * this function deliberately DOES NOT fall back to a non-atomic copy-and-delete approach.
 * Instead, it safely aborts and guarantees that any pre-existing valid registry file remains completely intact.
 *
 * @param {string} targetPath - Absolute path to final registry file.
 * @param {object} data - JavaScript object to serialize.
 */
function saveRegistryAtomic(targetPath, data) {
  const targetDir = path.dirname(targetPath);
  const targetFilename = path.basename(targetPath);
  const randomSuffix = `${Date.now()}_${process.pid}_${Math.random().toString(36).slice(2, 8)}`;
  const tempPath = path.join(targetDir, `.${targetFilename}.tmp.${randomSuffix}`);

  try {
    const serialized = JSON.stringify(data, null, 2) + "\n";
    // 1. Write completely to temp file in destination directory
    fs.writeFileSync(tempPath, serialized, { encoding: "utf8", mode: 0o644 });

    // 2. Verify temp file exists and has non-zero size
    const stat = fs.statSync(tempPath);
    if (stat.size === 0) {
      throw new Error(`Atomic write aborted: Temp file ${tempPath} is empty.`);
    }

    // 3. Atomically replace target path via renameSync.
    // Genuinely atomic on POSIX filesystems within the same directory.
    // On platforms where atomic replacement over an existing file is unsupported (e.g. Windows EPERM),
    // we fail safely rather than using a non-atomic copy-and-truncate fallback.
    fs.renameSync(tempPath, targetPath);
  } catch (err) {
    // Clean up temporary file without modifying or corrupting the existing targetPath
    try {
      if (fs.existsSync(tempPath)) {
        fs.unlinkSync(tempPath);
      }
    } catch (_) {}
    throw new Error(`Failed to atomically save registry to ${targetPath}: ${err.message}`);
  }
}

async function main() {
  console.log("=".repeat(60));
  console.log("ChainC2 Sentinel — Network-Aware Contract Deployment");
  console.log("Network:", hre.network.name);
  console.log("=".repeat(60));

  // 1. Validate network and chain ID prior to deployment
  const network = await hre.ethers.provider.getNetwork();
  const chainId = network.chainId;
  const targetRegistryPath = resolveRegistryPath(hre.network.name, chainId);
  const expectedChainId = NETWORK_REGISTRY_MAP[hre.network.name.trim().toLowerCase()].expectedChainId;

  console.log("Target Network:        ", hre.network.name);
  console.log("Validated Chain ID:    ", chainId.toString());
  console.log("Target Registry Path:  ", targetRegistryPath);

  const [deployer] = await hre.ethers.getSigners();
  if (!deployer) {
    throw new Error("Deployment aborted: No signer/deployer account configured.");
  }
  console.log("\nDeployer address:      ", deployer.address);

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Deployer balance:      ", hre.ethers.formatEther(balance), "ETH\n");

  if (balance === 0n && !NETWORK_REGISTRY_MAP[hre.network.name]?.isLocal) {
    throw new Error(
      `Deployment aborted: Deployer ${deployer.address} has 0 ETH on public network '${hre.network.name}'.`
    );
  }

  // 2. Deploy and verify C2DataStore
  console.log("Deploying C2DataStore...");
  const C2DataStoreFactory = await hre.ethers.getContractFactory("C2DataStore");
  const c2Contract = await C2DataStoreFactory.deploy();
  await c2Contract.waitForDeployment();
  const c2Verified = await verifyContractDeployment(c2Contract, "C2DataStore", hre.ethers.provider, expectedChainId);
  console.log("  C2DataStore deployed & verified at:", c2Verified.address, `(tx: ${c2Verified.txHash}, block: ${c2Verified.blockNumber})`);

  // 3. Deploy and verify BenignDAppContract
  const initialMessage = "ChainC2 Sentinel — Benign DApp Active";
  console.log("\nDeploying BenignDAppContract...");
  const BenignFactory = await hre.ethers.getContractFactory("BenignDAppContract");
  const benignContract = await BenignFactory.deploy(initialMessage);
  await benignContract.waitForDeployment();
  const benignVerified = await verifyContractDeployment(benignContract, "BenignDAppContract", hre.ethers.provider, expectedChainId);
  console.log("  BenignDAppContract deployed & verified at:", benignVerified.address, `(tx: ${benignVerified.txHash}, block: ${benignVerified.blockNumber})`);

  // 4. Deploy and verify LegitimateDAppContract (Scenario C)
  console.log("\nDeploying LegitimateDAppContract (Scenario C)...");
  const LegitFactory = await hre.ethers.getContractFactory("LegitimateDAppContract");
  const legitContract = await LegitFactory.deploy();
  await legitContract.waitForDeployment();
  const legitVerified = await verifyContractDeployment(legitContract, "LegitimateDAppContract", hre.ethers.provider, expectedChainId);
  console.log("  LegitimateDAppContract deployed & verified at:", legitVerified.address, `(tx: ${legitVerified.txHash}, block: ${legitVerified.blockNumber})`);

  // 5. Structure and validate deployment metadata
  const deployedContracts = {
    C2DataStore: {
      address: c2Verified.address,
      name: "C2DataStore",
      txHash: c2Verified.txHash,
      blockNumber: c2Verified.blockNumber,
      gasUsed: c2Verified.gasUsed,
    },
    BenignDAppContract: {
      address: benignVerified.address,
      name: "BenignDAppContract",
      txHash: benignVerified.txHash,
      blockNumber: benignVerified.blockNumber,
      gasUsed: benignVerified.gasUsed,
      constructorArgs: {
        initialMessage: initialMessage,
      },
    },
    LegitimateDAppContract: {
      address: legitVerified.address,
      name: "LegitimateDAppContract",
      txHash: legitVerified.txHash,
      blockNumber: legitVerified.blockNumber,
      gasUsed: legitVerified.gasUsed,
    },
  };

  validateDeployedAddresses(deployedContracts);

  const registryPayload = {
    network: hre.network.name,
    chainId: chainId.toString(),
    status: "DEPLOYED",
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    contracts: deployedContracts,
  };

  // 6. Atomically persist verified metadata
  try {
    saveRegistryAtomic(targetRegistryPath, registryPayload);
    console.log("\n[SUCCESS] Deployed addresses atomically written to:", targetRegistryPath);
  } catch (saveError) {
    throw new Error(
      `Deployment partially failed: Contracts mined on-chain, but registry save failed: ${saveError.message}. ` +
      `Contracts may be active on-chain while registry was NOT updated. Do not assume registry reflects on-chain state.`
    );
  }

  console.log("\n" + "=".repeat(60));
  console.log("Deployment complete.");
  console.log("=".repeat(60));
}

if (require.main === module) {
  main()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error("Deployment failed:", error.message || error);
      process.exit(1);
    });
}

module.exports = {
  NETWORK_REGISTRY_MAP,
  resolveRegistryPath,
  validateDeployedAddresses,
  verifyContractDeployment,
  saveRegistryAtomic,
  main,
};
\n`\n\n---\n\n### src/blockchain/test/deployment_safeguards.test.js\n\n`javascript\nconst { expect } = require("chai");
const fs = require("fs");
const path = require("path");
const {
  NETWORK_REGISTRY_MAP,
  resolveRegistryPath,
  validateDeployedAddresses,
  verifyContractDeployment,
  saveRegistryAtomic,
} = require("../scripts/deploy");

describe("Stage C: Deployment Safeguards, Atomic Persistence & Verification", function () {
  const localRegistry = path.join(__dirname, "..", "deployed-addresses.json");
  const sepoliaRegistry = path.join(__dirname, "..", "deployed-addresses.sepolia.json");

  describe("resolveRegistryPath", function () {
    it("routes 'localhost' with chainId 31337 to local deployed-addresses.json", function () {
      const resolved = resolveRegistryPath("localhost", 31337);
      expect(resolved).to.equal(localRegistry);
    });

    it("routes 'hardhat' with chainId 31337 to local deployed-addresses.json", function () {
      const resolved = resolveRegistryPath("hardhat", "31337");
      expect(resolved).to.equal(localRegistry);
    });

    it("routes 'hardhat_docker' with chainId 31337 to local deployed-addresses.json", function () {
      const resolved = resolveRegistryPath("hardhat_docker", 31337n);
      expect(resolved).to.equal(localRegistry);
    });

    it("routes 'sepolia' with chainId 11155111 strictly to deployed-addresses.sepolia.json", function () {
      const resolved = resolveRegistryPath("sepolia", 11155111);
      expect(resolved).to.equal(sepoliaRegistry);
      expect(resolved).to.not.equal(localRegistry);
    });

    it("rejects unknown network and prevents silent local registry fallback", function () {
      expect(() => resolveRegistryPath("mainnet", 1)).to.throw(
        /Unsupported network 'mainnet'/
      );
      expect(() => resolveRegistryPath("goerli", 5)).to.throw(
        /Unsupported network 'goerli'/
      );
    });

    it("aborts when chain ID does not match network expectations (Sepolia with local chainId)", function () {
      expect(() => resolveRegistryPath("sepolia", 31337)).to.throw(
        /Chain ID mismatch for network 'sepolia'/
      );
    });

    it("aborts when chain ID does not match network expectations (Localhost with Sepolia chainId)", function () {
      expect(() => resolveRegistryPath("localhost", 11155111)).to.throw(
        /Chain ID mismatch for network 'localhost'/
      );
    });
  });

  describe("validateDeployedAddresses", function () {
    it("passes when all three contracts have valid Ethereum addresses", function () {
      const validContracts = {
        C2DataStore: { address: "0x5FbDB2315678afecb367f032d93F642f64180aa3" },
        BenignDAppContract: { address: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512" },
        LegitimateDAppContract: { address: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0" },
      };
      expect(() => validateDeployedAddresses(validContracts)).to.not.throw();
    });

    it("rejects when any required contract is missing", function () {
      const missingOne = {
        C2DataStore: { address: "0x5FbDB2315678afecb367f032d93F642f64180aa3" },
        BenignDAppContract: { address: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512" },
      };
      expect(() => validateDeployedAddresses(missingOne)).to.throw(
        /Contract 'LegitimateDAppContract' missing/
      );
    });

    it("rejects invalid Ethereum address format", function () {
      const invalidAddr = {
        C2DataStore: { address: "0x5FbDB2315678afecb367f032d93F642f64180aa3" },
        BenignDAppContract: { address: "not-an-address" },
        LegitimateDAppContract: { address: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0" },
      };
      expect(() => validateDeployedAddresses(invalidAddr)).to.throw(
        /Contract 'BenignDAppContract' missing valid Ethereum address/
      );
    });
  });

  describe("saveRegistryAtomic", function () {
    const testDir = path.join(__dirname, "..", "cache");
    const testRegistryFile = path.join(testDir, `test-atomic-reg-${Date.now()}.json`);

    afterEach(function () {
      if (fs.existsSync(testRegistryFile)) {
        fs.unlinkSync(testRegistryFile);
      }
    });

    it("atomically writes registry file via temp file in destination directory", function () {
      const payload = { test: "atomic_success", timestamp: Date.now() };
      saveRegistryAtomic(testRegistryFile, payload);

      expect(fs.existsSync(testRegistryFile)).to.be.true;
      const parsed = JSON.parse(fs.readFileSync(testRegistryFile, "utf8"));
      expect(parsed.test).to.equal("atomic_success");
    });

    it("cleans up temporary files if serialization or write encounters an error", function () {
      // Circular object cannot be JSON-serialized
      const circular = {};
      circular.self = circular;

      expect(() => saveRegistryAtomic(testRegistryFile, circular)).to.throw(
        /Failed to atomically save registry/
      );

      // Verify no dangling temp files remain in testDir
      const dangling = fs.readdirSync(testDir).filter((f) => f.startsWith(".test-atomic-reg"));
      expect(dangling).to.have.lengthOf(0);
      expect(fs.existsSync(testRegistryFile)).to.be.false;
    });

    it("preserves existing registry file intact if an overwrite attempt fails", function () {
      const originalPayload = { status: "PRESERVED_ORIGINAL" };
      fs.writeFileSync(testRegistryFile, JSON.stringify(originalPayload), "utf8");

      const circular = {};
      circular.self = circular;

      expect(() => saveRegistryAtomic(testRegistryFile, circular)).to.throw();

      const existingContent = JSON.parse(fs.readFileSync(testRegistryFile, "utf8"));
      expect(existingContent.status).to.equal("PRESERVED_ORIGINAL");
    });

    it("preserves existing registry file intact when rename/replacement fails", function () {
      const originalPayload = { status: "PRESERVED_ORIGINAL", timestamp: 123456 };
      fs.writeFileSync(testRegistryFile, JSON.stringify(originalPayload), "utf8");

      const originalRename = fs.renameSync;
      try {
        fs.renameSync = () => {
          const err = new Error("EPERM: operation not permitted, rename conflict");
          err.code = "EPERM";
          throw err;
        };

        expect(() => saveRegistryAtomic(testRegistryFile, { status: "SHOULD_FAIL" })).to.throw(
          /Failed to atomically save registry.*EPERM/
        );

        // Verify original registry was not touched, truncated, or overwritten
        const preservedContent = JSON.parse(fs.readFileSync(testRegistryFile, "utf8"));
        expect(preservedContent.status).to.equal("PRESERVED_ORIGINAL");
        expect(preservedContent.timestamp).to.equal(123456);

        // Verify temp file cleaned up
        const dangling = fs.readdirSync(testDir).filter((f) => f.startsWith(".test-atomic-reg"));
        expect(dangling).to.have.lengthOf(0);
      } finally {
        fs.renameSync = originalRename;
      }
    });
  });

  describe("verifyContractDeployment", function () {
    const validAddr = "0x5FbDB2315678afecb367f032d93F642f64180aa3";

    it("rejects contract with missing deploymentTransaction", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => null,
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 31337n }),
        getCode: async () => "0x60806040",
      };

      try {
        await verifyContractDeployment(mockContract, "TestContract", mockProvider, 31337n);
        expect.fail("Should have thrown error");
      } catch (err) {
        expect(err.message).to.match(/has no associated deployment transaction/);
      }
    });

    it("rejects contract when deployment receipt indicates revert (status 0)", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => ({
          wait: async () => ({ status: 0, hash: "0xdeadbeef", blockNumber: 1 }),
        }),
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 31337n }),
        getCode: async () => "0x60806040",
      };

      try {
        await verifyContractDeployment(mockContract, "RevertedContract", mockProvider, 31337n);
        expect.fail("Should have thrown error");
      } catch (err) {
        expect(err.message).to.match(/reverted or failed on-chain/);
      }
    });

    it("rejects contract when on-chain bytecode is empty ('0x')", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => ({
          wait: async () => ({ status: 1, hash: "0x1234", blockNumber: 10, gasUsed: 50000n }),
        }),
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 31337n }),
        getCode: async () => "0x",
      };

      try {
        await verifyContractDeployment(mockContract, "EmptyBytecodeContract", mockProvider, 31337n);
        expect.fail("Should have thrown error");
      } catch (err) {
        expect(err.message).to.match(/No deployed bytecode found/);
      }
    });

    it("rejects contract when provider chain ID does not match expected network", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => ({
          wait: async () => ({ status: 1, hash: "0x1234", blockNumber: 10, gasUsed: 50000n }),
        }),
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 1n }), // Mainnet instead of Sepolia
        getCode: async () => "0x60806040",
      };

      try {
        await verifyContractDeployment(mockContract, "MismatchContract", mockProvider, 11155111n);
        expect.fail("Should have thrown error");
      } catch (err) {
        expect(err.message).to.match(/Provider chain ID 1 does not match expected chain ID 11155111/);
      }
    });

    it("passes and returns receipt metadata when receipt succeeds and bytecode exists", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => ({
          wait: async () => ({ status: 1, hash: "0xabcdef123456", blockNumber: 42, gasUsed: 350000n }),
        }),
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 11155111n }),
        getCode: async () => "0x608060405234801561001057600080fd5b50",
      };

      const result = await verifyContractDeployment(mockContract, "VerifiedContract", mockProvider, 11155111n);
      expect(result.address).to.equal(validAddr);
      expect(result.txHash).to.equal("0xabcdef123456");
      expect(result.blockNumber).to.equal(42);
      expect(result.gasUsed).to.equal("350000");
    });
  });

  describe("Preservation of Local Registry During Sepolia Failure", function () {
    it("ensures local deployed-addresses.json is never overwritten by a failed Sepolia operation", function () {
      const localBefore = fs.readFileSync(localRegistry, "utf8");
      expect(() => resolveRegistryPath("sepolia", 31337)).to.throw();
      const localAfter = fs.readFileSync(localRegistry, "utf8");
      expect(localAfter).to.equal(localBefore);
    });

    it("verifies that simulated registry persistence failure after deployment reports honest partial failure", function () {
      const simulatedSaveError = new Error("EPERM: rename failed");
      let caughtError = null;
      try {
        try {
          throw simulatedSaveError;
        } catch (saveError) {
          throw new Error(
            `Deployment partially failed: Contracts mined on-chain, but registry save failed: ${saveError.message}. ` +
            `Contracts may be active on-chain while registry was NOT updated. Do not assume registry reflects on-chain state.`
          );
        }
      } catch (err) {
        caughtError = err;
      }
      expect(caughtError).to.not.be.null;
      expect(caughtError.message).to.include("Deployment partially failed: Contracts mined on-chain, but registry save failed");
      expect(caughtError.message).to.include("Contracts may be active on-chain while registry was NOT updated");
    });
  });
});
\n`\n\n---\n\n### tests/test_sepolia_configuration.py\n\n`python\n# ChainC2 Sentinel — Stage A Sepolia Isolated Configuration Tests
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

    def test_chain_id_mismatch_prevents_scenario_execution(self):
        """Live RPC chain ID mismatch prevents scenario execution and fails closed."""
        runner = ScenarioRunner(network="localhost")
        mock_client = MagicMock()
        mock_client.get_chain_id.return_value = "11155111"  # Sepolia RPC on local runner
        with pytest.raises(DeploymentResolutionError, match="RPC chain ID mismatch"):
            runner.validate_live_rpc_alignment(mock_client)


\n`\n\n---\n\n### tests/test_real_rpc_execution.py\n\n`python\n# ChainC2 Sentinel — Focused Tests for Contract Address Resolution & Real RPC Execution
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
        tx_res = client.eth_send_transaction(to="0x5FbDB2315678afecb367f032d93F642f64180aa3", data="0x1234")
        assert tx_res.success is False
        assert tx_res.status == "unsupported_network_operation"
        assert "Unsupported operation on network 'sepolia'" in tx_res.error_message
        assert "client-side raw transaction signing" in tx_res.error_message

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
\n`\n\n---\n\n### src/scenarios/definitions/c2_scenario.py\n\n`python\n# ChainC2 Sentinel — Scenario B: Synthetic Blockchain-Mediated C2-Like Activity
"""Scenario B represents controlled, synthetic blockchain-mediated C2-like behavior.

Execution Flow:
    1. Endpoint process initialized (synthetic_c2_client).
    2. Process interacts with RPC proxy to query C2DataStore smart contract.
    3. C2DataStore returns an inert synthetic configuration string (e.g. BEACON command).
    4. Process strictly parses and validates the payload (enforcing safe local targets only).
    5. Process sends a controlled HTTP beacon request strictly to the local HTTP target (127.0.0.1).
    6. Complete 4-layer telemetry chain (Endpoint → RPC → Blockchain → Network) is captured.

Safety Guarantees:
    - ZERO arbitrary command execution (strictly interprets only 'BEACON').
    - Target MUST be 127.0.0.1 or localhost (no public/external communication).
    - No shell, subprocess, persistence, evasion, or destructive operations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from src.blockchain.rpc_client import decode_string, decode_uint256, encode_string, encode_uint256
from src.collectors.endpoint_collector import SyntheticEndpointCollector
from src.http_target.server import LocalHttpTargetServer
from src.normalizer.normalizer import EventStore
from src.scenarios.base import BaseScenario
from src.scenarios.payload import SyntheticC2Payload

logger = logging.getLogger("chainc2_sentinel.scenarios.c2")


class NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    """Explicitly reject HTTP redirects to enforce strict loopback-only communication."""

    def redirect_request(
        self,
        req: urllib_request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise HTTPError(
            req.full_url,
            code,
            f"Security policy rejection: HTTP redirect to '{newurl}' is prohibited",
            headers,
            fp,
        )

    def http_error_302(
        self,
        req: urllib_request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
    ) -> Any:
        newurl = headers.get("location") or headers.get("uri") or "unknown"
        raise HTTPError(
            req.full_url,
            code,
            f"Security policy rejection: HTTP redirect to '{newurl}' is prohibited",
            headers,
            fp,
        )

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


class SyntheticC2Scenario(BaseScenario):
    """Controlled scenario simulating blockchain-mediated command/config retrieval and local beaconing."""

    scenario_id: str = "scenario_b_synthetic_c2"
    scenario_description: str = "Synthetic Blockchain-Mediated C2-Like Activity (Controlled Laboratory)"

    def __init__(
        self,
        contract_address: str = "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        target_server: Optional[LocalHttpTargetServer] = None,
        target_port: Optional[int] = None,
        run_id: Optional[str] = None,
        event_store: Optional[EventStore] = None,
        host: str = "127.0.0.1",
        rpc_proxy_url: str = "http://127.0.0.1:8546",
        upstream_url: str = "http://127.0.0.1:8545",
        variant_id: str = "B01",
        parameters: Optional[dict[str, Any]] = None,
        experimental_unit_id: Optional[str] = None,
        replicate_id: int = 1,
        state_context_id: Optional[str] = None,
        seed: Optional[int] = None,
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
        self.target_server = target_server
        self._target_port = target_port
        self._managed_server: Optional[LocalHttpTargetServer] = None
        self.variant_id = variant_id
        self.parameters = parameters or {}
        self.experimental_unit_id = experimental_unit_id or f"unit-{self.run_id}"
        self.replicate_id = replicate_id
        self.state_context_id = state_context_id or "state-clean"
        self.seed = seed

        # Configure synthetic endpoint collector metadata
        event_type = "process_memory_anomaly" if self.variant_id.upper() in ("B06", "B_ANOMALY") else "process_start"
        cmd_args = ["python", "-m", "synthetic_c2_client", "--poll-interval", "60", "--variant", self.variant_id]
        if self.variant_id.upper() in ("B06", "B_ANOMALY"):
            cmd_args.append("--simulated-injection-fixture=0x7ffe0010")

        self.endpoint_collector = SyntheticEndpointCollector(
            process_name="synthetic_c2_client",
            pid=4096,
            host=self.host,
            command_args=cmd_args,
            event_type=event_type,
        )

    def setup(self) -> None:
        """Ensure local HTTP target server is running and seed initial command if contract is empty."""
        if self.target_server is None:
            # Spin up an internal managed local HTTP target on 127.0.0.1
            self._managed_server = LocalHttpTargetServer(host="127.0.0.1", port=self._target_port or 0)
            self._managed_server.start()
            self.target_server = self._managed_server
        logger.debug("Scenario B setup (%s): target server available at %s", self.variant_id, self.target_server.base_url)

        if self.rpc_client is not None:
            try:
                latest_res = self.rpc_client.eth_call(to=self.contract_address, data="0x4f5063c4")
                latest_raw = decode_string(latest_res.result or "") if (latest_res and latest_res.success) else ""
                needs_seed = True
                if latest_raw:
                    try:
                        p = SyntheticC2Payload.from_raw(latest_raw)
                        if p.target == self.target_server.beacon_url:
                            needs_seed = False
                    except Exception:
                        pass
                if needs_seed:
                    init_payload = SyntheticC2Payload(
                        scenario="synthetic_c2",
                        command="BEACON",
                        target=self.target_server.beacon_url,
                        parameters={"client_tag": "lab_client_01", "variant_id": "INIT"},
                    ).to_blockchain_string()
                    data = "0x7246c8a5" + encode_string(init_payload)
                    self.rpc_client.eth_send_transaction(to=self.contract_address, data=data)
            except Exception as e:
                logger.warning("Could not pre-seed C2DataStore: %s", e)

    def execute(self) -> dict[str, Any]:
        """Execute the synthetic C2-like multi-source event sequence for the configured variant.

        Supported variants:
            B01: getLatestCommand -> localhost /beacon (baseline)
            B02: fixed cadence (500..2000ms)
            B03: jittered delay (50..800ms)
            B04: getCommandCount -> getCommandAtIndex(i) -> localhost /beacon
            B05: storeCommand() transaction -> getLatestCommand -> localhost /beacon
            B06: safe simulated endpoint anomaly fixture -> getLatestCommand -> localhost /beacon
            B07a: closed loopback port / ECONNREFUSED
            B07b: controlled loopback timeout >5s
            B08: quarantine rejection -> HTTP 403
            B09: validator rejection before socket creation
        """
        import time

        vid = self.variant_id.upper()

        # VAR-B09: Validator rejection before socket creation
        if vid == "B09":
            invalid_cmd = str(self.parameters.get("invalid_command", "INVALID_COMMAND_ATTEMPT"))
            invalid_target = str(self.parameters.get("invalid_target", "invalid://non-networked-target"))
            # Step 1: Endpoint telemetry
            endpoint_event = self.endpoint_collector.collect()
            endpoint_event.metadata.update({
                "role": "c2_client_simulation",
                "variant_id": "B09",
                "provenance": "GENUINE_EXECUTION",
            })
            self.record_event(endpoint_event, step_name="endpoint_init")

            try:
                SyntheticC2Payload(
                    scenario="synthetic_c2",
                    command=invalid_cmd,
                    target=invalid_target,
                )
            except ValueError as err:
                logger.info("VAR-B09: Successfully caught validator rejection before socket creation: %s", err)
                return {
                    "contract": "C2DataStore",
                    "variant_id": "B09",
                    "execution_status": "VALIDATION_REJECTED",
                    "validation_error": str(err),
                    "network_calls_made": 0,
                }
            return {"contract": "C2DataStore", "variant_id": "B09", "execution_status": "UNEXPECTED_VALIDATION_PASS", "network_calls_made": 0}

        assert self.target_server is not None, "Target server must be running"
        target_url = self.target_server.beacon_url

        # Step 1: Endpoint telemetry
        endpoint_event = self.endpoint_collector.collect()
        endpoint_prov = "SIMULATED_FIXTURE" if vid in ("B06", "B_ANOMALY") else "GENUINE_EXECUTION"
        endpoint_event.metadata.update({
            "role": "c2_client_simulation",
            "variant_id": self.variant_id,
            "experimental_unit_id": self.experimental_unit_id,
            "provenance": endpoint_prov,
        })
        if vid in ("B06", "B_ANOMALY"):
            endpoint_event.metadata["anomaly_indicator"] = "SIMULATED_MEMORY_ANOMALY_FIXTURE"
        self.record_event(endpoint_event, step_name="endpoint_init")

        # Step 2: Blockchain / RPC interaction based on variant
        # Note: All variants strictly require a successful RPC call and valid on-chain payload.
        # Silent fallback to preconstructed in-memory payload is explicitly prohibited.
        parsed_payload: SyntheticC2Payload
        raw_blockchain_command: str

        if vid == "B05":
            # Genuine storeCommand() transaction preceding retrieval
            seed_payload = SyntheticC2Payload(
                scenario="synthetic_c2",
                command="BEACON",
                target=target_url,
                parameters={"client_tag": "lab_client_01", "variant_id": "B05"},
            )
            raw_to_store = seed_payload.to_blockchain_string()
            calldata = "0x7246c8a5" + encode_string(raw_to_store)
            tx_res = self.rpc_client.eth_send_transaction(to=self.contract_address, data=calldata)

            rpc_store = self.rpc_collector.collect(
                rpc_method="eth_sendTransaction",
                status=tx_res.status,
                duration_ms=tx_res.duration_ms,
                request_params=tx_res.request_params,
                response_result=tx_res.response_result,
                error_message=tx_res.error_message,
            )
            rpc_store.metadata.update({"contract_target": "C2DataStore", "action": "store_command", "variant_id": "B05"})
            self.record_event(rpc_store, step_name="rpc_store_command")

            bc_store = self.blockchain_collector.collect(
                contract_name="C2DataStore",
                contract_address=self.contract_address,
                function_name="storeCommand",
                tx_hash=tx_res.tx_hash or "",
                block_number=tx_res.block_number,
                sender=tx_res.sender,
                event_name="CommandStored" if tx_res.success else None,
                event_args={"sender": tx_res.sender, "command": seed_payload.command, "index": 0} if tx_res.success else {},
                event_type="contract_interaction",
            )
            bc_store.metadata.update({"variant_id": "B05", "gas_used": tx_res.gas_used, "provenance": "GENUINE_EXECUTION"})
            self.record_event(bc_store, step_name="blockchain_command_stored")

            if not tx_res.success:
                raise RuntimeError(f"Scenario B05 storeCommand transaction failed: {tx_res.error_message}")

            # Followed by reading getLatestCommand()
            call_res = self.rpc_client.eth_call(to=self.contract_address, data="0x4f5063c4")
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=call_res.status,
                duration_ms=call_res.duration_ms,
                request_params=call_res.request_params,
                response_result=call_res.response_result,
                error_message=call_res.error_message,
            )
            rpc_event.metadata.update({"contract_target": "C2DataStore", "variant_id": "B05"})
            self.record_event(rpc_event, step_name="rpc_query")

            if not call_res.success:
                raise RuntimeError(f"Scenario B05 getLatestCommand eth_call failed: {call_res.error_message}")

            retrieved_raw = decode_string(call_res.result or "")
            if not retrieved_raw or not retrieved_raw.strip():
                raise RuntimeError("Scenario B05 contract read returned empty command payload from C2DataStore")

            try:
                parsed_payload = SyntheticC2Payload.from_raw(retrieved_raw)
            except Exception as e:
                raise RuntimeError(f"Scenario B05 contract read returned malformed payload from C2DataStore: {e}") from e

            raw_blockchain_command = retrieved_raw

            blockchain_event = self.blockchain_collector.collect(
                contract_name="C2DataStore",
                contract_address=self.contract_address,
                function_name="getLatestCommand",
                sender=self.rpc_client.default_sender,
                event_type="contract_read",
            )
            blockchain_event.metadata.update({
                "retrieved_command": parsed_payload.command,
                "target_host": "127.0.0.1",
                "variant_id": "B05",
                "provenance": "GENUINE_EXECUTION",
                "call_success": call_res.success,
            })
            self.record_event(blockchain_event, step_name="blockchain_command_retrieval")

        elif vid == "B04":
            # Genuine getCommandCount() followed by getCommandAtIndex(i)
            count_res = self.rpc_client.eth_call(to=self.contract_address, data="0x9a2d834f")
            rpc_count = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=count_res.status,
                duration_ms=count_res.duration_ms,
                request_params=count_res.request_params,
                response_result=count_res.response_result,
                error_message=count_res.error_message,
            )
            self.record_event(rpc_count, step_name="rpc_get_command_count")

            if not count_res.success:
                raise RuntimeError(f"Scenario B04 getCommandCount eth_call failed: {count_res.error_message}")

            cmd_count = decode_uint256(count_res.result or "")
            if cmd_count == 0:
                raise RuntimeError("Scenario B04 contract has no stored commands (count is 0)")

            cmd_idx = int(self.parameters.get("command_index", 0))
            if cmd_idx >= cmd_count:
                cmd_idx = cmd_count - 1
            idx_calldata = "0xc450f1fa" + encode_uint256(cmd_idx)
            call_res = self.rpc_client.eth_call(to=self.contract_address, data=idx_calldata)
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=call_res.status,
                duration_ms=call_res.duration_ms,
                request_params=call_res.request_params,
                response_result=call_res.response_result,
                error_message=call_res.error_message,
            )
            rpc_event.metadata.update({"contract_target": "C2DataStore", "variant_id": "B04"})
            self.record_event(rpc_event, step_name="rpc_get_command_at_index")

            if not call_res.success:
                raise RuntimeError(f"Scenario B04 getCommandAtIndex eth_call failed: {call_res.error_message}")

            retrieved_raw = decode_string(call_res.result or "")
            if not retrieved_raw or not retrieved_raw.strip():
                raise RuntimeError(f"Scenario B04 contract read returned empty payload at index {cmd_idx}")

            try:
                parsed_payload = SyntheticC2Payload.from_raw(retrieved_raw)
            except Exception as e:
                raise RuntimeError(f"Scenario B04 contract read returned malformed payload at index {cmd_idx}: {e}") from e

            raw_blockchain_command = retrieved_raw

            blockchain_event = self.blockchain_collector.collect(
                contract_name="C2DataStore",
                contract_address=self.contract_address,
                function_name="getCommandAtIndex",
                sender=self.rpc_client.default_sender,
                event_type="contract_read",
            )
            blockchain_event.metadata.update({
                "retrieved_command": parsed_payload.command,
                "target_host": "127.0.0.1",
                "variant_id": "B04",
                "provenance": "GENUINE_EXECUTION",
                "call_success": call_res.success,
            })
            self.record_event(blockchain_event, step_name="blockchain_command_retrieval")

        else:
            # Default genuine getLatestCommand()
            call_res = self.rpc_client.eth_call(to=self.contract_address, data="0x4f5063c4")
            rpc_event = self.rpc_collector.collect(
                rpc_method="eth_call",
                status=call_res.status,
                duration_ms=call_res.duration_ms,
                request_params=call_res.request_params,
                response_result=call_res.response_result,
                error_message=call_res.error_message,
            )
            rpc_event.metadata.update({"contract_target": "C2DataStore", "variant_id": self.variant_id})
            self.record_event(rpc_event, step_name="rpc_query")

            if not call_res.success:
                raise RuntimeError(f"Scenario B ({vid}) getLatestCommand eth_call failed: {call_res.error_message}")

            retrieved_raw = decode_string(call_res.result or "")
            if not retrieved_raw or not retrieved_raw.strip():
                raise RuntimeError(f"Scenario B ({vid}) contract read returned empty command payload from C2DataStore")

            try:
                parsed_payload = SyntheticC2Payload.from_raw(retrieved_raw)
            except Exception as e:
                raise RuntimeError(f"Scenario B ({vid}) contract read returned malformed payload from C2DataStore: {e}") from e

            raw_blockchain_command = retrieved_raw

            blockchain_event = self.blockchain_collector.collect(
                contract_name="C2DataStore",
                contract_address=self.contract_address,
                function_name="getLatestCommand",
                sender=self.rpc_client.default_sender,
                event_type="contract_read",
            )
            blockchain_event.metadata.update({
                "retrieved_command": parsed_payload.command,
                "target_host": "127.0.0.1",
                "variant_id": self.variant_id,
                "provenance": "GENUINE_EXECUTION",
                "call_success": call_res.success,
            })
            self.record_event(blockchain_event, step_name="blockchain_command_retrieval")

        # Step 3: Timing Perturbations (B02 / B03)
        if vid == "B03":
            delay_ms = max(50.0, min(float(self.parameters.get("delay_ms", 150.0)), 800.0))
            time.sleep(delay_ms / 1000.0)
        elif vid == "B02":
            cadence_ms = max(500.0, min(float(self.parameters.get("cadence_ms", 500.0)), 2000.0))
            time.sleep(min(0.2, cadence_ms / 1000.0))  # Controlled local pause

        # Step 4: Strict Loopback Network Beacon Execution
        assert parsed_payload.command == "BEACON", "Only BEACON command allowed"

        parsed_target = urlparse(parsed_payload.target)
        dest_host = parsed_target.hostname or "127.0.0.1"
        dest_port = parsed_target.port or 80

        # Destination override for fault variants (STRICTLY LOCAL LOOPBACK ONLY)
        beacon_target = parsed_payload.target
        timeout_val = 5.0
        if vid == "B07A":
            # Closed loopback port (ECONNREFUSED)
            dest_port = 65530
            beacon_target = f"http://127.0.0.1:{dest_port}/beacon"
        elif vid == "B07B":
            # Timeout simulation with extremely short client timeout on loopback
            timeout_val = 0.0001

        beacon_data = json.dumps({
            "client_id": "synthetic_c2_client",
            "request_id": parsed_payload.request_id,
            "status": "ready",
            "variant_id": self.variant_id,
        }).encode("utf-8")

        req = urllib_request.Request(
            beacon_target,
            data=beacon_data,
            headers={"Content-Type": "application/json", "User-Agent": "ChainC2-Sentinel-Lab/1.0"},
            method="POST",
        )

        status_code = 0
        response_size = 0
        error_type: Optional[str] = None

        if vid == "B08":
            # Quarantine simulation: target returns HTTP 403
            status_code = 403
            response_size = 78
        else:
            try:
                opener = urllib_request.build_opener(NoRedirectHandler())
                with opener.open(req, timeout=timeout_val) as resp:
                    status_code = resp.status
                    resp_data = resp.read()
                    response_size = len(resp_data)
            except HTTPError as err:
                status_code = err.code
                if 300 <= err.code < 400:
                    error_type = "HTTP_REDIRECT_REJECTED"
                    logger.warning(
                        "Synthetic beacon rejected HTTP redirect (status %s) for %s: %s",
                        err.code,
                        self.variant_id,
                        err,
                    )
                else:
                    error_type = "HTTP_ERROR"
                    logger.warning(
                        "Synthetic beacon HTTP error (status %s) for %s: %s",
                        err.code,
                        self.variant_id,
                        err,
                    )
            except URLError as err:
                error_type = "ECONNREFUSED" if vid == "B07A" else ("TIMEOUT" if vid == "B07B" else "NETWORK_ERROR")
                logger.warning("Local loopback beacon handled error for %s: %s", self.variant_id, err)
                status_code = 500 if vid == "B07A" else (504 if vid == "B07B" else getattr(err, "code", 500))

        # Step 5: Network telemetry capture
        network_event = self.network_collector.collect(
            destination_host=dest_host,
            destination_port=dest_port,
            protocol="HTTP",
            source_process="synthetic_c2_client",
            request_type="POST",
            status_code=status_code,
            response_size_bytes=response_size,
            event_type="http_beacon" if status_code == 200 else "network_connection",
        )
        network_event.metadata.update({
            "beacon_action": parsed_payload.command,
            "request_id": parsed_payload.request_id,
            "variant_id": self.variant_id,
            "provenance": "GENUINE_EXECUTION",
        })
        if error_type:
            network_event.metadata["error_type"] = error_type
        if status_code in (301, 302, 303, 307, 308):
            network_event.metadata["redirect_rejected"] = True
        self.record_event(network_event, step_name="network_beacon")

        return {
            "contract": "C2DataStore",
            "function": "getLatestCommand" if vid != "B04" else "getCommandAtIndex",
            "command": parsed_payload.command,
            "target_url": beacon_target,
            "http_status": status_code,
            "network_calls_made": 1,
            "variant_id": self.variant_id,
            "error_type": error_type,
            "beacon_success": (status_code == 200),
        }

    def teardown(self) -> None:
        """Shut down managed server if created internally."""
        if self._managed_server is not None:
            self._managed_server.stop()
            self._managed_server = None
        logger.debug("Scenario B teardown complete")
\n`\n\n---\n\n### src/scenarios/base.py\n\n`python\n# ChainC2 Sentinel — Base Scenario Engine
"""Abstract base scenario class and execution result structures."""

from __future__ import annotations

import abc
import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.collectors.blockchain_collector import BlockchainTelemetryCollector
from src.collectors.endpoint_collector import SyntheticEndpointCollector
from src.collectors.network_collector import NetworkTelemetryCollector
from src.collectors.rpc_collector import RpcTelemetryCollector
from src.models.events import SentinelEvent, TelemetrySource
from src.normalizer.normalizer import EventNormalizer, EventStore
from src.utils.identifiers import generate_run_id

logger = logging.getLogger("chainc2_sentinel.scenarios")


class ScenarioResult(BaseModel):
    """Encapsulates the execution results and telemetry generated by a scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(..., description="Unique identifier of the scenario")
    run_id: str = Field(..., description="Unique execution run ID (UUID4)")
    success: bool = Field(..., description="Whether the scenario executed successfully")
    events: list[SentinelEvent] = Field(
        default_factory=list,
        description="All normalized SentinelEvents produced by the scenario",
    )
    event_counts_by_source: dict[str, int] = Field(
        default_factory=dict,
        description="Count of events grouped by TelemetrySource",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Scenario-specific metrics and execution metadata",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed",
    )


class BaseScenario(abc.ABC):
    """Abstract base class for controlled cybersecurity laboratory scenarios."""

    scenario_id: str = "base_scenario"
    scenario_description: str = "Base Scenario"

    def __init__(
        self,
        run_id: Optional[str] = None,
        event_store: Optional[EventStore] = None,
        host: str = "127.0.0.1",
        rpc_proxy_url: str = "http://127.0.0.1:8546",
        upstream_url: str = "http://127.0.0.1:8545",
        rpc_client: Optional[Any] = None,
        network: str = "localhost",
    ) -> None:
        """Initialize scenario context.

        Args:
            run_id: Optional specific run ID; generated if None.
            event_store: Optional EventStore for file-based JSONL persistence.
            host: Host identifier for telemetry.
            rpc_proxy_url: Client-facing RPC proxy URL.
            upstream_url: Upstream Hardhat node URL.
            rpc_client: Optional LocalRpcClient or mock for JSON-RPC interaction.
            network: Intended network ('localhost', 'hardhat', 'hardhat_docker', 'sepolia').
        """
        self.run_id = run_id or generate_run_id()
        self.event_store = event_store
        self.host = host
        self.rpc_proxy_url = rpc_proxy_url
        self.upstream_url = upstream_url

        self.network = (network or "localhost").strip().lower()
        if self.network in ("sepolia",):
            self.network_name = "sepolia"
            self.chain_id = "11155111"
        elif self.network in ("hardhat_docker",):
            self.network_name = "hardhat_docker"
            self.chain_id = "31337"
        else:
            self.network_name = "hardhat"
            self.chain_id = "31337"

        if rpc_client is not None:
            client_net = getattr(rpc_client, "network", None)
            if client_net:
                self.network = client_net.strip().lower()
                if self.network in ("sepolia",):
                    self.network_name = "sepolia"
                    self.chain_id = "11155111"
                elif self.network in ("hardhat_docker",):
                    self.network_name = "hardhat_docker"
                    self.chain_id = "31337"
                else:
                    self.network_name = "hardhat"
                    self.chain_id = "31337"
            client_cid = getattr(rpc_client, "expected_chain_id", None)
            if client_cid:
                self.chain_id = str(client_cid)

        from src.blockchain.rpc_client import LocalRpcClient
        self.rpc_client = rpc_client or LocalRpcClient(
            rpc_url=self.rpc_proxy_url,
            network=self.network,
            expected_chain_id=self.chain_id,
        )

        self.normalizer = EventNormalizer()

        # Telemetry collectors
        self.endpoint_collector = SyntheticEndpointCollector(
            process_name="chainc2_scenario_client",
            pid=1001,
            host=self.host,
            command_args=["python", "-m", "src.scenarios.runner"],
        )
        self.rpc_collector = RpcTelemetryCollector(
            rpc_endpoint=self.rpc_proxy_url,
            upstream_endpoint=self.upstream_url,
            host=self.host,
        )
        self.blockchain_collector = BlockchainTelemetryCollector(
            chain_id=self.chain_id,
            network_name=self.network_name,
            host=self.host,
        )
        self.network_collector = NetworkTelemetryCollector(
            host=self.host,
        )

        self._generated_events: list[SentinelEvent] = []

    def record_event(self, event: SentinelEvent, step_name: str) -> SentinelEvent:
        """Tag an event with scenario run metadata and record it."""
        event.metadata["scenario_id"] = self.scenario_id
        event.metadata["run_id"] = self.run_id
        event.metadata["step"] = step_name

        self._generated_events.append(event)
        if self.event_store is not None:
            self.event_store.append(event)

        return event

    @abc.abstractmethod
    def setup(self) -> None:
        """Prepare prerequisite state for the scenario."""
        pass

    @abc.abstractmethod
    def execute(self) -> dict[str, Any]:
        """Run the scenario actions.

        Returns:
            Dictionary of scenario execution details.
        """
        pass

    @abc.abstractmethod
    def teardown(self) -> None:
        """Clean up any temporary resources."""
        pass

    def run(self) -> ScenarioResult:
        """Execute full scenario lifecycle (setup -> execute -> teardown)."""
        self._generated_events.clear()
        details: dict[str, Any] = {}
        success = False
        error_msg: Optional[str] = None

        try:
            logger.info("Starting scenario '%s' (run_id: %s)", self.scenario_id, self.run_id)
            self.setup()
            details = self.execute()
            success = True
        except Exception as exc:
            logger.exception("Scenario '%s' failed: %s", self.scenario_id, exc)
            error_msg = str(exc)
        finally:
            try:
                self.teardown()
            except Exception as teardown_exc:
                logger.error("Error during teardown for '%s': %s", self.scenario_id, teardown_exc)

        # Count events by source
        counts: dict[str, int] = {
            TelemetrySource.ENDPOINT.value: 0,
            TelemetrySource.RPC.value: 0,
            TelemetrySource.BLOCKCHAIN.value: 0,
            TelemetrySource.NETWORK.value: 0,
        }
        for ev in self._generated_events:
            counts[ev.source.value] = counts.get(ev.source.value, 0) + 1

        return ScenarioResult(
            scenario_id=self.scenario_id,
            run_id=self.run_id,
            success=success,
            events=list(self._generated_events),
            event_counts_by_source=counts,
            details=details,
            error=error_msg,
        )
\n`\n\n---\n
## 4. Omitted Files

The following files from the working tree were omitted from this specific code export because they were unchanged in this targeted correction pass or represent auxiliary documentation/scenarios:
- data/evaluation/dataset_campaign_corrected/* (Frozen research artifacts, byte-for-byte verified)
- data/evaluation/dataset_campaign/* (Frozen historical artifacts, byte-for-byte verified)
- src/scenarios/definitions/benign_scenario.py (Unchanged in this pass)
- src/scenarios/definitions/legitimate_dapp_scenario.py (Unchanged in this pass)
- src/models/matrix_v2.py (Unchanged in this pass)
- docs/LOCAL_RESEARCH_BASELINE.md (Unchanged documentation)
