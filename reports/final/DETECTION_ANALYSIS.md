# Phase 1 Analysis: Detection of Blockchain-Mediated C2 Channels
## Empirical Evaluation of Multi-Layer Telemetry Correlation & Explainable Scoring (RULE-CHAINC2-001)

**Project:** ChainC2 Sentinel<br>
**Research Focus:** Phase 1 — Detection<br>
**Research Question 1 (RQ1):** *"Can cross-layer telemetry correlation detect blockchain-mediated C2-like behavioral sequences while distinguishing them from legitimate Web3 activity?"*<br>
**Benchmark ID:** `eval-e7ad9f1a-8361-4f27-8abb-cfb6bf00d48c`

---

## 1. Research Question & Objective

Phase 1 addresses the foundational research question:
> **RQ1:** *"Can cross-layer telemetry correlation detect blockchain-mediated C2-like behavioral sequences while distinguishing them from legitimate Web3 activity?"*

The primary objective is to determine whether synthetic blockchain-mediated command-and-control behavior leaves an observable, causally linkable signature across endpoint, JSON-RPC, smart contract, and network telemetry that can be distinguished from legitimate decentralized application (dApp) activity under controlled laboratory conditions using an explainable, rule-based weighted scoring model.

---

## 2. Multi-Layer Evidence Chain & Telemetry Pipeline

A standalone blockchain query closely mirrors normal Web3 operations. To achieve explainable detection, ChainC2 Sentinel models the entire operational lifecycle through a disciplined 4-layer telemetry pipeline:

```
Endpoint Telemetry
        ↓
RPC Telemetry
        ↓
Blockchain Telemetry
        ↓
Network Telemetry
        ↓
Normalization
        ↓
Correlation Engine
        ↓
Explainable Rule-Based Weighted Scoring
        ↓
Detection
        ↓
Evaluation
```

### Telemetry Layers:
1. **Endpoint Process Telemetry:** Captures process metadata (`synthetic_c2_client`, PID, command arguments).
2. **RPC Gateway Telemetry:** Captures JSON-RPC calls (`eth_call`, `eth_sendTransaction`, parameters, duration) via a dedicated monitoring proxy.
3. **Blockchain / Smart Contract Telemetry:** Captures contract address, function calls, emitted events, and retrieved configuration data.
4. **Network Telemetry:** Captures subsequent egress activity (`POST /beacon`, destination, latency).

---

## 3. Cross-Layer Correlation & Temporal Causality

The `CrossLayerCorrelationEngine` reconstructs multi-layer sequences by evaluating causal transitions and computing the inter-layer time delta ($\Delta t$):

$$\Delta t = t_{\text{network}} - t_{\text{blockchain}} > 0$$

### Causal Ordering Constraints:
1. **Monotonicity:** $t_{\text{endpoint}} \le t_{\text{rpc}} \le t_{\text{blockchain}} < t_{\text{network}}$.
2. **Context Preservation:** Process PID and Scenario Run ID are propagated across event transitions to prevent cross-stream contamination.
3. **Delta-Time Validation:** If network activity precedes blockchain access ($\Delta t < 0$), the sequence is classified as unrelated background traffic and discarded.

---

## 4. Explainable Rule-Based Weighted Scoring Model

ChainC2 Sentinel implements a transparent, explainable heuristic scoring engine (`src/detection/scoring.py`). The detector does not rely on opaque black-box machine learning or classify purely on contract address. Instead, it computes a cumulative score from observable correlated behavioral evidence:

| Evidence Component | Scoring Rule | Heuristic Weight | Rationale |
|:---|:---|:---:|:---|
| **Endpoint Context** | `endpoint_process_context` | **+10** | Observable host process initiating Web3 workflow |
| **RPC Gateway** | `rpc_gateway_interaction` | **+10** | Valid JSON-RPC interaction through Ethereum gateway |
| **Smart Contract** | `contract_interaction` | **+15** | Verified smart contract invocation or transaction execution |
| **Data Retrieval** | `suspicious_data_retrieval` | **+20** | Retrieval of command or structured configuration payload |
| **C2 Indicator** | `c2_configuration_indicator` | **+20** | Decoded payload contains actionable C2 command (`BEACON`) |
| **Network Egress** | `matched_network_activity` | **+25** | Subsequent outbound network connection matching configuration |
| **Total Conceptual Max** | | **100** | Maximum possible cumulative score |

> [!IMPORTANT]
> **Scoring Model Rationale:** These weights are configurable heuristic engineering weights designed to reflect layered behavioral suspicion. They are **not** probabilities, machine-learning hyperparameters, or universal constants. The detection threshold is configured to **80.0**, requiring correlated subsequent network follow-up matching retrieved blockchain instructions before declaring a detection.

---

## 5. Empirical Evaluation Results (30-Run Benchmark)

The Phase 1 evaluation was executed across 30 controlled experiments:
- **10 × Scenario A — Benign Web3** (basic counter increment negative control)
- **10 × Scenario B — Synthetic C2** (blockchain-mediated C2 positive control)
- **10 × Scenario C — Legitimate DApp Baseline** (multi-step task registry negative control)

*Authoritative Source: [`data/evaluation/evaluation_results.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evaluation/evaluation_results.json)*

### Confusion Matrix
```
                         Ground Truth (Positive)    Ground Truth (Negative)
Detector: Triggered             TP = 10                     FP = 0
Detector: Not Triggered         FN = 0                      TN = 20
```
*Note: Ground truth negatives comprise 10 runs of Scenario A and 10 runs of Scenario C ($TN = 10 + 10 = 20$).*

### Statistical Evaluation Metrics

| Metric | Measured Value | Calculation Formula | Research Significance |
|:---|:---:|:---|:---|
| **Total Experiments** | **30** | $\text{Total evaluated runs}$ | 10 Benign A + 10 Synthetic C2 B + 10 DApp C |
| **Successful Runs** | **30 / 30** (100.0%) | $\text{successful} / \text{total}$ | Robust, reproducible execution |
| **Detection Rate (Recall)**| **100.0%** | $TP / (TP + FN) = 10 / 10$ | Complete sensitivity on positive control |
| **False-Positive Rate** | **0.0%** | $FP / (FP + TN) = 0 / 20$ | Zero false alarms across both legitimate Web3 classes |
| **Precision** | **100.0%** | $TP / (TP + FP) = 10 / 10$ | All triggered alerts were authentic |
| **Specificity (TNR)** | **100.0%** | $TN / (TN + FP) = 20 / 20$ | Correctly cleared basic and realistic dApps |
| **Accuracy** | **100.0%** | $(TP + TN) / \text{total} = 30 / 30$ | Overall classification fidelity |
| **F1 Score** | **1.000** | $2 \cdot (P \cdot R) / (P + R)$ | Harmonic balance of precision & recall |

### Processing Latency Profile
- **Average Detection Latency:** **0.1016 ms** (~101.6 microseconds)
- **Minimum Latency:** **0.0451 ms**
- **Maximum Latency:** **0.6879 ms**

---

## 6. Detailed Analytical Breakdown Across Scenarios

### A. Scenario A — Benign Web3 (Negative Control)
- **Workflow:** Endpoint process interacts via RPC with `BenignDAppContract.sol`, incrementing a counter.
- **Evidence Observed:** Endpoint process (+10), RPC interaction (+10), Contract interaction (+15).
- **Calculated Score:** **35.0 / 100** (Threshold: 80.0) $\rightarrow$ `status = NOT_TRIGGERED`.
- **Result:** $TN = 10, FP = 0$. Confirms that basic blockchain interactions do not trigger alarms.

### B. Scenario C — Legitimate DApp Baseline (Negative Control)
- **Workflow:** Realistic multi-step enterprise decentralized application workload interacting with `LegitimateDAppContract.sol` (task creation $\rightarrow$ reading task $\rightarrow$ status update $\rightarrow$ reading state), generating multiple transactions and event logs without follow-up network activity.
- **Evidence Observed:** Endpoint process (+10), RPC interaction (+10), Contract interaction (+15).
- **Calculated Score:** **35.0 / 100** (Threshold: 80.0) $\rightarrow$ `status = NOT_TRIGGERED`.
- **Result:** $TN = 10, FP = 0$. Confirms that complex, multi-step DApp workloads with state modifications and event emissions do not trigger false detections.

### C. Scenario B — Synthetic C2 (Positive Control)
- **Workflow:** Endpoint queries `C2DataStore.sol`, retrieves inert configuration string (`BEACON`), and executes a local HTTP beacon to `127.0.0.1:8080/beacon`.
- **Evidence Observed:** Endpoint (+10), RPC (+10), Contract (+15), Suspicious retrieval (+20), C2 indicator (+20), Follow-up network activity (+25).
- **Calculated Score:** **100.0 / 100** (Threshold: 80.0) $\rightarrow$ `status = TRIGGERED`.
- **Result:** $TP = 10, FN = 0$. Reliable, sub-millisecond detection driven by correlated cross-layer causality.

### D. Negative Controls & Boundary Conditions
- **RPC Only:** Score = 10.0 $\rightarrow$ `NOT_TRIGGERED`
- **Contract Only:** Score = 15.0 $\rightarrow$ `NOT_TRIGGERED`
- **Suspicious Data Retrieval without Network Activity:** Score = 75.0 (Endpoint 10 + RPC 10 + Contract 15 + Retrieval 20 + Config 20) $\rightarrow$ Below threshold 80.0 $\rightarrow$ `NOT_TRIGGERED`
- **Network Activity Preceding Blockchain ($\Delta t < 0$):** Network rejected due to invalid causal ordering $\rightarrow$ `NOT_TRIGGERED`

---

## 7. Phase 1 Scope & Methodological Boundaries

1. **Synthetic Models Only:** Evaluated against defined synthetic smart contracts (`C2DataStore`, `BenignDAppContract`, `LegitimateDAppContract`).
2. **Localhost Testbed:** Conducted in a controlled local Hardhat EVM environment.
3. **No Claim of Universal Malware Classification:** Demonstrates that cross-layer behavioral correlation effectively distinguishes blockchain-mediated C2-like sequences from legitimate Web3 dApp activity. Does not claim universal detection across arbitrary obfuscated malware families.

---

## 8. Summary Answer to RQ1

> **RQ1 Conclusion:** Cross-layer telemetry correlation combined with explainable rule-based weighted scoring **can reliably detect blockchain-mediated C2-like behavioral sequences while distinguishing them from legitimate Web3 activity**. In empirical 30-run laboratory benchmarks spanning basic and multi-step legitimate DApps alongside synthetic C2, the framework achieved **100.0% Detection Rate**, **0.0% False-Positive Rate**, **100.0% Specificity**, and an average detection latency of **0.1016 ms**.
