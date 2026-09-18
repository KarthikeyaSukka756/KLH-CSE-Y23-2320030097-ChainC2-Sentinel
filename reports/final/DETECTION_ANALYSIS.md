# Phase 1 Analysis: Detection of Blockchain-Mediated C2 Channels
## Empirical Evaluation of Multi-Layer Telemetry Correlation (RULE-CHAINC2-001)

**Project:** ChainC2 Sentinel
**Research Focus:** Phase 1 — Detection
**Research Question 1 (RQ1):** *"Are blockchain-mediated C2 behaviors detectable?"*
**Benchmark ID:** `eval-53e4910d-a742-46fc-8188-3b6eb7c5f566`

---

## 1. Research Question & Objective

Phase 1 addresses the foundational research question:
> **RQ1:** *"Are blockchain-mediated C2 behaviors detectable?"*

The primary objective is to determine whether synthetic blockchain-mediated command-and-control behavior leaves an observable, causally linkable signature across endpoint, JSON-RPC, smart contract, and network telemetry that can be distinguished from legitimate decentralized application (dApp) activity under controlled laboratory conditions.

---

## 2. Multi-Layer Evidence Chain

A standalone blockchain query closely mirrors normal Web3 operations. To achieve explainable detection, ChainC2 Sentinel models the entire operational lifecycle as an ordered cross-layer evidence chain:

```
┌──────────────────────────────────────────────┐
│  Layer 1: Endpoint Process Telemetry         │
│  - Process Name: synthetic_c2_client         │
│  - Process PID: 4096                         │
│  - Execution Context & Working Directory     │
└──────────────────────┬───────────────────────┘
                       │ (Interacts via JSON-RPC)
                       ▼
┌──────────────────────────────────────────────┐
│  Layer 2: RPC Gateway Telemetry              │
│  - Method: eth_call / eth_sendTransaction    │
│  - Parameters: to = C2DataStore address      │
│  - Direction: Client -> RpcProxy -> Node     │
└──────────────────────┬───────────────────────┘
                       │ (Queries Smart Contract)
                       ▼
┌──────────────────────────────────────────────┐
│  Layer 3: Blockchain / Smart Contract        │
│  - Contract: C2DataStore.sol                 │
│  - Function: getLatestCommand()              │
│  - Retrieved Data: Synthetic C2 Payload      │
└──────────────────────┬───────────────────────┘
                       │ (Parses Target & Commands)
                       ▼
┌──────────────────────────────────────────────┐
│  Layer 4: Network Egress Activity            │
│  - Protocol: HTTP POST /beacon               │
│  - Destination: 127.0.0.1:8080               │
│  - Temporal Relation: t_net > t_blockchain   │
└──────────────────────────────────────────────┘
```

---

## 3. Cross-Layer Correlation & Temporal Causality

The `CrossLayerCorrelationEngine` reconstructs multi-layer sequences by evaluating causal transitions and computing the inter-layer time delta ($\Delta t$):

$$\Delta t = t_{\text{network}} - t_{\text{blockchain}} > 0$$

### Causal Ordering Constraints:
1. **Monotonicity:** $t_{\text{endpoint}} \le t_{\text{rpc}} \le t_{\text{blockchain}} < t_{\text{network}}$.
2. **Context Preservation:** Process PID and Scenario Run ID are propagated across event transitions to prevent cross-stream contamination.
3. **Delta-Time Validation:** If network activity precedes blockchain access ($\Delta t < 0$), the sequence is classified as unrelated background traffic and discarded.

---

## 4. Detection Rule Specification: `RULE-CHAINC2-001`

Detection rule `RULE-CHAINC2-001` (`Synthetic Blockchain-Mediated C2 Sequence Rule`) evaluates 7 deterministic, observable conditions:

| Condition ID | Name | Description | Verification Logic |
|:---|:---|:---|:---|
| `cond_endpoint` | Endpoint Process | Host process execution recorded | Endpoint event exists with valid PID and process name |
| `cond_rpc` | RPC Interaction | JSON-RPC query captured | RPC event exists targeting Ethereum EVM gateway |
| `cond_blockchain`| Contract Access | Smart contract interaction recorded | Blockchain event captured with verified contract address |
| `cond_c2datastore`| C2 Contract Target| Targeted contract is `C2DataStore` | Target address matches synthetic C2 repository address |
| `cond_network` | Network Follow-up | Subsequent network request captured | Network event recorded with valid HTTP target metadata |
| `cond_network_timing`| Forward Timing | Network occurs strictly after RPC/Contract | $t_{\text{network}} - t_{\text{blockchain}} > 0$ |
| `cond_causal_timeline`| Monotonic Order | Monotonic progression across all stages | Valid sequence across endpoint, RPC, contract, and network |

A detection candidate is classified as **TRIGGERED** if and only if **all 7 conditions** are satisfied.

---

## 5. Empirical Evaluation Results

The Phase 1 evaluation was executed across 20 controlled experiments (10 Scenario A negative controls and 10 Scenario B positive controls).

*Authoritative Source: [`data/evaluation/evaluation_results.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evaluation/evaluation_results.json)*

### Confusion Matrix
```
                         Ground Truth (Positive)    Ground Truth (Negative)
Detector: Triggered             TP = 10                     FP = 0
Detector: Not Triggered         FN = 0                      TN = 10
```

### Statistical Evaluation Metrics

| Metric | Measured Value | Calculation Formula | Research Significance |
|:---|:---:|:---|:---|
| **Total Experiments** | **20** | $\text{Total evaluated runs}$ | 10 Benign + 10 Synthetic C2 |
| **Successful Runs** | **20 / 20** (100.0%) | $\text{successful} / \text{total}$ | Robust, reproducible execution |
| **Detection Rate (Recall)**| **100.0%** | $TP / (TP + FN) = 10 / 10$ | Complete sensitivity on positive control |
| **False-Positive Rate** | **0.0%** | $FP / (FP + TN) = 0 / 10$ | Zero false alarms on legitimate Web3 |
| **Precision** | **100.0%** | $TP / (TP + FP) = 10 / 10$ | All triggered alerts were authentic |
| **Specificity (TNR)** | **100.0%** | $TN / (TN + FP) = 10 / 10$ | Correctly cleared benign dApp baseline |
| **Accuracy** | **100.0%** | $(TP + TN) / \text{total} = 20 / 20$ | Overall classification fidelity |
| **F1 Score** | **1.000** | $2 \cdot (P \cdot R) / (P + R)$ | Harmonic balance of precision & recall |

### Processing Latency Profile
- **Average Detection Latency:** **0.0480 ms** (~48 microseconds)
- **Minimum Latency:** **0.0252 ms**
- **Maximum Latency:** **0.0918 ms**

---

## 6. Detailed Analytical Breakdown

### A. The Critical Role of Scenario A (Negative Control)
In Scenario A, an endpoint process connects to the local EVM node via the RPC proxy, calls `BenignDAppContract.sol`, increments a counter, and updates a message string.
- Telemetry observed: Endpoint process $\rightarrow$ RPC `eth_sendTransaction` $\rightarrow$ Blockchain contract interaction.
- Because Scenario A terminates without making follow-up network connections, conditions `cond_network`, `cond_network_timing`, and `cond_causal_timeline` fail.
- **Outcome:** Resulted in `status = NOT_TRIGGERED` across all 10 runs ($TN = 10, FP = 0$).
- **Conclusion:** Blockchain interaction in isolation is **not** treated as malicious. Legitimate Web3 development, smart contract testing, and decentralized application usage proceed without triggering false alerts.

### B. Scenario B (Positive Control)
In Scenario B, the endpoint client queries `C2DataStore.sol`, parses the inert configuration string (`BEACON`), and issues an HTTP POST request to the local beacon endpoint.
- Telemetry observed: Endpoint process $\rightarrow$ RPC `eth_call` $\rightarrow$ `C2DataStore` interaction $\rightarrow$ Local HTTP beacon egress.
- All 7 conditions were satisfied across all 10 runs ($TP = 10, FN = 0$).
- **Outcome:** Reliable detection in under $0.1$ milliseconds per sequence.

### C. Forensic Evidence Snapshot Generation
For every triggered candidate, the detector outputs a factual `DetectionResult` preserving:
- Matched and unmatched condition vectors.
- Target contract name and address.
- Destination IP, port, and HTTP method.
- Complete event timeline with microsecond timestamps.
- Factual natural-language explanation.

---

## 7. Phase 1 Scope & Methodological Boundaries

1. **Synthetic Models Only:** The detector was evaluated against our defined `SyntheticC2Payload` model. Adversaries employing steganography, encrypted transaction blobs, or delayed asynchronous beaconing would require extended behavioral heuristics.
2. **Localhost Single-Host Testbed:** Telemetry events were generated on a single host. In enterprise environments, network jitter and NAT boundaries could widen inter-stage time deltas.
3. **No Claim of Universal Blockchain Malware Detection:** Phase 1 confirms that a blockchain-mediated C2 channel exhibiting cross-layer causality is detectable in a controlled laboratory setting. It does not assert that all possible blockchain C2 implementations are detectable by rule `RULE-CHAINC2-001`.

---

## 8. Summary Answer to RQ1

> **RQ1 Conclusion:** Blockchain-mediated C2 behaviors are **detectable** when multi-source telemetry across endpoint, RPC, smart contract, and network layers is causally and temporally correlated. In laboratory evaluations, the framework achieved a **100.0% Detection Rate**, **0.0% False-Positive Rate**, and sub-0.1ms rule processing latency while strictly preserving benign Web3 activity.
