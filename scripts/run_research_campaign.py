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
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.campaign import (
    BALANCED_CAMPAIGN_81,
    MINIMAL_CAMPAIGN_116,
    RECOMMENDED_CAMPAIGN_372,
    CampaignPlanGenerator,
)
from src.models.matrix_v2 import (
    VARIANT_REGISTRY,
    compute_aggregate_latency,
    compute_deterministic_seed,
)
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
        choices=["recommended", "minimal", "balanced"],
        default="recommended",
        help="Campaign tier: 'recommended' (372 runs across 27 variants), 'minimal' (116 runs), or 'balanced' (81 runs across 27 variants x 3 replicates)",
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

    if args.campaign == "balanced":
        allocation = BALANCED_CAMPAIGN_81
        campaign_name = "matrix_v2_81"
    elif args.campaign == "minimal":
        allocation = MINIMAL_CAMPAIGN_116
        campaign_name = "matrix_v2_116"
    else:
        allocation = RECOMMENDED_CAMPAIGN_372
        campaign_name = "matrix_v2_372"

    generator = CampaignPlanGenerator(allocation=allocation, campaign_name=campaign_name)

    # 1. Plan generation
    if args.generate_plan:
        plan_suffix = "81" if args.campaign == "balanced" else ("116" if args.campaign == "minimal" else "372")
        plan_file = out_dir / f"campaign_plan_{plan_suffix}.json"
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

    # 3. Campaign execution gate (dry-run default)
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

    # 4. Authorized Batch Campaign Execution
    results_filename = "matrix_v2_81_results.json" if args.campaign == "balanced" else f"{campaign_name}_results.json"
    results_file = out_dir / results_filename

    # Safety check: refuse to overwrite existing results file
    if results_file.exists():
        print(f"Error: Target results file '{results_file}' already exists. Refusing to overwrite existing research results.", file=sys.stderr)
        return 1

    specs = generator.generate_plan()
    telemetry_log = out_dir / f"telemetry_events_{args.campaign}.jsonl"
    runner = ScenarioRunner(output_path=str(telemetry_log))

    print(f"Starting batch execution for {campaign_name} ({len(specs)} planned runs)...")
    records: list[dict[str, Any]] = []
    completed_runs = 0

    for idx, spec in enumerate(specs, start=1):
        print(f"[{idx}/{len(specs)}] Executing {spec.workload_variant_id} (replicate {spec.replicate_id}, run_id: {spec.run_id})...")
        try:
            scenario_result, record = runner.run_variant(
                variant_id=spec.workload_variant_id,
                parameters=spec.parameters,
                run_id=spec.run_id,
                experimental_unit_id=spec.experimental_unit_id,
                replicate_id=spec.replicate_id,
                state_context_id=spec.state_context_id,
                seed=spec.seed,
            )
            records.append(record.model_dump(mode="json"))
            completed_runs += 1
        except Exception as e:
            logger.error("Campaign execution halted due to unhandled exception on %s (run_id: %s): %s", spec.workload_variant_id, spec.run_id, e)
            print(
                f"\nCRITICAL: Batch campaign aborted after {completed_runs}/{len(specs)} runs. "
                f"Run {spec.run_id} failed with unhandled exception: {e}\n"
                f"Partial execution has NOT been finalized to '{results_file.name}'.",
                file=sys.stderr,
            )
            return 1

    if completed_runs != len(specs):
        print(f"Error: Expected {len(specs)} runs, but only completed {completed_runs}. Aborting final export.", file=sys.stderr)
        return 1

    latency_summary = compute_aggregate_latency(records)
    campaign_doc = {
        "campaign_name": campaign_name,
        "total_planned_runs": len(specs),
        "completed_runs": completed_runs,
        "variant_count": len(allocation),
        "allocation": allocation,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETED",
        "detection_latency_summary": latency_summary,
        "records": records,
    }

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(campaign_doc, f, indent=2)

    print(f"Campaign {campaign_name} successfully executed. {completed_runs}/{len(specs)} runs recorded.")
    if latency_summary["measured_records"] > 0:
        print(f"Detection latency: mean={latency_summary['mean_latency_ms']}ms (n={latency_summary['measured_records']}, unmeasured={latency_summary['unmeasured_records']})")
    print(f"Results exported to: {results_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
