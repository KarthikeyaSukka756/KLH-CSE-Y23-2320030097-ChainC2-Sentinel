# ChainC2 Sentinel — Tests for Milestone 11 Final Research Analysis
"""Verification suite ensuring all Milestone 11 final research analysis reports,
structured JSON summaries, numerical cross-references, and safety declarations are valid.
"""

import json
from pathlib import Path
import pytest


@pytest.mark.unit
class TestFinalResearchAnalysis:
    """Validation suite for Milestone 11 artifacts and consistency."""

    def test_required_report_files_exist(self):
        """Verify all required final analysis markdown reports exist and are non-empty."""
        expected_reports = [
            Path("reports/final/FINAL_RESEARCH_ANALYSIS.md"),
            Path("reports/final/DETECTION_ANALYSIS.md"),
            Path("reports/final/PROTECTION_ANALYSIS.md"),
        ]
        for report_path in expected_reports:
            assert report_path.exists(), f"Missing expected report: {report_path}"
            content = report_path.read_text(encoding="utf-8")
            assert len(content) > 500, f"Report {report_path} is suspiciously short"

    def test_research_summary_json_exists_and_valid(self):
        """Verify results/final/research_summary.json exists and adheres to schema."""
        summary_path = Path("results/final/research_summary.json")
        assert summary_path.exists(), "Missing results/final/research_summary.json"

        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        required_sections = [
            "project",
            "research_questions",
            "phase_1",
            "phase_2",
            "combined_findings",
            "observations",
            "limitations",
            "security_implications",
            "reproducibility",
            "conclusion",
        ]
        for section in required_sections:
            assert section in summary, f"Missing required top-level section: {section}"

    def test_phase_1_metrics_match_source_artifacts(self):
        """Verify Phase 1 metrics in research_summary.json match authoritative detection results."""
        summary_path = Path("results/final/research_summary.json")
        source_path = Path("results/detection/evaluation_summary.json")

        assert source_path.exists(), "Source detection summary must exist"

        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        with open(source_path, "r", encoding="utf-8") as f:
            source = json.load(f)

        p1 = summary["phase_1"]
        assert p1["total_experiments"] == source["total_experiments"] == 30
        assert p1["successful_runs"] == source["successful_runs"] == 30
        assert p1["confusion_matrix"]["true_positives"] == source["true_positives"] == 10
        assert p1["confusion_matrix"]["true_negatives"] == source["true_negatives"] == 20
        assert p1["confusion_matrix"]["false_positives"] == source["false_positives"] == 0
        assert p1["confusion_matrix"]["false_negatives"] == source["false_negatives"] == 0
        assert p1["metrics"]["detection_rate"] == source["detection_rate"] == 1.0
        assert p1["metrics"]["false_positive_rate"] == source["false_positive_rate"] == 0.0
        assert p1["metrics"]["precision"] == source["precision"] == 1.0
        assert p1["metrics"]["true_negative_rate"] == source["true_negative_rate"] == 1.0
        assert p1["metrics"]["accuracy"] == source["accuracy"] == 1.0
        assert p1["metrics"]["f1_score"] == source["f1_score"] == 1.0
        assert p1["detection_latency"]["average_ms"] == source["detection_latency"]["average_ms"]

    def test_phase_2_metrics_match_source_artifacts(self):
        """Verify Phase 2 metrics in research_summary.json match authoritative protection results."""
        summary_path = Path("results/final/research_summary.json")
        source_path = Path("results/protection/evaluation_summary.json")

        assert source_path.exists(), "Source protection summary must exist"

        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        with open(source_path, "r", encoding="utf-8") as f:
            source = json.load(f)

        p2 = summary["phase_2"]
        assert p2["total_experiments"] == source["total_experiments"] == 22
        assert p2["successful_experiments"] == source["successful_experiments"] == 22
        assert p2["metrics"]["mitigation_success_rate"] == source["mitigation_success_rate"] == 1.0
        assert p2["metrics"]["rpc_blocking_rate"] == source["rpc_blocking_rate"] == 1.0
        assert p2["metrics"]["beacon_blocking_rate"] == source["beacon_blocking_rate"] == 1.0
        assert p2["metrics"]["process_isolation_success_rate"] == source["process_isolation_success_rate"] == 1.0
        assert p2["metrics"]["legitimate_traffic_preservation_rate"] == source["legitimate_traffic_preservation_rate"] == 1.0
        assert p2["metrics"]["false_mitigation_rate"] == source["false_mitigation_rate"] == 0.0
        assert p2["metrics"]["rollback_success_rate"] == source["rollback_success_rate"] == 1.0
        assert p2["metrics"]["evidence_preservation_rate"] == source["evidence_preservation_rate"] == 1.0
        assert p2["containment_latency"]["min_ms"] == source["containment_latency"]["min_ms"] == 1.490
        assert p2["containment_latency"]["max_ms"] == source["containment_latency"]["max_ms"] == 3.564
        assert p2["containment_latency"]["avg_ms"] == source["containment_latency"]["avg_ms"] == 2.091
        assert p2["containment_latency"]["median_ms"] == source["containment_latency"]["median_ms"] == 1.755

    def test_no_placeholders_in_reports(self):
        """Verify no placeholder text ('TBD', 'TODO', 'XXX') exists in final analysis files."""
        files_to_check = [
            Path("reports/final/FINAL_RESEARCH_ANALYSIS.md"),
            Path("reports/final/DETECTION_ANALYSIS.md"),
            Path("reports/final/PROTECTION_ANALYSIS.md"),
            Path("results/final/research_summary.json"),
        ]
        placeholders = ["TODO", "TBD", "XXX", "FIXME"]
        for p in files_to_check:
            text = p.read_text(encoding="utf-8")
            for placeholder in placeholders:
                assert placeholder not in text, f"Found placeholder '{placeholder}' in {p}"

    def test_two_phase_structure_adherence(self):
        """Verify reports strictly follow two-phase structure and do not refer to old 3-phase roadmap."""
        files_to_check = [
            Path("reports/final/FINAL_RESEARCH_ANALYSIS.md"),
            Path("reports/final/DETECTION_ANALYSIS.md"),
            Path("reports/final/PROTECTION_ANALYSIS.md"),
            Path("results/final/research_summary.json"),
        ]
        for p in files_to_check:
            text = p.read_text(encoding="utf-8").lower()
            assert "three-phase" not in text, f"Found reference to old 3-phase structure in {p}"
            assert "phase 3" not in text, f"Found reference to Phase 3 in {p}"
            assert "prc-1" not in text and "prc-2" not in text, f"Found review stage reference in {p}"

    def test_research_questions_correctly_mapped(self):
        """Verify RQ1 and RQ2 are explicitly mapped to Phase 1 and Phase 2 respectively."""
        with open("results/final/research_summary.json", "r", encoding="utf-8") as f:
            summary = json.load(f)

        rqs = summary["research_questions"]
        assert "rq1" in rqs and "rq2" in rqs
        assert rqs["rq1"]["target_phase"] == "Phase 1 — Detection"
        assert rqs["rq2"]["target_phase"] == "Phase 2 — Protection"
        assert "detect" in rqs["rq1"]["question"].lower()
        assert "defensive measures" in rqs["rq2"]["question"].lower()
