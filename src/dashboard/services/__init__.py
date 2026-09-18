# ChainC2 Sentinel — Dashboard Services Package
"""Backend services supporting the ChainC2 Sentinel Master Dashboard."""

from pathlib import Path


def get_repo_root() -> Path:
    """Return the repository root directory as a resolved Path object."""
    # src/dashboard/services/__init__.py -> 3 levels up to root
    return Path(__file__).resolve().parents[3]
