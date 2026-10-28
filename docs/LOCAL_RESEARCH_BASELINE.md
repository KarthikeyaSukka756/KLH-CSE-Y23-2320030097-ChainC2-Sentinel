# ChainC2 Sentinel — Local Research Baseline Specification & Evaluation Report

**Document Status:** Authoritative Baseline Documentation  
**Research Campaign:** Matrix v2 Balanced Evaluation (81 Planned Runs)  
**Execution Environment:** Controlled Local Laboratory (Hardhat EVM + Loopback RPC Proxy)  
**Execution Date:** October 27, 2026  
**Artifact Storage:** `data/evaluation/dataset_campaign_corrected/`  

---

## 1. Executive Summary

This document establishes the **authoritative local research baseline** for the ChainC2 Sentinel cybersecurity framework. The baseline evaluates the multi-layer correlation and detection of blockchain-mediated Command-and-Control (C2) activity across 27 workload variants with 3 replicates each ($N=81$ planned runs).

The corrected campaign was executed using genuine JSON-RPC calls through a loopback RPC proxy targeting a locally hosted Hardhat development node, generating real EVM transactions, smart contract reads, and localized network beacons. All output artifacts and raw telemetry streams were written to dedicated, non-overwriting paths to preserve historical research baselines byte-for-byte.

```
+----------------------------------------------------------------------------------------------------+
|                                 CAMPAIGN EXECUTION METRICS OVERVIEW                                |
+----------------------------------------------------------------------------------------------------+
| Total Planned Runs          | 81                                                                   |
| Total Completed Runs        | 81 (100.0% execution completion)                                     |
| Infrastructure Failures     | 0                                                                    |
| Total Telemetry Events      | 369 normalized events                                                |
| Mined EVM Transactions      | 63 on-chain transactions (sequential blocks 86–178)                  |
| Smart Contract Reads        | 27 genuine eth_call read operations                                  |
| Evaluable Test Cases        | 66 runs (39 True Negatives, 27 True Positives, 0 FP, 0 FN)           |
| Non-Evaluable / Excluded    | 15 runs (3 validation rejections, 6 EVM reverts, 6 fault sims)       |
| Mean Detection Latency      | 0.3683 ms (n=78 measured records, 3 unmeasured validation rejects)   |
| Historical Artifact Integrity| 100% byte-for-byte preservation across all 4 baseline files        |
+----------------------------------------------------------------------------------------------------+
```

> [!IMPORTANT]
> **Laboratory Context Disclaimer:** The 100% precision, recall, and accuracy metrics reported herein reflect performance under a **strictly controlled local laboratory environment** with synthetic payloads and deterministic state contexts. They demonstrate the internal theoretical and causal validity of the multi-layer correlation model, but **do not represent general-world effectiveness** against real-world in-the-wild adversaries, public testnets, or Ethereum mainnet.

---

## 2. Experimental Setup & Laboratory Architecture

### 2.1 Topology
The laboratory operates entirely within a loopback network boundary (`127.0.0.1`), strictly forbidding external or public network communication:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Controlled Local Laboratory                                │
│                                                                                              │
│  ┌─────────────────────────┐         ┌─────────────────────────┐                             │
│  │    Workload Clients     │         │   Local HTTP Target     │                             │
│  │ (Synthetic C2 / Benign) │──POST──>│ (127.0.0.1:<dyn_port>)  │ (Inert HTTP Beacon)         │
│  └────────────┬────────────┘         └─────────────────────────┘                             │
│               │ (JSON-RPC)                                                                   │
│               ▼                                                                              │
│  ┌─────────────────────────┐                                                                 │
│  │     RPC Proxy Layer     │                                                                 │
│  │  (http://127.0.0.1:8546)│                                                                 │
│  └────────────┬────────────┘                                                                 │
│               │ (Forwarded JSON-RPC)                                                         │
│               ▼                                                                              │
│  ┌─────────────────────────┐                                                                 │
│  │   Hardhat Node (EVM)    │ Chain ID: 31337                                                 │
│  │  (http://127.0.0.1:8545)│ Authoritative Contracts: C2DataStore, BenignDApp, LegitDApp     │
│  └─────────────────────────┘                                                                 │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Authoritative Deployed Contracts
Authoritative contract addresses are resolved dynamically via `src/blockchain/deployment.py` from `src/blockchain/deployed-addresses.json`:
- **`C2DataStore`** (`0x5FbDB2315678afecb367f032d93F642f64180aa3`): Stores dead-drop configuration payloads (`storeCommand`, `getLatestCommand`, `getCommandAtIndex`).
- **`BenignDAppContract`** (`0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`): Counter and message store representing benign Web3 interactions (`getCount`, `increment`, `updateMessage`).
- **`LegitimateDAppContract`** (`0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0`): Multi-step workflow management system representing enterprise decentralized application tasks (`createTask`, `updateTaskStatus`, `getTask`, `getTaskCount`).

### 2.3 Sender Account & Network Isolation
- **Sender Address:** Hardhat Account #0 (`0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266`).
- **HTTP Beacon Redirect Restriction:** Client requests use a custom `NoRedirectHandler` subclassing `urllib.request.HTTPRedirectHandler` that explicitly rejects 3xx redirects (`301`, `302`, `303`, `307`, `308`) with `HTTP_REDIRECT_REJECTED`, preventing redirection to external hostnames or IPs.

---

## 3. Workload Scenarios & Variant Allocation

The 81 runs consist of 27 distinct variants executed across 3 replicates each ($27 \times 3 = 81$), divided into Tier 1 (evaluation-eligible core scenarios) and Tier 2 (edge cases, timing perturbations, and fault modes):

### 3.1 Scenario A: Benign Web3 Client (9 Variants $\times$ 3 Replicates = 27 Runs)
- **A01–A03:** Pure contract read operations (`getCount`, `message`, `deployer`).
- **A04–A05:** Single contract state modifications (`increment`, `updateMessage`).
- **A06–A07:** Burst read transactions and parameter variations.
- **A08a–A08b (Tier 2):** Handled RPC disconnect and network drop simulations (simulated infrastructure failure modes).

### 3.2 Scenario B: Synthetic Blockchain-Mediated C2 (10 Variants $\times$ 3 Replicates = 30 Runs)
- **B01:** Baseline dead-drop retrieval (`getLatestCommand`) followed by local HTTP POST beacon.
- **B02–B03:** Fixed cadence (500–2000 ms) and jittered delay (50–800 ms) timing perturbations.
- **B04:** Index-based command retrieval (`getCommandCount` $\to$ `getCommandAtIndex(i)`).
- **B05:** Attacker command staging transaction (`storeCommand`) followed by victim retrieval and beaconing.
- **B06 (Tier 2):** Process injection / simulated memory anomaly fixture (`provenance="SIMULATED_FIXTURE"`).
- **B07a–B07b (Tier 2):** Network fault simulations: closed loopback port (`ECONNREFUSED`) and client timeout ($<0.1$ ms).
- **B08 (Tier 2):** Sentinel containment / quarantine simulation (HTTP 403 response).
- **B09 (Tier 2):** Validator rejection before socket creation (invalid target/command schema).

### 3.3 Scenario C: Legitimate DApp Multi-Step Lifecycle (8 Variants $\times$ 3 Replicates = 24 Runs)
- **C01–C02:** Standard task lifecycles (`createTask` $\to$ `read` $\to$ `updateTaskStatus` $\to$ `read`).
- **C03:** High-volume batch task processing (8 sequential task transactions).
- **C04:** Read-intensive querying bursts (6 sequential task inspections).
- **C05–C06:** Cancellation and reopening lifecycle edge cases.
- **C07 (Tier 2):** EVM revert simulation: invalid task status transition (`InvalidTaskStatus()`).
- **C08 (Tier 2):** EVM revert simulation: non-existent task query (`TaskNotFound()`).

---

## 4. Telemetry Breakdown & RPC Provenance

The campaign captured **369 normalized telemetry events** logged to `data/evaluation/dataset_campaign_corrected/telemetry_events_balanced.jsonl`:

```
+------------------+-------------+-------------------------------------------------------------------+
| Telemetry Source | Event Count | Description & Live EVM Attribution                                |
+------------------+-------------+-------------------------------------------------------------------+
| Endpoint         |          81 | Process tracking (synthetic_c2_client, benign_client, dapp_worker)|
| RPC              |         171 | 99 eth_call reads + 72 eth_sendTransaction calls via 127.0.0.1:8546|
| Blockchain       |          90 | 63 verified mined transactions + 27 contract read call events      |
| Network          |          27 | Strictly confined to Scenario B variants on ephemeral 127.0.0.1   |
+------------------+-------------+-------------------------------------------------------------------+
| Total Events     |         369 | Full multi-source cross-layer stream                              |
+------------------+-------------+-------------------------------------------------------------------+
```

### 4.1 Detailed RPC & Blockchain Reconciliation
- **Total `eth_sendTransaction` Calls:** 72
  - **63 Mined On-Chain Transactions:** Mined sequentially in Hardhat blocks 86 through 178, each verified with a unique 66-character `0x` transaction hash, gas consumption, and block receipt.
  - **9 Reverted / Unmined Transaction Attempts:** C07 (3 on-chain EVM reverts), A06 (3 simulated nonce errors), A07 (3 simulated gas price errors). All 9 returned `status="error"` and were excluded from mined block events.
- **Total `eth_call` Reads:** 99
  - Scenario A reads: 9 basic reads + 30 multi-call burst queries = 39.
  - Scenario B reads: 24 command queries + 3 index queries = 27.
  - Scenario C reads: 30 task state queries + 3 C08 reverts = 33.
- **Total Blockchain Events:** 90 (63 mined transactions + 27 contract read events).

---

## 5. Detection Logic & Scoring Invariants

The campaign evaluated all events against the locked, invariant detection specification:

### 5.1 Seven-Condition Rule Conjunction (`SyntheticC2SequenceRule`)
Detection triggering requires all seven conditions to be satisfied:
1. `cond_endpoint`: Endpoint process telemetry event exists.
2. `cond_rpc`: Web3 RPC telemetry event exists.
3. `cond_blockchain`: Smart contract interaction event exists.
4. `cond_c2datastore`: Smart contract targets `C2DataStore`.
5. `cond_network`: Subsequent outbound network event exists.
6. `cond_network_timing`: Network event occurs chronologically at or after blockchain read ($\Delta t \ge 0$).
7. `cond_causal_timeline`: Strict causal sequence verified: $\text{endpoint} \le \text{RPC} \le \text{blockchain} \le \text{network}$.

### 5.2 Heuristic Scoring Table (`RuleBasedScorer`)
- **Endpoint Context:** +10.0
- **RPC Interaction:** +10.0
- **Contract Interaction:** +15.0
- **Suspicious Data Retrieval:** +20.0
- **C2 / Configuration Indicator:** +20.0
- **Matched Subsequent Network Activity:** +25.0
- **Total Weight Maximum:** **100.0**
- **Deterministic Decision Threshold:** **80.0**

---

## 6. Empirical Performance Analysis

### 6.1 Accounting for Excluded Cases ($n=15$)
In accordance with rigorous empirical standards, runs that do not reach the evaluable stage or represent intentional non-evaluable failure modes are classified as `EXCLUDED`:
- **Pre-Socket Validation Rejection (B09, $n=3$):** Parameter validation halts the scenario before socket binding. Recorded `VALIDATION_REJECTED`, `detection_latency_ms=None`.
- **EVM Contract Reverts (C07 & C08, $n=6$):** EVM execution reverts on-chain; recorded `FAILED`.
- **Infrastructure Fault Simulations (A08a & A08b, $n=6$):** Controlled RPC/network disconnects; recorded `FAILED`.

### 6.2 Performance on Evaluable Test Cases ($n=66$)
Restricting evaluation strictly to empirical, evaluable test cases:

```
+----------------------------------------------------------------------------------------------------+
|                                EVALUABLE METRICS CONFUSION MATRIX                                  |
+------------------------------------+-------------------------------+-------------------------------+
|                                    | Actual Positive (C2 Activity) | Actual Negative (Benign/DApp) |
+------------------------------------+-------------------------------+-------------------------------+
| Predicted Positive (Score >= 80.0) | TP = 27                       | FP = 0                        |
| Predicted Negative (Score < 80.0)  | FN = 0                        | TN = 39                       |
+------------------------------------+-------------------------------+-------------------------------+
```

- **Accuracy:** $\frac{27 + 39}{66} = \mathbf{100.00\%}$
- **Precision:** $\frac{27}{27 + 0} = \mathbf{100.00\%}$
- **Recall (Sensitivity):** $\frac{27}{27 + 0} = \mathbf{100.00\%}$
- **Specificity:** $\frac{39}{39 + 0} = \mathbf{100.00\%}$
- **F1-Score:** $\mathbf{1.0000}$

### 6.3 Simulated Fixture Attribution
Variant **B06** ($n=3$) utilizes a simulated memory injection fixture (`provenance="SIMULATED_FIXTURE"`). If evaluated separately from pure live execution cases ($n=63$):
- **Pure Live Execution Cases ($n=63$):** $\text{TP}=24, \text{TN}=39, \text{FP}=0, \text{FN}=0 \implies \mathbf{100.00\%}$.
- **Simulated Fixture Cases ($n=3$):** $\text{TP}=3, \text{FP}=0 \implies \mathbf{100.00\%}$.

### 6.4 Detection Latency Distribution
Latency measurement excludes unmeasured validation-rejected runs, preventing downward statistical bias:
- **Total Records:** 81
- **Measured Records ($n$):** 78
- **Unmeasured Records (B09):** 3 (`None`)
- **Mean Detection Latency:** **0.3683 ms**
- **Minimum Latency:** **0.1298 ms**
- **Maximum Latency:** **1.2640 ms**

---

## 7. Historical Baseline Artifact Verification

The 4 historical baseline research artifacts were verified byte-for-byte to confirm that no historical data was overwritten or modified during this campaign:

| Historical Baseline Artifact | Expected Size | Actual Size | Expected SHA-256 Hash | Current SHA-256 Hash | Status |
| :--- | :---: | :---: | :--- | :--- | :---: |
| `data/evaluation/dataset_campaign/matrix_v2_81_results.json` | 114,232 B | 114,232 B | `15fa3d7e49a1cf5f8c1476a2ff5141849a46fb31eb021a3e2159a2d8998fd470` | `15fa3d7e49a1cf5f8c1476a2ff5141849a46fb31eb021a3e2159a2d8998fd470` | **VERIFIED** |
| `data/evaluation/dataset_campaign/telemetry_events_balanced.jsonl` | 267,774 B | 267,774 B | `519c1e988e221d889ed499badb8bb704a69dd2c17c96dc42881ddafbbce35aa0` | `519c1e988e221d889ed499badb8bb704a69dd2c17c96dc42881ddafbbce35aa0` | **VERIFIED** |
| `data/evaluation/dataset_campaign/campaign_plan_372.json` | 215,305 B | 215,305 B | `0c483d093ee32c4122ae4c47fdc6fd62451b78991ec45bd25077f517f0c23bc7` | `0c483d093ee32c4122ae4c47fdc6fd62451b78991ec45bd25077f517f0c23bc7` | **VERIFIED** |
| `results/final/research_summary.json` | 10,472 B | 10,472 B | `85b1d136d61c7657c518eb2872eedf50f245e968d9997178ca04cdcce7930bcc` | `85b1d136d61c7657c518eb2872eedf50f245e968d9997178ca04cdcce7930bcc` | **VERIFIED** |

---

## 8. Research Limitations & Future Work

1. **Synthetic Laboratory Workloads:** Payload strings (`BEACON`) and endpoint metadata represent controlled abstractions rather than live weaponized payloads or evasive rootkits.
2. **Local Hardhat Environment:** Hardhat mines blocks instantaneously or deterministically upon transaction submission. It does not replicate Ethereum mainnet mempool congestion, MEV bot frontrunning, re-orgs, or dynamic base fee ($EIP-1559$) volatility.
3. **Replicate Sample Size:** The balanced baseline uses 3 replicates per variant ($N=81$). While sufficient for statistical mean latency and behavioral consistency, it does not assess multi-day continuous drift.
4. **No Public Testnet / Mainnet Validation:** Efficacy on public networks (Sepolia, Holesky, or Ethereum mainnet) remains unproven and constitutes a subject for future multi-node distributed research.

---

## 9. Artifact Index & Audit References

- **Corrected Campaign Results:** [`data/evaluation/dataset_campaign_corrected/matrix_v2_81_results.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evaluation/dataset_campaign_corrected/matrix_v2_81_results.json)
- **Corrected Campaign Telemetry:** [`data/evaluation/dataset_campaign_corrected/telemetry_events_balanced.jsonl`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evaluation/dataset_campaign_corrected/telemetry_events_balanced.jsonl)
- **Formal Campaign Plan:** [`data/evaluation/dataset_campaign_corrected/campaign_plan_81.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evaluation/dataset_campaign_corrected/campaign_plan_81.json)
- **Verification Audit Script:** [`scratch/audit_campaign_81.py`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/scratch/audit_campaign_81.py)
- **Security Redirect Test Suite:** [`tests/test_beacon_redirect_security.py`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/tests/test_beacon_redirect_security.py)
