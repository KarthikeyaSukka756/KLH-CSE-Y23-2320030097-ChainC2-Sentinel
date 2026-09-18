# ChainC2 Sentinel — Network Containment Mitigation Handler
"""Controlled network containment handler for Milestone 9.

Integrates with the controlled LocalHttpTargetServer to reject subsequent
synthetic HTTP beacons (returning HTTP 403) without touching host network adapters.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.http_target.server import LocalHttpTargetServer
from src.protection.interfaces import BaseMitigationHandler
from src.protection.models import MitigationAction, MitigationStatus, MitigationType

logger = logging.getLogger("chainc2_sentinel.protection.handlers.network")


class NetworkContainmentHandler(BaseMitigationHandler):
    """Mitigation handler enforcing beacon containment on LocalHttpTargetServer."""

    def __init__(self, target_server: Optional[LocalHttpTargetServer] = None) -> None:
        """Initialize handler with target server reference.

        Args:
            target_server: Controlled LocalHttpTargetServer instance.
        """
        self.target_server = target_server

    @property
    def mitigation_type(self) -> MitigationType:
        return MitigationType.NETWORK_CONTAINMENT

    def execute(self, action: MitigationAction) -> bool:
        """Enable network containment on the local HTTP target server.

        Args:
            action: The structured mitigation action request.

        Returns:
            True if containment enabled, False otherwise.
        """
        client_ip = action.parameters.get("destination_host", "127.0.0.1")
        if client_ip not in ("127.0.0.1", "localhost"):
            action.status = MitigationStatus.FAILED
            action.error_message = f"Refusing containment for non-local host: {client_ip}"
            return False

        if self.target_server is not None:
            self.target_server.enable_containment()

        action.status = MitigationStatus.EXECUTED
        action.execution_timestamp = datetime.now(timezone.utc)
        logger.info("NetworkContainmentHandler: Enabled containment on target server")
        return True

    def verify(self, action: MitigationAction) -> bool:
        """Verify that containment is active on the local HTTP target server.

        Args:
            action: The executed mitigation action.

        Returns:
            True if containment verified, False otherwise.
        """
        if self.target_server is not None:
            if not self.target_server.is_containment_active():
                action.status = MitigationStatus.FAILED
                action.verification_details = "Target server containment is not active"
                return False

        action.status = MitigationStatus.VERIFIED
        action.verification_timestamp = datetime.now(timezone.utc)
        action.verification_details = "Confirmed HTTP 403 beacon containment active on local target"
        logger.info("NetworkContainmentHandler: Verified beacon containment active")
        return True

    def rollback(self, action: MitigationAction) -> bool:
        """Roll back network containment, restoring normal beacon acknowledgment.

        Args:
            action: The mitigation action to revert.

        Returns:
            True if containment disabled, False otherwise.
        """
        if self.target_server is not None:
            self.target_server.disable_containment()

        action.status = MitigationStatus.ROLLED_BACK
        logger.info("NetworkContainmentHandler: Rolled back beacon containment")
        return True
