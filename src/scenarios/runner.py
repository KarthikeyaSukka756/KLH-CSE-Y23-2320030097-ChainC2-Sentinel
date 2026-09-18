# ChainC2 Sentinel — Scenario Runner
"""Orchestrator for executing controlled detection scenarios and collecting multi-source telemetry.

Usage:
    runner = ScenarioRunner(output_path="data/telemetry/events.jsonl")
    results = runner.run_all()
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.http_target.server import LocalHttpTargetServer
from src.models.events import TelemetrySource
from src.normalizer.normalizer import EventStore
from src.scenarios.base import ScenarioResult
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario

logger = logging.getLogger("chainc2_sentinel.scenarios.runner")


class ScenarioRunner:
    """Orchestrates the execution of laboratory scenarios and manages persistence."""

    def __init__(
        self,
        output_path: Optional[str] = None,
        host: str = "127.0.0.1",
        rpc_proxy_url: str = "http://127.0.0.1:8546",
        upstream_url: str = "http://127.0.0.1:8545",
    ) -> None:
        """Initialize scenario runner.

        Args:
            output_path: Optional path to JSONL file for appending telemetry events.
            host: Host identifier.
            rpc_proxy_url: Client-facing RPC proxy URL.
            upstream_url: Upstream Hardhat node URL.
        """
        self.output_path = output_path
        self.host = host
        self.rpc_proxy_url = rpc_proxy_url
        self.upstream_url = upstream_url

        self.event_store = EventStore(output_path) if output_path else None

    def run_benign(self, run_id: Optional[str] = None) -> ScenarioResult:
        """Run Scenario A (Benign Web3 Activity)."""
        scenario = BenignWeb3Scenario(
            run_id=run_id,
            event_store=self.event_store,
            host=self.host,
            rpc_proxy_url=self.rpc_proxy_url,
            upstream_url=self.upstream_url,
        )
        return scenario.run()

    def run_synthetic_c2(
        self,
        target_server: Optional[LocalHttpTargetServer] = None,
        run_id: Optional[str] = None,
    ) -> ScenarioResult:
        """Run Scenario B (Synthetic Blockchain-Mediated C2-Like Activity)."""
        scenario = SyntheticC2Scenario(
            target_server=target_server,
            run_id=run_id,
            event_store=self.event_store,
            host=self.host,
            rpc_proxy_url=self.rpc_proxy_url,
            upstream_url=self.upstream_url,
        )
        return scenario.run()

    def run_all(self, target_server: Optional[LocalHttpTargetServer] = None) -> list[ScenarioResult]:
        """Run all Phase 1 Milestone 4 scenarios in sequence."""
        results = [
            self.run_benign(),
            self.run_synthetic_c2(target_server=target_server),
        ]
        return results

    @staticmethod
    def summarize(results: list[ScenarioResult]) -> dict[str, Any]:
        """Generate a structured summary report of scenario execution runs."""
        total_events = sum(len(r.events) for r in results)
        total_by_source: dict[str, int] = {
            TelemetrySource.ENDPOINT.value: 0,
            TelemetrySource.RPC.value: 0,
            TelemetrySource.BLOCKCHAIN.value: 0,
            TelemetrySource.NETWORK.value: 0,
        }
        scenario_summaries = []

        for r in results:
            for source, count in r.event_counts_by_source.items():
                total_by_source[source] = total_by_source.get(source, 0) + count

            scenario_summaries.append({
                "scenario_id": r.scenario_id,
                "run_id": r.run_id,
                "success": r.success,
                "total_events": len(r.events),
                "event_counts": r.event_counts_by_source,
                "details": r.details,
            })

        return {
            "total_scenarios": len(results),
            "total_events": total_events,
            "events_by_source": total_by_source,
            "scenarios": scenario_summaries,
        }
