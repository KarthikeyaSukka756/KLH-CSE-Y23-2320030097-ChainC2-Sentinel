# ChainC2 Sentinel Development Plan

## Project Overview

**ChainC2 Sentinel: A Cybersecurity Framework for Detecting Blockchain-Mediated Command-and-Control Channels**

ChainC2 Sentinel is a defensive cybersecurity research framework developed entirely within a controlled laboratory environment. All blockchain activity, endpoint monitoring, network communication, and simulated attack behaviors are synthetic and designed exclusively for safe local experimentation. No public blockchains or real malware/C2 infrastructure are utilized.

---

## Research Structure

The official ChainC2 Sentinel research roadmap follows a two-phase structure:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PHASE 1 — DETECTION                             │
│   Research Question: "Are blockchain-mediated C2 behaviors             │
│                       detectable?"                                     │
│                                                                        │
│   Milestones 1–7: Infrastructure, Synthetic EVM, Telemetry,            │
│                   Controlled Scenarios, Correlation, Detection,        │
│                   and Evaluation                                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        PHASE 2 — PROTECTION                            │
│   Research Question: "Once the behavior is detected, what defensive    │
│                       measures can be applied?"                        │
│                                                                        │
│   Milestones 8–11: Defensive Response Design, Controlled Mitigation,   │
│                    Protection Evaluation, and Final Research Analysis  │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 1 — Detection

#### Research Question
> *"Are blockchain-mediated C2 behaviors detectable?"*

#### Objectives
Phase 1 investigates whether blockchain-mediated C2-like behavior can be observed, normalized, correlated, and detected within a controlled cybersecurity laboratory. The objective is to reconstruct the multi-layer evidence chain and determine whether cross-layer telemetry can reliably differentiate synthetic C2 activity from legitimate Web3 interactions.

#### Intended Evidence Chain
```
Endpoint Process
       ↓
Blockchain/RPC Interaction
       ↓
Transaction / Smart Contract
       ↓
Retrieved Synthetic C2 Data / Configuration
       ↓
Subsequent Network Activity
       ↓
Cross-Layer Correlation
       ↓
Detection
       ↓
Evidence / Alert
```

#### Scope
Phase 1 includes:
- Controlled laboratory environment
- Synthetic blockchain environment
- Synthetic C2-like scenarios
- Endpoint telemetry
- RPC telemetry
- Blockchain telemetry
- Network telemetry
- Telemetry normalization
- Cross-source correlation
- Detection logic
- Evidence generation
- Detection evaluation

#### Milestones

- **Milestone 1 — Project Infrastructure**
  - Python/Node.js/Hardhat project setup
  - Directory structure and environment configuration
  - Testing frameworks (`pytest`, Hardhat/Mocha)

- **Milestone 2 — Synthetic Blockchain Environment**
  - Local Hardhat EVM (chain ID 31337)
  - `C2DataStore.sol` — synthetic research contract simulating C2 data-store operations
  - `BenignDAppContract.sol` — synthetic baseline contract simulating legitimate DApp behavior
  - Deployment scripts and automated contract test suite

- **Milestone 3 — Telemetry Foundation**
  - `SentinelEvent` common telemetry schema (Pydantic v2, strict validation)
  - Endpoint telemetry collector (safe local process metadata)
  - RPC telemetry collector and aiohttp RPC proxy (monitoring proxy distinct from upstream Hardhat node)
  - Blockchain telemetry collector (smart-contract event and transaction metadata)
  - Network telemetry collector (controlled local HTTP/network activity)
  - Event normalizer and JSONL file persistence (`data/telemetry/events.jsonl`)
  - Telemetry architecture documentation and automated unit tests

- **Milestone 4 — Controlled Detection Scenarios**
  - Legitimate Web3 baseline scenario (counter increment, message posting)
  - Synthetic blockchain-mediated C2-like scenario (configuration retrieval, subsequent local network activity)
  - Additional controlled scenarios as experimentally justified
  - Controlled local network activity targets

- **Milestone 5 — Cross-Layer Correlation**
  - Temporal correlation across event streams
  - Endpoint-to-RPC-to-blockchain-to-network relationship mapping
  - Evidence-chain reconstruction via correlation identifiers

- **Milestone 6 — Detection**
  - Detection logic and heuristic/behavioral rules
  - Suspicious behavior identification
  - Evidence generation and structured alert generation

- **Milestone 7 — Detection Evaluation**
  - Controlled experiment execution
  - Legitimate Web3 baseline comparison
  - Detection metrics where actually measured (precision, recall, F1, false-positive rate)
  - False-positive analysis
  - Detection-latency measurement

---

### Phase 2 — Protection

#### Research Question
> *"Once the behavior is detected, what defensive measures can be applied?"*

#### Objectives
Phase 2 begins after Phase 1 detection is established. It investigates how defensive measures can safely and effectively mitigate detected blockchain-mediated C2 behavior in a controlled environment. 

> [!IMPORTANT]
> Phase 2 is strictly defensive. All mitigation mechanisms remain controlled, defensive, and reversible within the laboratory. Phase 2 contains no offensive activity.

#### Scope
Phase 2 includes:
- Analysis of detected behavior
- Defensive response design
- Controlled mitigation mechanisms
- Protection and response implementation
- Evaluation of defensive effectiveness
- Final research analysis and documentation

#### Milestones

- **Milestone 8 — Defensive Response Design**
  - Identify appropriate defensive actions based on detected evidence
  - Define safe response boundaries within the controlled environment

- **Milestone 9 — Controlled Protection / Mitigation**
  - Implement defensive response mechanisms (e.g., process isolation, RPC throttling/blocking, network rule application)
  - Ensure all actions remain safe, controlled, and reversible in the laboratory

- **Milestone 10 — Protection Evaluation**
  - Evaluate the implemented defensive mechanisms
  - Compare system and communication behavior before and after mitigation under controlled experimental conditions

- **Milestone 11 — Final Research Analysis**
  - Final results aggregation and synthesis
  - Research limitations and future work discussion
  - Research conclusions and paper/deliverable documentation

---

## Current Implementation Status

| Phase | Milestone | Focus Area | Status |
|-------|-----------|------------|--------|
| **Phase 1** | **Milestone 1** | Project Infrastructure | ✅ **COMPLETE** |
| **Phase 1** | **Milestone 2** | Synthetic Blockchain Environment | ✅ **COMPLETE** |
| **Phase 1** | **Milestone 3** | Telemetry Foundation | ✅ **COMPLETE** |
| **Phase 1** | **Milestone 4** | Controlled Detection Scenarios | ✅ **COMPLETE** |
| **Phase 1** | **Milestone 5** | Cross-Layer Correlation | ✅ **COMPLETE** |
| **Phase 1** | **Milestone 6** | Detection | ✅ **COMPLETE** |
| **Phase 1** | **Milestone 7** | Detection Evaluation | ✅ **COMPLETE** |
| **Phase 2** | **Milestone 8** | Defensive Response Design | ✅ **COMPLETE** |
| **Phase 2** | **Milestone 9** | Controlled Protection / Mitigation | ✅ **COMPLETE** |
| **Phase 2** | **Milestone 10** | Protection Evaluation | ✅ **COMPLETE** |
| **Phase 2** | **Milestone 11** | Final Research Analysis | ✅ **COMPLETE** |

### Verified Current Repository Assets

- **Local Hardhat EVM:** Chain ID 31337, configured under `src/blockchain/`
- **Smart Contracts:** `C2DataStore.sol` and `BenignDAppContract.sol` compiled and tested
- **Telemetry Schema:** `SentinelEvent` Pydantic v2 model with strict schema validation
- **Collectors:** 4 modular collectors (`endpoint`, `rpc`, `blockchain`, `network`)
- **RPC Telemetry Proxy:** aiohttp proxy capturing JSON-RPC telemetry between client and Hardhat node
- **Normalization & Persistence:** `EventNormalizer` and JSONL `EventStore`
- **Controlled Laboratory Scenarios:**
  - `LocalHttpTargetServer` strictly bound to 127.0.0.1 with audit logging
  - `SyntheticC2Payload` safe inert configuration model and validator
  - `BenignWeb3Scenario` (Scenario A) — legitimate Web3 activity baseline with zero network follow-up
  - `SyntheticC2Scenario` (Scenario B) — synthetic blockchain-mediated C2-like behavior with local beaconing
  - `ScenarioRunner` orchestrator and reporting
- **Cross-Layer Correlation Engine:**
  - `CorrelatedSequence` & `EventTransition` models capturing evidence chains and layer transitions
  - `CrossLayerCorrelationEngine` reconstructing multi-stage causality with temporal ordering and delta-time calculations
- **Explainable Rule-Based Detection Layer:**
  - `SyntheticC2SequenceRule` evaluating 7 observable conditions across multi-layer evidence chains
  - `DetectionEngine` orchestrating rule evaluations with factual, transparent explanations
  - `DetectionResult` capturing matched/unmatched conditions and observable evidence
- **Detection Evaluation Framework (Milestone 7):**
  - `DetectionEvaluator` orchestrating repeated scenario experiments and computing deterministic statistical metrics
  - Structured models: `ExperimentRecord`, `EvaluationMetrics`, and `AggregateEvaluationResult`
  - Safe zero-denominator handling for all derived metrics
  - Machine-readable persistence (`data/evaluation/evaluation_results.json` and `results/detection/`)
  - Empirical 20-run benchmark: 100% detection rate, 0.0% false-positive rate, ~0.048ms average detection latency
- **Defensive Response Architecture (Milestone 8):**
  - Formal specification: `docs/DEFENSIVE_RESPONSE_SPEC.md`
  - Structured models: `DefensePlan`, `MitigationAction`, `DefenseExecutionRecord` in `src/protection/models.py`
  - Abstract responder contracts: `BaseMitigationHandler`, `BaseEvidencePreserver` in `src/protection/interfaces.py`
  - Policy engine: `DefensivePolicyEngine` in `src/protection/policy.py` mapping detection candidate evidence to layered defense actions with safety boundary enforcement
  - Strict negative-control bypass: confirmed non-triggered detections (Scenario A) yield zero defensive actions
- **Controlled Protection & Mitigation Handlers (Milestone 9):**
  - `RpcFilterHandler`: Application-layer RPC proxy filter blocking queries targeting synthetic `C2DataStore` while allowing benign contracts
  - `NetworkContainmentHandler`: Controlled HTTP containment on `LocalHttpTargetServer` rejecting `/beacon` requests with HTTP 403 while preserving `/health`
  - `ProcessIsolationHandler`: Cooperative laboratory worker isolation via `ScenarioWorkerRegistry`, strictly refusing arbitrary host process termination
  - `EvidenceSnapshotHandler`: Immutable structured forensic bundle preservation under `data/evidence/` with SHA-256 manifest checksums
  - `DefenseExecutor`: Deterministic executor managing full action lifecycle (`REQUESTED` → `EXECUTED` → `VERIFIED`/`FAILED`), automated post-action verification, and full rollback capabilities
- **Protection Evaluation Framework (Milestone 10):**
  - `ProtectionEvaluator` orchestrating repeatable multi-scenario protection experiments and computing deterministic metrics
  - Structured models: `ProtectionExperimentRecord`, `ProtectionEvaluationMetrics`, and `AggregateProtectionEvaluationResult`
  - Granular dimensions evaluated: Mitigation Success Rate (100%), RPC Blocking Rate (100%), Beacon Blocking Rate (100%), Process Isolation Success Rate (100%), Legitimate Traffic Preservation (100%), False Mitigation Rate (0.0%), Rollback Success Rate (100%), Evidence Preservation Rate (100%)
  - Containment latency measured across positive control runs (~2.09ms average latency)
  - Machine-readable artifacts persisted under `data/evaluation/protection_evaluation.json` and processed results in `results/protection/`
- **Final Research Analysis (Milestone 11):**
  - Comprehensive research reports under `reports/final/`: `FINAL_RESEARCH_ANALYSIS.md`, `DETECTION_ANALYSIS.md`, and `PROTECTION_ANALYSIS.md`
  - Machine-readable consolidated summary: `results/final/research_summary.json`
  - Explicit alignment to Research Questions: RQ1 (Phase 1 Detection) and RQ2 (Phase 2 Protection)
  - Methodological limitations, safety boundaries, security implications, and novelty positioning thoroughly documented
- **Test Suites:**
  - Python unit tests: **161 passing**
  - Hardhat contract tests: **26 passing**

### Next Implementation Target

**Master Dashboard → NEXT / FINAL CORE DELIVERABLE:**
- Build an interactive, comprehensive Master Dashboard synthesizing Phase 1 Detection telemetry and Phase 2 Protection mitigations
- Consume the stable, verified machine-readable schemas from `results/detection/`, `results/protection/`, `results/final/`, and `data/evidence/`
- Render real-time event timelines, cross-layer sequence graphs, detection condition matrices, protection mitigation records, and latency distributions

---

## Git Development & Engineering Rules

### Progressive Development
- Development proceeds incrementally through the defined milestones.
- Do not mark future milestones as complete until their implementation is fully integrated and tested.
- Do not combine unrelated milestones into a single commit.

### Meaningful Commits
- Maintain regular, meaningful Git commits representing genuine development progress.
- Use standard conventional commit prefixes:
  - `feat:` new functional capability
  - `test:` new or enhanced test suites
  - `docs:` substantive documentation updates
  - `fix:` bug fixes or error corrections
  - `chore:` maintenance, dependencies, or configuration
- **No artificial commits:** Do not create dummy or padded commits simply to inflate commit counts.

### Checkpoint and Milestone Tags
- Use Git tags to mark significant research milestones and phase completions (e.g., `phase-1-telemetry`, `phase-1-detection`, `phase-2-protection`).
- Ensure the repository is in a clean, tested, and verifiable state before applying a tag.

### Security and Data Safety
- Never commit private keys, mnemonic phrases, API secrets, `.env` files, or institutional credentials.
- No live malware or unconstrained exploit code; all scenarios are strictly synthetic and harmless.
- No public blockchain interaction; only local Hardhat EVM instances.

### Scientific and Research Integrity
- No fabricated results, mock test metrics, or invented benchmark numbers.
- Differentiate clearly between implemented capabilities and planned future work.