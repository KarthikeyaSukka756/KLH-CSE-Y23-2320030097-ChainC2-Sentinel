# ChainC2 Sentinel — Focused Tests for Beacon Redirect Security & Loopback Isolation
"""Tests demonstrating that:
1. Normal successful loopback beacon operation continues to work.
2. Redirects to external hostnames or IPs are rejected without being followed.
3. Redirect responses (301, 302, 303, 307, 308) are recorded accurately as failures.
4. Pre-request validation requiring HTTP and loopback destination is preserved.
5. Existing legitimate scenario behavior and locked detection criteria remain unchanged.
"""

from __future__ import annotations

import http.server
import json
import threading
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.blockchain.rpc_client import RpcCallResult, encode_string
from src.detection.rules import SyntheticC2SequenceRule
from src.detection.scoring import (
    DEFAULT_DETECTION_THRESHOLD,
    DEFAULT_WEIGHT_C2_CONFIGURATION,
    DEFAULT_WEIGHT_CONTRACT_INTERACTION,
    DEFAULT_WEIGHT_ENDPOINT_CONTEXT,
    DEFAULT_WEIGHT_NETWORK_FOLLOWUP,
    DEFAULT_WEIGHT_RPC_INTERACTION,
    DEFAULT_WEIGHT_SUSPICIOUS_RETRIEVAL,
    RuleBasedScorer,
)
from src.http_target.server import LocalHttpTargetServer
from src.models.events import TelemetrySource
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.definitions.legitimate_dapp_scenario import LegitimateDAppScenario
from src.scenarios.payload import SyntheticC2Payload


class _RedirectMockHttpServer:
    """Helper server running strictly on loopback (127.0.0.1) that issues HTTP redirects."""

    def __init__(self, redirect_status: int, redirect_location: str) -> None:
        self.redirect_status = redirect_status
        self.redirect_location = redirect_location
        self.received_requests: list[dict[str, Any]] = []

        status = self.redirect_status
        loc = self.redirect_location
        records = self.received_requests

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len) if content_len > 0 else b""
                records.append({
                    "path": self.path,
                    "method": "POST",
                    "headers": dict(self.headers),
                    "body": body,
                })
                self.send_response(status)
                self.send_header("Location", loc)
                self.send_header("Content-Type", "application/json")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(b'{"error": "redirect"}')

            def log_message(self, *args: Any) -> None:
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> _RedirectMockHttpServer:
        self.thread.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.server.shutdown()
        self.server.server_close()


def _make_mock_rpc_client(raw_payload: str) -> MagicMock:
    """Create a mock RPC client returning the encoded synthetic payload."""
    mock_rpc = MagicMock()
    mock_rpc.default_sender = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    mock_rpc.eth_call.return_value = RpcCallResult(
        success=True,
        status="success",
        result="0x" + encode_string(raw_payload),
        error_message=None,
        duration_ms=1.0,
        request_params={},
    )
    return mock_rpc


@pytest.mark.unit
class TestBeaconRedirectSecurity:
    """Verifies that the synthetic beacon client rejects redirects and preserves loopback isolation."""

    def test_normal_successful_loopback_beacon_still_works(self):
        """Standard B01 loopback beaconing to a 200 OK target continues to work normally."""
        with LocalHttpTargetServer(host="127.0.0.1", port=0) as target_srv:
            scenario = SyntheticC2Scenario(
                target_server=target_srv,
                run_id="run-c2-normal-beacon",
            )
            result = scenario.run()

            assert result.success is True
            assert result.event_counts_by_source[TelemetrySource.NETWORK.value] == 1

            net_ev = next(e for e in result.events if e.source == TelemetrySource.NETWORK)
            assert net_ev.network is not None
            assert net_ev.network.destination_host == "127.0.0.1"
            assert net_ev.network.destination_port == target_srv.port
            assert net_ev.network.status_code == 200
            assert net_ev.event_type == "http_beacon"
            assert net_ev.metadata.get("redirect_rejected") is None

            assert result.details["beacon_success"] is True
            assert result.details["http_status"] == 200
            assert result.details["error_type"] is None

            assert len(target_srv.received_requests) == 1
            assert target_srv.received_requests[0]["path"] == "/beacon"

    def test_redirect_to_external_hostname_is_not_followed(self):
        """A loopback 302 redirect targeting an external hostname is rejected and not followed."""
        external_dest = "http://external-c2-malicious.com:8080/beacon"

        with _RedirectMockHttpServer(redirect_status=302, redirect_location=external_dest) as redir_srv:
            mock_payload = SyntheticC2Payload(
                command="BEACON",
                target=f"http://127.0.0.1:{redir_srv.port}/beacon",
            ).to_blockchain_string()

            mock_rpc = _make_mock_rpc_client(mock_payload)

            scenario = SyntheticC2Scenario(
                variant_id="B01",
                run_id="run-c2-redirect-hostname",
                rpc_client=mock_rpc,
            )
            dummy_target = MagicMock()
            dummy_target.beacon_url = f"http://127.0.0.1:{redir_srv.port}/beacon"
            scenario.target_server = dummy_target

            result = scenario.run()

            assert result.success is True
            assert result.event_counts_by_source[TelemetrySource.NETWORK.value] == 1

            net_ev = next(e for e in result.events if e.source == TelemetrySource.NETWORK)
            assert net_ev.network is not None
            # Destination MUST remain the local loopback server, NEVER the external destination
            assert net_ev.network.destination_host == "127.0.0.1"
            assert net_ev.network.destination_port == redir_srv.port
            assert net_ev.network.status_code == 302
            # Event type MUST NOT be http_beacon
            assert net_ev.event_type == "network_connection"
            assert net_ev.metadata["error_type"] == "HTTP_REDIRECT_REJECTED"
            assert net_ev.metadata["redirect_rejected"] is True

            # Execution details accurately reflect failed beacon delivery
            assert result.details["error_type"] == "HTTP_REDIRECT_REJECTED"
            assert result.details["beacon_success"] is False
            assert result.details["http_status"] == 302

            # Only the local server received the initial POST; external destination was never contacted
            assert len(redir_srv.received_requests) == 1

    def test_redirect_to_external_ip_is_not_followed(self):
        """A loopback 301 redirect targeting a public IP is rejected and not followed."""
        external_ip_dest = "http://198.51.100.1:9000/exfil"

        with _RedirectMockHttpServer(redirect_status=301, redirect_location=external_ip_dest) as redir_srv:
            mock_payload = SyntheticC2Payload(
                command="BEACON",
                target=f"http://127.0.0.1:{redir_srv.port}/beacon",
            ).to_blockchain_string()

            mock_rpc = _make_mock_rpc_client(mock_payload)

            scenario = SyntheticC2Scenario(
                variant_id="B01",
                run_id="run-c2-redirect-ip",
                rpc_client=mock_rpc,
            )
            dummy_target = MagicMock()
            dummy_target.beacon_url = f"http://127.0.0.1:{redir_srv.port}/beacon"
            scenario.target_server = dummy_target

            result = scenario.run()

            assert result.success is True
            net_ev = next(e for e in result.events if e.source == TelemetrySource.NETWORK)
            assert net_ev.network is not None
            assert net_ev.network.destination_host == "127.0.0.1"
            assert net_ev.network.status_code == 301
            assert net_ev.event_type == "network_connection"
            assert net_ev.metadata["error_type"] == "HTTP_REDIRECT_REJECTED"
            assert net_ev.metadata["redirect_rejected"] is True
            assert result.details["beacon_success"] is False

    @pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
    def test_all_redirect_status_codes_are_rejected(self, status_code: int):
        """Every standard HTTP redirect status code is intercepted and rejected."""
        external_dest = "http://192.0.2.1:8000/sink"

        with _RedirectMockHttpServer(redirect_status=status_code, redirect_location=external_dest) as redir_srv:
            mock_payload = SyntheticC2Payload(
                command="BEACON",
                target=f"http://127.0.0.1:{redir_srv.port}/beacon",
            ).to_blockchain_string()

            mock_rpc = _make_mock_rpc_client(mock_payload)

            scenario = SyntheticC2Scenario(
                variant_id="B01",
                run_id=f"run-c2-redir-{status_code}",
                rpc_client=mock_rpc,
            )
            dummy_target = MagicMock()
            dummy_target.beacon_url = f"http://127.0.0.1:{redir_srv.port}/beacon"
            scenario.target_server = dummy_target

            result = scenario.run()

            assert result.success is True
            net_ev = next(e for e in result.events if e.source == TelemetrySource.NETWORK)
            assert net_ev.network is not None
            assert net_ev.network.status_code == status_code
            assert net_ev.metadata["error_type"] == "HTTP_REDIRECT_REJECTED"
            assert net_ev.metadata["redirect_rejected"] is True
            assert result.details["beacon_success"] is False


@pytest.mark.unit
class TestSecurityInvariantPreservation:
    """Ensures existing pre-request validation, legitimate scenario behavior, and detector invariants are preserved."""

    def test_pre_request_payload_validation_rejects_external_hosts(self):
        """SyntheticC2Payload still strictly rejects non-loopback hosts before any connection is made."""
        with pytest.raises(ValueError, match="Targets must strictly point to"):
            SyntheticC2Payload(
                command="BEACON",
                target="http://external-c2.com/beacon",
            )

        with pytest.raises(ValueError, match="Targets must strictly point to"):
            SyntheticC2Payload(
                command="BEACON",
                target="http://8.8.8.8/beacon",
            )

        with pytest.raises(ValueError, match="Only local 'http' protocol is allowed"):
            SyntheticC2Payload(
                command="BEACON",
                target="https://127.0.0.1/beacon",
            )

    def test_legitimate_scenario_produces_zero_network_events(self):
        """Scenario C (Legitimate DApp) continues to produce zero outbound network calls."""
        scenario = LegitimateDAppScenario(run_id="run-legit-preservation-check")
        result = scenario.run()

        assert result.success is True
        assert result.scenario_id == "legitimate_dapp"
        assert result.event_counts_by_source.get(TelemetrySource.NETWORK.value, 0) == 0
        assert result.details["network_calls_made"] == 0

    def test_benign_web3_scenario_produces_zero_network_events(self):
        """Scenario A (Benign Web3) continues to produce zero outbound network calls."""
        scenario = BenignWeb3Scenario(run_id="run-benign-preservation-check")
        result = scenario.run()

        assert result.success is True
        assert result.scenario_id == "scenario_a_benign"
        assert result.event_counts_by_source.get(TelemetrySource.NETWORK.value, 0) == 0

    def test_locked_detector_criteria_weights_and_threshold_remain_unchanged(self):
        """The 7 conjunction conditions, heuristic weights, and 80.0 threshold are strictly invariant."""
        rule = SyntheticC2SequenceRule()
        mock_seq = MagicMock()
        mock_seq.correlation_id = "test-inv-check"
        mock_seq.run_id = "test-inv-check"
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
        assert len(condition_ids) == 7

        scorer = RuleBasedScorer()
        total_weights = (
            scorer.weight_endpoint
            + scorer.weight_rpc
            + scorer.weight_contract
            + scorer.weight_retrieval
            + scorer.weight_c2_config
            + scorer.weight_network
        )
        assert total_weights == 100.0
        assert scorer.weight_endpoint == 10.0
        assert scorer.weight_rpc == 10.0
        assert scorer.weight_contract == 15.0
        assert scorer.weight_retrieval == 20.0
        assert scorer.weight_c2_config == 20.0
        assert scorer.weight_network == 25.0
        assert scorer.threshold == 80.0

        assert DEFAULT_WEIGHT_ENDPOINT_CONTEXT == 10.0
        assert DEFAULT_WEIGHT_RPC_INTERACTION == 10.0
        assert DEFAULT_WEIGHT_CONTRACT_INTERACTION == 15.0
        assert DEFAULT_WEIGHT_SUSPICIOUS_RETRIEVAL == 20.0
        assert DEFAULT_WEIGHT_C2_CONFIGURATION == 20.0
        assert DEFAULT_WEIGHT_NETWORK_FOLLOWUP == 25.0
        assert DEFAULT_DETECTION_THRESHOLD == 80.0
