# ChainC2 Sentinel — Local HTTP Target Server
"""Safe, controlled local HTTP server for laboratory scenario testing.

Architecture:
    Scenario B (client) ──POST /beacon──→ LocalHttpTargetServer (127.0.0.1:<port>)

Safety Guarantees:
- Binds strictly to 127.0.0.1 (localhost). External network interfaces are rejected.
- Only serves predetermined, harmless synthetic endpoints (/health, /beacon).
- Never executes commands, writes to system directories, or makes outbound calls.
- Maintains an in-memory audit log of received requests for test verification.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger("chainc2_sentinel.http_target")


class TargetRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the controlled laboratory target."""

    def log_message(self, format: str, *args: Any) -> None:
        """Route HTTP server logs through Python logging rather than stderr."""
        logger.debug("LocalHttpTarget: %s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

    def do_GET(self) -> None:
        """Handle incoming GET requests."""
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {
                "status": "healthy",
                "service": "chainc2-local-http-target",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        else:
            self._send_json(404, {"error": "Not found", "path": parsed.path})

    def do_POST(self) -> None:
        """Handle incoming POST requests (e.g., synthetic beaconing)."""
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""

        body_data: Any = None
        if body_bytes:
            try:
                body_data = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                body_data = body_bytes.decode("utf-8", errors="replace")

        # Record the request into server's history
        request_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": "POST",
            "path": parsed.path,
            "headers": dict(self.headers),
            "client_address": self.client_address[0],
            "client_port": self.client_address[1],
            "body": body_data,
        }
        self.server.record_request(request_record)  # type: ignore[attr-defined]

        if parsed.path == "/beacon":
            self._send_json(200, {
                "status": "acknowledged",
                "action": "BEACON",
                "received_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            self._send_json(404, {"error": "Not found", "path": parsed.path})

    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        """Helper to send a JSON HTTP response."""
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(response_bytes)


class TargetHTTPServer(HTTPServer):
    """Custom HTTPServer maintaining an in-memory request log."""

    def __init__(self, server_address: tuple[str, int], RequestHandlerClass: type[BaseHTTPRequestHandler]):
        super().__init__(server_address, RequestHandlerClass)
        self.received_requests: list[dict[str, Any]] = []

    def record_request(self, record: dict[str, Any]) -> None:
        """Record an incoming request record in thread-safe fashion."""
        self.received_requests.append(record)


class LocalHttpTargetServer:
    """Manager for the controlled local HTTP target.

    Supports running in a background daemon thread with explicit start() / stop(),
    or via context manager `with LocalHttpTargetServer() as target:`.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        """Initialize the local HTTP target.

        Args:
            host: Must be '127.0.0.1' or 'localhost'. Public bindings are rejected.
            port: Port to bind. Defaults to 0 (selects an available ephemeral port).

        Raises:
            ValueError: If host is not strictly local.
        """
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(f"LocalHttpTargetServer must bind strictly to 127.0.0.1 or localhost, got: '{host}'")

        self.host = "127.0.0.1" if host == "localhost" else host
        self.requested_port = port
        self._server: Optional[TargetHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def port(self) -> int:
        """Return the actual bound port number."""
        if self._server is None:
            return self.requested_port
        return self._server.server_address[1]

    @property
    def base_url(self) -> str:
        """Return the base URL of the running target server."""
        return f"http://{self.host}:{self.port}"

    @property
    def beacon_url(self) -> str:
        """Return the full beacon URL."""
        return f"{self.base_url}/beacon"

    @property
    def health_url(self) -> str:
        """Return the full health URL."""
        return f"{self.base_url}/health"

    @property
    def received_requests(self) -> list[dict[str, Any]]:
        """Return copies of all received requests recorded so far."""
        if self._server is None:
            return []
        return list(self._server.received_requests)

    def start(self) -> LocalHttpTargetServer:
        """Start the HTTP server in a background daemon thread."""
        if self._running:
            return self

        self._server = TargetHTTPServer((self.host, self.requested_port), TargetRequestHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"LocalHttpTarget-{self.port}",
            daemon=True,
        )
        self._thread.start()
        self._running = True
        logger.info("LocalHttpTarget started on %s:%d", self.host, self.port)
        return self

    def stop(self) -> None:
        """Stop the HTTP server and release the bound port."""
        if not self._running or self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._running = False
        logger.info("LocalHttpTarget stopped")

    def clear_requests(self) -> None:
        """Clear recorded requests."""
        if self._server is not None:
            self._server.received_requests.clear()

    def __enter__(self) -> LocalHttpTargetServer:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
