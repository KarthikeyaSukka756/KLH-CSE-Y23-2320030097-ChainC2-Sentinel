# ChainC2 Sentinel — Zoho Catalyst Data Store & Persistence Adapter
"""Dual-mode persistence adapter supporting Zoho Catalyst Data Store with seamless local fallback.

Preserves research evidence integrity, deduplicates transaction records, enforces idempotent
writes, and maintains monitoring cursors.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("chainc2_sentinel.cloudscale.storage")

# Optional import of Zoho Catalyst SDK
try:
    import zcatalyst_sdk
    HAS_CATALYST_SDK = True
except ImportError:
    zcatalyst_sdk = None
    HAS_CATALYST_SDK = False


class CatalystStorageAdapter:
    """Manages persistence for transactions, experiments, alerts, and cursors."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent.parent
        self.local_dir = self.repo_root / "data" / "telemetry"
        self.local_dir.mkdir(parents=True, exist_ok=True)

        self.is_catalyst_cloud = bool(
            os.environ.get("CATALYST_PROJECT_ID")
            or os.environ.get("X_ZOHO_CATALYST_PROJECT_ID")
            or os.environ.get("CATALYST_ENV")
        )
        self.catalyst_app = None
        if self.is_catalyst_cloud and HAS_CATALYST_SDK:
            try:
                self.catalyst_app = zcatalyst_sdk.initialize()
                logger.info("CatalystStorageAdapter: Connected to Zoho Catalyst Data Store.")
            except Exception as e:
                logger.warning("Failed to initialize Zoho Catalyst SDK; using local persistence: %s", e)
                self.catalyst_app = None

    # -------------------------------------------------------------------------
    # Monitoring State & Cursor
    # -------------------------------------------------------------------------

    def get_monitoring_cursor(self) -> dict[str, Any]:
        """Retrieve the latest observed block cursor and metadata."""
        cursor_file = self.local_dir / "monitoring_cursor.json"
        if cursor_file.exists():
            try:
                return json.loads(cursor_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Error reading local monitoring cursor: %s", e)
        return {
            "network": "sepolia",
            "chain_id": 11155111,
            "last_block_number": None,
            "last_poll_time": None,
            "total_polled_blocks": 0,
            "total_observed_transactions": 0,
        }

    def save_monitoring_cursor(
        self,
        last_block_number: int,
        polled_at: Optional[str] = None,
        total_txs_observed: int = 0,
    ) -> None:
        """Persist updated block cursor."""
        current = self.get_monitoring_cursor()
        current.update({
            "last_block_number": last_block_number,
            "last_poll_time": polled_at or datetime.now(timezone.utc).isoformat(),
            "total_polled_blocks": current.get("total_polled_blocks", 0) + 1,
            "total_observed_transactions": total_txs_observed or current.get("total_observed_transactions", 0),
        })

        cursor_file = self.local_dir / "monitoring_cursor.json"
        cursor_file.write_text(json.dumps(current, indent=2), encoding="utf-8")

        # Sync to Catalyst Data Store if online
        if self.catalyst_app:
            try:
                table = self.catalyst_app.datastore().table("MonitoringState")
                table.insert_row({
                    "cursor_key": "sepolia_latest",
                    "last_block_number": str(last_block_number),
                    "last_poll_time": current["last_poll_time"],
                })
            except Exception as e:
                logger.debug("CloudScale Data Store cursor update skipped: %s", e)

    # -------------------------------------------------------------------------
    # Observed Transactions (Deduplicated)
    # -------------------------------------------------------------------------

    def save_transaction(self, tx_record: dict[str, Any]) -> bool:
        """Idempotently persist an observed Sepolia transaction."""
        tx_hash = tx_record.get("tx_hash")
        if not tx_hash:
            return False

        tx_file = self.local_dir / "sepolia_transactions.json"
        existing = {"transactions": []}
        if tx_file.exists():
            try:
                existing = json.loads(tx_file.read_text(encoding="utf-8"))
            except Exception:
                existing = {"transactions": []}

        tx_list = existing.get("transactions", [])
        if any(t.get("tx_hash") == tx_hash for t in tx_list):
            return False  # Already exists (idempotent)

        tx_list.insert(0, tx_record)
        existing["transactions"] = tx_list[:500]  # Cap buffer
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        tx_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        if self.catalyst_app:
            try:
                table = self.catalyst_app.datastore().table("ObservedTransactions")
                table.insert_row({
                    "tx_hash": tx_hash,
                    "block_number": str(tx_record.get("block_number", "")),
                    "from_address": tx_record.get("from_address", ""),
                    "to_address": tx_record.get("to_address", ""),
                    "value_eth": str(tx_record.get("value_eth", 0.0)),
                    "classification": tx_record.get("classification", "Unclassified"),
                    "observed_at": tx_record.get("observed_at", datetime.now(timezone.utc).isoformat()),
                })
            except Exception as e:
                logger.debug("CloudScale Data Store tx insert skipped: %s", e)

        return True

    def get_transactions(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve recent observed transactions."""
        tx_file = self.local_dir / "sepolia_transactions.json"
        if tx_file.exists():
            try:
                data = json.loads(tx_file.read_text(encoding="utf-8"))
                return data.get("transactions", [])[:limit]
            except Exception:
                pass
        return []

    # -------------------------------------------------------------------------
    # Experiment Records & Evidence Bundles
    # -------------------------------------------------------------------------

    def save_experiment_record(self, record: dict[str, Any]) -> None:
        """Persist an experiment summary and audit record."""
        exp_file = self.local_dir / "cloudscale_experiments.json"
        data = {"experiments": []}
        if exp_file.exists():
            try:
                data = json.loads(exp_file.read_text(encoding="utf-8"))
            except Exception:
                data = {"experiments": []}

        exps = data.get("experiments", [])
        run_id = record.get("run_id")
        # Replace existing or prepend
        exps = [e for e in exps if e.get("run_id") != run_id]
        exps.insert(0, record)
        data["experiments"] = exps[:200]
        exp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        if self.catalyst_app:
            try:
                table = self.catalyst_app.datastore().table("ExperimentRuns")
                table.insert_row({
                    "run_id": run_id,
                    "scenario": record.get("scenario", ""),
                    "ground_truth": record.get("ground_truth", ""),
                    "detection_score": str(record.get("detection_score", 0.0)),
                    "is_detected": bool(record.get("is_detected", False)),
                    "mitigation_status": record.get("mitigation_status", "SKIPPED"),
                    "executed_at": record.get("executed_at", datetime.now(timezone.utc).isoformat()),
                })
            except Exception as e:
                logger.debug("CloudScale Data Store experiment insert skipped: %s", e)

    def get_experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve past experiment records."""
        exp_file = self.local_dir / "cloudscale_experiments.json"
        if exp_file.exists():
            try:
                data = json.loads(exp_file.read_text(encoding="utf-8"))
                return data.get("experiments", [])[:limit]
            except Exception:
                pass
        return []

