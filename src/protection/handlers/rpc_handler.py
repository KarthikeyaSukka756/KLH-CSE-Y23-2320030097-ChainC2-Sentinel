# ChainC2 Sentinel — RPC Filter Mitigation Handler
"""Application-layer RPC filter handler for Milestone 9.

Integrates with the client-facing JSON-RPC proxy to quarantine synthetic
smart contract addresses without modifying OS firewalls or host networking.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.protection.interfaces import BaseMitigationHandler
from src.protection.models import MitigationAction, MitigationStatus, MitigationType
from src.rpc_proxy.proxy import RpcProxy

logger = logging.getLogger("chainc2_sentinel.protection.handlers.rpc")


class RpcFilterHandler(BaseMitigationHandler):
    """Mitigation handler managing smart contract filtering on the RPC proxy."""

    def __init__(self, proxy: Optional[RpcProxy] = None) -> None:
        """Initialize handler with target RPC proxy instance.

        Args:
            proxy: Optional RpcProxy instance to manage.
        """
        self.proxy = proxy

    @property
    def mitigation_type(self) -> MitigationType:
        return MitigationType.RPC_FILTER

    def execute(self, action: MitigationAction) -> bool:
        """Apply contract filter to the RPC proxy.

        Args:
            action: The structured mitigation action request.

        Returns:
            True if filter applied successfully, False otherwise.
        """
        contract_address = (
            action.parameters.get("contract_address")
            or action.target_resource
        )
        if not contract_address:
            action.status = MitigationStatus.FAILED
            action.error_message = "No contract address provided in action parameters"
            return False

        if self.proxy is not None:
            self.proxy.add_contract_filter(contract_address)

        action.status = MitigationStatus.EXECUTED
        action.execution_timestamp = datetime.now(timezone.utc)
        logger.info("RpcFilterHandler: Quarantined contract %s on proxy", contract_address)
        return True

    def verify(self, action: MitigationAction) -> bool:
        """Verify that the contract filter is actively enforced.

        Args:
            action: The executed mitigation action.

        Returns:
            True if verified active, False otherwise.
        """
        contract_address = (
            action.parameters.get("contract_address")
            or action.target_resource
        )
        if not contract_address:
            action.status = MitigationStatus.FAILED
            action.error_message = "Missing contract address for verification"
            return False

        if self.proxy is not None:
            if not self.proxy.is_contract_filtered(contract_address):
                action.status = MitigationStatus.FAILED
                action.verification_details = "Proxy did not report contract as filtered"
                return False

        action.status = MitigationStatus.VERIFIED
        action.verification_timestamp = datetime.now(timezone.utc)
        action.verification_details = f"Confirmed application-layer filter active for {contract_address}"
        logger.info("RpcFilterHandler: Verified filter active for %s", contract_address)
        return True

    def rollback(self, action: MitigationAction) -> bool:
        """Roll back the contract filter, restoring normal query capability.

        Args:
            action: The mitigation action to revert.

        Returns:
            True if reverted, False otherwise.
        """
        contract_address = (
            action.parameters.get("contract_address")
            or action.target_resource
        )
        if self.proxy is not None and contract_address:
            self.proxy.remove_contract_filter(contract_address)

        action.status = MitigationStatus.ROLLED_BACK
        logger.info("RpcFilterHandler: Rolled back filter for %s", contract_address)
        return True
