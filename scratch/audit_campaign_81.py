# ChainC2 Sentinel — Read-Only Campaign Audit Script
import json
from collections import Counter, defaultdict
from pathlib import Path

RESULTS_FILE = Path("data/evaluation/dataset_campaign_corrected/matrix_v2_81_results.json")
PLAN_FILE = Path("data/evaluation/dataset_campaign_corrected/campaign_plan_81.json")
TELEMETRY_FILE = Path("data/evaluation/dataset_campaign_corrected/telemetry_events_balanced.jsonl")

with open(RESULTS_FILE, encoding="utf-8") as f:
    res = json.load(f)

with open(PLAN_FILE, encoding="utf-8") as f:
    plan = json.load(f)

events = []
with open(TELEMETRY_FILE, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            events.append(json.loads(line))

print("=== CHECK 1: PLAN vs RESULTS ALIGNMENT ===")
plan_runs = plan["planned_runs"]
res_records = res["records"]
print(f"Plan runs: {len(plan_runs)}, Results records: {len(res_records)}")
plan_ids = [r["run_id"] for r in plan_runs]
res_ids = [r["run_id"] for r in res_records]
print(f"Unique Run IDs: {len(set(res_ids))} / {len(res_records)}")
print(f"Sequence & ID identity: {plan_ids == res_ids}")
plan_v_counts = Counter(r["workload_variant_id"] for r in plan_runs)
res_v_counts = Counter(r["workload_variant_id"] for r in res_records)
print(f"Total unique variants: {len(res_v_counts)}")
print(f"All variants have exactly 3 replicates: {all(c == 3 for c in res_v_counts.values())}")
print(f"Variants set identical: {plan_v_counts == res_v_counts}")

print("\n=== CHECK 2: CLASSIFICATION & EXECUTION RECONCILIATION ===")
classes = Counter(r["classification"] for r in res_records)
statuses = Counter(r["execution_status"] for r in res_records)
print(f"Classifications: {dict(classes)}")
print(f"Execution Statuses: {dict(statuses)}")

events_by_run = defaultdict(list)
for e in events:
    rid = e["metadata"].get("run_id")
    if rid:
        events_by_run[rid].append(e)

print(f"Total runs with telemetry: {len(events_by_run)}")

# Breakdown by variant
for r in res_records:
    vid = r["workload_variant_id"]
    rid = r["run_id"]
    ev_list = events_by_run[rid]
    rec_event_count = r.get("total_events", len(r.get("event_ids", [])))

# Group variants by outcome
outcome_groups = defaultdict(list)
for r in res_records:
    key = (r["classification"], r["execution_status"])
    outcome_groups[key].append(r["workload_variant_id"])

for (c, s), vids in sorted(outcome_groups.items()):
    c_counts = Counter(vids)
    print(f"Classification={c:8s} Status={s:19s} Total={len(vids)} Variants={dict(c_counts)}")

print("\n=== CHECK 3: TELEMETRY PROVENANCE & RPC/BLOCKCHAIN BREAKDOWN ===")
total_events = len(events)
sources = Counter(e["source"] for e in events)
print(f"Total telemetry events: {total_events}")
print(f"Events by source: {dict(sources)}")

rpc_events = [e for e in events if e.get("rpc")]
rpc_methods = Counter(e["rpc"]["rpc_method"] for e in rpc_events)
print(f"Total RPC events: {len(rpc_events)}")
print(f"RPC methods: {dict(rpc_methods)}")

bc_events = [e for e in events if e.get("blockchain")]
print(f"Total blockchain events: {len(bc_events)}")
bc_tx_events = [e for e in bc_events if e["blockchain"].get("tx_hash")]
print(f"Mined transaction events with tx_hash: {len(bc_tx_events)}")
bc_call_events = [e for e in bc_events if not e["blockchain"].get("tx_hash")]
print(f"Read/call blockchain events: {len(bc_call_events)}")

# Check blocks and tx_hashes
tx_hashes = [e["blockchain"]["tx_hash"] for e in bc_tx_events]
block_numbers = [e["blockchain"]["block_number"] for e in bc_tx_events]
print(f"Unique transaction hashes: {len(set(tx_hashes))} / {len(tx_hashes)}")
print(f"Block range: {min(block_numbers)} -> {max(block_numbers)}")

print("\n=== CHECK 4: CAUSALITY & ISOLATION FOR SCENARIO B ===")
scenario_b_runs = [r for r in res_records if r["workload_variant_id"].startswith("B")]
print(f"Scenario B total runs: {len(scenario_b_runs)}")

causality_violations = 0
for r in scenario_b_runs:
    rid = r["run_id"]
    evs = events_by_run[rid]
    ep_ev = next((e for e in evs if e["source"] == "endpoint"), None)
    rpc_ev = next((e for e in evs if e["source"] == "rpc"), None)
    bc_ev = next((e for e in evs if e["source"] == "blockchain"), None)
    net_ev = next((e for e in evs if e["source"] == "network"), None)
    
    # Check if network exists
    if net_ev and bc_ev and rpc_ev and ep_ev:
        t_ep = ep_ev["timestamp"]
        t_rpc = rpc_ev["timestamp"]
        t_bc = bc_ev["timestamp"]
        t_net = net_ev["timestamp"]
        if not (t_ep <= t_rpc <= t_bc <= t_net):
            causality_violations += 1

print(f"Causality ordering violations in Scenario B: {causality_violations}")

# Check unintended network events in Scenario A and C
scenario_a_runs = [r["run_id"] for r in res_records if r["workload_variant_id"].startswith("A")]
scenario_c_runs = [r["run_id"] for r in res_records if r["workload_variant_id"].startswith("C")]

a_net_events = sum(len([e for e in events_by_run[rid] if e["source"] == "network"]) for rid in scenario_a_runs)
c_net_events = sum(len([e for e in events_by_run[rid] if e["source"] == "network"]) for rid in scenario_c_runs)
print(f"Scenario A outbound network events: {a_net_events}")
print(f"Scenario C outbound network events: {c_net_events}")

print("\n=== CHECK 5: LOOPBACK ENVIRONMENT VERIFICATION ===")
net_events = [e for e in events if e.get("network")]
non_loopback_destinations = []
for e in net_events:
    h = e["network"]["destination_host"]
    if h not in ("127.0.0.1", "localhost"):
        non_loopback_destinations.append(h)
print(f"Network events count: {len(net_events)}")
print(f"Non-loopback network destinations: {non_loopback_destinations}")

# Check RPC endpoints
rpc_destinations = set(e["rpc"]["rpc_endpoint"] for e in rpc_events)
print(f"RPC endpoints used: {rpc_destinations}")

print("\n=== CHECK 6: METRICS RECALCULATION ===")
# Excluded runs
evaluable_records = [r for r in res_records if r["classification"] != "EXCLUDED"]
print(f"Evaluable records: {len(evaluable_records)} / {len(res_records)}")
tp = sum(1 for r in evaluable_records if r["classification"] == "TP")
tn = sum(1 for r in evaluable_records if r["classification"] == "TN")
fp = sum(1 for r in evaluable_records if r["classification"] == "FP")
fn = sum(1 for r in evaluable_records if r["classification"] == "FN")

precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
accuracy = (tp + tn) / len(evaluable_records) if evaluable_records else 0.0

print(f"TP: {tp}, TN: {tn}, FP: {fp}, FN: {fn}")
print(f"Accuracy:    {accuracy:.4f} ({accuracy*100:.2f}%)")
print(f"Precision:   {precision:.4f} ({precision*100:.2f}%)")
print(f"Recall:      {recall:.4f} ({recall*100:.2f}%)")
print(f"Specificity: {specificity:.4f} ({specificity*100:.2f}%)")
print(f"F1-Score:    {f1:.4f} ({f1*100:.2f}%)")

# Latency summary recalculation
latencies = [r["detection_latency_ms"] for r in res_records if r["detection_latency_ms"] is not None]
unmeasured = sum(1 for r in res_records if r["detection_latency_ms"] is None)
print(f"Measured latencies count: {len(latencies)}, Unmeasured: {unmeasured}")
print(f"Mean latency: {sum(latencies)/len(latencies):.4f} ms")
print(f"Min latency: {min(latencies):.4f} ms, Max latency: {max(latencies):.4f} ms")
