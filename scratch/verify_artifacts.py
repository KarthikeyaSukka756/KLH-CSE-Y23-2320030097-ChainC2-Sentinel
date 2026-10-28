import hashlib
from pathlib import Path

authoritative = {
    "data/evaluation/dataset_campaign/matrix_v2_81_results.json": (
        "15fa3d7e49a1cf5f8c1476a2ff5141849a46fb31eb021a3e2159a2d8998fd470",
        114232,
    ),
    "data/evaluation/dataset_campaign/telemetry_events_balanced.jsonl": (
        "519c1e988e221d889ed499badb8bb704a69dd2c17c96dc42881ddafbbce35aa0",
        267774,
    ),
    "data/evaluation/dataset_campaign/campaign_plan_372.json": (
        "0c483d093ee32c4122ae4c47fdc6fd62451b78991ec45bd25077f517f0c23bc7",
        215305,
    ),
    "results/final/research_summary.json": (
        "85b1d136d61c7657c518eb2872eedf50f245e968d9997178ca04cdcce7930bcc",
        10472,
    ),
    "data/evaluation/dataset_campaign_corrected/matrix_v2_81_results.json": (
        "e696a9b669339efce57d5692fcc56193a0a4832f699501fe803dddb7ecd60b80",
        115043,
    ),
    "data/evaluation/dataset_campaign_corrected/telemetry_events_balanced.jsonl": (
        "400157379861087e2306631036b5511c3c55899812f186fc882103215a9bb652",
        442165,
    ),
    "data/evaluation/dataset_campaign_corrected/campaign_plan_81.json": (
        "17f7d40e4b65a1131c67218d4b84983a5c2e44ca8a8a7f0b3da0a6a5d2e22b47",
        47203,
    ),
}

all_match = True
for rel_path, (exp_hash, exp_size) in authoritative.items():
    p = Path(rel_path)
    if not p.exists():
        print(f"MISSING: {rel_path}")
        all_match = False
        continue
    data = p.read_bytes()
    act_size = len(data)
    act_hash = hashlib.sha256(data).hexdigest()
    size_ok = act_size == exp_size
    hash_ok = act_hash == exp_hash
    if not (size_ok and hash_ok):
        all_match = False
    print(f"File: {rel_path}")
    print(f"  Actual Size:   {act_size} bytes (Expected: {exp_size}) -> {'MATCH' if size_ok else 'MISMATCH'}")
    print(f"  Actual SHA256: {act_hash}")
    print(f"  Exp SHA256:    {exp_hash} -> {'MATCH' if hash_ok else 'MISMATCH'}")
    print(f"  Status:        {'VERIFIED' if (size_ok and hash_ok) else 'FAILED'}\n")

print(f"SUMMARY: {'ALL 7 ARTIFACTS VERIFIED EXACT MATCH' if all_match else 'INTEGRITY MISMATCH DETECTED'}")
