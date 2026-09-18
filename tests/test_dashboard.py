# ChainC2 Sentinel — Flask Dashboard End-to-End API Unit Tests
"""Unit tests for Flask app startup, HTTP endpoints, input validation,
path traversal defense, and concurrency enforcement.
"""

import pytest
import json
from src.dashboard.app import create_app
from src.dashboard.services.experiment_service import ExperimentService


@pytest.fixture
def client():
    """Create Flask test client in testing mode."""
    app = create_app({"TESTING": True})
    with app.test_client() as test_client:
        yield test_client


@pytest.mark.unit
class TestDashboardApp:
    """Validation of Flask routes, API responses, and safety boundaries."""

    def test_index_route(self, client):
        """Verify the main single-page application dashboard loads successfully."""
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "ChainC2 Sentinel" in html
        assert "Master Research Dashboard" in html
        assert "Experiment Center" in html

    def test_api_health(self, client):
        """Verify health check endpoint returns operational status."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["version"] == "2.0.0-frozen"

    def test_api_overview(self, client):
        """Verify executive overview API delivers system status and benchmark aggregates."""
        resp = client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "system_status" in data
        assert "experiment_summary" in data
        assert "detection_summary" in data
        assert data["detection_summary"]["precision"] == 1.0

    def test_api_evaluation_endpoints(self, client):
        """Verify detection and protection evaluation endpoints."""
        resp_det = client.get("/api/evaluation/detection")
        assert resp_det.status_code == 200
        det_data = resp_det.get_json()
        assert "summary_metrics" in det_data

        resp_prot = client.get("/api/evaluation/protection")
        assert resp_prot.status_code == 200
        prot_data = resp_prot.get_json()
        assert "summary_metrics" in prot_data

    def test_api_history_and_run_detail(self, client):
        """Verify experiment history listing and single run inspection."""
        resp = client.get("/api/experiments/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "runs" in data
        assert len(data["runs"]) > 0

        first_run = data["runs"][0]
        run_id = first_run["run_id"]

        resp_detail = client.get(f"/api/experiments/run/{run_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.get_json()
        assert detail["run_id"] == run_id

        # 404 on invalid run ID
        resp_404 = client.get("/api/experiments/run/invalid_run_999999")
        assert resp_404.status_code == 404

    def test_api_execute_experiment_validation(self, client):
        """Verify experiment execution accepts valid scenarios and rejects invalid inputs."""
        # Valid execution
        resp_valid = client.post(
            "/api/experiments/execute",
            json={"scenario": "scenario_a", "repetitions": 1}
        )
        assert resp_valid.status_code == 200
        res = resp_valid.get_json()
        assert res["status"] == "success"
        assert len(res["runs"]) == 1

        # Invalid scenario rejected cleanly
        resp_invalid = client.post(
            "/api/experiments/execute",
            json={"scenario": "malicious_scenario_xyz"}
        )
        assert resp_invalid.status_code == 400

    def test_api_execute_concurrency_lock(self, client):
        """Verify server-side concurrency lock rejects simultaneous executions."""
        # Artificially acquire lock
        ExperimentService.acquire_lock()
        try:
            resp_busy = client.post(
                "/api/experiments/execute",
                json={"scenario": "scenario_a"}
            )
            assert resp_busy.status_code == 409
            data = resp_busy.get_json()
            assert "rejected" in data["error"].lower() or "progress" in data["error"].lower()
        finally:
            ExperimentService.release_lock()

    def test_api_execute_run_all_3(self, client):
        """Verify 'Run All 3' generates three independent runs."""
        resp = client.post(
            "/api/experiments/execute",
            json={"mode": "run_all_3"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        runs = data["runs"]
        assert len(runs) == 3
        scenarios = {r["scenario"] for r in runs}
        assert any("scenario_a" in s for s in scenarios)
        assert any("scenario_b" in s for s in scenarios)
        assert any("scenario_c" in s or "dapp" in s for s in scenarios)

    def test_api_live_telemetry(self, client):
        """Verify live telemetry endpoint returns events."""
        resp = client.get("/api/telemetry/live")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "events" in data
        assert "is_live" in data

    def test_api_evidence_and_verification(self, client):
        """Verify evidence discovery and SHA-256 verification endpoints."""
        resp = client.get("/api/evidence")
        assert resp.status_code == 200
        data = resp.get_json()
        bundles = data["evidence_bundles"]
        assert len(bundles) > 0

        target_id = bundles[0]["bundle_id"]
        resp_bundle = client.get(f"/api/evidence/{target_id}")
        assert resp_bundle.status_code == 200

        resp_verify = client.post(f"/api/evidence/{target_id}/verify")
        assert resp_verify.status_code == 200
        verify_data = resp_verify.get_json()
        assert verify_data["verified"] is True

    def test_api_research_summary_and_reports(self, client):
        """Verify research summary and safe markdown report endpoints."""
        resp_summary = client.get("/api/research/summary")
        assert resp_summary.status_code == 200

        resp_report = client.get("/api/research/report/DETECTION_ANALYSIS.md")
        assert resp_report.status_code == 200
        data = resp_report.get_json()
        assert "content" in data

    def test_path_traversal_rejections(self, client):
        """Verify path traversal attempts in reports and downloads are safely rejected."""
        # Report traversal attempts
        resp1 = client.get("/api/research/report/../secrets.json")
        assert resp1.status_code in [400, 404]

        resp2 = client.get("/api/research/report/..%2fsecrets.json")
        assert resp2.status_code in [400, 404]

        # Download traversal attempts
        resp3 = client.get("/api/download/..%2fevaluation_results.json")
        assert resp3.status_code in [400, 404]

        resp4 = client.get("/api/download/unregistered_type")
        assert resp4.status_code in [400, 404]

    def test_api_downloads_list_and_valid_download(self, client):
        """Verify downloads listing and approved file download."""
        resp_list = client.get("/api/downloads")
        assert resp_list.status_code == 200
        downloads = resp_list.get_json()["downloads"]
        keys = [d["key"] for d in downloads]
        assert "evaluation_json" in keys

        resp_dl = client.get("/api/download/evaluation_json")
        assert resp_dl.status_code == 200
        assert resp_dl.content_type.startswith("application/json")
