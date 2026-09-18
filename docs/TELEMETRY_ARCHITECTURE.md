# ChainC2 Sentinel — Telemetry Architecture

## Overview

This document describes the telemetry foundation for ChainC2 Sentinel — the data collection, normalization, and persistence layer that captures controlled laboratory activity across four telemetry sources.

**Scope:** This document covers the telemetry foundation only. Correlation, detection, scoring, and evaluation are deferred to Phase 2 and Phase 3.

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
| `contract_name` | `str` | No | `C2DataStore` or `BenignDAppContract` |

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
Phase 1 (this milestone)          Phase 2 (future)          Phase 3 (future)
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│ Telemetry Foundation │──→│ Correlation Engine    │──→│ Evaluation &         │
│                      │   │                      │   │ Analysis             │
│ • SentinelEvent      │   │ • Cross-source       │   │ • Metrics            │
│ • Collectors (4)     │   │   correlation        │   │ • False-positive     │
│ • RPC Proxy          │   │ • Evidence chains    │   │   analysis           │
│ • Normalizer         │   │ • Detection rules    │   │ • Visualization      │
│ • Event Store        │   │ • Scoring            │   │ • Research paper     │
└──────────────────────┘   └──────────────────────┘   └──────────────────────┘
```

---

## What Is Implemented

- Pydantic v2 `SentinelEvent` schema with strict validation
- Four source-specific telemetry collectors
- aiohttp-based RPC proxy with telemetry capture
- `EventNormalizer` for raw dict → validated event conversion
- JSONL `EventStore` for persistence
- Utility modules (UUID generation, structured logging)
- Comprehensive unit tests

## What Is NOT Implemented (Deferred)

- Cross-source event correlation
- Detection rules or heuristics
- Behavioral or suspicion scoring
- ML-based detection
- Alert ranking or automated response
- Dashboard or visualization
- Evaluation metrics or performance claims
- OS-wide process enumeration or ETW/eBPF
- Packet capture or kernel-level instrumentation
- Public blockchain interaction
