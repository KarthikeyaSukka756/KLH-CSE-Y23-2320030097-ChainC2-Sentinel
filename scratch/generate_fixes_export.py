import os
from pathlib import Path

files_to_export = [
    ("src/scenarios/runner.py", "python"),
    ("src/blockchain/rpc_client.py", "python"),
    ("src/blockchain/deployment.py", "python"),
    ("tests/test_sepolia_configuration.py", "python"),
    ("tests/test_real_rpc_execution.py", "python"),
    ("src/scenarios/definitions/c2_scenario.py", "python"),
    ("src/scenarios/base.py", "python"),
    ("src/blockchain/scripts/deploy.js", "javascript"),
    ("src/blockchain/test/deployment_safeguards.test.js", "javascript"),
]

output_path = Path("scratch/stage_c2_fixes_export.md")

with open(output_path, "w", encoding="utf-8") as out:
    out.write("# ChainC2 Sentinel — Complete Changed Source & Test Export\n\n")
    out.write("## Summary of Implemented Fixes\n\n")
    out.write("1. **Fix 1: ScenarioRunner Address & Alignment-Cache Correctness**\n")
    out.write("   - Added `_compute_alignment_cache_key()` incorporating client instance identity, RPC URL, client network, expected chain ID, runner network, deployment registry path, and registry file `mtime_ns`.\n")
    out.write("   - Synchronized `self.deployed_addresses = addresses` upon successful validation.\n")
    out.write("   - Ensured all scenario entry points (`run_benign`, `run_legitimate_dapp`, `run_synthetic_c2`, `run_variant`, `run_all`) use the addresses returned by `validate_live_rpc_alignment()`.\n")
    out.write("   - Preserved `self.rpc_client` across iterations so runner does not recreate ephemeral clients.\n")
    out.write("   - Invalidate cache entries if validation fails or file mtime changes.\n")
    out.write("   - Preserved `force=True` behavior to ensure forced revalidation updates deployed addresses.\n\n")
    out.write("2. **Fix 2: Removed Local Chain-ID Fallback That Masked RPC Failure**\n")
    out.write("   - Removed exception suppression in `LocalRpcClient.get_chain_id()` that returned `'31337'` when offline.\n")
    out.write("   - Offline RPC connection errors, timeouts, or invalid responses now raise immediately.\n")
    out.write("   - `verify_rpc_and_registry_alignment()` rejects unavailable nodes and fails closed.\n\n")
    out.write("---\n\n")

    for rel_path, lang in files_to_export:
        p = Path(rel_path)
        if not p.exists():
            out.write(f"## {rel_path} (MISSING)\n\n")
            continue
        content = p.read_text(encoding="utf-8")
        out.write(f"## File: `{rel_path}`\n\n")
        out.write(f"```{lang}\n")
        out.write(content)
        if not content.endswith("\n"):
            out.write("\n")
        out.write("```\n\n---\n\n")

print(f"Exported {len(files_to_export)} files to {output_path}")
