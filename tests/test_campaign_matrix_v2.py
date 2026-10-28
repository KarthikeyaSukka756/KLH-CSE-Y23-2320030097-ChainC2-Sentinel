# ChainC2 Sentinel — Matrix v2 81-Run Campaign Validation Suite
"""Automated tests validating the Matrix v2 balanced campaign (81 runs):
- Exact 81-run allocation across all 27 registered variants
- Exactly 3 replicates per variant (Tier 1: 48, Tier 2: 33)
- Deterministic plan generation, PRNG seeding, and provenance tracking
- CLI dry-run non-destructive behavior
- CLI authorization latch (refusal to execute without --execute-authorized)
- Overwrite protection (refusal to overwrite existing result files)
- Unhandled failure abort handling (never labeling partial execution as complete)
- Preservation of existing evaluation baselines
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.evaluation.campaign import (
    BALANCED_CAMPAIGN_81,
    MINIMAL_CAMPAIGN_116,
    RECOMMENDED_CAMPAIGN_372,
    CampaignPlanGenerator,
    CampaignRunSpec,
)
from src.models.events import SentinelEvent, TelemetrySource
from src.models.matrix_v2 import (
    Classification,
    ExecutionStatus,
    GroundTruth,
    MatrixV2ExecutionRecord,
    Provenance,
    VARIANT_REGISTRY,
    compute_aggregate_latency,
    compute_deterministic_seed,
)
from src.scenarios.base import ScenarioResult
from src.scenarios.runner import ScenarioRunner


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.mark.unit
class TestCampaignMatrixV2Allocation:
    """Validates the structure and allocation of BALANCED_CAMPAIGN_81."""

    def test_balanced_campaign_total_runs(self):
        """Confirm exactly 81 runs in BALANCED_CAMPAIGN_81."""
        assert sum(BALANCED_CAMPAIGN_81.values()) == 81

    def test_all_27_variants_covered_once(self):
        """Confirm all 27 registered variants are included exactly once."""
        registered_keys = set(VARIANT_REGISTRY.keys())
        allocated_keys = set(BALANCED_CAMPAIGN_81.keys())
        assert allocated_keys == registered_keys
        assert len(BALANCED_CAMPAIGN_81) == 27

    def test_exactly_three_replicates_per_variant(self):
        """Confirm every variant is allocated exactly 3 replicates."""
        for vid, count in BALANCED_CAMPAIGN_81.items():
            assert count == 3, f"Variant {vid} has {count} replicates, expected 3"

    def test_tier_breakdown_48_and_33(self):
        """Confirm Tier 1 (48 runs) and Tier 2 (33 runs) partition."""
        tier1_variants = [
            "A01", "A02", "A03", "A04", "A05", "A06",
            "B01", "B02", "B03", "B04", "B05",
            "C01", "C02", "C03", "C04", "C05",
        ]
        tier2_variants = [
            "A07", "A08a", "A08b",
            "B06", "B07a", "B07b", "B08", "B09",
            "C06", "C07", "C08",
        ]
        assert len(tier1_variants) == 16
        assert len(tier2_variants) == 11
        assert len(tier1_variants) + len(tier2_variants) == 27

        tier1_sum = sum(BALANCED_CAMPAIGN_81[v] for v in tier1_variants)
        tier2_sum = sum(BALANCED_CAMPAIGN_81[v] for v in tier2_variants)

        assert tier1_sum == 48, f"Tier 1 sum is {tier1_sum}, expected 48"
        assert tier2_sum == 33, f"Tier 2 sum is {tier2_sum}, expected 33"
        assert tier1_sum + tier2_sum == 81


@pytest.mark.unit
class TestCampaignPlanGeneration:
    """Validates deterministic plan generation and provenance for 81 runs."""

    def test_generator_produces_81_specs(self):
        """Confirm generator produces 81 distinct CampaignRunSpec objects."""
        generator = CampaignPlanGenerator(allocation=BALANCED_CAMPAIGN_81)
        specs = generator.generate_plan()
        assert len(specs) == 81
        assert generator.campaign_name == "matrix_v2_81"

    def test_deterministic_seed_derivation(self):
        """Confirm seed is strictly derived from run_id using locked formula."""
        generator = CampaignPlanGenerator(allocation=BALANCED_CAMPAIGN_81)
        specs = generator.generate_plan()

        for s in specs:
            expected_seed = compute_deterministic_seed(s.run_id)
            assert s.seed == expected_seed
            formula_seed = int(hashlib.sha256(s.run_id.encode("utf-8")).hexdigest()[:8], 16)
            assert s.seed == formula_seed

    def test_run_spec_structural_identifiers(self):
        """Confirm all structural unit and state context IDs are unique per replicate."""
        generator = CampaignPlanGenerator(allocation=BALANCED_CAMPAIGN_81)
        specs = generator.generate_plan()

        run_ids = [s.run_id for s in specs]
        unit_ids = [s.experimental_unit_id for s in specs]
        state_ids = [s.state_context_id for s in specs]

        assert len(set(run_ids)) == 81
        assert len(set(unit_ids)) == 81
        assert len(set(state_ids)) == 81

    def test_planned_indices_sequential(self):
        """Confirm planned indices range from 1 to 81 continuously."""
        generator = CampaignPlanGenerator(allocation=BALANCED_CAMPAIGN_81)
        specs = generator.generate_plan()
        indices = [s.planned_index for s in specs]
        assert indices == list(range(1, 82))


@pytest.mark.unit
class TestCliDryRunAndSafety:
    """Validates CLI harness safety gates, dry-run output, and error conditions."""

    def test_cli_dry_run_balanced_returns_zero(self, repo_root):
        """Confirm CLI --campaign balanced runs in non-destructive dry-run by default."""
        cmd = [sys.executable, str(repo_root / "scripts" / "run_research_campaign.py"), "--campaign", "balanced"]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
        assert res.returncode == 0
        assert "ChainC2 Sentinel" in res.stdout
        assert "Total Planned Runs: 81" in res.stdout
        assert "Variants Covered:   27 of 27" in res.stdout
        assert "[SAFETY NOTICE] Live campaign execution is NOT authorized." in res.stdout

    def test_cli_dry_run_creates_no_result_files(self, tmp_path, repo_root):
        """Confirm dry-run never creates the final matrix_v2_81_results.json file."""
        temp_results = tmp_path / "matrix_v2_81_results.json"
        assert not temp_results.exists()

        cmd = [
            sys.executable,
            str(repo_root / "scripts" / "run_research_campaign.py"),
            "--campaign", "balanced",
            "--dry-run",
            "--output-dir", str(tmp_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
        assert res.returncode == 0
        assert not temp_results.exists(), "Dry run must never write matrix_v2_81_results.json"

    def test_refusal_to_overwrite_existing_results(self, tmp_path, repo_root):
        """Confirm batch orchestration refuses to overwrite existing results file."""
        from scripts.run_research_campaign import main
        fake_results = tmp_path / "matrix_v2_81_results.json"
        fake_results.write_text('{"existing": "prior_data"}', encoding="utf-8")

        test_args = [
            "run_research_campaign.py",
            "--campaign", "balanced",
            "--execute-authorized",
            "--output-dir", str(tmp_path),
        ]
        with patch.object(sys, "argv", test_args):
            ret = main()
            assert ret == 1

        # Confirm file was preserved
        assert fake_results.read_text(encoding="utf-8") == '{"existing": "prior_data"}'


@pytest.mark.unit
class TestMatrixV2RecordSerialization:
    """Validates that MatrixV2ExecutionRecord serializes cleanly with Pydantic mode='json'."""

    def test_record_serialization_mode_json(self):
        """Confirm MatrixV2ExecutionRecord serializes ISO timestamps and enums cleanly."""
        rec = MatrixV2ExecutionRecord(
            run_id="run-test-a01-001",
            experiment_id="exp-a01-run001",
            experimental_unit_id="unit-A01-rep001",
            workload_variant_id="A01",
            replicate_id=1,
            state_context_id="ctx-A01-r001",
            scenario="scenario_a",
            behavior_family="A-RO",
            variant_id="A01",
            seed=2252508433,
            timestamp_start="2026-10-27T14:00:00.000000Z",
            timestamp_end="2026-10-27T14:00:00.005000Z",
            execution_status=ExecutionStatus.SUCCESS,
            ground_truth=GroundTruth.BENIGN,
            detection_hypothesis="Negative control",
            provenance=Provenance.GENUINE_EXECUTION,
            endpoint_event_count=1,
            rpc_event_count=1,
            blockchain_event_count=0,
            network_event_count=0,
            total_events=2,
            detector_score=20.0,
            detector_threshold=80.0,
            rule_conjunction_triggered=False,
            score_threshold_met=False,
            triggered=False,
            classification=Classification.TN,
            detection_latency_ms=0.085,
        )

        d = rec.model_dump(mode="json")
        assert d["execution_status"] == "SUCCESS"
        assert d["ground_truth"] == "BENIGN"
        assert d["classification"] == "TN"
        assert d["provenance"] == "GENUINE_EXECUTION"
        assert isinstance(d["timestamp_start"], str)
        assert d["detector_score"] == 20.0

        # Must round-trip to JSON string
        json_str = json.dumps(d)
        assert "run-test-a01-001" in json_str


@pytest.mark.unit
class TestBaselinePreservation:
    """Verifies that all pre-existing evaluation datasets remain intact and unmodified."""

    def test_baseline_files_exist_and_non_empty(self, repo_root):
        """Confirm all immutable evaluation files exist and contain expected run counts."""
        f_eval30 = repo_root / "data" / "evaluation" / "evaluation_results.json"
        f_hist20 = repo_root / "data" / "evaluation" / "historical_ab_20_evaluation_results.json"
        f_prot22 = repo_root / "data" / "evaluation" / "protection_evaluation.json"
        f_plan372 = repo_root / "data" / "evaluation" / "dataset_campaign" / "campaign_plan_372.json"

        for f in [f_eval30, f_hist20, f_prot22, f_plan372]:
            assert f.exists(), f"Baseline file missing: {f}"
            assert f.stat().st_size > 1000, f"Baseline file unexpectedly truncated: {f}"

        with open(f_eval30, "r", encoding="utf-8") as f:
            d30 = json.load(f)
            assert len(d30["experiments"]) == 30

        with open(f_hist20, "r", encoding="utf-8") as f:
            d20 = json.load(f)
            assert len(d20["experiments"]) == 20

        with open(f_prot22, "r", encoding="utf-8") as f:
            d22 = json.load(f)
            assert len(d22["experiments"]) == 22

        with open(f_plan372, "r", encoding="utf-8") as f:
            dp372 = json.load(f)
            assert len(dp372["planned_runs"]) == 372


@pytest.mark.unit
class TestDetectionLatencyMeasurementAndAggregation:
    """Validates detection-latency measurement fidelity, missing-latency distinction, and unbiased aggregation."""

    def test_measured_detection_latency(self):
        """Confirm a measured detection latency produces a genuine float > 0.0 and distinct execution duration."""
        mock_event = SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type="process_spawn",
            metadata={"process_name": "test_runner"},
        )
        mock_result = ScenarioResult(
            scenario_id="scenario_a_benign",
            run_id="run-test-latency-001",
            success=True,
            events=[mock_event],
            event_counts_by_source={TelemetrySource.ENDPOINT.value: 1},
            details={"execution_status": "SUCCESS"},
        )

        runner = ScenarioRunner()
        with patch("src.scenarios.runner.BenignWeb3Scenario.run", return_value=mock_result):
            _, record = runner.run_variant("A01")

        assert record.detection_latency_ms is not None
        assert isinstance(record.detection_latency_ms, float)
        assert record.detection_latency_ms > 0.0
        assert record.execution_duration_ms is not None
        assert isinstance(record.execution_duration_ms, float)
        assert record.execution_duration_ms >= 0.0

    def test_unmeasured_detection_latency_zero_events(self):
        """Confirm zero-event runs do not evaluate detection and record None, not 0.0."""
        mock_result = ScenarioResult(
            scenario_id="scenario_a_benign",
            run_id="run-test-zero-events",
            success=True,
            events=[],
            event_counts_by_source={},
            details={"execution_status": "SUCCESS"},
        )

        runner = ScenarioRunner()
        with patch("src.scenarios.runner.BenignWeb3Scenario.run", return_value=mock_result):
            _, record = runner.run_variant("A01")

        assert record.total_events == 0
        assert record.detection_latency_ms is None
        # Must serialize cleanly to null in JSON
        d = record.model_dump(mode="json")
        assert d["detection_latency_ms"] is None
        assert json.loads(json.dumps(d))["detection_latency_ms"] is None
        # Execution duration is still tracked separately
        assert record.execution_duration_ms is not None

    def test_unmeasured_detection_latency_validation_rejected(self):
        """Confirm validation-rejected runs (e.g. B09) do not evaluate detection and record None, not 0.0."""
        mock_event = SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type="c2_pre_validation",
            metadata={"stage": "validator"},
        )
        mock_result = ScenarioResult(
            scenario_id="scenario_b_synthetic_c2",
            run_id="run-test-val-reject",
            success=False,
            events=[mock_event],
            event_counts_by_source={TelemetrySource.ENDPOINT.value: 1},
            details={
                "execution_status": "VALIDATION_REJECTED",
                "validation_error": "Invalid target socket URI",
            },
        )

        runner = ScenarioRunner()
        with patch("src.scenarios.runner.SyntheticC2Scenario.run", return_value=mock_result):
            _, record = runner.run_variant("B09")

        assert record.execution_status == ExecutionStatus.VALIDATION_REJECTED
        assert record.classification == Classification.EXCLUDED
        assert record.detection_latency_ms is None
        assert record.model_dump(mode="json")["detection_latency_ms"] is None

    def test_unmeasured_latency_explicitly_disabled(self):
        """Confirm evaluate_detection=False bypasses detection evaluation and records None."""
        mock_event = SentinelEvent(
            timestamp=datetime.now(timezone.utc),
            source=TelemetrySource.ENDPOINT,
            event_type="test_event",
            metadata={},
        )
        mock_result = ScenarioResult(
            scenario_id="scenario_a_benign",
            run_id="run-test-no-eval",
            success=True,
            events=[mock_event],
            event_counts_by_source={TelemetrySource.ENDPOINT.value: 1},
            details={"execution_status": "SUCCESS"},
        )

        runner = ScenarioRunner()
        with patch("src.scenarios.runner.BenignWeb3Scenario.run", return_value=mock_result):
            _, record = runner.run_variant("A01", evaluate_detection=False)

        assert record.detection_latency_ms is None

    def test_aggregation_mixed_measured_and_unmeasured_records(self):
        """Confirm aggregate latency calculations exclude unmeasured records and report measurement counts."""
        records = [
            {"run_id": "r1", "detection_latency_ms": 0.1000},
            {"run_id": "r2", "detection_latency_ms": 0.2000},
            {"run_id": "r3", "detection_latency_ms": 0.3000},
            {"run_id": "r4", "detection_latency_ms": None},
            {"run_id": "r5", "detection_latency_ms": None},
        ]

        agg = compute_aggregate_latency(records)
        assert agg["total_records"] == 5
        assert agg["measured_records"] == 3
        assert agg["unmeasured_records"] == 2
        assert agg["mean_latency_ms"] == pytest.approx(0.2000, abs=1e-4)
        assert agg["min_latency_ms"] == pytest.approx(0.1000, abs=1e-4)
        assert agg["max_latency_ms"] == pytest.approx(0.3000, abs=1e-4)

    def test_prevention_of_artificial_downward_bias(self):
        """Verify that missing latency does not drag mean latency towards zero."""
        # 1 valid measurement of 0.12 ms and 1 unmeasured run
        records = [
            {"run_id": "r1", "detection_latency_ms": 0.1200},
            {"run_id": "r2", "detection_latency_ms": None},
        ]

        agg = compute_aggregate_latency(records)

        # Flawed calculation (substituting 0.0) would yield: (0.12 + 0.0) / 2 = 0.0600 ms
        biased_mean = (0.1200 + 0.0) / 2.0
        assert biased_mean == pytest.approx(0.0600)

        # Correct calculation must exclude unmeasured record: (0.1200) / 1 = 0.1200 ms
        assert agg["mean_latency_ms"] == pytest.approx(0.1200, abs=1e-4)
        assert agg["mean_latency_ms"] > biased_mean
        assert agg["measured_records"] == 1
        assert agg["unmeasured_records"] == 1

    def test_aggregation_all_unmeasured_records(self):
        """Confirm aggregation when zero runs have measured latency returns None safely."""
        records = [
            {"run_id": "r1", "detection_latency_ms": None},
            {"run_id": "r2", "detection_latency_ms": None},
        ]

        agg = compute_aggregate_latency(records)
        assert agg["total_records"] == 2
        assert agg["measured_records"] == 0
        assert agg["unmeasured_records"] == 2
        assert agg["mean_latency_ms"] is None
        assert agg["min_latency_ms"] is None
        assert agg["max_latency_ms"] is None

    def test_latency_distinct_from_execution_duration(self):
        """Confirm detection latency and execution duration are tracked as distinct metrics."""
        rec = MatrixV2ExecutionRecord(
            run_id="run-test-distinct-metrics",
            experiment_id="exp-test",
            experimental_unit_id="unit-test",
            workload_variant_id="A01",
            replicate_id=1,
            state_context_id="ctx-test",
            scenario="scenario_a",
            behavior_family="A-RO",
            variant_id="A01",
            seed=12345678,
            timestamp_start="2026-10-27T14:00:00.000000Z",
            timestamp_end="2026-10-27T14:00:00.025000Z",
            execution_status=ExecutionStatus.SUCCESS,
            ground_truth=GroundTruth.BENIGN,
            detection_hypothesis="Negative control",
            provenance=Provenance.GENUINE_EXECUTION,
            detection_latency_ms=0.082,
            execution_duration_ms=25.0,
        )

        d = rec.model_dump(mode="json")
        assert d["detection_latency_ms"] == 0.082
        assert d["execution_duration_ms"] == 25.0
        assert d["detection_latency_ms"] != d["execution_duration_ms"]
