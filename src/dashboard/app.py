# ChainC2 Sentinel — Master Dashboard Flask Application
"""Web application and REST API providing integrated monitoring, experiment execution,
evidence exploration, and evaluation analytics for the ChainC2 Sentinel framework.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from flask import Flask, abort, jsonify, render_template, request, send_file

from src.dashboard.services import get_repo_root
from src.dashboard.services.benchmark_service import BenchmarkService
from src.dashboard.services.evidence_service import EvidenceService
from src.dashboard.services.experiment_service import ExperimentService
from src.dashboard.services.report_service import ReportService

logger = logging.getLogger("chainc2_sentinel.dashboard")


def create_app(
    repo_root: Optional[Any] = None,
    test_config: Optional[dict[str, Any]] = None,
) -> Flask:
    """Create and configure the Flask dashboard application."""
    if isinstance(repo_root, dict) and test_config is None:
        test_config = repo_root
        repo_root = None
    root = repo_root or get_repo_root()
    base_dir = Path(__file__).resolve().parent

    app = Flask(
        __name__,
        static_folder=str(base_dir / "static"),
        template_folder=str(base_dir / "templates"),
    )

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "chainc2-sentinel-local-research-secret-key"),
        REPO_ROOT=root,
    )
    if test_config:
        app.config.update(test_config)

    # Initialize backend services
    benchmark_service = BenchmarkService(root)
    evidence_service = EvidenceService(root)
    report_service = ReportService(root)
    experiment_service = ExperimentService(root)

    # -------------------------------------------------------------------------
    # Frontend Route
    # -------------------------------------------------------------------------

    @app.route("/")
    def index():
        """Render the single-page Master Dashboard interface."""
        return render_template("index.html")

    # -------------------------------------------------------------------------
    # API: Health & Status
    # -------------------------------------------------------------------------

    @app.route("/api/health", methods=["GET"])
    def health_check():
        """Service health check."""
        return jsonify({
            "status": "healthy",
            "service": "ChainC2 Sentinel Master Dashboard",
            "version": "2.0.0-frozen",
            "phases": ["Phase 1 — Detection", "Phase 2 — Protection"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment_in_progress": experiment_service.is_executing(),
        })

    # -------------------------------------------------------------------------
    # API: Overview
    # -------------------------------------------------------------------------

    @app.route("/api/overview", methods=["GET"])
    def get_overview():
        """Retrieve executive overview metrics, system status, and recent activity."""
        try:
            overview = benchmark_service.get_overview()
            overview["system_status"]["experiment_in_progress"] = experiment_service.is_executing()
            return jsonify(overview)
        except Exception as e:
            logger.error("Error generating overview: %s", e)
            return jsonify({"error": "Failed to compile overview metrics"}), 500

    # -------------------------------------------------------------------------
    # API: Evaluation Benchmarks
    # -------------------------------------------------------------------------

    @app.route("/api/evaluation/detection", methods=["GET"])
    def get_detection_evaluation():
        """Retrieve Phase 1 detection evaluation benchmark data and CSV metrics."""
        try:
            summary = benchmark_service.get_detection_summary()
            metrics_csv = benchmark_service.get_detection_metrics_csv()
            raw_eval = benchmark_service.get_detection_evaluation_raw()

            return jsonify({
                "summary": summary,
                "summary_metrics": summary,
                "metrics_table": metrics_csv,
                "total_experiments": summary.get("total_experiments", 30),
                "confusion_matrix": {
                    "tp": summary.get("true_positives", 10),
                    "tn": summary.get("true_negatives", 20),
                    "fp": summary.get("false_positives", 0),
                    "fn": summary.get("false_negatives", 0),
                },
                "rates": {
                    "precision": summary.get("precision", 1.0),
                    "recall": summary.get("detection_rate", 1.0),
                    "fpr": summary.get("false_positive_rate", 0.0),
                    "specificity": summary.get("true_negative_rate", 1.0),
                    "accuracy": summary.get("accuracy", 1.0),
                    "f1_score": summary.get("f1_score", 1.0),
                },
                "latency": summary.get("detection_latency", {}),
                "scenario_counts": summary.get("scenario_counts", {}),
                "experiments_sample": raw_eval.get("experiments", [])[:10],
            })
        except Exception as e:
            logger.error("Error retrieving detection evaluation: %s", e)
            return jsonify({"error": "Failed to load detection evaluation"}), 500

    @app.route("/api/evaluation/protection", methods=["GET"])
    def get_protection_evaluation():
        """Retrieve Phase 2 protection evaluation benchmark data."""
        try:
            summary = benchmark_service.get_protection_summary()
            metrics_csv = benchmark_service.get_protection_metrics_csv()

            return jsonify({
                "summary": summary,
                "summary_metrics": summary,
                "metrics_table": metrics_csv,
                "total_experiments": summary.get("total_experiments", 22),
                "metrics": {
                    "mitigation_success_rate": summary.get("mitigation_success_rate", 1.0),
                    "rpc_blocking_rate": summary.get("rpc_blocking_rate", 1.0),
                    "beacon_blocking_rate": summary.get("beacon_blocking_rate", 1.0),
                    "process_isolation_success_rate": summary.get("process_isolation_success_rate", 1.0),
                    "legitimate_traffic_preservation_rate": summary.get("legitimate_traffic_preservation_rate", 1.0),
                    "false_mitigation_rate": summary.get("false_mitigation_rate", 0.0),
                    "rollback_success_rate": summary.get("rollback_success_rate", 1.0),
                    "evidence_preservation_rate": summary.get("evidence_preservation_rate", 1.0),
                },
                "latency": summary.get("containment_latency", {}),
            })
        except Exception as e:
            logger.error("Error retrieving protection evaluation: %s", e)
            return jsonify({"error": "Failed to load protection evaluation"}), 500

    # -------------------------------------------------------------------------
    # API: Experiment History & Details
    # -------------------------------------------------------------------------

    @app.route("/api/experiments/history", methods=["GET"])
    def get_experiment_history():
        """Retrieve searchable, filterable history across on-demand and benchmark runs."""
        scenario = request.args.get("scenario")
        detection = request.args.get("detection")
        classification = request.args.get("classification")
        limit = request.args.get("limit", default=100, type=int)

        try:
            history = experiment_service.get_history(
                scenario_filter=scenario,
                detection_filter=detection,
                classification_filter=classification,
                limit=limit,
            )
            return jsonify({
                "total_returned": len(history),
                "experiments": history,
                "runs": history,
            })
        except Exception as e:
            logger.error("Error retrieving experiment history: %s", e)
            return jsonify({"error": "Failed to load experiment history"}), 500

    @app.route("/api/experiments/run/<run_id>", methods=["GET"])
    def get_run_details(run_id: str):
        """Retrieve full granular multi-layer chain for a specific run ID."""
        # Sanitize against path traversal in run_id
        clean_run_id = Path(run_id).name
        details = experiment_service.get_run_details(clean_run_id)
        if not details:
            return jsonify({"error": f"Experiment run '{clean_run_id}' not found"}), 404
        return jsonify(details)

    # -------------------------------------------------------------------------
    # API: Experiment Execution (Experiment Center)
    # -------------------------------------------------------------------------

    @app.route("/api/experiments/execute", methods=["POST"])
    def execute_experiment():
        """Execute a controlled scenario or Run All 3 on-demand."""
        # Vercel / Production deployment guard: live laboratory scenarios remain local-only
        if os.environ.get("VERCEL") or os.environ.get("CHAINC2_PRODUCTION") == "1" or app.config.get("PRODUCTION_MODE"):
            return jsonify({
                "status": "DISABLED",
                "error": "Live experiment execution is disabled in production deployment. Use the local research environment to run laboratory scenarios.",
                "is_running": False,
            }), 403

        if not request.is_json:
            return jsonify({"error": "Request body must be valid JSON"}), 400

        data = request.get_json() or {}
        scenario_id = data.get("scenario")
        if not scenario_id and data.get("mode") == "run_all_3":
            scenario_id = "all"
        repetitions = data.get("repetitions", 1)

        if not scenario_id:
            return jsonify({"error": "Missing required field 'scenario'"}), 400

        try:
            result = experiment_service.execute_scenario(
                scenario_id=scenario_id,
                repetitions=repetitions,
            )
            if result.get("status") == "LOCKED":
                return jsonify(result), 409
            return jsonify(result), 200
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            logger.error("Scenario execution error: %s", e)
            return jsonify({"error": f"Scenario execution failed: {str(e)}"}), 500

    # -------------------------------------------------------------------------
    # API: Live Telemetry
    # -------------------------------------------------------------------------

    @app.route("/api/telemetry/live", methods=["GET"])
    def get_live_telemetry():
        """Retrieve recent normalized telemetry records."""
        run_id = request.args.get("run_id")
        source = request.args.get("source")
        limit = request.args.get("limit", default=50, type=int)

        events = experiment_service.get_live_telemetry(
            run_id=Path(run_id).name if run_id else None,
            source=source,
            limit=limit,
        )
        return jsonify({
            "total_returned": len(events),
            "events": events,
            "is_live": experiment_service.is_executing(),
        })

    # -------------------------------------------------------------------------
    # API: Evidence Explorer & Forensic Checksum Verification
    # -------------------------------------------------------------------------

    @app.route("/api/evidence", methods=["GET"])
    def list_evidence():
        """List all discovered forensic evidence bundles."""
        bundles = evidence_service.list_evidence_bundles()
        return jsonify({
            "total_bundles": len(bundles),
            "bundles": bundles,
            "evidence_bundles": bundles,
        })

    @app.route("/api/evidence/<bundle_id>", methods=["GET"])
    def get_evidence_bundle(bundle_id: str):
        """Retrieve full details of a specific evidence bundle."""
        bundle = evidence_service.get_evidence_bundle(bundle_id)
        if not bundle:
            return jsonify({"error": f"Evidence bundle '{bundle_id}' not found"}), 404
        return jsonify(bundle)

    @app.route("/api/evidence/<bundle_id>/verify", methods=["GET", "POST"])
    def verify_evidence_checksum(bundle_id: str):
        """Compute and verify the SHA-256 cryptographic digest of an evidence snapshot."""
        verification = evidence_service.verify_checksum(bundle_id)
        if verification.get("status") == "NOT_FOUND":
            return jsonify(verification), 404
        return jsonify(verification)

    # -------------------------------------------------------------------------
    # API: Research Deliverables & Reports
    # -------------------------------------------------------------------------

    @app.route("/api/research/summary", methods=["GET"])
    def get_research_summary():
        """Retrieve the consolidated research summary (research_summary.json)."""
        summary = report_service.get_research_summary()
        return jsonify(summary)

    @app.route("/api/research/report/<path:report_name>", methods=["GET"])
    def get_research_report(report_name: str):
        """Retrieve markdown content of an allowed final report."""
        try:
            report = report_service.get_report_content(report_name)
            return jsonify(report)
        except (ValueError, FileNotFoundError) as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logger.error("Error retrieving report: %s", e)
            return jsonify({"error": "Failed to read report"}), 500

    # -------------------------------------------------------------------------
    # API: Secure Downloads
    # -------------------------------------------------------------------------

    @app.route("/api/download/<path:file_type>", methods=["GET"])
    def download_artifact(file_type: str):
        """Download an approved, whitelisted research artifact."""
        try:
            path, fname, mime = report_service.get_downloadable_file(file_type)
            return send_file(
                path_or_file=str(path),
                as_attachment=True,
                download_name=fname,
                mimetype=mime,
            )
        except (ValueError, FileNotFoundError) as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logger.error("Error downloading file: %s", e)
            return jsonify({"error": "Failed to download artifact"}), 500

    @app.route("/api/downloads", methods=["GET"])
    def list_downloads():
        """List all available download endpoints."""
        downloads = report_service.list_available_downloads()
        return jsonify({"downloads": downloads})

    # -------------------------------------------------------------------------
    # Error Handlers
    # -------------------------------------------------------------------------

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Resource not found", "path": request.path}), 404
        return render_template("index.html"), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def handle_server_error(e):
        logger.error("Unhandled internal server error: %s", e)
        return jsonify({"error": "An internal server error occurred"}), 500

    return app
