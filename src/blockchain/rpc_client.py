# ChainC2 Sentinel — Local JSON-RPC Client & ABI Encoding
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
        rpc_url: Optional[str] = None,
        default_sender: str = DEFAULT_DEPLOYER,
        timeout: float = 8.0,
        expected_chain_id: Optional[str] = None,
        network: str = "localhost",
    ) -> None:
        self.network = network.strip().lower()
        if rpc_url is not None:
            self.rpc_url = rpc_url
        else:
            net_cfg = get_network_config(self.network)
            self.rpc_url = net_cfg.rpc_url if net_cfg else DEFAULT_RPC_URL
        self.default_sender = default_sender
        self.timeout = timeout
        self.expected_chain_id = expected_chain_id
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
        # Unknown or invalid networks fail closed immediately without making an HTTP request.
        try:
            net_cfg = get_network_config(self.network)
        except Exception as e:
            err = f"Invalid or unknown network configuration for '{self.network}': {e}"
            logger.error(err)
            return RpcTxResult(
                success=False,
                status="invalid_network_configuration",
                tx_hash=None,
                block_number=None,
                gas_used=None,
                sender=sender,
                to=to,
                error_message=err,
                request_params=tx_params,
                response_result={"error": err},
            )

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
        if not tx_hash or not isinstance(tx_hash, str) or not tx_hash.startswith("0x"):
            err_msg = f"Invalid or missing transaction hash in RPC response: {data_resp}"
            duration_ms = (time.perf_counter() - t0) * 1000.0
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
                response_result=data_resp,
            )

        receipt = self.get_transaction_receipt(tx_hash)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        if not receipt:
            err_msg = f"Transaction receipt unconfirmed/timed out for tx_hash: {tx_hash}"
            return RpcTxResult(
                success=False,
                status="unconfirmed",
                tx_hash=tx_hash,
                block_number=None,
                gas_used=None,
                sender=sender,
                to=to,
                error_message=err_msg,
                duration_ms=duration_ms,
                request_params=tx_params,
                response_result={"tx_hash": tx_hash, "error": err_msg},
            )

        if not isinstance(receipt, dict):
            err_msg = f"Malformed transaction receipt returned for tx_hash: {tx_hash}"
            return RpcTxResult(
                success=False,
                status="error",
                tx_hash=tx_hash,
                block_number=None,
                gas_used=None,
                sender=sender,
                to=to,
                error_message=err_msg,
                duration_ms=duration_ms,
                request_params=tx_params,
                response_result={"tx_hash": tx_hash, "receipt": receipt, "error": err_msg},
            )

        receipt_status = receipt.get("status")
        tx_success = receipt_status in ("0x1", 1, True, "1")
        block_num = None
        if "blockNumber" in receipt and receipt["blockNumber"] is not None:
            try:
                bn = receipt["blockNumber"]
                block_num = int(bn, 16) if isinstance(bn, str) and bn.startswith("0x") else int(bn)
            except (ValueError, TypeError):
                block_num = None

        gas_used = None
        if "gasUsed" in receipt and receipt["gasUsed"] is not None:
            try:
                gu = receipt["gasUsed"]
                gas_used = int(gu, 16) if isinstance(gu, str) and gu.startswith("0x") else int(gu)
            except (ValueError, TypeError):
                gas_used = None

        logs = receipt.get("logs", [])
        if not isinstance(logs, list):
            logs = []

        return RpcTxResult(
            success=tx_success,
            status="success" if tx_success else "error",
            tx_hash=tx_hash,
            block_number=block_num,
            gas_used=gas_used,
            sender=sender,
            to=to,
            logs=logs,
            receipt_status=str(receipt_status) if receipt_status is not None else None,
            error_message=None if tx_success else f"Transaction reverted on-chain (status {receipt_status})",
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

    def eth_get_code(self, address: str, block: str = "latest") -> str:
        """Fetch on-chain bytecode for an address via eth_getCode."""
        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_getCode",
            "params": [address, block],
            "id": self._next_id(),
        }
        resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"eth_getCode RPC error: {data['error']}")
        return data.get("result", "0x")

    def eth_block_number(self) -> int:
        """Fetch the latest mined block number via eth_blockNumber."""
        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": self._next_id(),
        }
        resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"eth_blockNumber RPC error: {data['error']}")
        result = data.get("result")
        if not result:
            raise RuntimeError("Empty result in eth_blockNumber response")
        return int(result, 16) if isinstance(result, str) and result.startswith("0x") else int(result)

    def eth_get_block_by_number(
        self,
        block_num: Union[int, str],
        full_transactions: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Fetch block metadata and transactions by block number via eth_getBlockByNumber."""
        tag = hex(block_num) if isinstance(block_num, int) else block_num
        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [tag, full_transactions],
            "id": self._next_id(),
        }
        resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"eth_getBlockByNumber RPC error: {data['error']}")
        return data.get("result")

    def eth_get_transaction_by_hash(self, tx_hash: str) -> Optional[dict[str, Any]]:
        """Fetch transaction details by hash via eth_getTransactionByHash."""
        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionByHash",
            "params": [tx_hash],
            "id": self._next_id(),
        }
        resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"eth_getTransactionByHash RPC error: {data['error']}")
        return data.get("result")

    def eth_get_logs(
        self,
        from_block: Union[int, str] = "latest",
        to_block: Union[int, str] = "latest",
        address: Optional[str] = None,
        topics: Optional[list[Any]] = None,
    ) -> list[dict[str, Any]]:
        """Fetch event logs via eth_getLogs."""
        from_tag = hex(from_block) if isinstance(from_block, int) else from_block
        to_tag = hex(to_block) if isinstance(to_block, int) else to_block
        filter_params: dict[str, Any] = {
            "fromBlock": from_tag,
            "toBlock": to_tag,
        }
        if address:
            filter_params["address"] = address
        if topics:
            filter_params["topics"] = topics

        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_getLogs",
            "params": [filter_params],
            "id": self._next_id(),
        }
        resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"eth_getLogs RPC error: {data['error']}")
        return data.get("result", [])



