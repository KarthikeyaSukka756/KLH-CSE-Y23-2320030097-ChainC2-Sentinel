# ChainC2 Sentinel — Scenario Definitions Package
"""Scenario definitions for benign and C2-like laboratory scenarios."""

from src.scenarios.definitions.benign_scenario import BenignWeb3Scenario
from src.scenarios.definitions.c2_scenario import SyntheticC2Scenario

__all__ = [
    "BenignWeb3Scenario",
    "SyntheticC2Scenario",
]
