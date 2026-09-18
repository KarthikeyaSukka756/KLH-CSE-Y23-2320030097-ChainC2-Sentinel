# ChainC2 Sentinel — Blockchain Telemetry Collector
"""Converts blockchain transaction/event metadata into SentinelEvents.

Designed for the local Hardhat environment only.
Supports activity from both:
    - C2DataStore (synthetic research data store)
    - BenignDAppContract (legitimate DApp baseline)

The contract_name field allows later phases to distinguish
suspicious from legitimate blockchain activity.

No public blockchain interaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from src.models.events import (
    BlockchainInfo,
    SentinelEvent,
    TelemetrySource,
)


class BlockchainTelemetryCollector:
    """Converts blockchain interaction metadata into SentinelEvents.

    Accepts raw transaction/event data and produces normalized events.
    Does not interact with the blockchain directly — it converts
    metadata that has already been observed or retrieved.
    """

    def __init__(
        self,
        chain_id: str = "31337",
        network_name: str = "hardhat",
        host: Optional[str] = None,
    ) -> None:
        """Initialize the blockchain telemetry collector.

        Args:
            chain_id: Chain/network identifier (default: Hardhat's 31337).
            network_name: Network name (default: "hardhat").
            host: Host identifier for generated events.
        """
        self._chain_id = chain_id
        self._network_name = network_name
        self._host = host

    def collect(
        self,
        contract_name: str,
        event_type: str = "contract_interaction",
        tx_hash: Optional[str] = None,
        block_number: Optional[int] = None,
        contract_address: Optional[str] = None,
        sender: Optional[str] = None,
        function_name: Optional[str] = None,
        event_name: Optional[str] = None,
        event_args: Optional[dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> SentinelEvent:
        """Create a SentinelEvent from blockchain interaction metadata.

        Args:
            contract_name: Name of the contract
                           ("C2DataStore" or "BenignDAppContract").
            event_type: Specific event type string.
            tx_hash: Transaction hash.
            block_number: Block number.
            contract_address: Smart contract address.
            sender: Transaction sender address.
            function_name: Called function name.
            event_name: Emitted event name.
            event_args: Event arguments.
            timestamp: Event timestamp (defaults to now UTC).

        Returns:
            A SentinelEvent with source=BLOCKCHAIN and populated
            BlockchainInfo.
        """
        blockchain_info = BlockchainInfo(
            tx_hash=tx_hash,
            block_number=block_number,
            contract_address=contract_address,
            chain_id=self._chain_id,
            network_name=self._network_name,
            sender=sender,
            function_name=function_name,
            event_name=event_name,
            event_args=event_args,
            contract_name=contract_name,
        )

        return SentinelEvent(
            timestamp=timestamp or datetime.now(timezone.utc),
            source=TelemetrySource.BLOCKCHAIN,
            event_type=event_type,
            host=self._host,
            blockchain=blockchain_info,
        )
