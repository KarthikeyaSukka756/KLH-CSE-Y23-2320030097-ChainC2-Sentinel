# ChainC2 Sentinel — Scenario Engine Package
"""Scenario orchestrator and definitions for synthetic test scenarios."""

from src.scenarios.base import BaseScenario, ScenarioResult
from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario
from src.scenarios.payload import SyntheticC2Payload
from src.scenarios.runner import ScenarioRunner

__all__ = [
    "BaseScenario",
    "ScenarioResult",
    "SyntheticC2Payload",
    "BenignWeb3Scenario",
    "SyntheticC2Scenario",
    "ScenarioRunner",
]
