# ChainC2 Sentinel

### A Cybersecurity Framework for Detecting Blockchain-Mediated Command-and-Control Channels

**Engineering Capstone Project – I**  
**B.Tech Computer Science and Engineering – Cybersecurity**  
**Academic Year: 2026–2027**

---

## Project Title

**ChainC2 Sentinel: A Cybersecurity Framework for Detecting Blockchain-Mediated Command-and-Control Channels**

---

## Team Members

| S. No. | University ID | Name |
|:------:|:-------------:|:-----|
| 1 | 2320030094 | Surakanti Rithik Reddy |
| 2 | 2320030097 | Karthikeya Sukka |
| 3 | 2320030307 | Abhinav Kavarthapu |

---

## Project Supervisor

**Dr. V. Muniraju Naidu**

---

## Abstract

The increasing use of decentralized technologies has introduced new cybersecurity challenges, including the abuse of public blockchains as Command-and-Control (C2) infrastructure by malware. Unlike conventional Web2-based C2 systems, which commonly rely on centralized servers, domains, or IP addresses that can potentially be blocked or taken down, blockchain-mediated C2 can use blockchain transactions, smart contracts, and decentralized services as persistent communication or information-discovery mechanisms. ChainC2 Sentinel is a defensive cybersecurity framework proposed to detect and analyze such activity by correlating endpoint behavior with blockchain interactions and subsequent network activity. The framework will monitor suspicious processes, blockchain/RPC requests, smart-contract interactions, transaction data, and related network connections to identify potentially malicious communication patterns. A controlled laboratory environment will be used to simulate legitimate Web3 activity alongside safe blockchain-mediated C2 scenarios. The resulting telemetry will be correlated to investigate whether cross-layer behavioral analysis can improve the detection of suspected blockchain-mediated C2 while distinguishing it from legitimate blockchain usage. The project will be evaluated using measurable security metrics including detection accuracy, false-positive rate, and detection latency.

---

## Setup & Execution Instructions

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### Installation

```bash
# Clone the repository
git clone https://github.com/KarthikeyaSukka756/KLH-CSE-Y23-2320030097-ChainC2-Sentinel.git
cd KLH-CSE-Y23-2320030097-ChainC2-Sentinel

# Install Python dependencies
pip install -r requirements.txt

# Install Hardhat and blockchain dependencies
cd src/blockchain
npm install
cd ../..
```

### Running Tests

```bash
# Run Python unit tests (telemetry schema, collectors, normalizer, persistence)
python -m pytest tests/ -v --strict-markers -m unit

# Run Hardhat contract tests (C2DataStore, BenignDAppContract)
cd src/blockchain
npx hardhat test
```

### Development Environment

- **Python** — telemetry collectors, event schema, normalizer, persistence
- **Node.js / Hardhat** — local EVM environment, smart contract compilation and testing
- **Pydantic v2** — event schema validation
- **aiohttp** — RPC telemetry proxy
- **Solidity** — synthetic smart contracts (C2DataStore, BenignDAppContract)
- **ethers.js** — contract deployment and testing

All blockchain activity is local and synthetic. No public blockchains are used.

---

## Current Phase Status

**Current Phase:** Phase 2 — Protection  
**Research Question:** *"Once blockchain-mediated C2-like behavior is detected, what controlled defensive measures can be applied to reduce or contain the observed behavior?"*  
**Status:** 🟢 **Milestone 8 & Milestone 9 Complete (Defensive Response Design & Controlled Mitigation Implemented)**

### Completed Phase 1 Milestones

#### Milestone 1 — Project Infrastructure
- Project repository architecture, environment configuration, and dependency management
- Testing frameworks configured (`pytest`, `pytest-asyncio`, Hardhat/Mocha)

#### Milestone 2 — Synthetic Blockchain Environment
- Local Hardhat EVM environment (chain ID 31337)
- `C2DataStore` Solidity contract — synthetic research data store for safe C2 simulation
- `BenignDAppContract` Solidity contract — counter/message DApp for legitimate Web3 baseline activity
- Automated contract deployment script
- Hardhat contract test suite (26 passing)

#### Milestone 3 — Telemetry Foundation
- `SentinelEvent` normalized telemetry schema (Pydantic v2, strict validation)
- Four source-specific telemetry collectors:
  - **Endpoint** — safe local process metadata (current process only; no OS-wide enumeration)
  - **RPC** — JSON-RPC request/response metadata with client-facing proxy and upstream Hardhat node distinction
  - **Blockchain** — synthetic smart-contract interaction metadata (C2DataStore and BenignDAppContract)
  - **Network** — controlled local HTTP/network activity metadata (no packet capture)
- RPC telemetry proxy (aiohttp) — forwards requests between Web3 client and local Hardhat node while capturing telemetry; this is monitoring infrastructure, not attacker C2
- Event normalizer — validates and converts raw collector output into the common SentinelEvent schema
- JSONL event store — append-only file-based persistence (`data/telemetry/events.jsonl`) with replaceable interface
- Utility modules — UUID generation, structured JSON logging
- Telemetry architecture documentation

#### Milestone 4 — Controlled Detection Scenarios
- `LocalHttpTargetServer` — controlled HTTP server strictly bound to 127.0.0.1 with audit logging
- `SyntheticC2Payload` — safe inert configuration model and validator (restricting actions strictly to 'BEACON' and targets to localhost)
- `BenignWeb3Scenario` (Scenario A) — negative control executing legitimate BenignDAppContract interactions with zero follow-up network activity
- `SyntheticC2Scenario` (Scenario B) — synthetic blockchain-mediated C2-like behavior generating the complete 4-layer telemetry chain (Endpoint → RPC → Blockchain → Network)
- `ScenarioRunner` — scenario orchestrator with structured execution summaries and JSONL telemetry persistence

#### Milestone 5 — Cross-Layer Correlation
- `CrossLayerCorrelationEngine` — deterministic correlation engine reconstructing multi-layer evidence chains across telemetry layers
- `CorrelatedSequence` & `EventTransition` — structured models explicitly capturing temporal ordering, layer transitions, and causal time deltas ($\Delta t$)
- Scenario A correlation: accurately reconstructs legitimate Web3 activity and confirms zero follow-up network activity
- Scenario B correlation: accurately reconstructs the complete 4-layer evidence chain (Endpoint → RPC → Blockchain → Network)
- Robustness: handles incomplete/missing event sequences, out-of-order event ingestion, and separates mixed multi-scenario streams without leakage

#### Milestone 6 — Detection
- `DetectionEngine` — explainable, deterministic detection engine evaluating factual correlated behavioral sequences against explicit rule sets
- `SyntheticC2SequenceRule` (`RULE-CHAINC2-001`) — deterministic rule verifying 7 observable behavioral conditions (Endpoint → RPC → Blockchain `C2DataStore` → Subsequent Network follow-up)
- Structured `DetectionResult` — factual evidence summaries preserving matched conditions, contract/function details, network destination, time deltas, and execution timeline
- Negative-control verification: confirmed non-triggering on legitimate Web3 activity (Scenario A), benign contract interactions followed by network activity, inverted event timing, and incomplete sequences

#### Milestone 7 — Detection Evaluation
- `DetectionEvaluator` — configurable experimental evaluation orchestrator for repeated execution and statistical analysis
- Structured evaluation models: `ExperimentRecord`, `EvaluationMetrics`, and `AggregateEvaluationResult` with safe zero-denominator handling
- Benchmark evaluation dataset persisted to `data/evaluation/evaluation_results.json` and research summary artifacts in `results/detection/`
- Empirical laboratory benchmark (20 runs): 100% detection rate (recall), 0.0% false-positive rate, 100% precision, 100% accuracy, ~0.048ms average detection latency

### Completed Phase 2 Milestones

#### Milestone 8 — Defensive Response Design
- Formal defensive response specification: `docs/DEFENSIVE_RESPONSE_SPEC.md`
- Structured response models: `DefensePlan`, `MitigationAction`, `DefenseExecutionRecord` in `src/protection/models.py`
- Abstract responder interfaces: `BaseMitigationHandler`, `BaseEvidencePreserver` in `src/protection/interfaces.py`
- Policy engine: `DefensivePolicyEngine` in `src/protection/policy.py` mapping detection evidence to layered defense actions with safety boundary enforcement
- Strict negative-control bypass: confirmed non-triggered detections (Scenario A) yield zero defensive actions (`status=SKIPPED`)

#### Milestone 9 — Controlled Protection / Mitigation
- Concrete mitigation handlers adhering to `BaseMitigationHandler`:
  - `RpcFilterHandler`: Application-layer RPC proxy filter rejecting queries targeting synthetic `C2DataStore` while leaving benign contract calls unaffected
  - `NetworkContainmentHandler`: Application-layer containment on `LocalHttpTargetServer` rejecting synthetic `/beacon` requests with HTTP 403 while preserving `/health`
  - `ProcessIsolationHandler`: Cooperative laboratory scenario worker isolation via `ScenarioWorkerRegistry`, strictly refusing arbitrary host process termination
  - `EvidenceSnapshotHandler`: Immutable forensic evidence bundle generation under `data/evidence/` with SHA-256 integrity checksums
#### Milestone 10 — Protection Evaluation
- `ProtectionEvaluator` — configurable experimental orchestrator evaluating defensive responses across repeated runs
- Structured evaluation models: `ProtectionExperimentRecord`, `ProtectionEvaluationMetrics`, and `AggregateProtectionEvaluationResult`
- Measured dimensions across 22 controlled laboratory experiments (10 Benign Scenario A, 10 Synthetic C2 Scenario B, 2 Fault Injection):
  - **Mitigation Success Rate:** 100.0% ($40/40$ actions verified across positive control runs)
  - **RPC Blocking Rate:** 100.0% ($10/10$ synthetic C2DataStore queries blocked)
  - **Beacon Blocking Rate:** 100.0% ($10/10$ synthetic beacon requests rejected with HTTP 403)
  - **Process Isolation Success Rate:** 100.0% ($10/10$ registered scenario workers cooperatively contained)
  - **Legitimate Traffic Preservation:** 100.0% ($22/22$ runs maintained benign dApp and /health availability)
  - **False Mitigation Rate:** 0.0% ($0/10$ benign Scenario A runs received mitigation)
  - **Rollback Success Rate:** 100.0% ($10/10$ rollbacks verified baseline restoration)
  - **Evidence Preservation Rate:** 100.0% ($10/10$ positive control runs generated valid SHA-256 evidence bundles)
  - **Containment Latency:** 2.09ms avg (min: 1.49ms, max: 3.56ms)
- Machine-readable raw dataset persisted at `data/evaluation/protection_evaluation.json` and processed research artifacts in `results/protection/`

---

## Project Structure

```
src/
├── blockchain/          # Hardhat environment, Solidity contracts, deployment, tests
│   ├── contracts/       # C2DataStore.sol, BenignDAppContract.sol
│   ├── scripts/         # Contract deployment script
│   └── test/            # Hardhat/Mocha contract tests
├── collectors/          # Telemetry collectors (endpoint, RPC, blockchain, network)
├── correlation/         # Cross-layer correlation engine, sequence & transition models
├── detection/           # Explainable rule-based detection engine, rules, and result models
├── evaluation/          # Experimental detection evaluation orchestrator, metrics, and report models
├── http_target/         # Controlled local HTTP target server (127.0.0.1)
├── models/              # SentinelEvent Pydantic v2 schema and sub-models
├── normalizer/          # Event normalizer and JSONL persistence
├── protection/          # Phase 2 Defensive response & mitigation framework
│   ├── evaluation/      # Protection evaluation orchestrator, metrics models, and artifact exporter
│   ├── handlers/        # Concrete mitigation handlers (RPC, network, process, evidence)
│   ├── executor.py      # DefenseExecutor orchestrator with verification & rollback
│   ├── interfaces.py    # Abstract responder contracts (BaseMitigationHandler, BaseEvidencePreserver)
│   ├── models.py        # Pydantic v2 models (DefensePlan, MitigationAction, DefenseExecutionRecord)
│   ├── policy.py        # DefensivePolicyEngine mapping detections to defense plans
│   └── process_registry.py # Controlled scenario worker registry (cooperative isolation)
├── rpc_proxy/           # aiohttp JSON-RPC telemetry proxy with application-layer contract filtering
├── scenarios/           # Laboratory scenarios (Scenario A benign, Scenario B C2)
│   ├── definitions/     # Concrete scenario implementations
│   ├── payload.py       # Safe inert C2 payload schema and validator
│   └── runner.py        # Scenario execution orchestrator
└── utils/               # UUID generation, structured logging
tests/                   # Python unit tests (154 tests covering collectors, correlation, detection, evaluation, protection, scenarios)
docs/                    # Architecture documentation, development plan, defensive response specification
data/
├── evaluation/          # Machine-readable evaluation reports (detection & protection JSON)
└── evidence/            # Preserved immutable forensic evidence snapshots (JSON)
results/
├── detection/           # Processed detection research artifacts (summary JSON, metrics CSV, experiment history CSV)
└── protection/          # Processed protection research artifacts (summary JSON, metrics CSV, experiment history CSV)
```

---

## Validation Results

| Test Suite / Benchmark | Metric / Count | Result | Status |
|:---|:---:|:---:|:---:|
| Python Unit Tests (all modules) | 154 tests | 100% passing (11.02s) | ✅ Passing |
| Hardhat Contract Tests (Solidity) | 26 tests | 100% passing (855ms) | ✅ Passing |
| Scenario B Detection Rate (Recall) | 10 positive runs | 100.0% ($TP / [TP+FN]$) | ✅ Measured |
| Scenario A False-Positive Rate | 10 negative runs | 0.0% ($FP / [FP+TN]$) | ✅ Measured |
| Detection Precision | 10 triggered runs | 100.0% ($TP / [TP+FP]$) | ✅ Measured |
| Detection Processing Latency | 20 evaluated runs | ~0.048ms avg (min: 0.025ms, max: 0.092ms) | ✅ Measured |
| Mitigation Success Rate | 10 positive runs (40 actions) | 100.0% ($40/40$ verified) | ✅ Measured |
| RPC Blocking Rate | 10 positive runs | 100.0% ($10/10$ blocked) | ✅ Measured |
| Beacon Blocking Rate | 10 positive runs | 100.0% ($10/10$ rejected HTTP 403) | ✅ Measured |
| Process Isolation Success Rate | 10 positive runs | 100.0% ($10/10$ isolated) | ✅ Measured |
| False Mitigation Rate | 10 negative runs | 0.0% ($0/10$ mitigated) | ✅ Measured |
| Legitimate Traffic Preservation | 22 evaluated runs | 100.0% ($22/22$ preserved) | ✅ Measured |
| Rollback Success Rate | 10 positive runs | 100.0% ($10/10$ restored) | ✅ Measured |
| Containment Latency | 10 evaluated runs | ~2.09ms avg (min: 1.49ms, max: 3.56ms) | ✅ Measured |

*Note: The above metrics represent empirical laboratory evaluation on controlled synthetic scenarios. They quantify detectability and response in our controlled environment and do not assert real-world malware efficacy.*

---

## Project Status

**Current Research Phase:** Phase 2 — Protection (Milestones 8, 9, & 10 Complete)  
**Next Research Target:** Phase 2 — Protection, Milestone 11 — Final Research Analysis  

| Research Phase | Milestone | Focus Area | Status |
|:---|:---|:---|:---|
| **Phase 1 — Detection** | Milestone 1 | Project Infrastructure | ✅ Complete |
| **Phase 1 — Detection** | Milestone 2 | Synthetic Blockchain Environment | ✅ Complete |
| **Phase 1 — Detection** | Milestone 3 | Telemetry Foundation | ✅ Complete |
| **Phase 1 — Detection** | Milestone 4 | Controlled Detection Scenarios | ✅ Complete |
| **Phase 1 — Detection** | Milestone 5 | Cross-Layer Correlation | ✅ Complete |
| **Phase 1 — Detection** | Milestone 6 | Detection | ✅ Complete |
| **Phase 1 — Detection** | Milestone 7 | Detection Evaluation | ✅ Complete |
| **Phase 2 — Protection** | Milestone 8 | Defensive Response Design | ✅ Complete |
| **Phase 2 — Protection** | Milestone 9 | Controlled Protection / Mitigation | ✅ Complete |
| **Phase 2 — Protection** | Milestone 10 | Protection Evaluation | ✅ Complete |
| **Phase 2 — Protection** | Milestone 11 | Final Research Analysis | ⏳ Next Target |