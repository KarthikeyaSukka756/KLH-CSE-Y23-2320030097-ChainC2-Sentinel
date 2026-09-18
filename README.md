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

**Current Phase:** Phase 1 — Detection  
**Research Question:** *"Are blockchain-mediated C2 behaviors detectable?"*  
**Status:** 🟢 **Phase 1 Implementation In Progress (Milestones 1–3 Complete)**

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
- Python unit test suite (88 passing)

### Current Implementation Summary

The repository currently implements the foundational layers of Phase 1:
- Local Hardhat EVM testbed
- Synthetic smart contracts (`C2DataStore`, `BenignDAppContract`)
- `SentinelEvent` unified schema
- Modular collectors across endpoint, RPC, blockchain, and network telemetry
- JSON-RPC telemetry proxy
- Telemetry event normalizer
- File-based JSONL persistence
- Automated test suites (88 Python unit tests, 26 Hardhat contract tests)

### Next Milestones (Phase 1)

- **Completed:** Telemetry Foundation (Milestone 3)
- **Next:** Controlled Detection Scenarios (Milestone 4) → Cross-Layer Correlation (Milestone 5) → Detection Logic & Evidence Generation (Milestone 6) → Detection Evaluation (Milestone 7)
- **Later:** Phase 2 — Protection (Milestones 8–11: Defensive response design, controlled mitigation, and protection evaluation)

---

## Project Structure

```
src/
├── blockchain/          # Hardhat environment, Solidity contracts, deployment, tests
│   ├── contracts/       # C2DataStore.sol, BenignDAppContract.sol
│   ├── scripts/         # Contract deployment script
│   └── test/            # Hardhat/Mocha contract tests
├── collectors/          # Telemetry collectors (endpoint, RPC, blockchain, network)
├── models/              # SentinelEvent Pydantic v2 schema and sub-models
├── normalizer/          # Event normalizer and JSONL persistence
├── rpc_proxy/           # aiohttp JSON-RPC telemetry proxy
└── utils/               # UUID generation, structured logging
tests/                   # Python unit tests
docs/                    # Architecture documentation, development plan
```

---

## Validation Results

| Test Suite | Tests | Status |
|------------|-------|--------|
| Python unit tests (schema, collectors, normalizer, persistence) | 88 | ✅ Passing |
| Hardhat contract tests (C2DataStore, BenignDAppContract) | 26 | ✅ Passing |

These are actual test results from the current implementation. Detection accuracy, false-positive rate, and detection latency have not yet been experimentally measured and will be evaluated in future phases.

---

## Project Status

**Current Research Phase:** Phase 1 — Detection (Milestones 1–3 Implemented)  
**Next Research Target:** Phase 1, Milestone 4 — Controlled Detection Scenarios  

| Research Phase | Milestone | Focus Area | Status |
|:---|:---|:---|:---|
| **Phase 1 — Detection** | Milestone 1 | Project Infrastructure | ✅ Complete |
| **Phase 1 — Detection** | Milestone 2 | Synthetic Blockchain Environment | ✅ Complete |
| **Phase 1 — Detection** | Milestone 3 | Telemetry Foundation | ✅ Complete |
| **Phase 1 — Detection** | Milestone 4 | Controlled Detection Scenarios | ⏳ Not Yet Implemented |
| **Phase 1 — Detection** | Milestone 5 | Cross-Layer Correlation | ⏳ Not Yet Implemented |
| **Phase 1 — Detection** | Milestone 6 | Detection | ⏳ Not Yet Implemented |
| **Phase 1 — Detection** | Milestone 7 | Detection Evaluation | ⏳ Not Yet Implemented |
| **Phase 2 — Protection** | Milestone 8 | Defensive Response Design | 🔮 Future Research Phase |
| **Phase 2 — Protection** | Milestone 9 | Controlled Protection / Mitigation | 🔮 Future Research Phase |
| **Phase 2 — Protection** | Milestone 10 | Protection Evaluation | 🔮 Future Research Phase |
| **Phase 2 — Protection** | Milestone 11 | Final Research Analysis | 🔮 Future Research Phase |