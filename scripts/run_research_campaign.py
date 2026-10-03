#!/usr/bin/env python3
# ChainC2 Sentinel — Experimental Matrix v2 Headless Campaign CLI
"""CLI harness for Matrix v2 research campaign generation, validation, and single-variant runs.

SAFETY POLICY:
- Default mode is --dry-run.
- Batch campaign execution requires explicit authorization flag: --execute-authorized.
- All network targets are restricted strictly to loopback (127.0.0.1 / localhost).
- All outputs write to data/evaluation/dataset_campaign/ (NEVER overwriting existing baselines).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.campaign import (
    MINIMAL_CAMPAIGN_116,
    RECOMMENDED_CAMPAIGN_372,
    CampaignPlanGenerator,
)
from src.models.matrix_v2 import VARIANT_REGISTRY, compute_deterministic_seed
from src.scenarios.runner import ScenarioRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chainc2_sentinel.campaign_cli")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ChainC2 Sentinel — Matrix v2 Research Campaign Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--campaign",
        choices=["recommended", "minimal"],
        default="recommended",
        help="Campaign tier: 'recommended' (372 runs across 27 variants) or 'minimal' (116 runs)",
    )
    parser.add_argument(
        "--generate-plan",
        action="store_true",
        help="Generate and export the formal campaign plan JSON to data/evaluation/dataset_campaign/ without executing",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default=None,
        help="Execute a single explicitly selected Matrix variant (e.g. A01, B04, C06)",
    )
    parser.add_argument(
        "--params",
        type=str,
        default=None,
        help="JSON string of parameter overrides for single variant execution",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate execution schedule without making live RPC or network calls (default: True)",
    )
    parser.add_argument(
        "--execute-authorized",
        action="store_true",
        default=False,
        help="Explicit safety authorization required to execute live campaign runs",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/evaluation/dataset_campaign",
        help="Dedicated directory for campaign artifacts (default: data/evaluation/dataset_campaign)",
    )

    args = parser.parse_args()

    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    allocation = RECOMMENDED_CAMPAIGN_372 if args.campaign == "recommended" else MINIMAL_CAMPAIGN_116
    generator = CampaignPlanGenerator(allocation=allocation, campaign_name=f"matrix_v2_{len(allocation)}")

    # 1. Plan generation
    if args.generate_plan:
        plan_file = out_dir / f"campaign_plan_{'372' if args.campaign == 'recommended' else '116'}.json"
        generator.export_plan_file(plan_file)
        print(f"Generated formal campaign plan: {plan_file}")
        return 0

    # 2. Single variant execution
    if args.variant:
        variant_id = args.variant.strip()
        if variant_id not in VARIANT_REGISTRY:
            print(f"Error: Unknown variant ID '{variant_id}'. Registered variants: {list(VARIANT_REGISTRY.keys())}", file=sys.stderr)
            return 1

        parameters = json.loads(args.params) if args.params else {}
        if not args.execute_authorized:
            print(f"[DRY-RUN] Variant: {variant_id}")
            print(f"  Spec: {VARIANT_REGISTRY[variant_id]['name']}")
            print(f"  Ground Truth: {VARIANT_REGISTRY[variant_id]['ground_truth'].value}")
            print(f"  Hypothesis: {VARIANT_REGISTRY[variant_id]['detection_hypothesis']}")
            print(f"  Parameters: {parameters}")
            print("  Status: DRY-RUN ONLY. Pass --execute-authorized to perform live execution.")
            return 0

        runner = ScenarioRunner(output_path=str(out_dir / "telemetry_events.jsonl"))
        scenario_result, record = runner.run_variant(
            variant_id=variant_id,
            parameters=parameters,
        )
        print(f"Executed variant {variant_id}: status={record.execution_status.value}, triggered={record.triggered}, classification={record.classification.value}")
        return 0

    # 3. Campaign execution gate
    if not args.execute_authorized:
        specs = generator.generate_plan()
        print("============================================================")
        print(f"ChainC2 Sentinel — Matrix v2 Campaign Plan ({args.campaign.upper()})")
        print("============================================================")
        print(f"Total Planned Runs: {len(specs)}")
        print(f"Variants Covered:   {len(allocation)} of 27")
        print(f"Dedicated Output:   {out_dir}")
        print("Seed Derivation:    int(hashlib.sha256(run_id.encode('utf-8')).hexdigest()[:8], 16)")
        print("------------------------------------------------------------")
        print("ALLOCATION BREAKDOWN:")
        for v_id, count in allocation.items():
            print(f"  - {v_id:4s}: {count:2d} replicates ({VARIANT_REGISTRY[v_id]['name']})")
        print("------------------------------------------------------------")
        print("[SAFETY NOTICE] Live campaign execution is NOT authorized.")
        print("Pass --execute-authorized and --no-dry-run to start execution.")
        print("============================================================")
        return 0

    print("Batch live execution requires full lab environment prerequisites (Hardhat node, RPC proxy, HTTP target).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
