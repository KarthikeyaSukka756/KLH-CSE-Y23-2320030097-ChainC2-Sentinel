# ChainC2 Sentinel — Focused Read-Only Audit Report
**Audit Scope**:
1. ScenarioRunner alignment-cache invalidation.
2. LocalRpcClient.get_chain_id() local fallback behavior.

**Date**: 2026-10-28  
**Audit Mode**: Strictly Read-Only (no source or test files modified)

---

## 1. Executive Summary & Verdicts

| Concern | Subject | Verdict | Severity | Primary Demonstrated Finding |
| :--- | :--- | :---: | :---: | :--- |
| **Concern 1** | `ScenarioRunner` Alignment-Cache Invalidation | **DEFECT CONFIRMED** | **Medium** | Cache key uses ephemeral `id(client)` causing potential memory address collisions; returned validated addresses never update `self.deployed_addresses`, causing permanent reuse of stale `__init__` addresses even upon forced revalidation. |
| **Concern 2** | `LocalRpcClient.get_chain_id()` Local Fallback Behavior | **DEFECT CONFIRMED** | **High** | When `expected_chain_id is None` (the default), `get_chain_id()` suppresses offline connection errors on localhost and returns `"31337"`, allowing `verify_rpc_and_registry_alignment()` to mistakenly approve contract addresses without a live RPC connection. |

---

## 2. Concern 1: ScenarioRunner Alignment-Cache Invalidation

### A. Files and Functions Inspected
- `src/scenarios/runner.py`:
  - `ScenarioRunner.__init__()` (lines 53–118)
  - `ScenarioRunner.validate_live_rpc_alignment()` (lines 119–138)
  - Scenario execution entry points: `run_benign()`, `run_legitimate_dapp()`, `run_synthetic_c2()`, `run_variant()`, `run_all()` (lines 140–432)
- `src/blockchain/deployment.py`:
  - `verify_rpc_and_registry_alignment()` (lines 155–203)
  - `load_deployed_addresses()` (lines 104–153)
- `tests/test_sepolia_configuration.py`:
  - `test_live_rpc_alignment_caching_avoids_redundant_checks()` (lines 316–336)
  - `test_chain_id_mismatch_prevents_scenario_execution_all_entrypoints()` (lines 281–305)

### B. Detailed Technical Findings

#### 1. Exact Alignment-Cache Key and Cached Values
- **Cache Storage**: `self._validated_alignments = set()` ([runner.py:78](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/scenarios/runner.py#L78))
- **Cache Key**:
  ```python
  client_key = (id(client), self.network, str(self.deployment_path))
  ```
  ([runner.py:128](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/scenarios/runner.py#L128))
  - `id(client)`: Integer CPython memory address (`PyObject*`) of the `client` object.
  - `self.network`: Lowercase string network identifier on the runner instance (e.g. `'localhost'`, `'sepolia'`).
  - `str(self.deployment_path)`: String filesystem path to the registry JSON file.
- **Cached Values**:
  - The set stores only keys (membership testing `client_key in self._validated_alignments`).
  - On a cache hit (`if not force and client_key in self._validated_alignments:`), line 130 executes:
    ```python
    return self.deployed_addresses
    ```
    This returns `self.deployed_addresses`, which was loaded at `ScenarioRunner.__init__()` ([runner.py:108-112](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/scenarios/runner.py#L108-L112)). It does **not** cache or return the freshly parsed addresses from `verify_rpc_and_registry_alignment()`.

#### 2. Mutability of Execution Parameters After Validation
- **RPC Client Instance**: When `rpc_client` is not provided to the runner or entry point, `LocalRpcClient` is created as an ephemeral local variable inside `validate_live_rpc_alignment` ([runner.py:123-127](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/scenarios/runner.py#L123-L127)). The instance is deallocated as soon as `validate_live_rpc_alignment` returns. In CPython, a newly allocated object in a subsequent call can receive the exact same memory address.
- **Underlying RPC URL**: Mutable. If `client.rpc_url` is mutated in place, `id(client)` is unchanged.
- **Expected Network**: Set in `__init__`, but instance attribute `self.network` could be reassigned.
- **Deployment Registry Path**: Set in `__init__`, but `self.deployment_path` could be reassigned.
- **Registry Contents on Disk**: The registry JSON file on disk can be modified, rewritten, or re-deployed during the runner's process lifetime.

#### 3. Invalidation Behavior Upon Parameter Changes
- In-place mutation of `client.rpc_url`: **Does NOT invalidate cache**.
- In-place mutation of `client.network` or `client.expected_chain_id`: **Does NOT invalidate cache**.
- Registry file changes on disk: **Does NOT invalidate cache** (no mtime, hash, or inode in key).
- Ephemeral client memory address reuse: **False cache hit**. When `self.rpc_client` is None, temporary client instances created in subsequent calls can inherit freed memory addresses, matching previous cache keys.
- Changing `self.network` or `self.deployment_path`: Produces a different cache tuple, bypassing previous cache entries.
- Forced Invalidation: Supported via `validate_live_rpc_alignment(..., force=True)`. However, there is no automatic invalidation or `clear_cache()` method.

#### 4. Contract Address Staleness and Reuse
- **Demonstrated Defect**:
  In `ScenarioRunner.validate_live_rpc_alignment` ([runner.py:132-137](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/scenarios/runner.py#L132-L137)):
  ```python
  addresses = verify_rpc_and_registry_alignment(
      rpc_client=client,
      expected_network=self.network,
      deployment_path=self.deployment_path,
  )
  self._validated_alignments.add(client_key)
  return addresses
  ```
  Notice: `self.deployed_addresses` is **never updated** with `addresses`!
  Now examine `run_benign()` ([runner.py:147-150](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/scenarios/runner.py#L147-L150)):
  ```python
  self.validate_live_rpc_alignment(client)
  scenario = BenignWeb3Scenario(
      contract_address=self.deployed_addresses["BenignDAppContract"],
      ...
  ```
  `run_benign` (and `run_legitimate_dapp`, `run_synthetic_c2`, `run_variant`) ignores the return value of `validate_live_rpc_alignment()` and accesses `self.deployed_addresses` directly.
  If the registry on disk changes after `ScenarioRunner.__init__()`:
  - `verify_rpc_and_registry_alignment()` reads the updated addresses from disk, but `self.deployed_addresses` remains the old addresses from initialization.
  - On a cache hit, line 130 returns `self.deployed_addresses` (the old addresses).
  - All scenarios permanently execute using stale contract addresses loaded at `__init__`.

#### 5. Existing Test Coverage
- `test_live_rpc_alignment_caching_avoids_redundant_checks` in `tests/test_sepolia_configuration.py`:
  - Tests that calling `validate_live_rpc_alignment` twice with the same mock client does not query `get_chain_id` again.
  - Tests that `force=True` re-queries `get_chain_id`.
- **Gaps**: Existing tests do NOT test:
  - Behavior when `client.rpc_url` changes.
  - Behavior when the registry file on disk changes.
  - Behavior when `ScenarioRunner` is called without an injected `rpc_client` across iterations.

#### 6. Lifecycle Safety Assessment
- **Intentional Design**: Within a single execution run (e.g. running 81 Matrix v2 variants via `run_research_campaign.py`), the runner is instantiated once with fixed network and registry files that are not re-deployed mid-run.
- **Defects Confirmed**:
  1. `id(client)` is fragile for ephemeral clients.
  2. `self.deployed_addresses` is not synchronized with the validated addresses returned by `verify_rpc_and_registry_alignment()`.

### C. Concrete Reproduction Steps
```python
import json
from src.scenarios.runner import ScenarioRunner

# 1. Initialize runner
runner = ScenarioRunner(network="localhost")
orig_addr = runner.deployed_addresses["BenignDAppContract"]

# 2. Modify registry file on disk
reg_path = runner.deployment_path
with open(reg_path, "r", encoding="utf-8") as f:
    data = json.load(f)

data["contracts"]["BenignDAppContract"]["address"] = "0x1111111111111111111111111111111111111111"
with open(reg_path, "w", encoding="utf-8") as f:
    json.dump(data, f)

# 3. Force revalidation
validated = runner.validate_live_rpc_alignment(force=True)

# 4. Check whether runner.deployed_addresses was updated
print("Validated return:", validated["BenignDAppContract"])
print("Runner deployed_addresses:", runner.deployed_addresses["BenignDAppContract"])
# Demonstrated bug: runner.deployed_addresses remains orig_addr!
```

### D. Minimal Proposed Fix (For Review Only)
In `src/scenarios/runner.py`:
1. Use client properties (`getattr(client, 'rpc_url', None)`, `self.network`, `str(self.deployment_path)`) rather than `id(client)` in `client_key`.
2. In `validate_live_rpc_alignment`, update `self.deployed_addresses = addresses` upon successful validation so that cache hits and subsequent scenario instantiations use the verified addresses.
3. If `self.rpc_client` is None and `rpc_client` is None, retain `self.rpc_client = client` so the same client instance is reused across the runner's lifecycle.

---

## 3. Concern 2: LocalRpcClient.get_chain_id() Local Fallback Behavior

### A. Files and Functions Inspected
- `src/blockchain/rpc_client.py`:
  - `LocalRpcClient.__init__()` (lines 255–275)
  - `LocalRpcClient.get_chain_id()` (lines 512–540)
  - `LocalRpcClient.eth_send_transaction()` (lines 340–396)
- `src/blockchain/deployment.py`:
  - `verify_rpc_and_registry_alignment()` (lines 155–203)
- `src/scenarios/base.py`:
  - `BaseScenario.__init__()` (lines 111–115)
- `src/scenarios/runner.py`:
  - `ScenarioRunner.validate_live_rpc_alignment()` (lines 123–127)
- `tests/test_sepolia_configuration.py`:
  - `test_chain_id_validation_prevents_silent_cross_network_execution()` (lines 115–135)
  - `test_chain_id_mismatch_prevents_scenario_execution_all_entrypoints()` (lines 281–305)
- `tests/test_real_rpc_execution.py`:
  - `TestLiveLocalHardhatNodeIntegration.test_live_proxy_forwarding_and_chain_id()` (lines 665–670)

### B. Detailed Technical Findings

#### 1. Exact Conditions for Fallback to "31337"
In `LocalRpcClient.get_chain_id()` ([rpc_client.py:535-538](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/blockchain/rpc_client.py#L535-L538)):
```python
except Exception as e:
    if self.network in ("localhost", "hardhat") and self.expected_chain_id is None:
        logger.debug("Local RPC query failed, returning local default: %s", e)
        return "31337"
    raise
```
The fallback string `"31337"` is returned without a successful RPC response if and only if **all three** conditions are met:
1. `requests.post()` raises an exception or fails JSON decoding / error checking (e.g. `ConnectionRefusedError`, network timeout, HTTP error, empty result).
2. `self.network in ("localhost", "hardhat")` is True.
3. `self.expected_chain_id is None` is True.

If `self.network == "sepolia"`, it raises.  
If `self.expected_chain_id` is set (e.g. `"31337"` or `"11155111"`), it raises.

#### 2. Callers Providing vs. Omitting expected_chain_id
- **Callers providing `expected_chain_id`**:
  - `ScenarioRunner.validate_live_rpc_alignment()` default client ([runner.py:126](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/scenarios/runner.py#L126)): passes `expected_chain_id=self.chain_id`.
  - `BaseScenario.__init__()` default client ([base.py:114](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/scenarios/base.py#L114)): passes `expected_chain_id=self.chain_id`.
  - `test_chain_id_validation_prevents_silent_cross_network_execution` ([test_sepolia_configuration.py:120](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/tests/test_sepolia_configuration.py#L120)): passes `expected_chain_id="11155111"`.
- **Callers omitting `expected_chain_id` (`None`)**:
  - `verify_rpc_and_registry_alignment(rpc_client, expected_network)` ([deployment.py:183](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/blockchain/deployment.py#L183)): Accepts `rpc_client: Any`. If caller passes a `LocalRpcClient` instantiated with default arguments, `expected_chain_id` is `None`.
  - `LocalRpcClient()` default constructor ([rpc_client.py:261](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/blockchain/rpc_client.py#L261)): default `expected_chain_id=None`.
  - All unit test calls constructing `LocalRpcClient(rpc_url=...)` in `tests/test_real_rpc_execution.py` (lines 156, 174, 191, 220, 500, 666, 672, 682, 691).
  - External callers or scripts passing `LocalRpcClient()` to `runner.run_benign(rpc_client=...)`.

#### 3. Use of Fallback Value for Approvals, Registries, Telemetry, or Transactions
- **Approval of Contract Addresses & Registry Selection**: **YES (CONFIRMED)**.
  In `verify_rpc_and_registry_alignment()` ([deployment.py:183-202](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone%20Project%20-%201/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/src/blockchain/deployment.py#L183-L202)):
  ```python
  rpc_cid = str(rpc_client.get_chain_id())
  if rpc_cid != expected_cid:
      raise DeploymentResolutionError(...)
  target_path = deployment_path or get_deployment_path_for_network(norm_net)
  addresses = load_deployed_addresses(path=target_path, expected_network=norm_net, expected_chain_id=rpc_cid)
  return addresses
  ```
  When `rpc_client` has `expected_chain_id=None` (e.g. `client = LocalRpcClient()`), and the local RPC endpoint is completely offline, `get_chain_id()` catches the connection error and returns `"31337"`.
  Then `rpc_cid != expected_cid` (`"31337" != "31337"`) is False!
  It proceeds to `load_deployed_addresses()`, approves the addresses from `deployed-addresses.json`, and returns them as valid.
- **Telemetry Classification**: Not directly in detector. But telemetry events generated by subsequent calls will fail.
- **Transaction Authorization**: `eth_send_transaction()` checks `net_cfg.requires_signing` from `NETWORK_CONFIGS`, not `get_chain_id()`.

#### 4. Can RPC Unavailability Be Mistaken for Successful Live Validation?
- **YES (CONFIRMED)**.
  When a caller passes a `LocalRpcClient(network="localhost")` (without explicit `expected_chain_id`) to `verify_rpc_and_registry_alignment()`, complete RPC unavailability produces a successful validation outcome, returning contract addresses as if the live node responded with chain ID `31337`.

#### 5. Existing Test Coverage
- `test_chain_id_validation_prevents_silent_cross_network_execution` in `tests/test_sepolia_configuration.py` tests that when `network="sepolia"` and `expected_chain_id="11155111"`, an offline `ConnectionError` raises.
- **Gaps**:
  - Offline failure when `network="localhost"` and `expected_chain_id=None` is NOT tested.
  - The silent fallback in `verify_rpc_and_registry_alignment()` when `LocalRpcClient(network="localhost")` is offline is NOT tested.

### C. Concrete Reproduction Steps
Executed directly against the current repository state:
```python
from unittest.mock import patch
from src.blockchain.rpc_client import LocalRpcClient
from src.blockchain.deployment import verify_rpc_and_registry_alignment

# 1. Instantiate client with default network="localhost", expected_chain_id=None
client = LocalRpcClient(network="localhost")

# 2. Simulate RPC endpoint being completely offline (ConnectionRefusedError)
with patch("requests.post", side_effect=ConnectionRefusedError("Connection refused")):
    cid = client.get_chain_id()
    print("get_chain_id() returned:", cid)
    addrs = verify_rpc_and_registry_alignment(client, "localhost")
    print("verify_rpc_and_registry_alignment returned:", addrs)
```
**Actual Output Produced**:
```
get_chain_id() returned: 31337
verify_rpc_and_registry_alignment returned: {'C2DataStore': '0x5FbDB2315678afecb367f032d93F642f64180aa3', 'BenignDAppContract': '0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512', 'LegitimateDAppContract': '0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0'}
```
**Demonstrated Impact**: Contract addresses were approved and declared "verified" even though the RPC endpoint was completely offline.

### D. Minimal Proposed Fix (For Review Only)
In `src/blockchain/rpc_client.py`:
Remove the silent exception suppression in `LocalRpcClient.get_chain_id()`:
```python
    def get_chain_id(self) -> str:
        """Fetch chain ID from the RPC endpoint."""
        req_payload = {
            "jsonrpc": "2.0",
            "method": "eth_chainId",
            "params": [],
            "id": self._next_id(),
        }
        resp = requests.post(self.rpc_url, json=req_payload, timeout=self.timeout)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"eth_chainId RPC error: {data['error']}")
        res = data.get("result")
        if not res:
            raise RuntimeError("Empty result in eth_chainId response")
        chain_id = str(int(res, 16))
        if self.expected_chain_id and chain_id != self.expected_chain_id:
            raise RuntimeError(
                f"Chain ID mismatch for network '{self.network}': "
                f"expected {self.expected_chain_id}, got {chain_id}"
            )
        return chain_id
```
When live RPC validation is requested, an unreachable RPC must fail closed across all networks, including `localhost`.

---

## 4. Tests Executed vs. Inspected

### Tests Actually Executed
1. `npx hardhat test test/deployment_safeguards.test.js` (cwd: `src/blockchain`):
   - **Exit Code**: 0
   - **Result**: 21 passed
2. `python -m pytest tests/test_sepolia_configuration.py tests/test_real_rpc_execution.py -m "not integration"`:
   - **Exit Code**: 0
   - **Result**: 53 passed, 4 deselected
3. `python -m pytest tests/test_sepolia_configuration.py tests/test_real_rpc_execution.py tests/test_beacon_redirect_security.py tests/test_campaign_matrix_v2.py tests/test_scenarios.py -m "not integration"`:
   - **Exit Code**: 0
   - **Result**: 95 passed, 4 deselected
4. Concrete reproduction scripts for Concern 1 (address staleness & memory id reuse) and Concern 2 (offline fallback to 31337).

### Tests Merely Inspected
- `tests/test_sepolia_configuration.py`: Lines 115–135 (`test_chain_id_validation_prevents_silent_cross_network_execution`)
- `tests/test_real_rpc_execution.py`: Lines 665–670 (`test_live_proxy_forwarding_and_chain_id`)

---

## 5. Git Status Confirmation

Executing `git status --short` confirms that no source files, test files, or tracked repository files were modified during this audit:
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
*(Only `scratch/focused_audit_report.md` was created; no tracked or staging changes).*
