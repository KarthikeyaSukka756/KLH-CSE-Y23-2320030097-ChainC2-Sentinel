# PRC-III: Comprehensive Academic Defense & Technical Deliverable
## ChainC2 Sentinel: A Cybersecurity Framework for Detecting Blockchain-Mediated Command-and-Control Channels

**Department of Computer Science and Engineering**
**Koneru Lakshmaiah Education Foundation (KLH), Hyderabad, India**
**B.Tech Engineering Capstone Project – I (2026–2027)**

---

### Project Identity & Academic Metadata

- **Project Title:** ChainC2 Sentinel: A Cybersecurity Framework for Detecting Blockchain-Mediated Command-and-Control Channels
- **Department:** Computer Science and Engineering — Cybersecurity Specialization
- **Institution:** Koneru Lakshmaiah Education Foundation (KLH), Hyderabad, India
- **Academic Year:** 2026–2027
- **Team Members:**
  1. **Surakanti Rithik Reddy** (University ID: `2320030094`)
  2. **Karthikeya Sukka** (University ID: `2320030097`)
  3. **Abhinav Kavarthapu** (University ID: `2320030307`)
- **Project Supervisor:** **Dr. V. Muniraj Naidu**, Associate Professor, Department of Computer Science and Engineering, KLH Hyderabad

---

## 1. Project Introduction

Command-and-Control (C2) infrastructure is the operational backbone of modern persistent malware campaigns. Attackers rely on C2 channels to deliver commands, exfiltrate credentials, and coordinate lateral movement. Historically, defenders have combated C2 infrastructures by identifying centralized command nodes and executing domain sinkholing, IP-based boundary blacklisting, or SSL/TLS certificate revocation.

The advent of decentralized, permissionless smart-contract platforms (e.g., Ethereum, Polygon, Arbitrum) introduces an evasion vector. Malware authors can exploit public blockchains as **decentralized dead-drop resolvers**. Instead of hardcoding an IP or querying a dynamic DNS domain, malware queries a smart contract on a decentralized ledger using standard JSON-RPC gateways over HTTPS (`eth_call`). Because blockchains are immutable and permissionless, the stored C2 instructions cannot be seized, modified, or taken down by law enforcement or internet service providers.

**ChainC2 Sentinel** is an end-to-end defensive cybersecurity research framework designed to detect, analyze, and mitigate blockchain-mediated C2 channels. Rather than treating blockchain and host activity as isolated silos, ChainC2 Sentinel correlates host endpoint execution, JSON-RPC queries, smart-contract calldata, and subsequent local network connections into a unified causal graph, evaluating explainable weighted rules to detect threats in sub-millisecond time.

---

## 2. Problem Statement

Modern enterprise networks face three critical challenges when addressing blockchain-mediated C2 channels:

1. **The Invalidation of Takendown Defenses:** Conventional threat mitigation depends on the seizure or takedown of centralized infrastructure (DNS registrars, VPS providers, BGP routing). Public blockchains have no centralized administrative point of failure; smart contracts are immutable and permanently accessible.
2. **Encrypted RPC Gateway Blinding:** Endpoint hosts interact with blockchains using standard JSON-RPC protocols over HTTPS targeting legitimate providers (e.g., Infura, Alchemy, PublicNode) or enterprise RPC nodes. Because destination IP addresses and ports (TCP 443) belong to legitimate services, conventional perimeter firewalls and Network Intrusion Detection Systems (NIDS) cannot distinguish malicious dead-drop queries from legitimate decentralized finance (DeFi) activity.
3. **Endpoint-to-Network Correlation Void:** Traditional Host Intrusion Detection Systems (HIDS) monitor processes but lack smart-contract context. Conversely, on-chain analytics platforms monitor ledgers but lack host process attribution. Neither system can establish whether a process executed an RPC call and subsequently used the retrieved calldata to beacon out to a remote server.

---

## 3. Project Objectives

1. **Design a Unified Telemetry Schema:** Implement a strict, normalized event model (`SentinelEvent`) capturing four layers: Endpoint (PID, executable hash), RPC (method, gateway), Blockchain (contract, function selector, calldata), and Network (target IP, port, URI).
2. **Develop a Deterministic Cross-Layer Correlation Engine:** Build a time-sliding window correlation engine that reconstructs causal behavioral chains ($\Delta t \le 120\text{s}$) across heterogeneous log sources.
3. **Establish an Explainable Heuristic Detection Model:** Formulate a scoring algorithm (`RuleBasedScorer`) allocating transparent weights (+10, +10, +15, +20, +20, +25) with an 80.0-point threshold, producing verifiable forensic explanations.
4. **Build a Controlled Local Laboratory Testbed:** Develop a local Hardhat EVM (Chain ID 31337) and synthetic Solidity smart contracts (`C2DataStore`, `BenignDAppContract`, `LegitimateDAppContract`) to safely test scenarios with zero malware and zero public mainnet exposure.
5. **Rigorously Evaluate Detection and Mitigation:** Execute empirical evaluation campaigns measuring Recall, Precision, Specificity, Accuracy, False-Positive Rate, and Containment Latency across positive and negative controls.
6. **Implement Coordinated Application-Layer Defenses:** Develop an automated policy engine executing RPC contract filtering, network containment, cooperative worker isolation, and SHA-256 forensic snapshotting.

---

## 4. Literature Review & Verified Citations

| Reference & Author(s) | Venue & Year | Core Focus | Comparison with ChainC2 Sentinel |
|:---|:---|:---|:---|
| **Ali, R., et al.** | *IEEE S&P*, 2020 | Explores how adversaries abuse Ethereum smart contracts as attack proxies to coordinate multi-stage exploits. | Focused exclusively on offensive feasibility; ChainC2 Sentinel provides defensive multi-layer telemetry correlation and detection. |
| **Purtell, K., & Buescher, M.** | *Journal of Cybersecurity*, 2021 | Categorizes C2 techniques over distributed ledgers, including Bitcoin OP_RETURN and Ethereum contract calldata. | Theoretical taxonomy lacking an empirical implementation of real-time detection systems. |
| **Trend Micro Research** | *Threat Defense Brief*, 2019 | Analyzed the Glupteba botnet, which queried Bitcoin transactions as a backup mechanism to discover C2 addresses. | Post-mortem reverse engineering; did not build a host-level correlation engine to detect queries in real time. |
| **Zimba, A., et al.** | *Computers & Security*, 2019 | Demonstrated multi-stage ransomware detection by correlating process, filesystem, and network telemetry. | Restricted to conventional Web2 ransomware; did not consider blockchain RPC gateways or decentralized storage. |
| **Antonakakis, M., et al.** | *USENIX Security*, 2017 | Evaluated the Mirai botnet architecture, DNS lookup behavior, and domain sinkholing strategies. | Presumes centralized domain infrastructure; completely ineffective against immutable on-chain smart contracts. |
| **Scarfone, K., & Mell, P.** | *NIST SP 800-94*, 2007 | Established fundamental criteria for intrusion detection, event normalization, and false-positive reduction. | Serves as the architectural foundation for ChainC2 Sentinel's normalized schema and zero-denominator metrics. |

---

## 5. Research Gap Identification

Prior research has created three distinct silos:
```
┌─────────────────────────┐       ┌─────────────────────────┐       ┌─────────────────────────┐
│     ON-CHAIN DATA       │       │    JSON-RPC GATEWAYS    │       │     HOST ENDPOINT       │
│  - Ledger Analytics     │  ≠    │  - Transport Layer TLS  │  ≠    │  - EDR / Process Logs   │
│  - Explorer Scraping    │       │  - Opaque Packet Data   │       │  - Network Sockets      │
│  (No host attribution)  │       │  (Blind to application) │       │  (No contract context)  │
└─────────────────────────┘       └─────────────────────────┘       └─────────────────────────┘
```
**The Research Gap:**
No defensive system has connected these three layers in real time. Naive detection rules that flag any host making JSON-RPC requests generate massive false positives in legitimate Web3 environments. A robust framework must analyze the **causal sequence** from process execution $\to$ RPC query $\to$ contract data extraction $\to$ network beaconing.

---

## 6. Existing vs. Proposed Methodology

| Dimension | Existing Conventional Solutions | ChainC2 Sentinel Framework |
|:---|:---|:---|
| **Detection Basis** | Static IP/domain blacklisting, SNI domain filtering | Behavioral cross-layer causality and temporal parameter correlation |
| **C2 Take Down** | DNS sinkholing, ISP domain seizure | Application-layer RPC proxy filtering and local network containment |
| **Web3 Awareness** | Blind to JSON-RPC payload content (treats port 443 as generic) | Deep inspection of function selectors, contract targets, and calldata |
| **False-Positive Defense** | High false alarms on developer/Web3 endpoints | Zero false alarms ($0.0\%$) verified against multi-step DApp baselines |
| **Explainability** | Black-box ML models prone to hallucination | Factual, deterministic scoring broken down by individual rule criteria |
| **Forensic Preservation** | Ephemeral system logs easily lost or tampered | Cryptographically hashed (SHA-256) JSON evidence bundles |

---

## 7. System Architecture & Telemetry Pipeline

```mermaid
flowchart LR
    subgraph Sources["1. Telemetry Sources"]
        EP["Endpoint Collector (Process PID, Hash)"]
        RPC["RPC Collector (eth_call, Params)"]
        BC["Blockchain Collector (Calldata, Block #)"]
        NET["Network Collector (Target IP, URI)"]
    end

    subgraph CoreEngine["2. Normalization & Correlation"]
        NORM["Normalizer (SentinelEvent Pydantic v2)"]
        STORE[("JSONL Storage: events.jsonl")]
        CORR["Correlation Engine (Window: delta-t <= 120s)"]
        GRAPH["Causal Transition Sequence Graph"]
    end

    subgraph DetectionMitigation["3. Detection & Mitigation"]
        SCORER["RuleBasedScorer (Max 100, Threshold 80)"]
        DET["DetectionEngine (RULE-CHAINC2-001)"]
        DEF["DefensivePolicyEngine"]
        EXEC["DefenseExecutor (RPC, Net, Process, Evidence)"]
    end

    EP --> NORM
    RPC --> NORM
    BC --> NORM
    NET --> NORM
    NORM --> STORE
    STORE --> CORR
    CORR --> GRAPH
    GRAPH --> SCORER
    SCORER --> DET
    DET --> DEF
    DEF --> EXEC
```

---

## 8. Implementation Details

- **Backend & Detection Pipeline:** Developed in Python 3.10+ using `Pydantic v2` for strict type enforcement, `Flask` for REST API endpoints, and `aiohttp` for the non-blocking RPC proxy.
- **Smart Contract Environment:** Written in Solidity 0.8.20 and deployed on Hardhat EVM (Node.js 18+):
  - `C2DataStore.sol`: Stores synthetic payload metadata (`0x9a2d834f` selector).
  - `BenignDAppContract.sol`: Counter/greeting contract simulating basic legitimate Web3 activity (`0xa87d942c` selector).
  - `LegitimateDAppContract.sol`: Multi-step task registry contract simulating enterprise DApp workflows (`0xc17a340e` selector).
- **Public Ethereum Sepolia Monitor:** Read-only transaction observer connecting to Sepolia RPC (Chain ID 11155111). Features atomic `.tmp` + `os.replace` cursor persistence, monotonic sequential block advancement, and race-protected status caching.
- **Master Dashboard:** Single Page Application (SPA) built with vanilla ES6 JavaScript, HTML5, and CSS3. Provides real-time event streaming, causal timeline graphs, confusion matrices, and live SHA-256 evidence verification.

---

## 9. Controlled Experimental Methodology

The framework was evaluated across three controlled scenarios designed to stress-test detection accuracy and false-alarm resistance:

1. **Scenario A (Negative Control — Basic Benign Web3):**
   - Interacts with `BenignDAppContract.sol` by executing read calls (`getCount`).
   - Generates Endpoint, RPC, and Blockchain events with **zero** subsequent network beaconing.
   - *Expected Behavior:* Scoring criteria 4, 5, and 6 evaluate to 0 points. Score = $35.0 / 100.0 < 80.0 \implies \text{NOT\_TRIGGERED}$.
2. **Scenario B (Positive Control — Synthetic Blockchain C2):**
   - Executes an endpoint process querying `C2DataStore.sol` for an inert payload (`{"scenario": "synthetic_c2", "command": "BEACON", "target": "http://127.0.0.1:8080/beacon"}`).
   - Follows up with an HTTP POST beacon to the local target server.
   - Produces the complete 4-layer evidence chain (Endpoint $\to$ RPC $\to$ Blockchain $\to$ Network).
   - *Expected Behavior:* All 6 scoring criteria match. Score = $100.0 / 100.0 \ge 80.0 \implies \text{TRIGGERED}$.
3. **Scenario C (Negative Control — Realistic Multi-Step DApp Baseline):**
   - Executes a complete task lifecycle on `LegitimateDAppContract.sol`: `createTask` $\to$ `getTask` $\to$ `updateTask` $\to$ `getTask`.
   - Generates high-volume, multi-transaction telemetry with **zero** network follow-up.
   - *Expected Behavior:* Score = $35.0 / 100.0 < 80.0 \implies \text{NOT\_TRIGGERED}$.

---

## 10. Dataset & Empirical Evaluation Results

### 10.1 Phase 1: Detection Evaluation (30-Run Balanced Benchmark)
Evaluated across 10 Scenario A runs, 10 Scenario B runs, and 10 Scenario C runs:

```
                      PREDICTED POSITIVE        PREDICTED NEGATIVE
ACTUAL POSITIVE          TP = 10                     FN = 0
ACTUAL NEGATIVE          FP = 0                      TN = 20
```

- **Detection Rate (Recall):** $\frac{TP}{TP + FN} = \frac{10}{10 + 0} = \mathbf{100.0\%}$
- **False-Positive Rate (FPR):** $\frac{FP}{FP + TN} = \frac{0}{0 + 20} = \mathbf{0.0\%}$
- **Precision:** $\frac{TP}{TP + FP} = \frac{10}{10 + 0} = \mathbf{100.0\%}$
- **Specificity (TNR):** $\frac{TN}{TN + FP} = \frac{20}{20 + 0} = \mathbf{100.0\%}$
- **Accuracy:** $\frac{TP + TN}{\text{Total}} = \frac{10 + 20}{30} = \mathbf{100.0\%}$
- **F1 Score:** $2 \cdot \frac{P \cdot R}{P + R} = \mathbf{1.000}$
- **Average Detection Latency:** $\mathbf{0.102\text{ ms}}$ (min: $0.045\text{ ms}$, max: $0.688\text{ ms}$)

### 10.2 Phase 2: Defensive Response Evaluation (22 Experiments)
Evaluated across 10 positive control runs, 10 negative control runs, and 2 fault injection runs:

- **Mitigation Success Rate:** $\mathbf{100.0\%}$ ($40/40$ actions verified)
- **RPC Query Blocking Rate:** $\mathbf{100.0\%}$ ($10/10$ malicious queries blocked with HTTP 403)
- **Network Beacon Blocking Rate:** $\mathbf{100.0\%}$ ($10/10$ beacon requests blocked with HTTP 403)
- **Cooperative Process Isolation:** $\mathbf{100.0\%}$ ($10/10$ scenario workers paused safely)
- **Legitimate Traffic Preservation:** $\mathbf{100.0\%}$ ($22/22$ runs maintained benign dApp functionality)
- **False Mitigation Rate:** $\mathbf{0.0\%}$ ($0/10$ benign runs received mitigation)
- **Rollback Verification:** $\mathbf{100.0\%}$ ($10/10$ rollbacks restored baseline state)
- **Evidence Snapshot Integrity:** $\mathbf{100.0\%}$ ($10/10$ bundles verified via SHA-256)
- **Average Containment Latency:** $\mathbf{2.091\text{ ms}}$ (min: $1.49\text{ ms}$, max: $3.56\text{ ms}$)

### 10.3 Authoritative 81-Run Research Campaign (Matrix v2)
The locked academic campaign comprises 81 runs ($A=27, B=30, C=24$):
- Fully preserved in `data/evaluation/dataset_campaign/matrix_v2_81_results.json` (SHA-256: `15fa3d7e...`).
- 100% byte-for-byte verified by automated regression test suites.

---

## 11. Master Dashboard & CloudScale Operations

The Master Dashboard is fully operational locally and hosted on Zoho Catalyst CloudScale:
- **Web Client URL:** `https://project-rainfall-60091766377.development.catalystserverless.in/app/index.html`
- **AppSail Service URL:** `https://chainc2-sentinel-service-50046833542.development.catalystappsail.in`
- **Features:** 10 interactive SPA views, real-time live Sepolia monitoring, on-demand scenario execution with concurrency locks, and an evidence explorer with cryptographic SHA-256 verification.

---

## 12. Security Review & Limitations

### Ethical Safeguards & Invariants
- **Zero Real Malware:** All payloads are harmless, inert configuration models strictly targeting `127.0.0.1:8080/beacon`.
- **Zero Gas Cost:** Sepolia testnet observation is completely read-only ($0.00 gas spend). Zero mainnet transactions.
- **Zero Kernel Tampering:** Defensive controls operate strictly at the application layer without OS firewall or kernel-level interference.

### Research Limitations
1. **Single-Host Laboratory Binding:** Evaluated on localhost; real-world enterprise networks introduce packet loss, NAT, and background noise.
2. **Deterministic Payload Model:** Evaluated against structured JSON payloads; advanced adversaries may employ steganography or zero-knowledge rollups.
3. **Application-Layer Proxy Dependency:** The RPC filter requires traffic to traverse the proxy; local administrative bypass is out of scope.

---

## 13. Conclusion

ChainC2 Sentinel successfully proves the central research hypotheses:
1. **Answer to RQ1:** Cross-layer telemetry correlation reliably detects blockchain-mediated C2 channels ($100.0\%$ recall, $0.0\%$ false positives) while distinguishing them from legitimate Web3 DApp workloads in sub-millisecond time ($0.102\text{ ms}$).
2. **Answer to RQ2:** Layered application-layer defensive controls rapidly contain observed C2 communication within an average latency of $2.091\text{ ms}$ while preserving $100.0\%$ of legitimate Web3 operations.

The framework provides an open, fully reproducible foundation for enterprise Security Operations Centers (SOCs) to eliminate the blind spot of blockchain-mediated attack surfaces.

---
### End of PRC-III Comprehensive Defense Document
