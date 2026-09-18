# Phase 2 Analysis: Controlled Defensive Protection & Mitigation
## Empirical Evaluation of Application-Layer Containment and Verification

**Project:** ChainC2 Sentinel
**Research Focus:** Phase 2 — Protection
**Research Question 2 (RQ2):** *"Once the behavior is detected, what defensive measures can be applied?"*
**Benchmark ID:** `eval-prot-8fd434fa-4c9d-41b8-bebe-7c118bf3a024`

---

## 1. Research Question & Objective

Phase 2 addresses the operational defense question:
> **RQ2:** *"Once the behavior is detected, what defensive measures can be applied?"*

The primary objective is to investigate what controlled, application-layer defensive countermeasures can be applied to reduce or contain detected blockchain-mediated C2 activity in a laboratory environment, without modifying host operating system firewalls, terminating arbitrary host processes, or disrupting legitimate Web3 and localhost network activity.

---

## 2. Defensive Response Architecture

The defensive pipeline enforces strict separation between detection, policy planning, and handler execution:

```
┌──────────────────────────────────────────────┐
│  Phase 1: Detection Verdict                  │
│  - Candidate: TRIGGERED / NOT_TRIGGERED      │
│  - Evidence: Contract, Process, Target       │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Defensive Policy Engine                     │
│  - Safety Boundary Enforcement               │
│  - If NOT_TRIGGERED -> Plan: SKIPPED         │
│  - If TRIGGERED     -> Plan: PROPOSED        │
│  - Synthesizes 4-layer MitigationAction set  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Defense Executor (Deterministic Order)      │
│  1. Evidence Preservation Handler            │
│  2. Network Containment Handler              │
│  3. RPC Proxy Filter Handler                 │
│  4. Cooperative Process Isolation Handler    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Post-Mitigation Active Verification Probing │
│  - Probe RPC Proxy: Is C2 blocked?           │
│  - Probe Target Server: Is beacon 403?       │
│  - Probe Process Registry: Is worker paused? │
│  - Probe Baseline: Is benign dApp working?   │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Baseline Restoration / Rollback Routine     │
│  - Remove RPC Filter                         │
│  - Disable Network Containment               │
│  - Restore Process State                     │
│  - Preserve Immutable Forensic Evidence      │
└──────────────────────────────────────────────┘
```

---

## 3. Four Concrete Mitigation Handlers

### 1. `RpcFilterHandler` (Application-Layer RPC Quarantine)
- **Integration:** Hooks into the client-facing `RpcTelemetryProxy`.
- **Mechanism:** Inspects incoming JSON-RPC payloads (`eth_call`, `eth_sendTransaction`, `eth_estimateGas`) for quarantined smart contract addresses.
- **Behavior:** When targeted at `C2DataStore`, returns standard JSON-RPC error `-32000` (`"Blocked by Sentinel RPC Protection Policy"`).
- **Preservation:** Calls targeting `BenignDAppContract` or other contract addresses continue to proxy to the upstream EVM node without interruption.
- **Safety Boundary:** Operates purely at the HTTP application layer. Zero packet filtering, OS routing changes, or kernel modifications.

### 2. `NetworkContainmentHandler` (Local Egress Containment)
- **Integration:** Hooks into `LocalHttpTargetServer`.
- **Mechanism:** Activates application-level containment on synthetic egress routes (`/beacon`).
- **Behavior:** Quarantines the client IP, returning `HTTP 403 Forbidden` (`{"error": "Client or endpoint is quarantined by Sentinel network containment"}`).
- **Preservation:** Unrelated local endpoints, including `/health`, continue to return `HTTP 200 OK`.
- **Safety Boundary:** Confined to `127.0.0.1`. Zero changes to Windows Defender, `netsh`, or `iptables`.

### 3. `ProcessIsolationHandler` (Cooperative Scenario Worker Quarantine)
- **Integration:** Hooks into `ScenarioWorkerRegistry`.
- **Mechanism:** Issues cooperative pause tokens (`isolated: True`) to registered laboratory scenario workers.
- **Behavior:** The scenario worker acknowledges the signal and ceases execution.
- **Safety Boundary:** **Strict refusal of arbitrary processes.** If a PID or process name is not pre-registered in `ScenarioWorkerRegistry`, the handler immediately refuses the action with `MitigationStatus.FAILED`. Never invokes `kill -9`, `taskkill`, `Stop-Process`, or OS process termination.

### 4. `EvidenceSnapshotHandler` (Forensic Preservation)
- **Integration:** Writes structured JSON bundles to `data/evidence/`.
- **Mechanism:** Captures `DetectionResult`, `CorrelatedSequence` summary, timestamps, matched conditions, and defense context.
- **Integrity:** Computes and embeds a SHA-256 integrity hash over the JSON payload.
- **Safety Boundary:** Strict sanitization ensures zero private keys, wallet mnemonics, or environment secrets are written to disk.

---

## 4. Execution Lifecycle & Deterministic Progression

Every mitigation action transitions through an auditable lifecycle:
$$\text{REQUESTED} \longrightarrow \text{EXECUTED} \longrightarrow \text{VERIFIED} \quad (\text{or } \text{FAILED})$$

1. **Ordering:** Evidence is snapshot *first* so that forensic artifacts are secured before network or process states are modified.
2. **Verification Probing:** An action is never assumed to have succeeded. The executor actively verifies state changes (e.g. sending a real HTTP probe to `/beacon` to verify the 403 response).
3. **Rollback Routine:** Calling `executor.rollback_plan()` restores laboratory baseline in reverse order while intentionally preserving the immutable evidence files on disk.

---

## 5. Empirical Evaluation Results

The Phase 2 evaluation benchmark comprised **22 live laboratory experiments**:
- **Scenario A (Benign Negative Control):** 10 runs
- **Scenario B (Synthetic C2 Positive Control):** 10 runs
- **Scenario C (Controlled Fault Injection):** 2 runs

*Authoritative Source: [`data/evaluation/protection_evaluation.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/data/evaluation/protection_evaluation.json)*

### Comprehensive Metrics Table

| Metric | Measured Value | Formula / Denominator | Interpretation |
|:---|:---:|:---|:---|
| **Total Experiments** | **22** | All evaluated scenario runs | 10 Benign + 10 C2 + 2 Fault Injection |
| **Successful Experiments** | **22 / 22** (100.0%) | $\text{successful} / \text{total}$ | All scenarios completed without unhandled error |
| **Mitigation Success Rate** | **100.0%** | $40 / 40$ verified actions | 100% of requested actions in positive runs verified |
| **RPC Blocking Rate** | **100.0%** | $10 / 10$ queries blocked | Synthetic `C2DataStore` queries rejected |
| **Beacon Blocking Rate** | **100.0%** | $10 / 10$ beacons rejected | Subsequent `/beacon` requests returned HTTP 403 |
| **Process Isolation Success** | **100.0%** | $10 / 10$ workers isolated | All registered scenario workers cooperatively paused |
| **Legitimate Traffic Preservation**| **100.0%** | $22 / 22$ runs preserved | Benign contracts & `/health` functional in all runs |
| **False Mitigation Rate** | **0.0%** | $0 / 10$ benign runs mitigated | Zero defensive actions applied to Scenario A |
| **Rollback Success Rate** | **100.0%** | $10 / 10$ rollbacks verified | Clean return to baseline after positive runs |
| **Evidence Preservation Rate** | **100.0%** | $10 / 10$ bundles created | Structured JSON with valid SHA-256 digests |

### Containment Latency Profile (Milliseconds)
Measured from defense plan execution invocation to completion of all post-mitigation verification probes:

| Latency Statistic | Measured Value | Meaning |
|:---|:---:|:---|
| **Minimum Containment Latency** | **1.490 ms** | Fastest plan execution and verification probe |
| **Maximum Containment Latency** | **3.564 ms** | Maximum measured containment latency |
| **Average Containment Latency** | **2.091 ms** | Sub-3ms mean response time |
| **Median Containment Latency** | **1.755 ms** | Stable central tendency with low variance |

---

## 6. Detailed Analytical Breakdown

### A. Non-Interference with Benign Web3 Operations
A critical requirement of Phase 2 is that defense mechanisms must not degrade benign systems:
- In Scenario A (10 runs), `DefensivePolicyEngine` observed `status = NOT_TRIGGERED` and generated a plan with `status = SKIPPED` ($0$ actions).
- `False Mitigation Rate = 0.0%`.
- In Scenario B (10 runs), even when active containment was blocking `C2DataStore` queries, concurrent queries to `BenignDAppContract` received normal JSON-RPC responses, and GET requests to `/health` returned `200 OK`.
- `Legitimate Traffic Preservation Rate = 100.0%` across all 22 experiments.

### B. Controlled Fault Injection Analysis (Scenario C)
In Scenario C (2 runs), an isolation request was issued for an unregistered phantom PID (PID 99999):
- `ScenarioWorkerRegistry` logged an explicit refusal (`"Process is not a registered laboratory worker"`).
- `ProcessIsolationHandler` returned `False`, marking the action as `FAILED`.
- `DefenseExecutor` recorded `actions_failed = 1` and marked the plan as `FAILED`.
- The system handled the failure safely without throwing unhandled exceptions, demonstrating robust error handling without risking arbitrary host process interaction.

### C. Forensic Evidence Vault
The 10 evidence bundles persisted under `data/evidence/` maintain an immutable audit trail:
- Every bundle contains the exact `run_id`, `rule_id`, matched condition vector, and action identifiers.
- A SHA-256 hash computed over the serialized payload guarantees integrity and detects post-incident tampering.

---

## 7. Phase 2 Scope & Methodological Boundaries

1. **Decentralized Ledger Reality:** Filtering a smart contract at a local proxy does **not** delete or disable the contract on the blockchain. Any external host not routing through the proxy could still interact with the contract.
2. **Cooperative Process Quarantine:** Real-world advanced malware will not honor cooperative pause tokens. True host containment requires endpoint detection and response (EDR) agents capable of process suspension or cgroup/container termination.
3. **Local Loopback Scope:** Network containment was evaluated against local HTTP target servers on `127.0.0.1`. Real-world C2 infrastructure involves domain fronting, CDN proxies, and encrypted TLS egress.
4. **No Operating-System Modifications:** Defensive actions were strictly application-layer, avoiding host firewall modifications or raw packet filtering.

---

## 8. Summary Answer to RQ2

> **RQ2 Conclusion:** Once blockchain-mediated C2 behavior is detected, **controlled application-layer defensive measures can rapidly contain subsequent activity while preserving legitimate Web3 operations.** In laboratory evaluations, the framework achieved a **100.0% Mitigation Success Rate**, **100.0% Legitimate Traffic Preservation**, **0.0% False Mitigation Rate**, and **2.091 ms average containment latency** across repeated trials.
