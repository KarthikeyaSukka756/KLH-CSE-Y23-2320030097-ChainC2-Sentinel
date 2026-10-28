import os
from pathlib import Path

files_to_export = [
    ("src/blockchain/rpc_client.py", "python"),
    ("src/scenarios/runner.py", "python"),
    ("src/blockchain/deployment.py", "python"),
    ("src/scenarios/definitions/c2_scenario.py", "python"),
    ("src/scenarios/base.py", "python"),
    ("src/blockchain/scripts/deploy.js", "javascript"),
    ("src/blockchain/test/deployment_safeguards.test.js", "javascript"),
    ("tests/test_sepolia_configuration.py", "python"),
    ("tests/test_real_rpc_execution.py", "python"),
]

output_path = Path("scratch/stage_c2_corrections_export.md")

with open(output_path, "w", encoding="utf-8") as out:
    out.write("# ChainC2 Sentinel — Complete Updated Source and Test Export\n\n")
    out.write("This document provides the full, unabridged source code for all updated files addressing:\n")
    out.write("1. Production live RPC alignment enforcement in ScenarioRunner across all entry points.\n")
    out.write("2. Safe live RPC alignment boundary caching avoiding redundant RPC queries within a single execution.\n")
    out.write("3. Removal of the unknown-network transaction bypass in LocalRpcClient.eth_send_transaction().\n")
    out.write("4. Offline test fixtures verifying that mismatched chain IDs block execution and unknown networks do not perform HTTP requests.\n\n")
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
