# ChainC2 Sentinel — Zoho Catalyst CloudScale Operations Manual

## 1. Architectural Overview & Component Topology

ChainC2 Sentinel is engineered as a hybrid cloud-native, credit-aware cybersecurity detection and monitoring framework deployed on **Zoho Catalyst CloudScale**. It operates against the **Ethereum Sepolia Testnet** (Chain ID: `11155111`) within a hard financial budget cap of **USD $250.00** in authorized Catalyst credits.

```mermaid
graph TD
    subgraph "Public Interfaces"
        UserBrowser["Research Operator / Web Browser"]
        SepoliaRPC["Ethereum Sepolia Public RPC<br/>(Chain ID: 11155111)"]
        SepoliaExplorer["Sepolia Etherscan / Blockscout<br/>(Public Explorers)"]
    end

    subgraph "Zoho Catalyst CloudScale Environment ($250.00 Credit Cap)"
        WebClient["Web Client Hosting<br/>(SPA Dashboard Frontend)"]
        AppSail["AppSail Service<br/>(Flask REST API - Python 3.11, 512MB)"]
        CronFunction["Serverless Cron Function<br/>(functions/sepolia_cron - Python 3.11)"]
        BudgetMgr["Credit-Aware Budget Manager<br/>(Progressive Safety Policy)"]
        DataStore["Catalyst Data Store / Local Fallback<br/>(Transactions, Experiments, Cursors)"]
    end

    UserBrowser -->|HTTP GET / SPA Assets| WebClient
    UserBrowser -->|REST API Calls / Real-time Poll| AppSail
    WebClient -->|Proxied REST Calls| AppSail
    AppSail -->|Enforces Budget Limits| BudgetMgr
    AppSail -->|Reads / Writes Telemetry| DataStore
    CronFunction -->|Scheduled Execution (Every 5m)| BudgetMgr
    CronFunction -->|Polls Latest Blocks & Logs| SepoliaRPC
    CronFunction -->|Records Tx & State| DataStore
    UserBrowser -.->|Clickable Evidence Links| SepoliaExplorer
```

### Component Breakdown

| Catalyst Component | Repository Directory | Stack / Runtime | Operational Role |
| :--- | :--- | :--- | :--- |
| **Web Client Hosting** | `client/` | Static HTML5, CSS3, Vanilla ES6 JavaScript | Serves the single-page research dashboard, telemetry graphs, live feed, budget meter, and manual trigger controls. |
| **AppSail Service** | `appsail/` | Python 3.11, 512 MB Container | Hosts the core Sentinel REST API (`/api/sepolia/*`, `/api/cloudscale/*`, `/api/health`, `/api/overview`). Binds to `X_ZOHO_CATALYST_LISTEN_PORT`. |
| **Serverless Cron Function** | `functions/sepolia_cron/` | Python 3.11 Serverless Function | Scheduled worker executing continuous block observation, transaction ingestion, and authorized scenario execution without human intervention. |
| **Persistence Layer** | `src/cloudscale/storage_adapter.py` | Catalyst Data Store / Local JSON fallback | Dual-mode storage persisting `ObservedTransactions`, `ExperimentRuns`, and `MonitoringState` cursors. |
| **Budget Controller** | `src/cloudscale/budget_manager.py` | In-memory + persisted JSON state | Tracks function invocations, compute GB-seconds, AppSail uptime, and DB writes; enforces progressive safety thresholds. |

---

## 2. Financial Budget & Progressive Safety Controls

To guarantee compliance with the **USD $250.00** authorized credit limit and ensure **$0 in unauthorized out-of-pocket spending**, the system operates an active `CatalystBudgetManager`.

### Credit Consumption Rates

- **AppSail Container**: \$0.015 / compute hour (512 MB RAM)
- **Cron Serverless Function**: \$0.000016 / invocation + \$0.000002 / GB-second
- **Data Store Operations**: \$0.000001 / read/write operation
- **Data Storage**: \$0.0002 / MB-month

### Progressive Safety Tiers

| Tier | Credit Spent | Threshold Percentage | Operating Policy | Triggered Actions |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: NORMAL** | \$0.00 – \$187.49 | < 75.0% | Normal Autonomous Operations | Continuous cron polling every 5 minutes; authorized synthetic C2 experiments enabled; full dashboard telemetry streaming. |
| **Tier 2: WARNING** | \$187.50 – \$224.99 | 75.0% – 89.9% | Elevated Caution | Warning logs emitted; dashboard status badge transitions to amber; operators alerted to evaluate remaining test campaign tasks. |
| **Tier 3: PAUSE_EXPERIMENTS** | \$225.00 – \$237.49 | 90.0% – 94.9% | Read-Only Monitoring | All synthetic C2 scenario executions and automated transaction submissions are suspended. Passive Sepolia block observation continues. |
| **Tier 4: SAFE_SHUTDOWN** | $\ge$ \$237.50 | $\ge$ 95.0% | Fail-Safe Halting | Immediate cessation of all cron function cycles, background telemetry polls, and AppSail compute loops. Prevents credit exhaustion or billable overrun. |

---

## 3. Environment Configuration & Secret Handling

All deployment configuration is managed declaratively in [`catalyst.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone Project - 1/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/catalyst.json), [`appsail/app-config.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone Project - 1/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/appsail/app-config.json), and [`functions/sepolia_cron/catalyst-config.json`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone Project - 1/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/functions/sepolia_cron/catalyst-config.json).

### Environment Variables Template

Configure the following variables in the Zoho Catalyst CloudScale Console under **AppSail > Configuration > Environment Variables** and **Functions > Environment Variables**:

```bash
# ==============================================================================
# Blockchain Network Configuration (Ethereum Sepolia Testnet)
# ==============================================================================
SEPOLIA_CHAIN_ID=11155111
SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
BLOCK_EXPLORER_TX_BASE=https://sepolia.etherscan.io/tx/
BLOCK_EXPLORER_ADDRESS_BASE=https://sepolia.etherscan.io/address/

# ==============================================================================
# Financial & Safety Configuration
# ==============================================================================
CATALYST_BUDGET_CAP_USD=250.00
CATALYST_WARNING_THRESHOLD=0.75
CATALYST_PAUSE_THRESHOLD=0.90
CATALYST_SHUTDOWN_THRESHOLD=0.95

# ==============================================================================
# Smart Contract & Security Credentials (Zoho Catalyst Secrets Manager)
# ==============================================================================
# NOTE: Store private keys strictly in Catalyst Secrets Manager, NEVER in plaintext files.
C2_DEPLOYER_PRIVATE_KEY=<ENCRYPTED_IN_CATALYST_SECRETS_STORE>
C2_ROUTER_CONTRACT_ADDRESS=0x71C8A33E2B8D2c99a538202512F43f382a93Eb3B
```

---

## 4. Deployment Prerequisites & Execution Procedures

### Prerequisite 1: Catalyst CLI Installation

The Zoho Catalyst CLI (`zcatalyst-cli`) is already installed globally on the deployment environment:
```bash
catalyst --version
# Expected output: zcatalyst-cli v1.29.0
```

### Prerequisite 2: Account Authentication

Zoho Catalyst requires interactive OAuth authentication to link the deployment workspace to your Zoho account. Run either of the following commands in your host terminal:

1. **Standard Browser Login**:
   ```bash
   catalyst login
   ```
   *This opens a browser tab requesting your Zoho CloudScale authorization.*

2. **Headless / Terminal-Based Login**:
   ```bash
   catalyst login --no-localhost
   ```
   *This outputs an authorization URL. Open the URL on any browser, approve permissions, and paste the returned verification token into the terminal prompt.*

3. **Verify Authentication**:
   ```bash
   catalyst whoami
   ```
   *Displays your logged-in email and associated Zoho Catalyst Organization ID.*

---

### Step 3: Automated One-Click Deployment Pipeline

A dedicated automated deployment script [`scripts/deploy_catalyst.py`](file:///c:/Users/KARTHIKEYA/OneDrive/Desktop/Capstone Project - 1/KLH-CSE-Y23-2320030097-ChainC2-Sentinel/scripts/deploy_catalyst.py) performs prerequisite checks, configuration audits, regression testing, and deployment:

```bash
# Dry run verification (validates files, tests, and CLI parameters without deploying):
python scripts/deploy_catalyst.py --dry-run

# Live production deployment:
python scripts/deploy_catalyst.py --deploy
```

### Step 4: Manual Deployment Commands (Alternative)

If you prefer deploying individual targets directly using the Catalyst CLI:

```bash
# Associate workspace with your Catalyst project:
catalyst project:use

# Deploy Web Client, AppSail service, and Cron function:
catalyst deploy --only client,appsail,functions:sepolia_cron
```

---

## 5. System Health Verification & Endpoint Auditing

Following deployment, probe the following endpoints on the deployed AppSail URL to verify nominal operations:

### 1. Health Status Probe
```bash
curl -s https://<your-appsail-domain>.catalystappsail.com/api/health
```
**Expected Response**:
```json
{
  "status": "HEALTHY",
  "version": "1.0.0",
  "platform": "Zoho Catalyst CloudScale",
  "chain_id": 11155111,
  "budget_state": "NORMAL"
}
```

### 2. Credit Budget Probe
```bash
curl -s https://<your-appsail-domain>.catalystappsail.com/api/cloudscale/budget
```
**Expected Response**:
```json
{
  "status": "success",
  "budget": {
    "cap_usd": 250.0,
    "total_spent_usd": 0.05,
    "remaining_usd": 249.95,
    "burn_rate_pct": 0.02,
    "operating_state": "NORMAL"
  }
}
```

### 3. Manual Cron Function Execution Probe
```bash
curl -s -X POST https://<your-appsail-domain>.catalystappsail.com/api/cloudscale/cron/trigger
```
**Expected Response**:
```json
{
  "status": "success",
  "result": {
    "status": "SUCCESS",
    "operating_state": "NORMAL",
    "blocks_polled": 1,
    "new_transactions": 24,
    "remaining_budget_usd": 249.9499
  }
}
```

---

## 6. Autonomous Operation Lifecycle & Fail-Safe Recovery

1. **Autonomous Polling**: The serverless cron function executes on a 5-minute recurrence rule configured in Zoho Catalyst Cron.
2. **Deterministic Logging**: Every cycle records block hashes, processed transaction counts, remaining budget, and execution time.
3. **Fail-Safe Circuit Breaker**: If RPC errors occur, the cron cycle gracefully logs `RPC_UNAVAILABLE` without crashing or spinning CPU cycles.
4. **Budget Depletion Recovery**:
   - If `SAFE_SHUTDOWN` is entered ($237.50 spent), the system halts all operations to protect against billable charges.
   - To resume after reviewing billing, reset the budget tracking state:
     ```bash
     python -c "from src.cloudscale.budget_manager import CatalystBudgetManager; CatalystBudgetManager().reset()"
     ```

