# ChainC2 Sentinel — Dashboard Package
"""Master Dashboard module for ChainC2 Sentinel research framework.

Provides an integrated, local-first web interface and REST API
for evaluating cross-layer telemetry correlation and defensive protection.
"""

from src.dashboard.app import create_app

__all__ = ["create_app"]
