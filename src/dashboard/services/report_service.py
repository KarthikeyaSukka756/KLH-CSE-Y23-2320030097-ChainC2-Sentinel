# ChainC2 Sentinel — Research Synthesis & Secure Artifact Export Service
"""Data service for accessing final research summaries, analytical reports, and whitelisted export artifacts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from src.dashboard.services import get_repo_root

logger = logging.getLogger("chainc2_sentinel.dashboard.report_service")


class ReportService:
    """Service providing safe access to final research deliverables and downloadable artifacts."""

    ALLOWED_REPORTS: dict[str, str] = {
        "DETECTION_ANALYSIS.md": "reports/final/DETECTION_ANALYSIS.md",
        "FINAL_RESEARCH_ANALYSIS.md": "reports/final/FINAL_RESEARCH_ANALYSIS.md",
        "PROTECTION_ANALYSIS.md": "reports/final/PROTECTION_ANALYSIS.md",
    }

    DOWNLOAD_WHITELIST: dict[str, dict[str, str]] = {
        "detection_json": {
            "name": "Phase 1 Detection Evaluation Results",
            "description": "Full 30-run JSON benchmark dataset with multi-layer telemetry, correlation sequences, and explainability verdicts.",
            "path": "data/evaluation/evaluation_results.json",
            "filename": "evaluation_results_30_runs.json",
            "mimetype": "application/json",
        },
        "protection_json": {
            "name": "Phase 2 Protection Evaluation Results",
            "description": "Full 22-run JSON benchmark dataset with automated response execution, verification checks, and rollback results.",
            "path": "data/evaluation/protection_evaluation.json",
            "filename": "protection_evaluation_22_runs.json",
            "mimetype": "application/json",
        },
        "historical_ab_json": {
            "name": "Historical Phase 1 A/B Evaluation",
            "description": "Baseline 20-run A/B benchmark dataset comparing benign Web3 baseline against synthetic C2 sequences.",
            "path": "data/evaluation/historical_ab_20_evaluation_results.json",
            "filename": "historical_ab_20_evaluation_results.json",
            "mimetype": "application/json",
        },
        "detection_summary_json": {
            "name": "Detection Benchmark Summary",
            "description": "Consolidated metrics summary JSON for Phase 1 detection (100% precision, 100% recall, 0% FPR).",
            "path": "results/detection/evaluation_summary.json",
            "filename": "detection_evaluation_summary.json",
            "mimetype": "application/json",
        },
        "detection_metrics_csv": {
            "name": "Detection Metrics Table",
            "description": "Tabular statistical metrics (Precision, Recall, FPR, Specificity, Accuracy, F1-score) in CSV format.",
            "path": "results/detection/detection_metrics.csv",
            "filename": "detection_metrics.csv",
            "mimetype": "text/csv",
        },
        "experiment_results_csv": {
            "name": "Detection Experiments CSV",
            "description": "Per-experiment breakdown across 30 runs including scenario labels, latency, and ground truth.",
            "path": "results/detection/experiment_results.csv",
            "filename": "experiment_results_detection.csv",
            "mimetype": "text/csv",
        },
        "protection_summary_json": {
            "name": "Protection Benchmark Summary",
            "description": "Consolidated metrics summary JSON for Phase 2 defensive response and containment.",
            "path": "results/protection/evaluation_summary.json",
            "filename": "protection_evaluation_summary.json",
            "mimetype": "application/json",
        },
        "protection_metrics_csv": {
            "name": "Protection Metrics Table",
            "description": "Tabular metrics for Phase 2 defense: mitigation success rate, RPC blocking, beacon blocking, and containment latency.",
            "path": "results/protection/protection_metrics.csv",
            "filename": "protection_metrics.csv",
            "mimetype": "text/csv",
        },
        "protection_results_csv": {
            "name": "Protection Experiments CSV",
            "description": "Per-experiment breakdown across 22 runs including action counts, verification probes, and rollback verdicts.",
            "path": "results/protection/experiment_results.csv",
            "filename": "experiment_results_protection.csv",
            "mimetype": "text/csv",
        },
        "research_summary_json": {
            "name": "Consolidated Research Summary",
            "description": "Formal research questions, multi-layer methodology overview, and synthesized empirical findings.",
            "path": "results/final/research_summary.json",
            "filename": "chainc2_sentinel_research_summary.json",
            "mimetype": "application/json",
        },
        "detection_analysis_md": {
            "name": "Detection Analysis Report",
            "description": "Full markdown analysis report evaluating Phase 1 cross-layer telemetry correlation and explainable scoring.",
            "path": "reports/final/DETECTION_ANALYSIS.md",
            "filename": "DETECTION_ANALYSIS.md",
            "mimetype": "text/markdown",
        },
        "final_research_analysis_md": {
            "name": "Final Research Analysis Report",
            "description": "Milestone 11 capstone synthesis report on blockchain-mediated C2 channel detection and defense.",
            "path": "reports/final/FINAL_RESEARCH_ANALYSIS.md",
            "filename": "FINAL_RESEARCH_ANALYSIS.md",
            "mimetype": "text/markdown",
        },
        "protection_analysis_md": {
            "name": "Protection Analysis Report",
            "description": "Full markdown analysis report evaluating Phase 2 automated response, verification, and forensic preservation.",
            "path": "reports/final/PROTECTION_ANALYSIS.md",
            "filename": "PROTECTION_ANALYSIS.md",
            "mimetype": "text/markdown",
        },
    }

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or get_repo_root()

        # Add common aliases for flexibility
        self.DOWNLOAD_WHITELIST["detection_csv"] = self.DOWNLOAD_WHITELIST["detection_metrics_csv"]
        self.DOWNLOAD_WHITELIST["evaluation_json"] = self.DOWNLOAD_WHITELIST["detection_json"]

    def get_research_summary(self) -> dict[str, Any]:
        """Load results/final/research_summary.json."""
        file_path = self.repo_root / "results" / "final" / "research_summary.json"
        if not file_path.exists():
            logger.warning("Research summary not found at %s", file_path)
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Map authoritative questions and synthesized conclusions
            rqs = data.get("research_questions", {})
            if "rq1" in rqs:
                data.setdefault("research_question", rqs["rq1"].get("question"))
                data.setdefault("phase1_detection_summary", rqs["rq1"].get("conclusion"))
            if "rq2" in rqs:
                data.setdefault("phase2_protection_summary", rqs["rq2"].get("conclusion"))

            return data
        except Exception as e:
            logger.error("Failed to read research summary: %s", e)
            return {}

    def get_report_content(self, report_name: str) -> dict[str, Any]:
        """Retrieve the markdown content of an allowed report safely.

        Strictly rejects arbitrary file paths or path traversal with ValueError.
        """
        if ".." in report_name or "/" in report_name or "\\" in report_name or report_name not in self.ALLOWED_REPORTS:
            logger.warning("Path traversal or unauthorized report request rejected: %s", report_name)
            raise ValueError(f"Access denied or invalid report: '{report_name}'")

        rel_path = self.ALLOWED_REPORTS[report_name]
        target_path = (self.repo_root / rel_path).resolve()

        # Enforce that resolved path is strictly within the reports directory
        allowed_dir = (self.repo_root / "reports" / "final").resolve()
        if allowed_dir not in target_path.parents and target_path != allowed_dir:
            logger.warning("Path traversal attempt detected: %s", report_name)
            raise ValueError(f"Path traversal detected: '{report_name}'")

        if not target_path.exists():
            logger.warning("Report file does not exist: %s", target_path)
            raise FileNotFoundError(f"Report file not found: '{report_name}'")

        try:
            content = target_path.read_text(encoding="utf-8")
            title = report_name
            for line in content.splitlines():
                s = line.strip()
                if s.startswith("# "):
                    title = s[2:].strip()
                    break
            return {
                "report_name": report_name,
                "title": title,
                "path": rel_path,
                "content": content,
                "char_count": len(content),
            }
        except Exception as e:
            logger.error("Failed to read report %s: %s", target_path, e)
            raise

    def get_download_artifact(self, file_type: str) -> Optional[dict[str, Any]]:
        """Retrieve path and download metadata for a whitelisted file key.

        Returns dict with 'absolute_path', 'filename', and 'mimetype' or None if invalid.
        """
        if ".." in file_type or "/" in file_type or "\\" in file_type or file_type not in self.DOWNLOAD_WHITELIST:
            logger.warning("Rejected un-whitelisted download request: %s", file_type)
            return None

        info = self.DOWNLOAD_WHITELIST[file_type]
        target_path = (self.repo_root / info["path"]).resolve()

        # Enforce boundary within repository root
        if self.repo_root.resolve() not in target_path.parents:
            logger.warning("Download path traversal attempt: %s", file_type)
            return None

        if not target_path.exists():
            logger.warning("Download target does not exist: %s", target_path)
            return None

        return {
            "absolute_path": target_path,
            "filename": info["filename"],
            "mimetype": info["mimetype"],
            "size_bytes": target_path.stat().st_size,
        }

    def get_downloadable_file(self, file_type: str) -> tuple[Path, str, str]:
        """Retrieve downloadable file tuple (path, filename, mimetype) or raise ValueError."""
        artifact = self.get_download_artifact(file_type)
        if not artifact:
            raise ValueError(f"Unauthorized or invalid download artifact: '{file_type}'")
        return artifact["absolute_path"], artifact["filename"], artifact["mimetype"]

    def list_available_downloads(self) -> list[dict[str, Any]]:
        """List all available download endpoints and metadata."""
        items = []
        for key, info in self.DOWNLOAD_WHITELIST.items():
            target_path = self.repo_root / info["path"]
            items.append({
                "key": key,
                "name": info.get("name", key),
                "description": info.get("description", info["filename"]),
                "filename": info["filename"],
                "mimetype": info["mimetype"],
                "exists": target_path.exists(),
                "size_bytes": target_path.stat().st_size if target_path.exists() else 0,
            })
        return items

    # Alias for convenience
    get_available_downloads = list_available_downloads
