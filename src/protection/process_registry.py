# ChainC2 Sentinel — Controlled Scenario Worker Registry
"""Thread-safe registry for cooperative process-level containment in the laboratory.

Safety Declarations:
- Operates SOLELY via cooperative signaling for registered laboratory workers.
- Strictly refuses to touch, signal, or terminate arbitrary OS processes.
- NEVER invokes kill -9, taskkill, TerminateProcess, PowerShell, or subprocess signals.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

logger = logging.getLogger("chainc2_sentinel.protection.process_registry")


class ScenarioWorkerRegistry:
    """Registry managing the cooperative containment lifecycle of laboratory workers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workers: dict[str, dict[str, Any]] = {}

    def register_worker(
        self,
        process_name: str,
        pid: int,
        worker_id: Optional[str] = None,
    ) -> str:
        """Register an active laboratory scenario worker.

        Args:
            process_name: Name of the laboratory scenario process.
            pid: PID reported by the synthetic endpoint collector.
            worker_id: Optional worker identifier.

        Returns:
            The registered worker key.
        """
        key = worker_id or f"{process_name}:{pid}"
        with self._lock:
            self._workers[key] = {
                "process_name": process_name,
                "pid": pid,
                "status": "ACTIVE",
                "isolated": False,
            }
        logger.info("WorkerRegistry: Registered laboratory worker %s (PID=%d)", process_name, pid)
        return key

    def isolate_worker(
        self,
        process_name: str,
        pid: Optional[int] = None,
    ) -> bool:
        """Cooperatively signal containment for a registered laboratory worker.

        Refuses to touch any process not explicitly registered in the laboratory registry.

        Args:
            process_name: Name of the process.
            pid: Optional PID.

        Returns:
            True if a matching laboratory worker was found and isolated; False otherwise.
        """
        with self._lock:
            found = False
            for key, worker in self._workers.items():
                if worker["process_name"] == process_name:
                    if pid is None or worker["pid"] == pid:
                        worker["status"] = "ISOLATED"
                        worker["isolated"] = True
                        found = True
                        logger.info("WorkerRegistry: Cooperatively isolated worker %s (PID=%d)", process_name, worker["pid"])

            if not found:
                logger.warning(
                    "WorkerRegistry: Refused isolation request for '%s' (PID=%s) — process is not a registered laboratory worker.",
                    process_name,
                    pid,
                )
                return False
            return True

    def rollback_worker(
        self,
        process_name: str,
        pid: Optional[int] = None,
    ) -> bool:
        """Roll back cooperative isolation, restoring ACTIVE status.

        Args:
            process_name: Name of the process.
            pid: Optional PID.

        Returns:
            True if worker was rolled back, False otherwise.
        """
        with self._lock:
            found = False
            for key, worker in self._workers.items():
                if worker["process_name"] == process_name:
                    if pid is None or worker["pid"] == pid:
                        worker["status"] = "ACTIVE"
                        worker["isolated"] = False
                        found = True
                        logger.info("WorkerRegistry: Restored worker %s (PID=%d) to ACTIVE", process_name, worker["pid"])
            return found

    def is_isolated(self, process_name: str, pid: Optional[int] = None) -> bool:
        """Check whether a laboratory worker is currently isolated."""
        with self._lock:
            for key, worker in self._workers.items():
                if worker["process_name"] == process_name:
                    if pid is None or worker["pid"] == pid:
                        return worker["isolated"]
            return False

    def get_worker(self, process_name: str, pid: Optional[int] = None) -> Optional[dict[str, Any]]:
        """Retrieve worker record if present."""
        with self._lock:
            for key, worker in self._workers.items():
                if worker["process_name"] == process_name:
                    if pid is None or worker["pid"] == pid:
                        return dict(worker)
            return None

    def clear(self) -> None:
        """Clear all registered workers."""
        with self._lock:
            self._workers.clear()


# Default global registry for scenario executions
_global_registry = ScenarioWorkerRegistry()


def get_worker_registry() -> ScenarioWorkerRegistry:
    """Return the global ScenarioWorkerRegistry instance."""
    return _global_registry
