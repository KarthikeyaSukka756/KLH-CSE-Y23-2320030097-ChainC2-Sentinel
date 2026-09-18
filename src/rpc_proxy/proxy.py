# ChainC2 Sentinel — RPC Telemetry Proxy
"""Thin aiohttp-based JSON-RPC proxy for telemetry capture.

Architecture:
    Web3 client → RPC Proxy (client-facing) → Hardhat Node (upstream)

The proxy:
- Listens on a configurable client-facing address
- Forwards JSON-RPC requests to the upstream Hardhat node
- Captures safe request/response metadata as SentinelEvents
- Preserves the distinction between client-facing and upstream endpoints

This is telemetry infrastructure, NOT C2.
Research-prototype quality — not a production API gateway.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Optional

import aiohttp
from aiohttp import web

from src.collectors.rpc_collector import RpcTelemetryCollector
from src.models.events import SentinelEvent

logger = logging.getLogger("chainc2_sentinel.rpc_proxy")


class RpcProxy:
    """Async JSON-RPC forwarding proxy with telemetry capture.

    Attributes:
        events: List of captured SentinelEvents (in-memory).
    """

    def __init__(
        self,
        listen_host: str = "0.0.0.0",
        listen_port: int = 8546,
        upstream_url: str = "http://127.0.0.1:8545",
        on_event: Optional[Callable[[SentinelEvent], None]] = None,
    ) -> None:
        """Initialize the RPC proxy.

        Args:
            listen_host: Host to bind the client-facing server to.
            listen_port: Port for the client-facing server.
            upstream_url: URL of the upstream Hardhat node.
            on_event: Optional callback invoked for each captured event.
        """
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._upstream_url = upstream_url
        self._on_event = on_event

        # Build the client-facing endpoint string
        self._rpc_endpoint = f"http://{listen_host}:{listen_port}"

        self._collector = RpcTelemetryCollector(
            rpc_endpoint=self._rpc_endpoint,
            upstream_endpoint=self._upstream_url,
        )

        self.events: list[SentinelEvent] = []
        self._filtered_contracts: set[str] = set()

    def add_contract_filter(self, contract_address: str) -> None:
        """Add a smart contract address to the RPC proxy quarantine filter."""
        self._filtered_contracts.add(contract_address.lower())
        logger.info("RPC Proxy: Added contract filter for %s", contract_address)

    def remove_contract_filter(self, contract_address: str) -> None:
        """Remove a smart contract address from the RPC proxy quarantine filter."""
        self._filtered_contracts.discard(contract_address.lower())
        logger.info("RPC Proxy: Removed contract filter for %s", contract_address)

    def clear_filters(self) -> None:
        """Clear all active contract filters."""
        self._filtered_contracts.clear()
        logger.info("RPC Proxy: Cleared all contract filters")

    def is_contract_filtered(self, contract_address: str) -> bool:
        """Check if a smart contract address is currently filtered."""
        return contract_address.lower() in self._filtered_contracts

    def create_app(self) -> web.Application:
        """Create the aiohttp web application.

        Returns:
            Configured aiohttp Application with the proxy route.
        """
        app = web.Application()
        app.router.add_post("/", self._handle_rpc)
        # Also handle root GET for health checks
        app.router.add_get("/health", self._handle_health)
        return app

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Simple health-check endpoint.

        Args:
            request: The incoming HTTP request.

        Returns:
            JSON response indicating the proxy is running.
        """
        return web.json_response({
            "status": "ok",
            "component": "rpc-proxy",
            "upstream": self._upstream_url,
            "events_captured": len(self.events),
            "filtered_contracts_count": len(self._filtered_contracts),
        })

    async def _handle_rpc(self, request: web.Request) -> web.Response:
        """Forward a JSON-RPC request and capture telemetry.

        Args:
            request: The incoming JSON-RPC POST request.

        Returns:
            The upstream response forwarded to the client.
        """
        try:
            body = await request.read()
            rpc_request = json.loads(body)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Invalid JSON-RPC request: %s", e)
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
                status=400,
            )

        rpc_method = rpc_request.get("method", "unknown")
        request_id = str(rpc_request.get("id", "")) if rpc_request.get("id") is not None else None

        # Safe parameter summary (avoid logging sensitive data)
        request_params = _safe_params_summary(rpc_request.get("params"))

        # Application-layer containment check: inspect target contract address
        target_contract = _extract_target_contract(rpc_request.get("params"))
        if target_contract and target_contract in self._filtered_contracts:
            error_msg = f"Blocked by Sentinel RPC Protection Policy: target contract {target_contract} is quarantined"
            logger.warning("RPC containment triggered for target contract: %s", target_contract)
            event = self._collector.collect(
                rpc_method=rpc_method,
                status="error",
                request_id=request_id,
                request_params=request_params,
                error_message=error_msg,
                duration_ms=0.0,
            )
            self._record_event(event)
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": error_msg,
                    },
                    "id": rpc_request.get("id"),
                },
                status=200,
            )

        start_time = time.monotonic()

        # Forward to upstream
        status = "success"
        error_message = None
        response_result = None
        upstream_response_body: dict[str, Any] = {}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._upstream_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                ) as upstream_response:
                    upstream_response_body = await upstream_response.json()
        except Exception as e:
            status = "error"
            error_message = f"Upstream connection failed: {type(e).__name__}"
            logger.error("Failed to forward to upstream %s: %s", self._upstream_url, e)

            # Capture telemetry even on failure
            duration_ms = (time.monotonic() - start_time) * 1000
            event = self._collector.collect(
                rpc_method=rpc_method,
                status=status,
                request_id=request_id,
                request_params=request_params,
                error_message=error_message,
                duration_ms=round(duration_ms, 2),
            )
            self._record_event(event)

            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32603, "message": error_message}, "id": rpc_request.get("id")},
                status=502,
            )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Check for JSON-RPC error in response
        if "error" in upstream_response_body:
            status = "error"
            rpc_error = upstream_response_body["error"]
            error_message = rpc_error.get("message", "Unknown RPC error") if isinstance(rpc_error, dict) else str(rpc_error)

        # Safe response summary
        if "result" in upstream_response_body:
            response_result = _safe_result_summary(upstream_response_body["result"])

        # Capture telemetry
        event = self._collector.collect(
            rpc_method=rpc_method,
            status=status,
            request_id=request_id,
            request_params=request_params,
            response_result=response_result,
            error_message=error_message,
            duration_ms=round(duration_ms, 2),
        )
        self._record_event(event)

        return web.json_response(upstream_response_body)

    def _record_event(self, event: SentinelEvent) -> None:
        """Record a captured event.

        Args:
            event: The SentinelEvent to record.
        """
        self.events.append(event)

        if self._on_event is not None:
            try:
                self._on_event(event)
            except Exception as e:
                logger.warning("Event callback failed: %s", e)

        logger.debug(
            "RPC event captured: %s (status=%s)",
            event.rpc.rpc_method if event.rpc else "unknown",
            event.rpc.status if event.rpc else "unknown",
        )


def _safe_params_summary(params: Any) -> Optional[dict[str, Any]]:
    """Create a safe summary of RPC request parameters.

    Avoids logging potentially sensitive data by summarizing
    rather than including raw values.

    Args:
        params: Raw JSON-RPC params (list or dict).

    Returns:
        A safe dict summary, or None if params is empty.
    """
    if params is None:
        return None
    if isinstance(params, list):
        return {"_type": "list", "_count": len(params)}
    if isinstance(params, dict):
        return {"_type": "dict", "_keys": list(params.keys())}
    return {"_type": type(params).__name__}


def _safe_result_summary(result: Any) -> Optional[dict[str, Any]]:
    """Create a safe summary of an RPC response result.

    Args:
        result: Raw JSON-RPC result value.

    Returns:
        A safe dict summary, or None.
    """
    if result is None:
        return None
    if isinstance(result, str):
        return {"_type": "string", "_length": len(result)}
    if isinstance(result, (int, float, bool)):
        return {"_type": type(result).__name__, "_value": result}
    if isinstance(result, dict):
        return {"_type": "dict", "_keys": list(result.keys())[:10]}
    if isinstance(result, list):
        return {"_type": "list", "_count": len(result)}
    return {"_type": type(result).__name__}


def _extract_target_contract(params: Any) -> Optional[str]:
    """Safely extract target contract address from JSON-RPC params for containment inspection.

    Args:
        params: Raw JSON-RPC params (list or dict).

    Returns:
        Lowercased contract address string if present, or None.
    """
    if isinstance(params, list) and len(params) > 0 and isinstance(params[0], dict):
        to_addr = params[0].get("to")
        if isinstance(to_addr, str):
            return to_addr.lower()
    elif isinstance(params, dict):
        to_addr = params.get("to")
        if isinstance(to_addr, str):
            return to_addr.lower()
    return None
