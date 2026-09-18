# ChainC2 Sentinel — Pytest Fixtures
"""Shared fixtures for the ChainC2 Sentinel test suite."""

import os
import pytest
import tempfile


@pytest.fixture
def telemetry_output_dir(tmp_path):
    """Provides a temporary directory for telemetry output during tests."""
    output_dir = tmp_path / "telemetry"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_correlation_id():
    """Provides a fixed correlation ID for deterministic testing."""
    return "test-correlation-00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_run_id():
    """Provides a fixed run ID for deterministic testing."""
    return "test-run-00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_scenario_id():
    """Provides a fixed scenario ID for deterministic testing."""
    return "test_scenario_v1"
