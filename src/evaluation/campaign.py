# ChainC2 Sentinel — Experimental Matrix v2 Campaign Generator & Orchestrator
"""Headless campaign planning and orchestration infrastructure for Matrix v2.

Formal Campaign Allocation: 372 Total Planned Runs
- Scenario A (Benign Web3): 9 variants x 12 replicates = 108 runs
- Scenario B (Synthetic C2): 10 variants (7x18 + 3x12) = 162 runs
- Scenario C (Legitimate DApp): 8 variants (6x15 + 2x6) = 102 runs
Total = 108 + 162 + 102 = 372 runs

Safety & Integrity:
- Ground truth remains strictly decoupled from detector output.
- Deterministic PRNG seed formula frozen for every run:
    seed = int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16)
- Experimental units distinctly tracked (experimental_unit_id, replicate_id, state_context_id).
- Dedicated output directory: data/evaluation/dataset_campaign/
- Existing baseline artifacts are NEVER overwritten.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.models.matrix_v2 import (
    Classification,
    ExecutionStatus,
    GroundTruth,
    MatrixV2ExecutionRecord,
    Provenance,
    VARIANT_REGISTRY,
    compute_deterministic_seed,
)

logger = logging.getLogger("chainc2_sentinel.evaluation.campaign")

# Formal Matrix v2 372-Run Campaign Allocation
RECOMMENDED_CAMPAIGN_372: dict[str, int] = {
    # Scenario A: 9 variants x 12 = 108
    "A01": 12,
    "A02": 12,
    "A03": 12,
    "A04": 12,
    "A05": 12,
    "A06": 12,
    "A07": 12,
    "A08a": 12,
    "A08b": 12,
    # Scenario B: 7 x 18 + 3 x 12 = 162
    "B01": 18,
    "B02": 18,
    "B03": 18,
    "B04": 18,
    "B05": 18,
    "B06": 18,
    "B07a": 12,
    "B07b": 12,
    "B08": 18,
    "B09": 12,
    # Scenario C: 6 x 15 + 2 x 6 = 102
    "C01": 15,
    "C02": 15,
    "C03": 15,
    "C04": 15,
    "C05": 15,
    "C06": 15,
    "C07": 6,
    "C08": 6,
}

# Fast Minimal Validation Allocation: 116 Runs
MINIMAL_CAMPAIGN_116: dict[str, int] = {
    "A01": 4, "A02": 4, "A03": 4, "A04": 4, "A05": 4, "A06": 4, "A07": 4, "A08a": 4, "A08b": 4,
    "B01": 5, "B02": 5, "B03": 5, "B04": 5, "B05": 5, "B06": 5, "B07a": 4, "B07b": 4, "B08": 5, "B09": 4,
    "C01": 4, "C02": 4, "C03": 4, "C04": 4, "C05": 4, "C06": 4, "C07": 4, "C08": 4,
}


@dataclass
class CampaignRunSpec:
    """Pre-execution specification for a single planned research run."""

    planned_index: int
    workload_variant_id: str
    replicate_id: int
    experimental_unit_id: str
    state_context_id: str
    run_id: str
    seed: int
    scenario: str
    behavior_family: str
    ground_truth: str
    detection_hypothesis: str
    provenance: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CampaignPlanGenerator:
    """Generates deterministic execution plans for Matrix v2 campaigns without live execution."""

    def __init__(self, allocation: Optional[dict[str, int]] = None, campaign_name: str = "matrix_v2_372") -> None:
        self.allocation = allocation or RECOMMENDED_CAMPAIGN_372
        self.campaign_name = campaign_name

    def generate_plan(self) -> list[CampaignRunSpec]:
        """Generate ordered list of planned execution specs."""
        specs: list[CampaignRunSpec] = []
        global_idx = 1

        for variant_id, replicate_count in self.allocation.items():
            if variant_id not in VARIANT_REGISTRY:
                raise ValueError(f"Unknown variant in allocation: {variant_id}")

            meta = VARIANT_REGISTRY[variant_id]

            for rep in range(1, replicate_count + 1):
                run_id = f"run-mat2-{variant_id.lower()}-{rep:03d}"
                seed = compute_deterministic_seed(run_id)
                unit_id = f"unit-{variant_id}-rep{rep:03d}"
                state_id = f"ctx-{variant_id}-r{rep:03d}"

                params = self._derive_variant_params(variant_id, rep)

                spec = CampaignRunSpec(
                    planned_index=global_idx,
                    workload_variant_id=variant_id,
                    replicate_id=rep,
                    experimental_unit_id=unit_id,
                    state_context_id=state_id,
                    run_id=run_id,
                    seed=seed,
                    scenario=meta["scenario"],
                    behavior_family=meta["behavior_family"],
                    ground_truth=meta["ground_truth"].value,
                    detection_hypothesis=meta["detection_hypothesis"],
                    provenance=meta["provenance"].value,
                    parameters=params,
                )
                specs.append(spec)
                global_idx += 1

        return specs

    def _derive_variant_params(self, variant_id: str, replicate: int) -> dict[str, Any]:
        """Provide controlled parameter sweeps across replicates."""
        if variant_id == "A07":
            # Vary burst count 5..10 and delay 1..8ms
            burst_n = 5 + (replicate % 6)
            return {"burst_count": burst_n, "burst_delay_ms": 2.0}
        elif variant_id == "B02":
            # Vary cadence across 500ms, 1000ms, 2000ms
            cadences = [500, 1000, 2000]
            return {"cadence_ms": cadences[replicate % len(cadences)]}
        elif variant_id == "B03":
            # Vary jitter bounds
            jitters = [(50, 200), (100, 400), (200, 800)]
            min_j, max_j = jitters[replicate % len(jitters)]
            return {"jitter_min_ms": min_j, "jitter_max_ms": max_j}
        elif variant_id == "C03":
            # Vary batch size 2..5
            return {"batch_size": 2 + (replicate % 4)}
        elif variant_id == "C04":
            # Vary read counts 3..6
            return {"read_count": 3 + (replicate % 4)}
        elif variant_id == "B07a":
            # Distinct closed ports
            return {"closed_port": 59990 + (replicate % 5)}
        elif variant_id == "B07b":
            # Controlled delay >5s
            return {"delay_seconds": 5.2}
        return {}

    def export_plan_file(self, output_path: str | Path) -> Path:
        """Export the campaign plan to JSON without executing anything."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        specs = self.generate_plan()

        plan_doc = {
            "campaign_name": self.campaign_name,
            "total_planned_runs": len(specs),
            "variant_count": len(self.allocation),
            "allocation": self.allocation,
            "seed_formula": "int(hashlib.sha256(run_id.encode('utf-8')).hexdigest()[:8], 16)",
            "planned_runs": [s.to_dict() for s in specs],
        }

        with open(out, "w", encoding="utf-8") as f:
            json.dump(plan_doc, f, indent=2)

        logger.info("Exported campaign plan (%d runs) to %s", len(specs), out)
        return out
