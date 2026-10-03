# ChainC2 Sentinel — Experimental Matrix v2 Dataset Campaign Directory

This directory is the dedicated storage location for the ChainC2 Sentinel Matrix v2 research campaign dataset.

## Target Campaign Structure:
- `execution_records.jsonl`: Complete execution-by-execution record stream implementing `MatrixV2ExecutionRecord`.
- `campaign_summary.json`: Aggregate metrics, confusion matrix, coverage analysis, and latency breakdown.
- `campaign_plan.json`: Deterministic schedule of planned experimental units across 27 variants (372 runs).

## Integrity Guarantees:
- Completely isolated from legacy baseline artifacts:
  - `data/evaluation/evaluation_results.json` (UNTOUCHED)
  - `data/evaluation/historical_ab_20_evaluation_results.json` (UNTOUCHED)
  - `data/evaluation/protection_evaluation.json` (UNTOUCHED)
  - `results/final/research_summary.json` (UNTOUCHED)
- All records preserve:
  - Factual provenance (`GENUINE_EXECUTION`, `SIMULATED_FIXTURE`, `RECONSTRUCTED_FALLBACK`, `ILLUSTRATIVE`)
  - Ground truth decoupled from detector prediction
  - Experimental unit, replicate, and state context IDs
  - Frozen deterministic seed: `int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16)`
