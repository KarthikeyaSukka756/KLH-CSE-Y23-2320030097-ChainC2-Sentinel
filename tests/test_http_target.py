# ChainC2 Sentinel — Tests for Local HTTP Target Server
"""Unit tests for the controlled local HTTP target server."""

import json
import urllib.request
from urllib.error import HTTPError

import pytest

from src.http_target.server import LocalHttpTargetServer


@pytest.mark.unit
class TestLocalHttpTargetServer:
    """Tests verifying LocalHttpTargetServer behavior and safety constraints."""

    def test_rejects_external_host(self):
        """Server must reject binding to any non-local host."""
        with pytest.raises(ValueError, match="must bind strictly to 127.0.0.1 or localhost"):
            LocalHttpTargetServer(host="192.168.1.100")

        with pytest.raises(ValueError, match="must bind strictly to 127.0.0.1 or localhost"):
            LocalHttpTargetServer(host="8.8.8.8")

    def test_lifecycle_and_health_endpoint(self):
        """Server starts on ephemeral port, responds to /health, and stops cleanly."""
        server = LocalHttpTargetServer(host="127.0.0.1", port=0)
        server.start()
        try:
            assert server.port > 0
            assert "127.0.0.1" in server.base_url

            req = urllib.request.Request(server.health_url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode("utf-8"))
                assert data["status"] == "healthy"
                assert data["service"] == "chainc2-local-http-target"
        finally:
            server.stop()

    def test_beacon_endpoint_and_request_recording(self):
        """Server handles POST /beacon, returns 200 acknowledged, and logs request."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as server:
            payload = {"client_id": "test_agent_01", "status": "ping"}
            payload_bytes = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                server.beacon_url,
                data=payload_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode("utf-8"))
                assert data["status"] == "acknowledged"
                assert data["action"] == "BEACON"

            # Verify request recording
            requests = server.received_requests
            assert len(requests) == 1
            rec = requests[0]
            assert rec["method"] == "POST"
            assert rec["path"] == "/beacon"
            assert rec["body"] == payload
            assert rec["client_address"] == "127.0.0.1"

            # Clear requests
            server.clear_requests()
            assert len(server.received_requests) == 0

    def test_unknown_path_returns_404(self):
        """Server returns 404 for any unregistered endpoint."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as server:
            unknown_url = f"{server.base_url}/nonexistent"
            req = urllib.request.Request(unknown_url, method="GET")
            with pytest.raises(HTTPError) as exc_info:
                urllib.request.urlopen(req, timeout=3.0)
            assert exc_info.value.code == 404
