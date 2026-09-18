# Final Research Analysis: ChainC2 Sentinel
## A Cybersecurity Framework for Detecting Blockchain-Mediated Command-and-Control Channels

**Project Repository:** `KLH-CSE-Y23-2320030097-ChainC2-Sentinel`
**Milestone:** Milestone 11 — Final Research Analysis
**Research Phases:** Phase 1 — Detection | Phase 2 — Protection
**Author:** Academic Capstone Project Research Team
**Evaluation Dates:** September 2026

---

## 1. Executive Summary

Decentralized smart-contract platforms introduce new operational surfaces for command-and-control (C2) architectures. By leveraging public blockchains as immutable, decentralized dead-drop resolvers or dead-drop data stores, adversaries can potentially publish instructions that client endpoints query via standard JSON-RPC gateways.

The **ChainC2 Sentinel** research project investigates whether such blockchain-mediated C2 behavioral patterns are detectable through host and network telemetry, and what controlled defensive mitigations can be executed once detected.

The research is organized strictly into two sequential phases:
1. **Phase 1 — Detection:** Focuses on **Research Question 1 (RQ1)**: *"Can cross-layer telemetry correlation detect blockchain-mediated C2-like behavioral sequences while distinguishing them from legitimate Web3 activity?"*
2. **Phase 2 — Protection:** Focuses on **Research Question 2 (RQ2)**: *"Once the behavior is detected, what defensive measures can be applied?"*

Across controlled, reproducible laboratory experiments executed on a local Hardhat Ethereum Virtual Machine (EVM) testbed:
- **Phase 1 Detection Evaluation (30 runs):** Achieved **100.0% Detection Rate (Recall)** across 10 positive control runs and **0.0% False-Positive Rate** across 20 negative control runs (10 Scenario A and 10 Scenario C), with an average rule processing latency of **0.102 ms**.
- **Phase 2 Protection Evaluation (22 runs):** Achieved **100.0% Mitigation Success Rate** (40/40 actions verified), **100.0% RPC Blocking Rate**, **100.0% Beacon Blocking Rate**, **100.0% Process Isolation Success Rate**, **100.0% Legitimate Traffic Preservation**, and **0.0% False Mitigation Rate**, with an average containment latency of **2.091 ms** and full rollback verification.

These findings demonstrate that cross-layer causal correlation can reliably separate synthetic blockchain-mediated C2 sequences from legitimate Web3 dApp activity, and that layered application-layer defensive controls can rapidly contain suspicious activity while preserving benign operations.

---

## 2. Research Questions

The research is structured around two central research questions:

### Research Question 1 (RQ1) — Phase 1: Detection
> *"Can cross-layer telemetry correlation detect blockchain-mediated C2-like behavioral sequences while distinguishing them from legitimate Web3 activity?"*
- **Hypothesis:** By correlating endpoint process execution, JSON-RPC queries, smart contract interactions, and subsequent network activity across time, a defensive monitoring pipeline can distinguish blockchain-mediated C2-like sequences from legitimate decentralized application interactions without flagging benign blockchain activity.

### Research Question 2 (RQ2) — Phase 2: Protection
> *"Once the behavior is detected, what defensive measures can be applied?"*
- **Hypothesis:** Once a factual detection is generated, an automated policy engine can coordinate safe, application-layer containment mechanisms (RPC contract filtering, local beacon blocking, cooperative process isolation, and immutable forensic snapshotting) to neutralize the observed behavior while strictly preserving legitimate Web3 interactions and localhost operations.

---

## 3. Research Scope & Boundaries

The research operates under strict ethical, technical, and laboratory safeguards:
- **Inert Synthetic Data Only:** The `C2DataStore` smart contract stores inert, synthetic configuration metadata (e.g. `{"scenario": "synthetic_c2", "command": "BEACON", "target": "http://127.0.0.1:8080/beacon"}`). No live malware, exploit payloads, weaponized scripts, or persistence techniques are employed.
- **Local Isolated Infrastructure:** All blockchain transactions execute on a private Hardhat EVM (Chain ID 31337) bound to `127.0.0.1`. No public blockchains (Ethereum Mainnet, Sepolia, Arbitrum, etc.) or public RPC gateways are contacted.
- **Controlled Application-Layer Defense:** Defensive mitigations operate exclusively within local monitored components (`RpcTelemetryProxy`, `LocalHttpTargetServer`, `ScenarioWorkerRegistry`, and evidence persistence). Zero OS firewall manipulation (`netsh`, `iptables`, `nft`), packet filtering, or operating system process termination (`kill -9`, `taskkill`) are performed.
- **Laboratory Scope:** Findings quantify performance within this controlled testbed and do not claim universal real-world malware containment or attribution against advanced persistent threats.

---

## 4. Experimental Methodology

The experimental framework consists of four primary telemetry layers and controlled operational scenarios across both phases:

### Telemetry Pipeline
```
[ Endpoint Collector ]  ──> Process PID, Executable Name, CLI
[ RPC Collector ]       ──> JSON-RPC Method, Params, Latency
[ Blockchain Collector] ──> Contract Address, Function, Transaction
[ Network Collector ]   ──> HTTP Method, Destination Host, Port, URI
          │
          ▼
[ Event Normalizer ]    ──> SentinelEvent Schema Validation (Pydantic v2)
          │
          ▼
[ Cross-Layer Engine ]  ──> Temporal & Causal Correlation (Delta Time Δt)
          │
          ▼
[ Scoring Engine ]      ──> Explainable Weighted Scoring (Threshold: 80.0)
          │
          ▼
[ Detection Engine ]    ──> Rule Evaluation (RULE-CHAINC2-001)
          │
          ▼
[ Policy Engine ]       ──> DefensePlan Generation (Layered Actions)
          │
          ▼
[ Defense Executor ]    ──> Mitigation Execution, Probing & Rollback
```

### Scenario Specifications

| Scenario | Nature | Target Contract | Follow-up Network Activity | Ground Truth |
|:---|:---:|:---|:---:|:---:|
| **Scenario A** | Legitimate Web3 dApp | `BenignDAppContract` | Zero follow-up network activity | `BENIGN` (Negative Control) |
| **Scenario B** | Synthetic C2-Like Activity | `C2DataStore` | Controlled HTTP beacon to `127.0.0.1` | `SYNTHETIC_C2` (Positive Control) |
| **Scenario C** | Legitimate DApp Baseline | `LegitimateDAppContract` | Zero follow-up network activity | `LEGITIMATE_DAPP` (Negative Control) |

*(Note: Phase 2 Protection evaluation additionally tests 2 controlled fault-injection runs to verify handler refusal boundaries and error safety).*

---

## 5. Phase 1 — Detection Analysis

Phase 1 evaluated whether the cross-layer correlation of multi-source telemetry combined with explainable rule-based weighted scoring can detect blockchain-mediated C2-like sequences while avoiding false alarms against basic and realistic legitimate Web3 dApp baseline activity.

### Explainable Rule-Based Weighted Scoring Model
Rather than relying on opaque ML models or simple contract identity, the detector evaluates factual evidence contributions:
- Endpoint Process Context: **+10**
- RPC Gateway Interaction: **+10**
- Contract Interaction: **+15**
- Suspicious Data Retrieval: **+20**
- C2/Configuration Indicator: **+20**
- Matched Subsequent Network Activity: **+25**
- Maximum Conceptual Score: **100**, Default Threshold: **80.0**

### Empirical Detection Results (Benchmark: 30 Runs)
*Source Artifact: [`results/detection/evaluation_summary.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/detection/evaluation_summary.json)*

| Metric | Measured Value | Formula / Denominator | Interpretation |
|:---|:---:|:---|:---|
| **Total Experiments** | 30 | 10 Scenario A + 10 Scenario B + 10 Scenario C | Balanced multi-scenario suite |
| **True Positives ($TP$)** | 10 | Scenario B triggered | 100% positive control identification |
| **True Negatives ($TN$)** | 20 | Scenario A (10) + Scenario C (10) not triggered | 100% negative control baseline preservation |
| **False Positives ($FP$)** | 0 | Neither Scenario A nor C triggered | Zero false alarms on legitimate Web3 |
| **False Negatives ($FN$)** | 0 | Scenario B missed | Zero missed detections |
| **Detection Rate (Recall)** | **100.0%** | $TP / (TP + FN)$ | Perfect sensitivity on testbed sequences |
| **False-Positive Rate** | **0.0%** | $FP / (FP + TN)$ | Zero false-alarm fall-out across 20 negatives |
| **Precision** | **100.0%** | $TP / (TP + FP)$ | Triggered detections are 100% reliable |
| **Specificity (TNR)** | **100.0%** | $TN / (TN + FP)$ | Correctly cleared basic and realistic dApps |
| **Accuracy** | **100.0%** | $(TP + TN) / \text{total}$ | Complete classification correctness |
| **F1 Score** | **1.000** | $2 \cdot (P \cdot R) / (P + R)$ | Optimal harmonic balance |
| **Average Detection Latency** | **0.102 ms** | $\text{mean}(\text{latency})$ | Sub-millisecond rule processing |
| **Min / Max Latency** | **0.045 ms / 0.688 ms** | Range of rule evaluations | Highly deterministic timing |

### Key Analytical Takeaways for Phase 1
- **Negative Control Significance:** Both basic legitimate Web3 activity (Scenario A, score 35.0) and realistic multi-step DApp task-registry activity (Scenario C, score 35.0) generated extensive process, RPC, and smart contract telemetry. Because neither executed subsequent beaconing, both scored well below the 80.0 threshold, yielding $FP = 0$.
- **Cross-Layer Causality:** An isolated blockchain query or complex DApp transaction workflow looks like normal decentralized application activity. Only when correlated with subsequent network connections originating from the same endpoint context does the signature emerge.

---

## 6. Phase 2 — Protection Analysis

Phase 2 evaluated the defensive response to confirmed detection candidates. Once `RULE-CHAINC2-001` triggers, the policy engine synthesizes a `DefensePlan`, and the `DefenseExecutor` coordinates deterministic application-layer containment.

### Mitigation Handlers & Execution Lifecycle
The execution follows a strict 4-stage deterministic progression:
$$\text{PRESERVE\_EVIDENCE} \longrightarrow \text{CONTAIN\_NETWORK} \longrightarrow \text{FILTER\_RPC} \longrightarrow \text{ISOLATE\_PROCESS}$$

Every action transitions through:
$$\text{REQUESTED} \longrightarrow \text{EXECUTED} \longrightarrow \text{VERIFIED} \quad (\text{or } \text{FAILED})$$

### Empirical Protection Results (Benchmark: 22 Runs)
*Source Artifact: [`results/protection/evaluation_summary.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/protection/evaluation_summary.json)*

| Metric | Measured Value | Formula / Denominator | Interpretation |
|:---|:---:|:---|:---|
| **Total Experiments** | 22 | 10 Benign + 10 C2 + 2 Fault Injection | Comprehensive operational suite |
| **Experiment Success Rate** | **100.0%** | $22 / 22$ successful executions | All scenarios completed without error |
| **Mitigation Success Rate** | **100.0%** | $40 / 40$ verified actions | All requested actions confirmed verified |
| **RPC Blocking Rate** | **100.0%** | $10 / 10$ queries blocked | Synthetic `C2DataStore` queries rejected |
| **Beacon Blocking Rate** | **100.0%** | $10 / 10$ beacons rejected | Subsequent `/beacon` requests returned HTTP 403 |
| **Process Isolation Rate** | **100.0%** | $10 / 10$ workers isolated | Registered workers cooperatively contained |
| **Legitimate Traffic Preservation**| **100.0%** | $22 / 22$ runs preserved | Benign contracts & `/health` functional |
| **False Mitigation Rate** | **0.0%** | $0 / 10$ benign runs mitigated | Scenario A produced zero defense actions |
| **Rollback Success Rate** | **100.0%** | $10 / 10$ rollbacks verified | Baseline restored; evidence preserved |
| **Evidence Preservation Rate** | **100.0%** | $10 / 10$ bundles created | Structured JSON with valid SHA-256 digest |
| **Average Containment Latency** | **2.091 ms** | Mean plan execution & probe time | Rapid sub-4ms response |
| **Median Containment Latency** | **1.755 ms** | Median containment latency | Low variance across repeated runs |
| **Min / Max Latency** | **1.490 ms / 3.564 ms** | Latency performance boundaries | Predictable execution envelope |

### Key Analytical Takeaways for Phase 2
- **Layered Application Containment:** Rather than attempting to censor or rewrite the decentralized blockchain ledger (which is cryptographically impossible), the system intervenes at the local application boundary: the client RPC proxy and local network egress.
- **Preservation of Legitimate Operations:** Even while containment was actively blocking `C2DataStore` and `/beacon`, benign smart contract interactions (`BenignDAppContract`) and server health endpoints (`/health`) operated with zero degradation.
- **Rollback & Forensic Integrity:** Automated rollback cleared proxy filters and containment flags in inverse order, restoring baseline conditions while preserving evidence snapshots intact.

---

## 7. Combined Findings: The Closed-Loop Pipeline

The integration of Phase 1 and Phase 2 establishes an end-to-end defensive workflow:

$$\underbrace{\text{Observe} \longrightarrow \text{Correlate} \longrightarrow \text{Detect} \longrightarrow \text{Snapshot}}_{\text{Phase 1: Detection Pipeline}} \quad \Longrightarrow \quad \underbrace{\text{Plan} \longrightarrow \text{Contain} \longrightarrow \text{Verify} \longrightarrow \text{Roll Back / Audit}}_{\text{Phase 2: Protection Pipeline}}$$

### Conceptual Decoupling
Detection and protection are explicitly decoupled:
1. **Detection Capability:** Evaluates pattern recognition accuracy (sensitivity, false-alarm rejection, temporal validation).
2. **Protection Capability:** Evaluates intervention efficacy (containment speed, precision, baseline preservation, rollback reliability).

By decoupling policy generation from handler execution, the framework ensures that non-triggered detections (Scenario A) skip protection automatically, eliminating false mitigations.

---

## 8. Structured Research Observations

1. **Blockchain Interaction Alone is Non-Malicious:** Legitimate enterprise dApps, NFT platforms, and decentralized finance protocols issue the same JSON-RPC methods (`eth_call`, `eth_sendTransaction`) as synthetic C2 channels. Labeling blockchain access alone as malicious leads to unacceptable false-alarm rates.
2. **Cross-Layer Evidence Bridges the Semantic Gap:** Telemetry from any single layer provides insufficient context. Endpoint context identifies the process; RPC context identifies the target contract; network context reveals egress beaconing. Detection is possible only at their intersection.
3. **Temporal Ordering is a Critical Discriminator:** Inverting the sequence (e.g. network connection occurring *before* blockchain interaction) invalidates the C2 hypothesis. Causal timing ($\Delta t > 0$) is essential for high precision.
4. **Negative Controls are Methodologically Indispensable:** Without Scenario A, detection rules could easily overfit to any blockchain activity. Negative control testing validates specificity.
5. **Application-Layer Interventions are Feasible and Safe:** While defenders cannot alter external blockchain consensus, they possess full authority over the local RPC proxy and host egress. Application-layer filtering avoids risky kernel modifications.
6. **Evidence Preservation Must Precede Containment:** Isolating a process or filtering network traffic may cause client processes to terminate or alter internal state. Forensic snapshotting must capture artifacts before active intervention.
7. **Mitigation Requires Verification Probing:** A defensive framework must not assume an API call succeeded. Active probing (e.g. testing whether `/beacon` actually returns HTTP 403) is essential before declaring containment verified.
8. **Automated Rollback Restores Research Baseline:** Clean rollback enables high-throughput laboratory experimentation without requiring container or OS restarts.
9. **Controlled Fault Injection Demonstrates Robustness:** Injecting invalid actions (such as unapproved PIDs) confirms that handlers fail gracefully without crashing or touching arbitrary OS processes.
10. **Forensic Hashing Guarantees Chain of Custody:** Generating SHA-256 integrity checksums over detection evidence bundles guarantees auditability and non-repudiation for incident responders.

---

## 9. Research Limitations

To maintain scientific integrity, the following limitations are explicitly documented:

- **Controlled Laboratory Environment:** Experiments were conducted on a single host (`127.0.0.1`) using local socket bindings. Real-world enterprise environments introduce network jitter, NAT gateways, DNS tunneling, proxy chains, and high-volume background traffic.
- **Synthetic Behavioral Models:** The `C2DataStore` contract and client represent a model of blockchain dead-drop communication. Real-world adversaries may utilize steganography, encrypted transaction calldata, decentralized storage (IPFS, Arweave), or zero-knowledge rollups.
- **Sample Size:** Benchmarks comprised 20 detection runs and 22 protection runs. While statistically sufficient for a deterministic testbed, broad statistical variance under noisy enterprise networks was not measured.
- **Single EVM Platform:** Evaluated on Hardhat EVM (Chain ID 31337). Behavior across non-EVM blockchains (e.g. Solana, Bitcoin, Cosmos) or layer-2 rollups was not evaluated.
- **Application-Layer Proxy Dependence:** The RPC filter requires traffic to traverse the monitored `RpcProxy`. Adversaries with local administrative privileges could bypass a user-space proxy by resolving endpoints directly.
- **Cooperative Process Isolation:** Process containment relies on cooperative signaling via `ScenarioWorkerRegistry`. Malicious, adversarial code designed for evasion would require kernel-level sandboxing, EDR process suspension, or container termination.
- **No Claim of Real-World Efficacy:** The 100% detection and mitigation rates achieved in this study quantify performance on our predefined synthetic models; they must not be interpreted as a claim of 100% efficacy against real-world advanced persistent threats.

---

## 10. Security Implications

- **Decentralized Infrastructure as a Blind Spot:** As Web3 technologies integrate into enterprise workflows, corporate endpoints increasingly connect to blockchain nodes. Security Operations Centers (SOCs) that fail to monitor JSON-RPC endpoints will have a visibility blind spot.
- **The Telemetry Opportunity:** Standard JSON-RPC calls (`eth_call`, `eth_getLogs`) are unencrypted over HTTP unless wrapped in TLS. By deploying local RPC inspection proxies or monitoring localhost RPC daemon logs, defenders gain rich, actionable security telemetry.
- **Avoiding Over-Blocking:** Banning all blockchain traffic risks disrupting legitimate business dApps. Defenses must be behavioral, discriminating based on cross-layer causality rather than destination port or protocol alone.
- **Defense-in-Depth:** A robust response requires layered actions: preserving evidence immediately, containing local network egress, filtering malicious contract calls at the proxy, and cooperatively pausing suspect processes.

---

## 11. Research Contribution & Novelty Position

### Research Positioning
The use of blockchains for covert signaling and C2 dead-drops has been established in prior academic literature (e.g. Bitcoin OP_RETURN data storage, smart contract event logging).

The contribution of **ChainC2 Sentinel** is **not** the discovery of blockchain-mediated C2 as a threat concept. Rather, the research contributes:
1. **A Defensive, Multi-Layer Telemetry Architecture:** A formal schema (`SentinelEvent`) unifying endpoint, JSON-RPC, smart contract, and network telemetry into a common format.
2. **Deterministic Cross-Layer Correlation:** A correlation engine that reconstructs causal behavioral chains and calculates causal delta times ($\Delta t$) across heterogeneous telemetry sources.
3. **Transparent, Explainable Rule-Based Detection:** A detection model (`RULE-CHAINC2-001`) that evaluates 7 observable conditions with zero reliance on opaque, non-deterministic machine learning.
4. **An Application-Layer Defensive Response System:** A layered mitigation framework providing RPC contract filtering, network containment, cooperative process isolation, and SHA-256 evidence snapshotting with sub-4ms response latency.
5. **Rigorous Empirical Negative-Control Testing:** Demonstrating 0.0% false alarms and 0.0% false mitigations against legitimate Web3 baseline activity across repeated trials.
6. **Fully Reproducible Experimental Testbed:** All smart contracts, collectors, scenarios, evaluators, and raw datasets are open, automated, and verifiable via automated test suites.

---

## 12. Final Conclusions

### Answer to Research Question 1 (RQ1)
> *"Can cross-layer telemetry correlation detect blockchain-mediated C2-like behavioral sequences while distinguishing them from legitimate Web3 activity?"*

**Conclusion:** **Yes.** Within a controlled laboratory environment, blockchain-mediated C2-like sequences can be detected with high reliability (100.0% detection rate, 0.0% false-positive rate across both basic and realistic DApp negative controls, ~0.102 ms latency) when host endpoint activity, RPC interactions, and subsequent network beacons are temporally and causally correlated using explainable weighted scoring. Negative-control testing confirms that legitimate Web3 dApp interactions (Scenario A and Scenario C) are not erroneously classified as malicious.

### Answer to Research Question 2 (RQ2)
> *"Once the behavior is detected, what defensive measures can be applied?"*

**Conclusion:** **Layered application-layer mitigations can rapidly and safely contain the behavior.** The implemented framework achieves a 100.0% mitigation success rate with an average containment latency of 2.091 ms. Subsequent C2 contract queries and beacon requests are blocked, registered scenario workers are cooperatively isolated, immutable forensic evidence is preserved, and legitimate Web3 activity remains 100.0% functional.

### Research Closure
ChainC2 Sentinel demonstrates that blockchain-mediated command-and-control behavior presents an observable multi-layer signature that can be reliably detected and safely contained through disciplined cross-layer telemetry and application-layer defenses.

---

## 13. Reproducibility & Source Artifacts

All metrics, rates, and latencies reported in this analysis are directly traceable to the machine-readable evaluation artifacts committed to the repository:

| Research Dimension | Raw JSON Dataset | Processed Summary / CSV |
|:---|:---|:---|
| **Phase 1 Detection** | [`data/evaluation/evaluation_results.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evaluation/evaluation_results.json) | [`results/detection/evaluation_summary.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/detection/evaluation_summary.json)<br>[`results/detection/detection_metrics.csv`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/detection/detection_metrics.csv)<br>[`results/detection/experiment_results.csv`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/detection/experiment_results.csv) |
| **Phase 2 Protection** | [`data/evaluation/protection_evaluation.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evaluation/protection_evaluation.json) | [`results/protection/evaluation_summary.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/protection/evaluation_summary.json)<br>[`results/protection/protection_metrics.csv`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/protection/protection_metrics.csv)<br>[`results/protection/experiment_results.csv`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/protection/experiment_results.csv) |
| **Forensic Evidence** | [`data/evidence/`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evidence/) | 10 JSON evidence bundles with SHA-256 integrity checksums |
| **Consolidated Summary** | [`results/final/research_summary.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/results/final/research_summary.json) | Consolidated research summary covering both research questions |

### Test Verification Commands
```bash
# Execute Python unit and integration test suite
python -m pytest tests/ -v --strict-markers -m unit

# Execute Hardhat smart contract verification suite (35 passing)
npx hardhat test
```
