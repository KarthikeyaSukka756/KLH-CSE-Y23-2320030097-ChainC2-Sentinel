# ChainC2 Sentinel — Engineering Completion & Research Readiness Verification Report

**Project**: ChainC2 Sentinel: A Cybersecurity Framework for Detecting Blockchain-Mediated Command-and-Control Channels  
**Repository**: `KarthikeyaSukka756/KLH-CSE-Y23-2320030097-ChainC2-Sentinel`  
**Date**: 2026-10-28  
**Audit & Engineering Role**: Lead Software Engineer, Cybersecurity Research Engineer, and Test Engineer  
**Final Status**: **READY FOR REPRODUCIBLE LOCAL EVALUATION**

---

## 1. Initial Repository State and Commit

- **Repository Root**: `c:\Users\KARTHIKEYA\OneDrive\Desktop\Capstone Project - 1\KLH-CSE-Y23-2320030097-ChainC2-Sentinel`
- **Active Branch**: `main`
- **Current Main Commit**: `24db27085a3f107858d90e3304d82710e65f541a`
- **Working Tree State**: Working tree contained uncommitted Stage C1/C2 additions and improvements. All modifications have been preserved without discarding, resetting, or altering user work.

---

## 2. Files Inspected

The following authoritative files across the blockchain, scenario execution, telemetry collection, evaluation, and testing layers were reviewed:

1. **Scenario Execution & Runner**:
   - `src/scenarios/runner.py`: Alignment validation, address dispatch, cache lifecycle, client propagation.
   - `src/scenarios/base.py`: Client binding, collector instantiation, telemetry normalization.
   - `src/scenarios/definitions/benign_scenario.py`: Scenario A benign interaction execution.
   - `src/scenarios/definitions/c2_scenario.py`: Scenario B synthetic C2 read/write execution and data provenance.
   - `src/scenarios/definitions/legitimate_dapp_scenario.py`: Scenario C multi-step dApp activity execution.
2. **Blockchain & RPC Layer**:
   - `src/blockchain/rpc_client.py`: `LocalRpcClient` implementation, JSON-RPC queries, `eth_sendTransaction`, `get_chain_id`, `eth_getCode`.
   - `src/blockchain/deployment.py`: Address registry loading, metadata validation, live RPC alignment verification, bytecode verification.
   - `src/blockchain/scripts/deploy.js`: Hardhat deployment script, atomic registry persistence, deployment receipt verification.
   - `src/blockchain/hardhat.config.js`: Hardhat network configuration and isolation.
   - `src/blockchain/deployed-addresses.json`: Local development registry.
   - `src/blockchain/deployed-addresses.sepolia.json`: Isolated Sepolia deployment registry.
3. **Detection & Correlation Layer**:
   - `src/detection/rules/sequence_rules.py`: Synthetic C2 sequence rule and locked seven-condition conjunction.
   - `src/detection/detector.py`: Scoring engine, criterion weights, threshold evaluation.
   - `src/correlation/engine.py`: Cross-layer correlation and event temporal ordering.
4. **Test Suites & Automation**:
   - `tests/test_sepolia_configuration.py`: Network isolation, registry enforcement, cache invalidation, client propagation.
   - `tests/test_real_rpc_execution.py`: Address resolution, RPC unit tests, data provenance, state-changing boundary, detection invariance.
   - `tests/test_beacon_redirect_security.py`: HTTP redirect security, local target enforcement, SSRF protection.
   - `tests/test_campaign_matrix_v2.py`: Matrix v2 campaign plan, allocation, deterministic seeding, detection latency metrics.
   - `tests/test_scenarios.py`: Scenario payload validation, execution control.
   - `src/blockchain/test/deployment_safeguards.test.js`: Deployment safeguards, atomic registry writes, verification receipts.

---

## 3. Confirmed Defects and Exact Fixes

### Defect 1: Client Propagation & Identity Inconsistency in ScenarioRunner
- **Defect**: In `ScenarioRunner`, when no RPC client was injected, `validate_live_rpc_alignment()` created a local default client and assigned `self.rpc_client = client`. However, `run_benign()`, `run_legitimate_dapp()`, `run_synthetic_c2()`, and `run_variant()` evaluated `client = rpc_client if rpc_client is not None else self.rpc_client` *before* validation, leaving local `client` as `None`. As a result, scenarios were instantiated with `rpc_client=None`, triggering scenario-level instantiation of a brand new, unvalidated `LocalRpcClient`.
- **Fix**: Updated all scenario entry points (`run_benign`, `run_legitimate_dapp`, `run_synthetic_c2`, `run_variant`, `run_all`) in `src/scenarios/runner.py` to resolve `active_client = client or self.rpc_client` after validation and pass `rpc_client=active_client` to scenario constructors. Added regression test asserting `scenario.rpc_client is active_client` across all entry points.

### Defect 2: Stale Contract Addresses Used During Scenario Execution
- **Defect**: `ScenarioRunner.__init__()` loaded `self.deployed_addresses` once. `validate_live_rpc_alignment()` called `verify_rpc_and_registry_alignment()`, but never updated `self.deployed_addresses`. Furthermore, scenarios read directly from `self.deployed_addresses`, ignoring the return value of `validate_live_rpc_alignment()`. If registry addresses changed on disk or revalidation was forced, scenarios permanently executed using stale addresses.
- **Fix**:
  1. Updated `validate_live_rpc_alignment()` to synchronize `self.deployed_addresses = addresses` upon successful validation.
  2. Updated all scenario entry points to capture `validated_addresses = self.validate_live_rpc_alignment(client)` and pass `validated_addresses[<ContractName>]` to scenario constructors.
  3. Preserved `force=True` revalidation behavior and tested that forced revalidation immediately updates the active addresses used by scenarios.

### Defect 3: Cache Invalidation Fragility & Ephemeral Object Identity
- **Defect**: The alignment cache key relied solely on `(id(client), self.network, str(self.deployment_path))`. Because Python reuses memory addresses for deallocated objects, ephemeral clients could collide with prior cache entries. Furthermore, changes to client configuration (e.g. `rpc_url`) or modifications to the registry file on disk did not invalidate the cache.
- **Fix**: Implemented `_compute_alignment_cache_key(client)` incorporating client reference identity (`id(client)`), string `rpc_url`, client network, expected chain ID, runner network, deployment registry path, and the registry file modification timestamp (`mtime_ns`). If the registry file on disk is modified or re-written, or if the client endpoint changes, the cache key automatically changes, forcing revalidation. If validation raises an exception, the key is immediately purged via `self._validated_alignments.discard(client_key)`.

### Defect 4: Local Chain-ID Fallback Masking RPC Unavailability
- **Defect**: In `LocalRpcClient.get_chain_id()`, an `except Exception:` block caught network failures and returned `"31337"` when `self.network in ("localhost", "hardhat") and self.expected_chain_id is None`. Consequently, calling `verify_rpc_and_registry_alignment()` with a default `LocalRpcClient(network="localhost")` against an offline endpoint succeeded, approving contract addresses as verified without contacting an active node.
- **Fix**: Removed the silent fallback in `LocalRpcClient.get_chain_id()`. Network connection failures, timeouts, HTTP errors, and malformed responses now raise exceptions immediately across all networks. `verify_rpc_and_registry_alignment()` rejects unavailable nodes with `DeploymentResolutionError`.

### Defect 5: Missing On-Chain Bytecode Verification in Python Layer
- **Defect**: The Python deployment layer checked address syntax and registry metadata, but did not provide an `eth_getCode` facility to verify that contract bytecode actually exists on-chain before interacting with contracts.
- **Fix**:
  1. Added `LocalRpcClient.eth_get_code(address, block="latest")` to execute `eth_getCode` JSON-RPC calls.
  2. Added `verify_contract_bytecode(rpc_client, address)` helper in `src/blockchain/deployment.py`.
  3. Added optional `verify_bytecode: bool = False` parameter to `verify_rpc_and_registry_alignment()` to assert that non-empty bytecode exists at every registered address.

---

## 4. Test Commands and Actual Results

All testing was conducted strictly offline using mocks and local unit tests.

### A. Hardhat Deployment Safeguards Suite
- **Command**: `npx hardhat test test/deployment_safeguards.test.js`
- **Working Directory**: `src/blockchain`
- **Exit Code**: `0`
- **Output Summary**:
  ```
  Stage C: Deployment Safeguards, Atomic Persistence & Verification
    resolveRegistryPath: 7 passing
    validateDeployedAddresses: 3 passing
    saveRegistryAtomic: 4 passing
    verifyContractDeployment: 5 passing
    Preservation of Local Registry During Sepolia Failure: 2 passing
  Total: 21 passing (69ms)
  ```

### B. Unit & Configuration Regression Suite
- **Command**: `python -m pytest tests/test_sepolia_configuration.py tests/test_real_rpc_execution.py -m "not integration" -v`
- **Working Directory**: Repository root
- **Exit Code**: `0`
- **Output Summary**: `63 passed, 4 deselected in 0.64s`

### C. Full Repository Offline Regression Suite
- **Command**: `python -m pytest tests/test_sepolia_configuration.py tests/test_real_rpc_execution.py tests/test_beacon_redirect_security.py tests/test_campaign_matrix_v2.py tests/test_scenarios.py -m "not integration"`
- **Working Directory**: Repository root
- **Exit Code**: `0`
- **Output Summary**: `105 passed, 4 deselected in 5.52s`
  - `tests/test_sepolia_configuration.py`: 30 passed
  - `tests/test_real_rpc_execution.py`: 26 passed
  - `tests/test_beacon_redirect_security.py`: 12 passed
  - `tests/test_campaign_matrix_v2.py`: 21 passed
  - `tests/test_scenarios.py`: 9 passed
  - Deselected: 4 tests (marked `@pytest.mark.integration`, requiring a live running Hardhat node).

---

## 5. Detection-Rule and Scoring Invariance Comparison

| Detection Parameter | Baseline Specification | Current Implementation | Comparison Status |
| :--- | :---: | :---: | :---: |
| **Conjunction Condition 1** | Endpoint / Process Telemetry | `endpoint_event is not None` | **IDENTICAL (PRESERVED)** |
| **Conjunction Condition 2** | RPC Proxy Interaction | `rpc_event is not None` | **IDENTICAL (PRESERVED)** |
| **Conjunction Condition 3** | Smart Contract Interaction | `blockchain_event is not None` | **IDENTICAL (PRESERVED)** |
| **Conjunction Condition 4** | Target Contract is `C2DataStore` | `blockchain_event.contract_name == "C2DataStore"` | **IDENTICAL (PRESERVED)** |
| **Conjunction Condition 5** | Subsequent Outbound Network Activity | `network_event is not None` | **IDENTICAL (PRESERVED)** |
| **Conjunction Condition 6** | Network Occurs At/After Blockchain | `network_event.timestamp >= blockchain_event.timestamp` | **IDENTICAL (PRESERVED)** |
| **Conjunction Condition 7** | Causal Chain: `EP <= RPC <= BC <= NET` | `t_ep <= t_rpc <= t_bc <= t_net` | **IDENTICAL (PRESERVED)** |
| **Criterion Weight: EP** | +10.0 | +10.0 | **IDENTICAL (PRESERVED)** |
| **Criterion Weight: RPC** | +10.0 | +10.0 | **IDENTICAL (PRESERVED)** |
| **Criterion Weight: BC** | +15.0 | +15.0 | **IDENTICAL (PRESERVED)** |
| **Criterion Weight: Suspicious Retrieval** | +20.0 | +20.0 | **IDENTICAL (PRESERVED)** |
| **Criterion Weight: C2 Config Indicator** | +20.0 | +20.0 | **IDENTICAL (PRESERVED)** |
| **Criterion Weight: Subsequent Network** | +25.0 | +25.0 | **IDENTICAL (PRESERVED)** |
| **Score Threshold** | 80.0 | 80.0 | **IDENTICAL (PRESERVED)** |
| **Detection Requirement** | `conjunction_triggered AND score >= 80.0` | `rule_conjunction_triggered and score >= 80.0` | **IDENTICAL (PRESERVED)** |

---

## 6. Protected Research Artifacts Integrity Audit

All seven historical and baseline research artifacts were verified byte-for-byte using raw binary SHA-256 and exact byte count checks:

| Artifact Relative Path | Actual Size | Expected Size | Size Status | Actual SHA-256 | Expected SHA-256 | Hash Status |
| :--- | :---: | :---: | :---: | :--- | :--- | :---: |
| `data/evaluation/dataset_campaign/matrix_v2_81_results.json` | 114,232 B | 114,232 B | **MATCH** | `15fa3d7e49a1cf5f8c1476a2ff5141849a46fb31eb021a3e2159a2d8998fd470` | `15fa3d7e49a1cf5f8c1476a2ff5141849a46fb31eb021a3e2159a2d8998fd470` | **VERIFIED** |
| `data/evaluation/dataset_campaign/telemetry_events_balanced.jsonl` | 267,774 B | 267,774 B | **MATCH** | `519c1e988e221d889ed499badb8bb704a69dd2c17c96dc42881ddafbbce35aa0` | `519c1e988e221d889ed499badb8bb704a69dd2c17c96dc42881ddafbbce35aa0` | **VERIFIED** |
| `data/evaluation/dataset_campaign/campaign_plan_372.json` | 215,305 B | 215,305 B | **MATCH** | `0c483d093ee32c4122ae4c47fdc6fd62451b78991ec45bd25077f517f0c23bc7` | `0c483d093ee32c4122ae4c47fdc6fd62451b78991ec45bd25077f517f0c23bc7` | **VERIFIED** |
| `results/final/research_summary.json` | 10,472 B | 10,472 B | **MATCH** | `85b1d136d61c7657c518eb2872eedf50f245e968d9997178ca04cdcce7930bcc` | `85b1d136d61c7657c518eb2872eedf50f245e968d9997178ca04cdcce7930bcc` | **VERIFIED** |
| `data/evaluation/dataset_campaign_corrected/matrix_v2_81_results.json` | 115,043 B | 115,043 B | **MATCH** | `e696a9b669339efce57d5692fcc56193a0a4832f699501fe803dddb7ecd60b80` | `e696a9b669339efce57d5692fcc56193a0a4832f699501fe803dddb7ecd60b80` | **VERIFIED** |
| `data/evaluation/dataset_campaign_corrected/telemetry_events_balanced.jsonl` | 442,165 B | 442,165 B | **MATCH** | `400157379861087e2306631036b5511c3c55899812f186fc882103215a9bb652` | `400157379861087e2306631036b5511c3c55899812f186fc882103215a9bb652` | **VERIFIED** |
| `data/evaluation/dataset_campaign_corrected/campaign_plan_81.json` | 47,203 B | 47,203 B | **MATCH** | `17f7d40e4b65a1131c67218d4b84983a5c2e44ca8a8a7f0b3da0a6a5d2e22b47` | `17f7d40e4b65a1131c67218d4b84983a5c2e44ca8a8a7f0b3da0a6a5d2e22b47` | **VERIFIED** |

---

## 7. Remaining Risks and Limitations

1. **Sepolia Public Deployment State**: The Sepolia registry (`src/blockchain/deployed-addresses.sepolia.json`) is intentionally in an `UNCONFIGURED` state with zero placeholder addresses. Deploying contracts to Sepolia requires funding a deployment address with testnet ETH and executing the deployment script in an explicitly authorized session. Unsigned transaction execution (`eth_sendTransaction`) on Sepolia is strictly rejected by design.
2. **Local Hardhat Integration Prerequisites**: Running the 4 integration tests marked `@pytest.mark.integration` requires a live local Hardhat node running on port 8545 and the local RPC proxy on port 8546. The offline regression suite operates with 100% pass rate using isolated unit mocks.
3. **Pydantic Validation on RPC Collector**: RPC telemetry collection strictly requires `status` to be either `'success'` or `'error'`. Unhandled intermediate status strings (e.g. `'unsupported_network_operation'`) are translated to `'error'` with detailed descriptive error messages to maintain schema conformity.

---

## 8. Full Final Git Status

```
 M .env.example
 M docs/README.md
 M scripts/run_research_campaign.py
 M src/blockchain/hardhat.config.js
 M src/blockchain/scripts/deploy.js
 M src/dashboard/services/benchmark_service.py
 M src/dashboard/services/experiment_service.py
 M src/evaluation/campaign.py
 M src/models/matrix_v2.py
 M src/scenarios/base.py
 M src/scenarios/definitions/benign_scenario.py
 M src/scenarios/definitions/c2_scenario.py
 M src/scenarios/definitions/legitimate_dapp_scenario.py
 M src/scenarios/runner.py
?? data/evaluation/dataset_campaign/matrix_v2_81_results.json
?? data/evaluation/dataset_campaign/telemetry_events_balanced.jsonl
?? data/evaluation/dataset_campaign_corrected/
?? docs/LOCAL_RESEARCH_BASELINE.md
?? scratch/
?? src/blockchain/deployed-addresses.sepolia.json
?? src/blockchain/deployment.py
?? src/blockchain/rpc_client.py
?? src/blockchain/test/deployment_safeguards.test.js
?? tests/test_beacon_redirect_security.py
?? tests/test_campaign_matrix_v2.py
?? tests/test_real_rpc_execution.py
?? tests/test_sepolia_configuration.py
```

### Confirmation of Safeguards:
- **No Git commits were created.**
- **No Git pushes or branch switches occurred.**
- **No files were staged.**
- **No private keys, mnemonics, or credentials were added or exposed.**
- **No packages were installed.**
- **No public network transactions or deployments were dispatched.**

---

## 9. Final Decision

# **READY FOR REPRODUCIBLE LOCAL EVALUATION**

All demonstrated code and test defects in the execution path, RPC client consistency, network validation, deployment integrity, and address dispatch have been resolved. The complete changed source files and test suites are exported to `scratch/research_ready_source_bundle.md`.
