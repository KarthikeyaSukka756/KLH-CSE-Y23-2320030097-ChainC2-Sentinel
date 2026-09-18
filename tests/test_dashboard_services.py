# ChainC2 Sentinel — Dashboard Services Unit Tests
"""Unit tests verifying dashboard services:
- BenchmarkService (metrics aggregation, scenario counts, run details)
- EvidenceService (discovery, metadata, cryptographic SHA-256 verification)
- ReportService (research summary, path traversal rejection, whitelist downloads)
- ExperimentService (validation, concurrency lock, run isolation)
"""

import pytest
from pathlib import Path

from src.dashboard.services.benchmark_service import BenchmarkService
from src.dashboard.services.evidence_service import EvidenceService
from src.dashboard.services.report_service import ReportService
from src.dashboard.services.experiment_service import ExperimentService


@pytest.mark.unit
class TestBenchmarkService:
    """Validation of benchmark data loading and metrics aggregation."""

    def test_detection_evaluation_loads(self):
        service = BenchmarkService()
        eval_data = service.get_detection_evaluation_raw()
        assert eval_data is not None
        metrics = eval_data.get("metrics") or eval_data.get("summary_metrics")
        assert metrics is not None
        assert metrics["total_experiments"] >= 30
        assert metrics["precision"] == 1.0
        assert metrics.get("recall", metrics.get("detection_rate")) == 1.0
        assert metrics["false_positive_rate"] == 0.0

    def test_protection_evaluation_loads(self):
        service = BenchmarkService()
        prot_data = service.get_protection_evaluation_raw()
        assert prot_data is not None
        metrics = prot_data.get("metrics") or prot_data.get("summary_metrics")
        assert metrics is not None
        assert metrics["mitigation_success_rate"] == 1.0
        assert metrics["legitimate_traffic_preservation_rate"] == 1.0

    def test_overview_summary_combines_metrics(self):
        service = BenchmarkService()
        overview = service.get_overview_summary()
        assert "system_status" in overview
        assert "experiment_summary" in overview
        assert "detection_summary" in overview
        assert "latest_activity" in overview

        exp = overview["experiment_summary"]
        assert exp["total_experiments"] >= 30
        assert exp["scenario_a_count"] >= 10
        assert exp["scenario_b_count"] >= 10
        assert exp["scenario_c_count"] >= 10

    def test_history_and_run_detail(self):
        service = BenchmarkService()
        history = service.get_experiment_history()
        assert len(history) >= 30

        first_run = history[0]
        run_id = first_run["run_id"]
        detail = service.get_run_detail(run_id)
        assert detail is not None
        assert detail["run_id"] == run_id
        assert "telemetry_events" in detail
        assert "correlation" in detail
        assert "scoring" in detail


@pytest.mark.unit
class TestEvidenceService:
    """Validation of evidence discovery and cryptographic checksum verification."""

    def test_discover_evidence_bundles(self):
        service = EvidenceService()
        bundles = service.list_evidence_bundles()
        assert isinstance(bundles, list)
        assert len(bundles) > 0

        first = bundles[0]
        assert "bundle_id" in first
        assert "sha256_checksum" in first
        assert len(first["sha256_checksum"]) == 64

    def test_get_evidence_bundle(self):
        service = EvidenceService()
        bundles = service.list_evidence_bundles()
        if bundles:
            bundle_id = bundles[0]["bundle_id"]
            retrieved = service.get_evidence_bundle(bundle_id)
            assert retrieved is not None
            assert retrieved["bundle_id"] == bundle_id

    def test_verify_checksum_success_and_failure(self):
        service = EvidenceService()
        bundles = service.list_evidence_bundles()
        if bundles:
            bundle_id = bundles[0]["bundle_id"]
            res = service.verify_checksum(bundle_id)
            assert res["verified"] is True
            assert res["calculated_checksum"] == res["recorded_checksum"]

        # Nonexistent bundle
        invalid_res = service.verify_checksum("nonexistent_bundle_id_12345")
        assert invalid_res["verified"] is False
        assert "error" in invalid_res


@pytest.mark.unit
class TestReportService:
    """Validation of research reports and path traversal protection."""

    def test_research_summary_loads(self):
        service = ReportService()
        summary = service.get_research_summary()
        assert "research_question" in summary
        assert "phase1_detection_summary" in summary
        assert "phase2_protection_summary" in summary

    def test_get_allowed_report(self):
        service = ReportService()
        report = service.get_report_content("DETECTION_ANALYSIS.md")
        content = report["content"] if isinstance(report, dict) else report
        assert len(content) > 100
        assert "ChainC2 Sentinel" in content or "Detection" in content

    def test_reject_unauthorized_or_traversal_report(self):
        service = ReportService()
        with pytest.raises(ValueError):
            service.get_report_content("../secret.txt")

        with pytest.raises(ValueError):
            service.get_report_content("..\\secret.txt")

        with pytest.raises(ValueError):
            service.get_report_content("unregistered_report.md")

    def test_download_whitelist_and_rejection(self):
        service = ReportService()
        downloads = service.list_available_downloads()
        keys = [d["key"] for d in downloads]
        assert "detection_csv" in keys
        assert "evaluation_json" in keys

        # Valid download
        path, fname, mime = service.get_downloadable_file("detection_csv")
        assert path.exists()
        assert fname.endswith(".csv")

        # Invalid download key
        with pytest.raises(ValueError):
            service.get_downloadable_file("arbitrary_key")


@pytest.mark.unit
class TestExperimentService:
    """Validation of experiment execution safety, scenario validation, and isolation."""

    def test_scenario_validation(self):
        service = ExperimentService()
        with pytest.raises(ValueError, match="Invalid scenario"):
            service.execute_scenario("malicious_scenario_xyz")

        with pytest.raises(ValueError, match="Invalid scenario"):
            service.execute_scenario("../../../etc/passwd")

    def test_run_isolation_and_distinct_ids(self):
        service = ExperimentService()
        # Test Run All 3 mode produces 3 independent runs with distinct IDs
        res = service.execute_run_all_3()
        assert res["status"] == "success"
        runs = res["runs"]
        assert len(runs) == 3

        scenarios = [r["scenario"] for r in runs]
        assert any("scenario_a" in s for s in scenarios)
        assert any("scenario_b" in s for s in scenarios)
        assert any("scenario_c" in s or "dapp" in s for s in scenarios)

        run_ids = [r["run_id"] for r in runs]
        assert len(set(run_ids)) == 3, "Run IDs must be distinct for each independent scenario"

        # Check that Scenario A and C are benign and Scenario B is detected
        for r in runs:
            if "scenario_b" in r["scenario"]:
                assert r["detected"] is True
                assert r["score"] >= 80
            else:
                assert r["detected"] is False
                assert r["score"] < 80

    def test_concurrency_lock(self):
        # Verify acquire and release of concurrency lock
        acquired = ExperimentService.acquire_lock()
        assert acquired is True

        # Second acquire while locked should fail
        second_acquire = ExperimentService.acquire_lock()
        assert second_acquire is False

        ExperimentService.release_lock()

        # Should now be acquirable again
        reacquired = ExperimentService.acquire_lock()
        assert reacquired is True
        ExperimentService.release_lock()
