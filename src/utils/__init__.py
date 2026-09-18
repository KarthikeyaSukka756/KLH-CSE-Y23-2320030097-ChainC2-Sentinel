# ChainC2 Sentinel — Utilities Package
"""Shared utilities: configuration, logging, identifiers."""

from src.utils.identifiers import generate_correlation_id, generate_event_id
from src.utils.logging import setup_logging

__all__ = [
    "generate_correlation_id",
    "generate_event_id",
    "setup_logging",
]
