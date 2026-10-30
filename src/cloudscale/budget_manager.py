# ChainC2 Sentinel — Zoho Catalyst CloudScale Credit & Budget Safety Manager
"""Enforces credit-aware autonomous operation within the authorized $250.00 credit limit.

Strict Financial & Safety Boundaries:
- Budget Limit: Exactly $250.00 USD in Zoho Catalyst credits (hard spending cap).
- Zero Mainnet / Zero Paid Third-Party APIs: Never incurs charges outside Catalyst credits.
- Progressive Safety Policy:
    * NORMAL (< 75% utilized): Full autonomous monitoring and experiment scheduling.
    * WARNING (75% - 90% utilized): Bounded polling frequency, operational alerts logged.
    * PAUSE_EXPERIMENTS (90% - 95% utilized): Pauses new experiment triggers; preserves read-only monitoring.
    * SAFE_SHUTDOWN (>= 95% utilized): Halts scheduled worker, freezes state, prevents budget exhaustion.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("chainc2_sentinel.cloudscale.budget")

DEFAULT_CREDIT_BUDGET_USD = 250.00
WARNING_THRESHOLD_PERCENT = 75.0
PAUSE_THRESHOLD_PERCENT = 90.0
SHUTDOWN_THRESHOLD_PERCENT = 95.0


class BudgetOperatingState(str, Enum):
    """Lifecycle operating state dictated by credit consumption thresholds."""

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    PAUSE_EXPERIMENTS = "PAUSE_EXPERIMENTS"
    SAFE_SHUTDOWN = "SAFE_SHUTDOWN"


@dataclass
class ResourceUsageEstimate:
    """Estimated resource metrics and calculated cost breakdown."""

    function_invocations: int = 0
    function_compute_gb_sec: float = 0.0
    appsail_hours: float = 0.0
    datastore_reads: int = 0
    datastore_writes: int = 0
    storage_mb: float = 0.0
    network_egress_mb: float = 0.0
    estimated_cost_usd: float = 0.0
    actual_billed_cost_usd: Optional[float] = None
    last_updated_at: str = ""


class CatalystBudgetManager:
    """Tracks resource consumption and enforces progressive budget containment policies."""

    def __init__(
        self,
        total_budget_usd: float = DEFAULT_CREDIT_BUDGET_USD,
        repo_root: Optional[Path] = None,
        persistence_path: Optional[Path] = None,
    ) -> None:
        self.total_budget_usd = max(1.0, float(total_budget_usd))
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent.parent
        self.persistence_path = (
            persistence_path
            or self.repo_root / "data" / "telemetry" / "catalyst_budget_state.json"
        )
        self.usage = ResourceUsageEstimate(
            last_updated_at=datetime.now(timezone.utc).isoformat()
        )
        self.warning_threshold_pct = WARNING_THRESHOLD_PERCENT
        self.pause_threshold_pct = PAUSE_THRESHOLD_PERCENT
        self.shutdown_threshold_pct = SHUTDOWN_THRESHOLD_PERCENT
        self._load_state()

    def _load_state(self) -> None:
        """Load persisted budget and usage counters if available."""
        if self.persistence_path.exists():
            try:
                data = json.loads(self.persistence_path.read_text(encoding="utf-8"))
                u = data.get("usage", {})
                self.usage = ResourceUsageEstimate(
                    function_invocations=u.get("function_invocations", 0),
                    function_compute_gb_sec=u.get("function_compute_gb_sec", 0.0),
                    appsail_hours=u.get("appsail_hours", 0.0),
                    datastore_reads=u.get("datastore_reads", 0),
                    datastore_writes=u.get("datastore_writes", 0),
                    storage_mb=u.get("storage_mb", 0.0),
                    network_egress_mb=u.get("network_egress_mb", 0.0),
                    estimated_cost_usd=u.get("estimated_cost_usd", 0.0),
                    actual_billed_cost_usd=u.get("actual_billed_cost_usd"),
                    last_updated_at=u.get(
                        "last_updated_at", datetime.now(timezone.utc).isoformat()
                    ),
                )
            except Exception as e:
                logger.warning("Failed to load budget state from disk: %s", e)

    def _persist_state(self) -> None:
        """Persist current usage and budget state."""
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            state_data = {
                "total_budget_usd": self.total_budget_usd,
                "current_operating_state": self.get_operating_state().value,
                "usage": asdict(self.usage),
                "remaining_credits_usd": self.get_remaining_budget_usd(),
                "percent_consumed": self.get_percent_consumed(),
                "thresholds": {
                    "warning_pct": self.warning_threshold_pct,
                    "pause_pct": self.pause_threshold_pct,
                    "shutdown_pct": self.shutdown_threshold_pct,
                },
            }
            self.persistence_path.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to persist budget state: %s", e)

    def record_function_invocation(
        self, duration_sec: float = 1.0, memory_mb: int = 256
    ) -> None:
        """Record a serverless function or cron execution."""
        self.usage.function_invocations += 1
        gb_sec = (memory_mb / 1024.0) * duration_sec
        self.usage.function_compute_gb_sec += gb_sec
        # Estimated Catalyst pricing: ~$0.00001667 per GB-second + $0.20 per million calls
        call_cost = 0.0000002
        compute_cost = gb_sec * 0.00001667
        self.usage.estimated_cost_usd += (call_cost + compute_cost)
        self.usage.last_updated_at = datetime.now(timezone.utc).isoformat()
        self._persist_state()

    def record_datastore_operation(self, op_type: str = "read", count: int = 1) -> None:
        """Record Data Store read or write operations."""
        if op_type.lower() == "write":
            self.usage.datastore_writes += count
            # Estimated Catalyst pricing: ~$0.50 per 100k writes
            self.usage.estimated_cost_usd += count * 0.000005
        else:
            self.usage.datastore_reads += count
            # Estimated Catalyst pricing: ~$0.10 per 100k reads
            self.usage.estimated_cost_usd += count * 0.000001
        self.usage.last_updated_at = datetime.now(timezone.utc).isoformat()
        self._persist_state()

    def record_appsail_runtime(self, runtime_hours: float = 1.0) -> None:
        """Record AppSail container runtime hours."""
        self.usage.appsail_hours += runtime_hours
        # Estimated AppSail base container rate: ~$0.03 per hour for 512MB tier
        self.usage.estimated_cost_usd += runtime_hours * 0.03
        self.usage.last_updated_at = datetime.now(timezone.utc).isoformat()
        self._persist_state()

    def set_actual_billed_cost(self, actual_cost_usd: float) -> None:
        """Update actual cost when queried from Zoho Catalyst billing console."""
        self.usage.actual_billed_cost_usd = max(0.0, float(actual_cost_usd))
        self.usage.last_updated_at = datetime.now(timezone.utc).isoformat()
        self._persist_state()

    def get_consumed_cost_usd(self) -> float:
        """Return the effective consumed cost, prioritizing actual billed if available."""
        if self.usage.actual_billed_cost_usd is not None:
            return self.usage.actual_billed_cost_usd
        return round(self.usage.estimated_cost_usd, 4)

    def get_percent_consumed(self) -> float:
        """Return the percentage of total authorized credit consumed."""
        consumed = self.get_consumed_cost_usd()
        return round(min(100.0, (consumed / self.total_budget_usd) * 100.0), 2)

    def get_remaining_budget_usd(self) -> float:
        """Return remaining credit balance in USD."""
        consumed = self.get_consumed_cost_usd()
        return round(max(0.0, self.total_budget_usd - consumed), 4)

    def get_operating_state(self) -> BudgetOperatingState:
        """Evaluate current resource consumption against progressive safety thresholds."""
        pct = self.get_percent_consumed()
        if pct >= self.shutdown_threshold_pct:
            return BudgetOperatingState.SAFE_SHUTDOWN
        elif pct >= self.pause_threshold_pct:
            return BudgetOperatingState.PAUSE_EXPERIMENTS
        elif pct >= self.warning_threshold_pct:
            return BudgetOperatingState.WARNING
        return BudgetOperatingState.NORMAL

    def can_execute_experiment(self) -> tuple[bool, str]:
        """Determine if a new controlled research experiment is permitted."""
        state = self.get_operating_state()
        if state == BudgetOperatingState.SAFE_SHUTDOWN:
            return (
                False,
                f"Budget safeguard: Operation is in SAFE_SHUTDOWN ({self.get_percent_consumed()}% of ${self.total_budget_usd:.2f} credits consumed).",
            )
        elif state == BudgetOperatingState.PAUSE_EXPERIMENTS:
            return (
                False,
                f"Budget safeguard: New experiments PAUSED ({self.get_percent_consumed()}% of ${self.total_budget_usd:.2f} credits consumed).",
            )
        return True, "Operation permitted within authorized budget."

    def get_status_summary(self) -> dict[str, Any]:
        """Return structured summary for API responses and dashboard widgets."""
        state = self.get_operating_state()
        can_exec, reason = self.can_execute_experiment()
        return {
            "platform": "Zoho Catalyst CloudScale",
            "authorized_budget_usd": self.total_budget_usd,
            "consumed_cost_usd": self.get_consumed_cost_usd(),
            "remaining_budget_usd": self.get_remaining_budget_usd(),
            "percent_consumed": self.get_percent_consumed(),
            "operating_state": state.value,
            "experiment_execution_permitted": can_exec,
            "policy_reason": reason,
            "cost_type": "ACTUAL_BILLED" if self.usage.actual_billed_cost_usd is not None else "ESTIMATED_RUNTIMES",
            "thresholds": {
                "warning_threshold_pct": self.warning_threshold_pct,
                "pause_threshold_pct": self.pause_threshold_pct,
                "shutdown_threshold_pct": self.shutdown_threshold_pct,
            },
            "resource_counters": asdict(self.usage),
        }

