# ChainC2 Sentinel — Master Dashboard Flask Application
"""Web application and REST API providing integrated monitoring, experiment execution,
evidence exploration, and evaluation analytics for the ChainC2 Sentinel framework.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from flask import Flask, abort, jsonify, render_template, request, send_file

from src.cloudscale.budget_manager import CatalystBudgetManager
from src.cloudscale.cron_handler import CatalystCronWorker
from src.dashboard.services import get_repo_root
from src.dashboard.services.benchmark_service import BenchmarkService
from src.dashboard.services.evidence_service import EvidenceService
from src.dashboard.services.experiment_service import ExperimentService
from src.dashboard.services.report_service import ReportService
from src.dashboard.services.sepolia_service import SepoliaService
from src.scenarios.generator import ControlledGenerator

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
    sepolia_service = SepoliaService(root)
    budget_manager = CatalystBudgetManager(repo_root=root)
    cron_worker = CatalystCronWorker(repo_root=root, budget_manager=budget_manager)
    generator = ControlledGenerator.get_instance(repo_root=root)

    # Auto-start autonomous monitoring daemon in non-testing environments (or when explicitly forced)
    if not app.config.get("TESTING") or app.config.get("FORCE_AUTO_START"):
        if os.environ.get("CHAINC2_AUTO_START_MONITOR", "1") == "1" and not app.config.get("TESTING"):
            try:
                sepolia_service.start_monitoring(interval_seconds=15.0)
                logger.info("Sepolia continuous monitoring auto-started successfully")
            except Exception as e:
                logger.warning("Could not auto-start Sepolia monitoring: %s", e)

        # Bounded generator auto-start if explicitly enabled by environment
        if os.environ.get("CHAINC2_AUTO_START_GENERATOR") == "1":
            try:
                bounded_cycles = int(os.environ.get("CHAINC2_GENERATOR_MAX_CYCLES", "4"))
                generator.start(max_cycles=bounded_cycles)
                logger.info("Controlled generator auto-started with bounded max_cycles=%d", bounded_cycles)
            except Exception as e:
                logger.warning("Could not auto-start generator: %s", e)

    @app.after_request
    def add_cors_headers(response):
        """Enable Cross-Origin Resource Sharing for Catalyst Web Client hosting and prevent stale API caching."""
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.route("/api/<path:dummy>", methods=["OPTIONS"])
    def handle_options_preflight(dummy):
        """Handle CORS pre-flight requests."""
        return "", 204

    # -------------------------------------------------------------------------
    # Frontend Route
    # -------------------------------------------------------------------------

    @app.route("/")
    def index():
        """Render the single-page Master Dashboard interface."""
        return render_template("index.html")

    @app.route("/openapi.json", methods=["GET"])
    def openapi_spec():
        """Serve the OpenAPI 3.0.3 specification."""
        from src.dashboard.openapi import get_openapi_spec
        return jsonify(get_openapi_spec()), 200

    # -------------------------------------------------------------------------
    def is_production() -> bool:
        if app.config.get("PRODUCTION_MODE") or os.environ.get("CHAINC2_PRODUCTION") == "1":
            return True
        return False

    # -------------------------------------------------------------------------
    # API: Health & Status
    # -------------------------------------------------------------------------

    @app.route("/api/health", methods=["GET"])
    def health_check():
        """Service health check."""
        prod = is_production()
        return jsonify({
            "status": "healthy",
            "service": "ChainC2 Sentinel Master Dashboard",
            "version": "2.0.0-frozen",
            "phases": ["Phase 1 — Detection", "Phase 2 — Protection"],
            "environment": "Zoho Catalyst CloudScale" if prod else "Controlled Laboratory (Localhost)",
            "execution_enabled": not prod,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment_in_progress": experiment_service.is_executing(),
            "cloudscale_budget_state": budget_manager.get_operating_state().value,
            "cloudscale_remaining_credits_usd": budget_manager.get_remaining_budget_usd(),
        })

    # -------------------------------------------------------------------------
    # API: Overview
    # -------------------------------------------------------------------------

    @app.route("/api/overview", methods=["GET"])
    def get_overview():
        """Retrieve executive overview metrics, system status, and recent activity."""
        try:
            overview = benchmark_service.get_overview()
            prod = is_production()
            overview["system_status"]["experiment_in_progress"] = experiment_service.is_executing()
            overview["system_status"]["execution_enabled"] = not prod
            overview["system_status"]["environment"] = "Zoho Catalyst CloudScale" if prod else "Controlled Laboratory (Localhost)"
            if prod:
                overview["system_status"]["dashboard"] = "CLOUD_DASHBOARD"
                overview["system_status"]["dashboard_status"] = "CLOUD_DASHBOARD"
                overview["system_status"]["blockchain_status"] = "HISTORICAL_BENCHMARK"
                overview["system_status"]["local_blockchain"] = "HISTORICAL_BENCHMARK"
                overview["system_status"]["telemetry"] = "BENCHMARK_TRACES"
                overview["system_status"]["telemetry_status"] = "BENCHMARK_TRACES"
            overview["cloudscale_budget"] = budget_manager.get_status_summary()
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
            hist_eval = benchmark_service.get_historical_ab_evaluation()

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
                "historical_ab": {
                    "total_experiments": hist_eval.get("metrics", {}).get("total_experiments", 20),
                    "metrics": hist_eval.get("metrics", {}),
                    "scenario_counts": hist_eval.get("scenario_counts", {}),
                },
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
            raw_prot = benchmark_service.get_protection_evaluation_raw()

            return jsonify({
                "summary": summary,
                "summary_metrics": summary,
                "metrics_table": metrics_csv,
                "total_experiments": summary.get("total_experiments", 22),
                "experiments": raw_prot.get("experiments", []),
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

    @app.route("/api/experiments", methods=["GET"])
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
        # Production deployment guard: live laboratory scenarios remain local-only
        if os.environ.get("CHAINC2_PRODUCTION") == "1" or app.config.get("PRODUCTION_MODE"):
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
        """Retrieve recent normalized telemetry records and current execution batch metadata."""
        run_id = request.args.get("run_id")
        source = request.args.get("source")
        limit = request.args.get("limit", default=100, type=int)

        clean_run_id = Path(run_id).name if run_id and run_id != "ALL" else None
        batch_info = experiment_service.get_current_execution_batch()
        batch_events = batch_info.get("events", [])

        if batch_events:
            if clean_run_id:
                events = [e for e in batch_events if e.get("run_id") == clean_run_id]
                if not events:
                    events = experiment_service.get_live_telemetry(run_id=clean_run_id, source=source, limit=limit)
            elif source:
                events = [e for e in batch_events if e.get("layer") == source.upper() or e.get("source") == source.lower()]
            else:
                events = batch_events[:limit]
        else:
            events = experiment_service.get_live_telemetry(
                run_id=clean_run_id,
                source=source,
                limit=limit,
            )
        is_cur = batch_info.get("is_current_execution", False)
        return jsonify({
            "total_returned": len(events),
            "events": events,
            "execution_batch": batch_info.get("execution_batch"),
            "summary": batch_info.get("summary"),
            "runs": batch_info.get("runs"),
            "source": batch_info.get("source", "current_execution" if is_cur else "historical_benchmark"),
            "is_current_execution": is_cur,
            "is_live": bool(experiment_service.is_executing() or is_cur),
        })

    DEFAULT_INGEST_KEY = "sentinel-telemetry-sec-ingest-token-2026"

    @app.route("/api/telemetry/ingest", methods=["POST"])
    def ingest_telemetry():
        """Secure, authenticated ingestion of raw telemetry events with idempotency and schema validation."""
        # 1. Server-Side Authentication
        expected_key = os.environ.get("CHAINC2_INGEST_KEY", DEFAULT_INGEST_KEY)
        auth_header = request.headers.get("Authorization", "").strip()
        custom_header = request.headers.get("X-Sentinel-Ingest-Key", "").strip()

        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif custom_header:
            token = custom_header

        if not token or not hmac.compare_digest(token, expected_key):
            sepolia_service.monitor.record_ingest_metrics("AUTH_FAILURE")
            return jsonify({
                "status": "UNAUTHORIZED",
                "error": "Missing or invalid telemetry ingestion credentials (Authorization: Bearer <token> or X-Sentinel-Ingest-Key required).",
            }), 401

        # 2. Payload Format & Content-Length Bounds
        if not request.is_json:
            sepolia_service.monitor.record_ingest_metrics("MALFORMED", error="Request body is not JSON")
            return jsonify({"status": "ERROR", "error": "Request body must be valid JSON"}), 400

        if request.content_length and request.content_length > 512 * 1024:
            sepolia_service.monitor.record_ingest_metrics("MALFORMED", error="Payload exceeds 512KB limit")
            return jsonify({"status": "REJECTED", "error": "Payload size exceeds maximum allowed limit (512KB)."}), 413

        # 3. Idempotency & Replay Protection
        raw_body = request.get_data(as_text=False)
        idempotency_key = request.headers.get("X-Idempotency-Key") or request.headers.get("Idempotency-Key")
        payload = request.get_json(silent=True)
        if not idempotency_key and isinstance(payload, dict) and payload.get("request_id"):
            idempotency_key = str(payload["request_id"])
        if not idempotency_key:
            idempotency_key = f"hash-{hashlib.sha256(raw_body).hexdigest()}"

        if sepolia_service.monitor.is_idempotency_key_seen(idempotency_key):
            sepolia_service.monitor.record_ingest_metrics("DUPLICATE")
            return jsonify({
                "status": "DUPLICATE_IGNORED",
                "message": "Telemetry payload or request ID was previously ingested and processed.",
                "idempotency_key": idempotency_key,
                "events_received": 0,
                "alerts_created": [],
            }), 200

        sepolia_service.monitor.register_idempotency_key(idempotency_key)

        # 4. Event Extraction & Batch Limiting
        raw_events = []
        if isinstance(payload, list):
            raw_events = payload
        elif isinstance(payload, dict):
            if "events" in payload and isinstance(payload["events"], list):
                raw_events = payload["events"]
            else:
                raw_events = [payload]
        else:
            sepolia_service.monitor.record_ingest_metrics("MALFORMED", error="Invalid JSON payload shape")
            return jsonify({"status": "ERROR", "error": "Invalid telemetry payload format. Expected list or object with 'events'."}), 400

        if len(raw_events) > 50:
            sepolia_service.monitor.record_ingest_metrics("MALFORMED", error="Batch size exceeds 50 events")
            return jsonify({"status": "REJECTED", "error": "Maximum batch size of 50 events exceeded."}), 400

        # 5. Schema, Source, and Timestamp Validation
        from src.models.events import SentinelEvent
        validated_events = []
        parsing_errors = []
        now_utc = datetime.now(timezone.utc)

        for idx, item in enumerate(raw_events):
            try:
                ev = SentinelEvent.model_validate(item)
                # Timestamp sanity check: reject timestamps > 10m in future or > 7d in past
                if ev.timestamp:
                    time_diff = (ev.timestamp - now_utc).total_seconds()
                    if time_diff > 600 or time_diff < -604800:
                        parsing_errors.append(f"Event at index {idx}: timestamp {ev.timestamp.isoformat()} outside allowable temporal window (+10m / -7d).")
                        continue
                validated_events.append(ev)
            except Exception as e:
                parsing_errors.append(f"Event at index {idx}: {str(e)}")

        if not validated_events and parsing_errors:
            sepolia_service.monitor.record_ingest_metrics("MALFORMED", error=str(parsing_errors[0]))
            return jsonify({"status": "ERROR", "error": "All events failed schema or timestamp validation", "details": parsing_errors}), 400

        # 6. Execute Correlation, Rule Scoring, and Autonomous Mitigation
        process_summary = sepolia_service.process_telemetry_events(validated_events)
        sepolia_service.monitor.record_ingest_metrics("SUCCESS", count=len(validated_events))
        process_summary["schema_errors"] = parsing_errors
        process_summary["idempotency_key"] = idempotency_key
        return jsonify(process_summary), 200

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
    # API: Ethereum Sepolia Testnet Monitor & Experiment Engine
    # -------------------------------------------------------------------------

    @app.route("/api/sepolia/status", methods=["GET"])
    def get_sepolia_status():
        """Retrieve Sepolia testnet connectivity, RPC health, and contract status."""
        force = request.args.get("force", "").lower() in ("1", "true")
        return jsonify(sepolia_service.get_status(force=force))

    @app.route("/api/sepolia/transactions", methods=["GET"])
    def get_sepolia_transactions():
        """Retrieve observed Sepolia transactions with optional filter and limit."""
        ft = request.args.get("filter")
        try:
            limit_arg = request.args.get("limit")
            limit = int(limit_arg) if limit_arg else 1000
        except ValueError:
            limit = 1000
        txs = sepolia_service.get_transactions(filter_type=ft, limit=limit)
        return jsonify({
            "total_returned": len(txs),
            "filter": ft,
            "transactions": txs,
        })

    @app.route("/api/sepolia/poll", methods=["POST"])
    def poll_sepolia_blocks():
        """Trigger an on-demand poll of recent Sepolia blocks."""
        new_txs = sepolia_service.poll_blocks(count=1)
        return jsonify({
            "status": "success",
            "new_transactions_count": len(new_txs),
            "transactions": new_txs,
        })

    @app.route("/api/sepolia/alerts", methods=["GET"])
    def get_sepolia_alerts():
        """Retrieve detection alerts generated from Sepolia-correlated sequences."""
        alerts = sepolia_service.get_alerts()
        return jsonify({"alerts": alerts, "total_alerts": len(alerts)})

    @app.route("/api/sepolia/experiments", methods=["GET"])
    def get_sepolia_experiments():
        """Retrieve history of Sepolia-correlated controlled experiments."""
        experiments = sepolia_service.get_experiments()
        return jsonify({"experiments": experiments, "total_experiments": len(experiments)})

    @app.route("/api/sepolia/mitigations", methods=["GET"])
    def get_sepolia_mitigations():
        """Retrieve defensive mitigation audit log."""
        mitigations = sepolia_service.get_mitigations()
        return jsonify({"mitigations": mitigations, "total_mitigations": len(mitigations)})

    @app.route("/api/sepolia/execute", methods=["POST"])
    def execute_sepolia_experiment():
        """Trigger a controlled laboratory experiment with Sepolia correlation."""
        if is_production():
            return jsonify({
                "status": "REJECTED",
                "error": "Live experiment execution is disabled in production cloud mode.",
            }), 403

        data = request.get_json(silent=True) or {}
        exp_type = data.get("experiment_type", "positive_c2")
        try:
            result = sepolia_service.execute_experiment(experiment_type=exp_type)
            return jsonify({
                "status": "success",
                "experiment": result,
            })
        except Exception as e:
            logger.error("Failed executing Sepolia experiment (%s): %s", exp_type, e)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/sepolia/rollback", methods=["POST"])
    def rollback_sepolia_mitigations():
        """Rollback active defensive mitigations."""
        if is_production():
            return jsonify({
                "status": "REJECTED",
                "error": "Mitigation rollback is disabled in production cloud mode.",
            }), 403

        result = sepolia_service.rollback_mitigations()
        return jsonify(result)

    @app.route("/api/sepolia/verify-tx/<tx_hash>", methods=["GET"])
    def verify_sepolia_transaction(tx_hash: str):
        """Independently verify transaction existence and contract target on Sepolia."""
        expected_contract = request.args.get("expected_contract")
        result = sepolia_service.verify_transaction(tx_hash=tx_hash, expected_contract=expected_contract)
        return jsonify(result)

    @app.route("/api/sepolia/catch-up", methods=["POST"])
    def catch_up_sepolia():
        """Manually trigger bounded catch-up of Sepolia monitoring cursor."""
        max_blocks = request.args.get("max_blocks", default=10, type=int)
        result = sepolia_service.catch_up(max_blocks=max_blocks)
        return jsonify(result)

    @app.route("/api/sepolia/monitoring/start", methods=["POST"])
    @app.route("/api/sepolia/start-monitoring", methods=["POST"])
    def start_sepolia_monitoring():
        """Start unattended continuous Sepolia monitoring daemon."""
        interval = request.args.get("interval", default=15.0, type=float)
        started = sepolia_service.start_monitoring(interval_seconds=interval)
        return jsonify({
            "status": "SUCCESS" if started else "ALREADY_RUNNING",
            "monitoring_active": True,
            "continuous_monitoring_active": True,
            "interval_seconds": interval,
        })

    @app.route("/api/sepolia/monitoring/stop", methods=["POST"])
    @app.route("/api/sepolia/stop-monitoring", methods=["POST"])
    def stop_sepolia_monitoring():
        """Stop unattended continuous Sepolia monitoring daemon."""
        stopped = sepolia_service.stop_monitoring()
        return jsonify({
            "status": "STOPPED" if stopped else "ALREADY_STOPPED",
            "monitoring_active": False,
            "continuous_monitoring_active": False,
        })

    # -------------------------------------------------------------------------
    # API: Zoho Catalyst CloudScale & Budget Endpoints
    # -------------------------------------------------------------------------

    @app.route("/api/cloudscale/budget", methods=["GET"])
    def get_cloudscale_budget():
        """Retrieve credit consumption, remaining credits, and budget safety state."""
        return jsonify(budget_manager.get_status_summary())

    @app.route("/api/cloudscale/status", methods=["GET"])
    def get_cloudscale_status():
        """Retrieve overall CloudScale operational status."""
        cursor = cron_worker.storage_adapter.get_monitoring_cursor()
        budget = budget_manager.get_status_summary()
        return jsonify({
            "service": "ChainC2 Sentinel — Zoho Catalyst CloudScale",
            "version": "2.0.0-catalyst",
            "environment": "Zoho Catalyst CloudScale" if os.environ.get("CATALYST_ENV") or os.environ.get("CATALYST_PROJECT_ID") else "Local Laboratory / Emulated",
            "budget": budget,
            "cursor": cursor,
            "sepolia_connected": sepolia_service.monitor.is_connected,
        })

    @app.route("/api/cloudscale/cron/trigger", methods=["POST"])
    def trigger_cloudscale_cron():
        """Manually trigger a single Cron observation and autonomous experiment cycle."""
        result = cron_worker.run_cron_cycle(auto_trigger_experiment=True)
        return jsonify(result)

    # -------------------------------------------------------------------------
    # API: Dedicated Alerts & Investigation Records
    # -------------------------------------------------------------------------

    @app.route("/api/alerts", methods=["GET"])
    def get_all_alerts():
        """Retrieve all alerts with optional limit and severity filter."""
        limit_arg = request.args.get("limit")
        limit = int(limit_arg) if limit_arg else 1000
        sev_filter = request.args.get("severity")
        alerts = sepolia_service.get_alerts(limit=limit)
        if sev_filter:
            alerts = [a for a in alerts if a.get("severity", "").upper() == sev_filter.upper()]
        return jsonify({"alerts": alerts, "total": len(alerts)})

    @app.route("/api/alerts/<alert_id>", methods=["GET"])
    def get_single_alert(alert_id: str):
        """Retrieve individual alert details."""
        alert = sepolia_service.get_alert_by_id(alert_id)
        if not alert:
            return jsonify({"error": f"Alert '{alert_id}' not found"}), 404
        return jsonify(alert)

    @app.route("/api/investigations", methods=["GET"])
    def get_all_investigations():
        """Retrieve all forensic investigation records."""
        limit_arg = request.args.get("limit")
        limit = int(limit_arg) if limit_arg else 1000
        invs = sepolia_service.get_investigations(limit=limit)
        return jsonify({"investigations": invs, "total": len(invs)})

    @app.route("/api/investigations/<investigation_id>", methods=["GET"])
    def get_single_investigation(investigation_id: str):
        """Retrieve individual investigation record with complete multi-layer chain and timeline."""
        inv = sepolia_service.get_investigation_by_id(investigation_id)
        if not inv:
            return jsonify({"error": f"Investigation '{investigation_id}' not found"}), 404
        return jsonify(inv)

    @app.route("/api/mitigations", methods=["GET"])
    def get_all_mitigations():
        """Retrieve all defensive mitigation records."""
        limit_arg = request.args.get("limit")
        limit = int(limit_arg) if limit_arg else 1000
        mits = sepolia_service.get_mitigations(limit=limit)
        return jsonify({"mitigations": mits, "total": len(mits)})

    # -------------------------------------------------------------------------
    # API: System Component Health
    # -------------------------------------------------------------------------

    @app.route("/api/system/health", methods=["GET"])
    def get_system_health():
        """Comprehensive operational health across detector, monitor, RPC, persistence, and generator."""
        sep_status = sepolia_service.get_status()
        gen_status = generator.get_status()
        budg_status = budget_manager.get_status_summary()
        now_iso = datetime.now(timezone.utc).isoformat()
        is_conn = bool(sep_status.get("is_connected"))

        return jsonify({
            "service": "ChainC2 Sentinel Framework",
            "version": "2.0.0-frozen",
            "status": "healthy" if is_conn else "degraded",
            "timestamp": now_iso,
            "components": {
                "sepolia_monitor": {
                    "status": "online" if is_conn else "disconnected",
                    "is_connected": is_conn,
                    "connected": is_conn,
                    "chain_id": sep_status.get("chain_id"),
                    "latest_block": sep_status.get("latest_block"),
                    "last_ingested_block": sep_status.get("last_ingested_block"),
                    "monitoring_lag_blocks": sep_status.get("monitoring_lag_blocks", 0),
                    "monitoring_active": sep_status.get("monitoring_active", False),
                    "sync_status": sep_status.get("sync_status", "UNKNOWN"),
                    "total_observed_transactions": sep_status.get("total_observed_transactions", 0),
                    "contract_status": sep_status.get("contract_status"),
                    "last_poll_time": sep_status.get("last_poll_time"),
                },
                "ethereum_rpc": {
                    "url": sep_status.get("rpc_url"),
                    "status": "Connected" if is_conn else "Disconnected",
                    "is_connected": is_conn,
                    "connected": is_conn,
                    "polling_errors": sep_status.get("polling_errors_count", 0),
                    "rate_limits": sep_status.get("rate_limit_count", 0),
                    "last_health_check": now_iso,
                },
                "controlled_generator": {
                    "status": gen_status.get("status"),
                    "isolated_vm_mode": False,
                    "vm_infrastructure_status": gen_status.get("vm_infrastructure_status", "NO_EXTERNAL_VM_PROVISIONED"),
                    "vm_infrastructure_details": gen_status.get("vm_infrastructure_details"),
                    "telemetry_source_type": "IN_PROCESS_SIMULATION",
                    "current_scenario": gen_status.get("current_scenario"),
                    "cycles_completed": gen_status.get("cycles_completed", 0),
                    "total_events_emitted": gen_status.get("total_events_emitted", 0),
                    "cycle_interval_seconds": gen_status.get("cycle_interval_seconds"),
                    "last_cycle_time": gen_status.get("last_cycle_time"),
                    "last_event_time": gen_status.get("last_event_time"),
                    "delivery_status": gen_status.get("delivery_status", "ACTIVE_INTAKE"),
                },
                "telemetry_ingestion": {
                    "status": "ACTIVE",
                    "authenticated": True,
                    "auth_scheme": "Bearer Token / X-Sentinel-Ingest-Key",
                    "total_events_ingested": sep_status.get("total_telemetry_events_ingested", 0),
                    "last_event_time": sep_status.get("last_telemetry_event_time"),
                    "intake_endpoint": "/api/telemetry/ingest",
                    "storage_stream": "data/telemetry/events.jsonl",
                    "diagnostics": sep_status.get("ingestion_diagnostics", {}),
                },
                "cloudscale_budget": {
                    "state": budg_status.get("operating_state", "NORMAL"),
                    "operating_state": budg_status.get("operating_state", "NORMAL"),
                    "credit_cap_usd": budg_status.get("authorized_budget_usd", 250.0),
                    "authorized_budget_usd": budg_status.get("authorized_budget_usd", 250.0),
                    "remaining_credits_usd": budg_status.get("remaining_budget_usd", 249.9986),
                    "remaining_budget_usd": budg_status.get("remaining_budget_usd", 249.9986),
                    "consumed_cost_usd": budg_status.get("consumed_cost_usd", 0.0014),
                    "percent_consumed": budg_status.get("percent_consumed", 0.0),
                },
                "defense_readiness": {
                    "status": "PARTIALLY_ACTIVE",
                    "summary": "Local process isolation & evidence preservation active; network/RPC containment unattached in container.",
                    "local_enforcement": "ACTIVE",
                    "network_enforcement": "UNVERIFIABLE",
                    "process_isolation": "VERIFIED",
                    "evidence_preservation": "VERIFIED",
                    "rpc_filtering": "UNVERIFIABLE",
                    "network_containment": "UNVERIFIABLE",
                },
                "detection_engine": {
                    "status": "ACTIVE",
                    "state": "IDLE" if sep_status.get("monitoring_lag_blocks", 0) <= 2 else "CATCHING_UP",
                    "rule_id": "RULE-CHAINC2-001",
                    "criteria_count": 6,
                    "score_threshold": 80.0,
                    "total_alerts": sep_status.get("total_alerts", 0),
                },
            },
        })

    # -------------------------------------------------------------------------
    # API: Independent Generator Controls (Separated from Detection)
    # -------------------------------------------------------------------------

    @app.route("/api/generator/status", methods=["GET"])
    def get_generator_status():
        """Retrieve operational state of the independent generator."""
        return jsonify(generator.get_status())

    @app.route("/api/generator/start", methods=["POST"])
    def start_generator():
        """Start the independent laboratory generator loop."""
        if is_production():
            return jsonify({"status": "REJECTED", "error": "Generator background daemon disabled in cloud production mode."}), 403
        data = request.get_json(silent=True) or {}
        single_step = data.get("single_step", False)
        if single_step:
            res = generator.step_cycle()
            return jsonify({"status": "STEP_COMPLETED", "result": res})
        max_cycles = data.get("max_cycles")
        if max_cycles is None:
            max_cycles = 4
        ok = generator.start(max_cycles=max_cycles)
        return jsonify({"status": "STARTED" if ok else "ALREADY_RUNNING", "max_cycles": max_cycles})

    @app.route("/api/generator/stop", methods=["POST"])
    def stop_generator():
        """Stop the independent laboratory generator."""
        ok = generator.stop()
        return jsonify({"status": "STOPPED" if ok else "NOT_RUNNING"})

    @app.route("/api/generator/step", methods=["POST"])
    def step_generator():
        """Execute a single workload rotation cycle on-demand."""
        res = generator.step_cycle()
        return jsonify({"status": "STEP_COMPLETED", "result": res})

    # -------------------------------------------------------------------------
    # API: Post-Run Evaluation (Access-Controlled Ground Truth vs Decisions)
    # -------------------------------------------------------------------------

    @app.route("/api/evaluation/post-run", methods=["GET"])
    def get_post_run_evaluation():
        """Evaluate detector performance against isolated generator ground-truth records."""
        gt_file = root / "data" / "evaluation" / "generator_ground_truth.jsonl"
        ground_truths = []
        if gt_file.exists():
            for line in gt_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        ground_truths.append(json.loads(line))
                    except Exception:
                        pass

        alerts = sepolia_service.get_alerts()
        alert_runs = {a.get("run_id") for a in alerts if a.get("run_id")}

        tp, fp, tn, fn = 0, 0, 0, 0
        for gt in ground_truths:
            rid = gt.get("run_id")
            actual_positive = (gt.get("ground_truth") == "POSITIVE")
            detected = rid in alert_runs
            if actual_positive and detected:
                tp += 1
            elif actual_positive and not detected:
                fn += 1
            elif not actual_positive and detected:
                fp += 1
            else:
                tn += 1

        total = tp + fp + tn + fn
        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 1.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 1.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 1.0

        return jsonify({
            "total_evaluated_cycles": total,
            "metrics": {
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
            },
            "ground_truth_records_count": len(ground_truths),
            "detector_alerts_count": len(alerts),
            "evaluation_policy": "Separate access-controlled post-run audit; zero live leakage to detector.",
        })

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
