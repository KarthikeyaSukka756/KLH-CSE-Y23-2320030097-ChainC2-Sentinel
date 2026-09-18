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
            "path": "data/evaluation/evaluation_results.json",
            "filename": "evaluation_results_30_runs.json",
            "mimetype": "application/json",
        },
        "protection_json": {
            "path": "data/evaluation/protection_evaluation.json",
            "filename": "protection_evaluation_22_runs.json",
            "mimetype": "application/json",
        },
        "historical_ab_json": {
            "path": "data/evaluation/historical_ab_20_evaluation_results.json",
            "filename": "historical_ab_20_evaluation_results.json",
            "mimetype": "application/json",
        },
        "detection_summary_json": {
            "path": "results/detection/evaluation_summary.json",
            "filename": "detection_evaluation_summary.json",
            "mimetype": "application/json",
        },
        "detection_metrics_csv": {
            "path": "results/detection/detection_metrics.csv",
            "filename": "detection_metrics.csv",
            "mimetype": "text/csv",
        },
        "experiment_results_csv": {
            "path": "results/detection/experiment_results.csv",
            "filename": "experiment_results_detection.csv",
            "mimetype": "text/csv",
        },
        "protection_summary_json": {
            "path": "results/protection/evaluation_summary.json",
            "filename": "protection_evaluation_summary.json",
            "mimetype": "application/json",
        },
        "protection_metrics_csv": {
            "path": "results/protection/protection_metrics.csv",
            "filename": "protection_metrics.csv",
            "mimetype": "text/csv",
        },
        "protection_results_csv": {
            "path": "results/protection/experiment_results.csv",
            "filename": "experiment_results_protection.csv",
            "mimetype": "text/csv",
        },
        "research_summary_json": {
            "path": "results/final/research_summary.json",
            "filename": "chainc2_sentinel_research_summary.json",
            "mimetype": "application/json",
        },
        "detection_analysis_md": {
            "path": "reports/final/DETECTION_ANALYSIS.md",
            "filename": "DETECTION_ANALYSIS.md",
            "mimetype": "text/markdown",
        },
        "final_research_analysis_md": {
            "path": "reports/final/FINAL_RESEARCH_ANALYSIS.md",
            "filename": "FINAL_RESEARCH_ANALYSIS.md",
            "mimetype": "text/markdown",
        },
        "protection_analysis_md": {
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

            # Add convenient flat keys if nested
            if "research_questions" in data and "research_question" not in data:
                data["research_question"] = data["research_questions"].get("phase_1")
            if "phase_1" in data and "phase1_detection_summary" not in data:
                data["phase1_detection_summary"] = data["phase_1"].get("research_question", "Detection Evaluation Complete")
            if "phase_2" in data and "phase2_protection_summary" not in data:
                data["phase2_protection_summary"] = data["phase_2"].get("research_question", "Protection Evaluation Complete")

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
            return {
                "report_name": report_name,
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
                "filename": info["filename"],
                "mimetype": info["mimetype"],
                "exists": target_path.exists(),
                "size_bytes": target_path.stat().st_size if target_path.exists() else 0,
            })
        return items

    # Alias for convenience
    get_available_downloads = list_available_downloads
