# ChainC2 Sentinel — Telemetry Architecture

## Overview

This document describes the telemetry foundation for ChainC2 Sentinel — the data collection, normalization, and persistence layer that captures controlled laboratory activity across four telemetry sources.

**Research Phase:** Phase 1 — Detection  
**Milestone:** Milestone 3 — Telemetry Foundation  
**Research Question Addressed:** *"Can cross-layer telemetry correlation detect blockchain-mediated C2-like behavioral sequences while distinguishing them from legitimate Web3 activity?"*

Telemetry serves as the foundational, enabling data layer for the Phase 1 detection research question. Rather than acting as a standalone detection system, this foundation collects, normalizes, and stores the multi-source evidence necessary to enable downstream cross-layer correlation (Milestone 5) and detection logic (Milestone 6).

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Controlled Laboratory                        │
│                                                                      │
│  ┌─────────────┐    ┌───────────────┐    ┌───────────────────────┐  │
│  │  Endpoint    │    │  Web3 Client  │    │  Controlled HTTP      │  │
│  │  Processes   │    │  (web3.py)    │    │  Target               │  │
│  └──────┬──────┘    └───────┬───────┘    └───────────┬───────────┘  │
│         │                   │                         │              │
│         ▼                   ▼                         ▼              │
│  ┌──────────────┐   ┌──────────────┐          ┌──────────────┐     │
│  │  Endpoint    │   │  RPC Proxy   │          │  Network     │     │
│  │  Collector   │   │  (aiohttp)   │          │  Collector   │     │
│  └──────┬──────┘   └──────┬───────┘          └──────┬──────┘     │
│         │                  │                         │              │
│         │                  ▼                         │              │
│         │           ┌──────────────┐                │              │
│         │           │  Hardhat     │                │              │
│         │           │  Node        │                │              │
│         │           └──────┬──────┘                │              │
│         │                  │                         │              │
│         │                  ▼                         │              │
│         │           ┌──────────────┐                │              │
│         │           │  Blockchain  │                │              │
│         │           │  Collector   │                │              │
│         │           └──────┬──────┘                │              │
│         │                  │                         │              │
│         ▼                  ▼                         ▼              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   Event Normalizer                          │   │
│  │            raw dict → validated SentinelEvent               │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│                             ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   Event Store (JSONL)                        │   │
│  │              data/telemetry/events.jsonl                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## SentinelEvent Schema

The `SentinelEvent` is the common normalized event representation. All telemetry sources produce events in this format.

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | `str` | Auto | UUID4, auto-generated |
| `timestamp` | `datetime` | Yes | UTC timestamp |
| `source` | `TelemetrySource` | Yes | `endpoint`, `rpc`, `blockchain`, or `network` |
| `event_type` | `str` | Yes | Specific event type (e.g. `process_snapshot`, `rpc_call`) |
| `host` | `str` | No | Host identifier |
| `process` | `ProcessInfo` | No | Endpoint process metadata |
| `rpc` | `RpcInfo` | No | RPC request/response metadata |
| `blockchain` | `BlockchainInfo` | No | Blockchain interaction metadata |
| `network` | `NetworkInfo` | No | Network activity metadata |
| `metadata` | `dict` | No | Extensible key-value pairs (default: `{}`) |

### TelemetrySource Enum

| Value | Description |
|-------|-------------|
| `endpoint` | Local process metadata |
| `rpc` | JSON-RPC request/response pairs |
| `blockchain` | Synthetic smart-contract interactions |
| `network` | Controlled HTTP/network activity |

### ProcessInfo

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `process_name` | `str` | Yes | Process name |
| `pid` | `int` | Yes | Process ID |
| `parent_pid` | `int` | No | Parent process ID |
| `executable` | `str` | No | Executable path |
| `command_args` | `list[str]` | No | Command-line arguments |

### RpcInfo

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `rpc_endpoint` | `str` | Yes | Client-facing RPC proxy address |
| `upstream_endpoint` | `str` | Yes | Upstream Hardhat node address |
| `rpc_method` | `str` | Yes | JSON-RPC method name |
| `request_id` | `str` | No | JSON-RPC request ID |
| `request_params` | `dict` | No | Safe parameter summary |
| `response_result` | `dict` | No | Safe result summary |
| `status` | `str` | Yes | `success` or `error` |
| `error_message` | `str` | No | Error message |
| `duration_ms` | `float` | No | Round-trip duration (ms) |

**Important:** `rpc_endpoint` and `upstream_endpoint` are always distinct. The RPC proxy is telemetry infrastructure, not C2.

### BlockchainInfo

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tx_hash` | `str` | No | Transaction hash |
| `block_number` | `int` | No | Block number |
| `contract_address` | `str` | No | Smart contract address |
| `chain_id` | `str` | No | Chain identifier (default: `31337`) |
| `network_name` | `str` | No | Network name (default: `hardhat`) |
| `sender` | `str` | No | Sender address |
| `function_name` | `str` | No | Called function name |
| `event_name` | `str` | No | Emitted event name |
| `event_args` | `dict` | No | Event arguments |
| `contract_name` | `str` | No | `C2DataStore`, `BenignDAppContract`, or `LegitimateDAppContract` |

### NetworkInfo

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `destination_host` | `str` | Yes | Destination host/IP |
| `destination_port` | `int` | Yes | Destination port |
| `protocol` | `str` | Yes | Protocol (e.g. `HTTP`, `TCP`) |
| `source_process` | `str` | No | Source process name |
| `request_type` | `str` | No | Request type (e.g. `GET`, `POST`) |
| `status_code` | `int` | No | HTTP status code |
| `response_size_bytes` | `int` | No | Response body size |

---

## Source-to-Event Flow

### Endpoint Telemetry

```
Python process → LocalEndpointCollector.collect()
                      │
                      ▼
              SentinelEvent(source=ENDPOINT, process=ProcessInfo(...))
```

- Captures the current Python process's own metadata
- Uses `os.getpid()`, `os.getppid()`, `sys.executable`, `platform.node()`
- Does NOT enumerate all running processes

### RPC Telemetry

```
Web3 client ─POST→ RPC Proxy (client-facing :8546)
                      │
                      ├─ capture metadata ─→ RpcTelemetryCollector.collect()
                      │                           │
                      │                           ▼
                      │                   SentinelEvent(source=RPC, rpc=RpcInfo(...))
                      │
                      └─POST→ Hardhat Node (upstream :8545)
                                │
                                └─response→ RPC Proxy ─response→ Web3 client
```

- `rpc_endpoint` = client-facing proxy address
- `upstream_endpoint` = Hardhat node address

### Blockchain Telemetry

```
Transaction/event metadata → BlockchainTelemetryCollector.collect()
                                  │
                                  ▼
                          SentinelEvent(source=BLOCKCHAIN, blockchain=BlockchainInfo(...))
```

- Accepts metadata from Hardhat node interactions
- `contract_name` distinguishes C2DataStore from BenignDAppContract

### Network Telemetry

```
HTTP activity observation → NetworkTelemetryCollector.collect()
                                 │
                                 ▼
                         SentinelEvent(source=NETWORK, network=NetworkInfo(...))
```

- Controlled local HTTP/network activity only
- No packet capture or kernel-level instrumentation

---

## Persistence

Events are persisted in JSONL format (one JSON object per line):

```
data/telemetry/events.jsonl
```

The `EventStore` provides:
- `append(event)` — write one event
- `append_many(events)` — write multiple events
- `load_events()` — read all events back as validated `SentinelEvent` objects
- `count()` — count stored events
- `clear()` — truncate the file

The interface is deliberately simple so it can be replaced with PostgreSQL or another backend in later phases without changing collector or normalizer code.

---

## Relationship to ChainC2 Sentinel Architecture

```
Phase 1 — Detection                                                    Phase 2 — Protection
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ Milestone 3: Telemetry   │ ──→ │ Milestone 5: Cross-Layer│ ──→ │ Milestone 6 & 7:        │ ──→ │ Milestones 8–11:        │
│ Foundation (Implemented)│     │ Correlation (Future)    │     │ Detection & Evaluation  │     │ Defensive Response &    │
│                         │     │                         │     │ (Future)                │     │ Mitigation (Future)     │
│ • SentinelEvent schema  │     │ • Temporal correlation  │     │ • Detection logic       │     │ • Defensive response    │
│ • 4 Telemetry collectors│     │ • Multi-source linkage  │     │ • Heuristic rules       │     │ • Controlled mitigation │
│ • RPC proxy telemetry   │     │ • Evidence-chain        │     │ • Alert generation      │     │ • Protection evaluation │
│ • Event normalizer      │     │   reconstruction        │     │ • Measured metrics      │     │ • Security analysis     │
│ • JSONL persistence     │     │                         │     │ • Baseline comparison   │     │                         │
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘
```

The intended detection evidence chain flows as:
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
Cross-Layer Correlation (Phase 1, Milestone 5)
       ↓
Detection Logic (Phase 1, Milestone 6)
       ↓
Evidence / Alert (Phase 1, Milestone 6)
```

---

## What Is Implemented

- Pydantic v2 `SentinelEvent` schema with strict validation
- Four source-specific telemetry collectors (endpoint, RPC, blockchain, network)
- aiohttp-based RPC proxy with telemetry capture (distinct from upstream Hardhat node)
- `EventNormalizer` for raw dict → validated event conversion
- JSONL `EventStore` for persistence
- Utility modules (UUID generation, structured logging)
- Comprehensive unit tests (88 passing)

## What Is NOT Implemented (Deferred to Future Milestones)

- **Phase 1, Milestone 4:** Controlled detection scenarios (benign Web3 baseline and synthetic C2-like scenarios)
- **Phase 1, Milestone 5:** Cross-source event correlation and temporal evidence linking
- **Phase 1, Milestone 6:** Detection rules, heuristics, behavioral suspicion scoring, and alert generation
- **Phase 1, Milestone 7:** Detection evaluation metrics (accuracy, precision, recall, latency, false-positive analysis)
- **Phase 2, Milestones 8–11:** Defensive response design, controlled mitigation, protection evaluation, and final analysis
- OS-wide process enumeration or ETW/eBPF kernel instrumentation
- Packet capture or promiscuous network monitoring
- Public blockchain interactions or real-world malware execution
