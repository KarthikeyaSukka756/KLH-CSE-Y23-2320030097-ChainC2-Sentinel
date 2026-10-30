# ChainC2 Sentinel — Sepolia Testnet Monitoring & Experiment Dashboard Service
"""Dashboard service exposing Ethereum Sepolia Testnet monitoring, public transaction observation,
live controlled experiment execution, and defensive mitigation records.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from src.blockchain.monitor import SepoliaMonitor
from src.dashboard.services import get_repo_root

logger = logging.getLogger("chainc2_sentinel.dashboard.sepolia_service")


class SepoliaService:
    """Service wrapping the SepoliaMonitor for Flask routes."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or get_repo_root()
        self.monitor = SepoliaMonitor.get_instance(repo_root=self.repo_root)

    def get_status(self, force: bool = False) -> dict[str, Any]:
        """Return connectivity and monitor status."""
        return self.monitor.check_connection(force=force)

    def get_transactions(
        self,
        filter_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return observed transactions, optionally filtered."""
        with self.monitor._lock:
            txs = list(self.monitor.observed_transactions)

        if filter_type:
            ft = filter_type.strip().lower()
            if ft == "detected":
                txs = [t for t in txs if t.get("detection_status") == "TRIGGERED"]
            elif ft == "benign":
                txs = [t for t in txs if t.get("detection_status") == "BENIGN"]
            elif ft == "unclassified":
                txs = [t for t in txs if t.get("classification") == "Unclassified"]

        return txs[:limit]

    def poll_blocks(self, count: int = 1) -> list[dict[str, Any]]:
        """Poll latest Sepolia blocks."""
        return self.monitor.poll_latest_blocks(block_count=count)

    def get_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return generated detection alerts."""
        with self.monitor._lock:
            return list(self.monitor.alerts)[:limit]

    def get_experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return experiment history."""
        with self.monitor._lock:
            return list(self.monitor.experiment_records)[:limit]

    def get_mitigations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return mitigation execution records."""
        with self.monitor._lock:
            return list(self.monitor.mitigation_records)[:limit]

    def execute_experiment(self, experiment_type: str = "positive_c2") -> dict[str, Any]:
        """Trigger a controlled experiment."""
        return self.monitor.execute_controlled_experiment(experiment_type=experiment_type)

    def rollback_mitigations(self) -> dict[str, Any]:
        """Rollback active defensive mitigations."""
        return self.monitor.rollback_mitigations()

    def verify_transaction(
        self,
        tx_hash: str,
        expected_contract: Optional[str] = None,
    ) -> dict[str, Any]:
        """Independently verify transaction on Sepolia."""
        return self.monitor.verify_transaction_on_sepolia(tx_hash=tx_hash, expected_contract=expected_contract)

    def get_investigations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return investigation records."""
        return self.monitor.get_investigations(limit=limit)

    def get_investigation_by_id(self, inv_id: str) -> Optional[dict[str, Any]]:
        """Return specific investigation record."""
        return self.monitor.get_investigation_by_id(inv_id)

    def get_alert_by_id(self, alert_id: str) -> Optional[dict[str, Any]]:
        """Return specific alert record."""
        return self.monitor.get_alert_by_id(alert_id)

    def start_monitoring(self, interval_seconds: float = 15.0) -> bool:
        """Start unattended continuous monitoring."""
        return self.monitor.start_continuous_monitoring(poll_interval_seconds=interval_seconds)

    def stop_monitoring(self) -> bool:
        """Stop unattended continuous monitoring."""
        return self.monitor.stop_continuous_monitoring()

    def catch_up(self, max_blocks: int = 10) -> dict[str, Any]:
        """Catch up ingestion cursor towards Sepolia chain head within bounded limits."""
        return self.monitor.catch_up(max_blocks=max_blocks)

    def process_telemetry_events(self, events: Any) -> dict[str, Any]:
        """Process incoming raw telemetry events."""
        return self.monitor.process_telemetry_events(events)

