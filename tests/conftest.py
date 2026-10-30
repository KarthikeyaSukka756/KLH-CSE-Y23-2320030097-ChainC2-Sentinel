# ChainC2 Sentinel — Pytest Fixtures
"""Shared fixtures for the ChainC2 Sentinel test suite."""

import os
from typing import Any, Optional
from unittest.mock import MagicMock
import pytest
import tempfile

from src.blockchain.rpc_client import RpcCallResult, RpcTxResult, encode_string
from src.scenarios.payload import SyntheticC2Payload


class MockOfflineRpcClient:
    """Deterministic offline RPC client for scenario execution in unit tests."""

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        network: str = "localhost",
        expected_chain_id: Optional[str] = None,
        timeout: float = 5.0,
    ) -> None:
        self.rpc_url = rpc_url or "http://127.0.0.1:8546"
        self.network = network or "localhost"
        self.expected_chain_id = expected_chain_id or "31337"
        self.default_sender = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        self.timeout = timeout
        self._stored_commands: dict[str, str] = {}

    def get_chain_id(self) -> str:
        return "31337"

    def eth_get_code(self, address: str, block: str = "latest") -> str:
        return "0x60806040"

    def eth_call(self, to: str, data: str, block: str = "latest") -> RpcCallResult:
        data_str = str(data)
        # C2DataStore getLatestCommand (0x4f5063c4)
        if "4f5063c4" in data_str:
            stored = self._stored_commands.get(to)
            if not stored:
                stored = SyntheticC2Payload(command="BEACON", target="http://127.0.0.1:8080/beacon").to_blockchain_string()
            return RpcCallResult(
                success=True,
                status="success",
                result="0x" + encode_string(stored),
                error_message=None,
                duration_ms=1.0,
                request_params={"to": to, "data": data},
            )
        # getCommandCount (0x9a2d834f)
        if "9a2d834f" in data_str:
            return RpcCallResult(
                success=True,
                status="success",
                result="0x0000000000000000000000000000000000000000000000000000000000000001",
                error_message=None,
                duration_ms=1.0,
                request_params={"to": to, "data": data},
            )
        # getCommandAtIndex (0x7e52b2f6)
        if "7e52b2f6" in data_str:
            stored = self._stored_commands.get(to) or SyntheticC2Payload(command="BEACON", target="http://127.0.0.1:8080/beacon").to_blockchain_string()
            return RpcCallResult(
                success=True,
                status="success",
                result="0x" + encode_string(stored),
                error_message=None,
                duration_ms=1.0,
                request_params={"to": to, "data": data},
            )
        # Generic counter / string / address returns for benign and legitimate dApps
        return RpcCallResult(
            success=True,
            status="success",
            result="0x0000000000000000000000000000000000000000000000000000000000000001",
            error_message=None,
            duration_ms=1.0,
            request_params={"to": to, "data": data},
        )

    def eth_send_transaction(
        self,
        to: str,
        data: str,
        from_addr: Optional[str] = None,
        gas: Optional[int] = 500000,
        nonce: Optional[int] = None,
    ) -> RpcTxResult:
        data_str = str(data)
        # If storeCommand (0x7246c8a5), update stored command
        if "7246c8a5" in data_str:
            try:
                from src.blockchain.rpc_client import decode_string
                clean_hex = data_str[10:] if data_str.startswith("0x7246c8a5") else data_str
                raw_payload = decode_string(clean_hex)
                self._stored_commands[to] = raw_payload
            except Exception:
                pass
        return RpcTxResult(
            success=True,
            status="success",
            tx_hash="0x4a7e9b3c2d1f0e8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a",
            block_number=101,
            gas_used=21000,
            sender=from_addr or self.default_sender,
            to=to,
            response_result={"receipt": {"status": "0x1", "blockNumber": "0x65", "gasUsed": "0x5208", "logs": []}},
        )

    def get_transaction_receipt(self, tx_hash: str, max_retries: int = 5) -> Optional[dict[str, Any]]:
        return {"status": "0x1", "blockNumber": "0x65", "gasUsed": "0x5208", "logs": []}


@pytest.fixture(autouse=True)
def mock_offline_scenario_rpc(request, monkeypatch):
    """Provide a deterministic offline RPC client for scenario execution in unit tests."""
    mod = getattr(request.module, "__name__", "")
    # Do not mock in modules that specifically test real LocalRpcClient or Sepolia boundary behavior
    if mod in ("test_sepolia_configuration", "test_real_rpc_execution"):
        return

    shared_client = MockOfflineRpcClient()

    # Patch LocalRpcClient in base scenario and runner modules so default instances use the offline double
    monkeypatch.setattr("src.blockchain.rpc_client.LocalRpcClient", lambda *a, **kw: shared_client)


@pytest.fixture
def telemetry_output_dir(tmp_path):
    """Provides a temporary directory for telemetry output during tests."""
    output_dir = tmp_path / "telemetry"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_correlation_id():
    """Provides a fixed correlation ID for deterministic testing."""
    return "test-correlation-00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_run_id():
    """Provides a fixed run ID for deterministic testing."""
    return "test-run-00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_scenario_id():
    """Provides a fixed scenario ID for deterministic testing."""
    return "test_scenario_v1"
