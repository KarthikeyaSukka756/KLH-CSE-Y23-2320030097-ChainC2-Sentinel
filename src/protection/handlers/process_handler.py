# ChainC2 Sentinel — Cooperative Process Isolation Handler
"""Cooperative scenario process isolation handler for Milestone 9.

Integrates with ScenarioWorkerRegistry to cooperatively isolate laboratory
scenario workers without ever terminating arbitrary OS processes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.protection.interfaces import BaseMitigationHandler
from src.protection.models import MitigationAction, MitigationStatus, MitigationType
from src.protection.process_registry import ScenarioWorkerRegistry, get_worker_registry

logger = logging.getLogger("chainc2_sentinel.protection.handlers.process")


class ProcessIsolationHandler(BaseMitigationHandler):
    """Mitigation handler enforcing cooperative process isolation."""

    def __init__(self, registry: Optional[ScenarioWorkerRegistry] = None) -> None:
        """Initialize handler with worker registry.

        Args:
            registry: Optional ScenarioWorkerRegistry. Defaults to global registry.
        """
        self.registry = registry or get_worker_registry()

    @property
    def mitigation_type(self) -> MitigationType:
        return MitigationType.PROCESS_ISOLATION

    def execute(self, action: MitigationAction) -> bool:
        """Cooperatively isolate the designated laboratory scenario worker.

        Args:
            action: The structured mitigation action request.

        Returns:
            True if worker successfully signaled, False if unregistered or invalid.
        """
        process_name = (
            action.parameters.get("process_name")
            or action.target_resource
        )
        pid = action.parameters.get("pid")

        # Refuse to proceed if process name is empty or not in safe laboratory whitelist
        if not process_name:
            action.status = MitigationStatus.FAILED
            action.error_message = "No process name specified for isolation"
            return False

        # Execute cooperative containment via laboratory registry
        success = self.registry.isolate_worker(process_name=process_name, pid=pid)
        if not success:
            action.status = MitigationStatus.FAILED
            action.error_message = f"Process '{process_name}' (PID={pid}) is not a registered laboratory worker"
            logger.warning("ProcessIsolationHandler: Refused isolation: %s", action.error_message)
            return False

        action.status = MitigationStatus.EXECUTED
        action.execution_timestamp = datetime.now(timezone.utc)
        logger.info("ProcessIsolationHandler: Cooperatively isolated worker %s (PID=%s)", process_name, pid)
        return True

    def verify(self, action: MitigationAction) -> bool:
        """Verify that the laboratory worker state is marked ISOLATED.

        Args:
            action: The executed mitigation action.

        Returns:
            True if worker is isolated, False otherwise.
        """
        process_name = (
            action.parameters.get("process_name")
            or action.target_resource
        )
        pid = action.parameters.get("pid")

        if not self.registry.is_isolated(process_name=process_name, pid=pid):
            action.status = MitigationStatus.FAILED
            action.verification_details = f"Worker {process_name} (PID={pid}) is not in ISOLATED state"
            return False

        action.status = MitigationStatus.VERIFIED
        action.verification_timestamp = datetime.now(timezone.utc)
        action.verification_details = f"Confirmed worker {process_name} (PID={pid}) state is ISOLATED"
        logger.info("ProcessIsolationHandler: Verified isolation for %s", process_name)
        return True

    def rollback(self, action: MitigationAction) -> bool:
        """Roll back cooperative isolation, restoring worker to ACTIVE state.

        Args:
            action: The mitigation action to revert.

        Returns:
            True if rolled back, False otherwise.
        """
        process_name = (
            action.parameters.get("process_name")
            or action.target_resource
        )
        pid = action.parameters.get("pid")

        self.registry.rollback_worker(process_name=process_name, pid=pid)
        action.status = MitigationStatus.ROLLED_BACK
        logger.info("ProcessIsolationHandler: Rolled back isolation for %s", process_name)
        return True
