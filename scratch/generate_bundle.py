import hashlib
from pathlib import Path

# Files to bundle
bundle_files = [
    ("src/scenarios/runner.py", "python"),
    ("src/blockchain/rpc_client.py", "python"),
    ("src/blockchain/deployment.py", "python"),
    ("src/scenarios/definitions/c2_scenario.py", "python"),
    ("src/scenarios/base.py", "python"),
    ("src/blockchain/scripts/deploy.js", "javascript"),
    ("src/blockchain/test/deployment_safeguards.test.js", "javascript"),
    ("tests/test_sepolia_configuration.py", "python"),
    ("tests/test_real_rpc_execution.py", "python"),
]

output_bundle = Path("scratch/research_ready_source_bundle.md")

with open(output_bundle, "w", encoding="utf-8") as out:
    out.write("# ChainC2 Sentinel — Complete Changed Source & Test Bundle\n\n")
    out.write("This bundle contains the complete, unabridged source files and test suites reflecting all implemented fixes:\n")
    out.write("1. Exact RPC client validation, identity propagation, and address synchronization in ScenarioRunner.\n")
    out.write("2. Removal of silent local chain ID fallback and unknown-network transaction bypass in LocalRpcClient.\n")
    out.write("3. Bytecode verification support via eth_getCode in LocalRpcClient and deployment.py.\n")
    out.write("4. Safe atomic deployment registry persistence and receipt verification in deploy.js.\n")
    out.write("5. Data provenance enforcement in Scenario B preventing synthetic fallback upon failed reads/writes.\n\n")
    out.write("---\n\n")

    for rel_path, lang in bundle_files:
        p = Path(rel_path)
        if not p.exists():
            out.write(f"## File: `{rel_path}` (NOT FOUND)\n\n")
            continue
        content = p.read_text(encoding="utf-8")
        out.write(f"## File: `{rel_path}`\n\n")
        out.write(f"```{lang}\n")
        out.write(content)
        if not content.endswith("\n"):
            out.write("\n")
        out.write("```\n\n---\n\n")

print(f"Generated source bundle: {output_bundle} ({len(output_bundle.read_bytes())} bytes)")
