# ChainC2 Sentinel — OpenAPI 3.0.3 Specification Generator
"""Programmatic OpenAPI 3.0.3 specification for ChainC2 Sentinel Master Dashboard & API."""

from __future__ import annotations

from typing import Any


def get_openapi_spec() -> dict[str, Any]:
    """Return the authoritative OpenAPI 3.0.3 specification dictionary."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "ChainC2 Sentinel REST API",
            "version": "2.0.0",
            "description": (
                "Cybersecurity Framework for Detecting and Mitigating Blockchain-Mediated "
                "Command-and-Control (C2) Channels on Ethereum Sepolia Testnet and Local Laboratories."
            ),
            "contact": {
                "name": "ChainC2 Sentinel Research Project",
            },
            "license": {
                "name": "Academic Research / Capstone Project License",
            },
        },
        "servers": [
            {
                "url": "/",
                "description": "Current active environment (AppSail CloudScale or Localhost)",
            },
            {
                "url": "https://chainc2-sentinel-service-50046833542.development.catalystappsail.in",
                "description": "Zoho Catalyst AppSail CloudScale Deployment",
            },
        ],
        "paths": {
            "/api/health": {
                "get": {
                    "summary": "Service health check",
                    "description": "Returns operational status, version, budget state, and execution permissions.",
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string", "example": "healthy"},
                                            "service": {"type": "string"},
                                            "version": {"type": "string", "example": "2.0.0-frozen"},
                                            "execution_enabled": {"type": "boolean"},
                                            "cloudscale_budget_state": {"type": "string", "example": "NORMAL"},
                                            "cloudscale_remaining_credits_usd": {"type": "number"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/overview": {
                "get": {
                    "summary": "Executive overview metrics",
                    "description": "Compiles benchmark scenario distribution, detection rates, system status, and cloud budget.",
                    "responses": {
                        "200": {
                            "description": "Overview metrics compiled successfully",
                        }
                    },
                }
            },
            "/api/evaluation/detection": {
                "get": {
                    "summary": "Phase 1 Detection benchmark analytics",
                    "responses": {
                        "200": {"description": "Detection rates, confusion matrix, and latency benchmarks"}
                    },
                }
            },
            "/api/evaluation/protection": {
                "get": {
                    "summary": "Phase 2 Defensive Protection benchmark analytics",
                    "responses": {
                        "200": {"description": "Mitigation efficacy, containment rates, and safety metrics"}
                    },
                }
            },
            "/api/experiments": {
                "get": {
                    "summary": "List experiment history (Alias to /api/experiments/history)",
                    "parameters": [
                        {"name": "scenario", "in": "query", "schema": {"type": "string"}},
                        {"name": "detection", "in": "query", "schema": {"type": "string"}},
                        {"name": "classification", "in": "query", "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    ],
                    "responses": {
                        "200": {"description": "List of experiment run summaries"}
                    },
                }
            },
            "/api/experiments/history": {
                "get": {
                    "summary": "Filterable experiment history",
                    "parameters": [
                        {"name": "scenario", "in": "query", "schema": {"type": "string"}},
                        {"name": "detection", "in": "query", "schema": {"type": "string"}},
                        {"name": "classification", "in": "query", "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    ],
                    "responses": {
                        "200": {"description": "Filtered list of experiment run records"}
                    },
                }
            },
            "/api/experiments/run/{run_id}": {
                "get": {
                    "summary": "Detailed multi-layer forensic record for a run",
                    "parameters": [
                        {"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {"description": "Full run detail including telemetry and score contributions"},
                        "404": {"description": "Run ID not found"},
                    },
                }
            },
            "/api/experiments/execute": {
                "post": {
                    "summary": "Execute controlled laboratory experiment",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "scenario": {"type": "string", "example": "scenario_b_synthetic_c2"},
                                        "repetitions": {"type": "integer", "default": 1, "minimum": 1, "maximum": 10},
                                    },
                                    "required": ["scenario"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Experiment executed successfully"},
                        "403": {"description": "Execution disabled in production mode"},
                        "409": {"description": "Experiment execution in progress (concurrency lock)"},
                    },
                }
            },
            "/api/telemetry/live": {
                "get": {
                    "summary": "Live telemetry event stream",
                    "parameters": [
                        {"name": "run_id", "in": "query", "schema": {"type": "string"}},
                        {"name": "source", "in": "query", "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    ],
                    "responses": {
                        "200": {"description": "List of normalized Sentinel events"}
                    },
                }
            },
            "/api/telemetry/ingest": {
                "post": {
                    "summary": "Ingest raw multi-layer telemetry events from remote VM or emitter",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "events": {
                                            "type": "array",
                                            "items": {"type": "object"}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Telemetry processed, correlated, and evaluated"}
                    }
                }
            },
            "/api/evidence": {
                "get": {
                    "summary": "List preserved forensic evidence bundles",
                    "responses": {
                        "200": {"description": "List of evidence bundle descriptors with SHA-256 checksums"}
                    },
                }
            },
            "/api/evidence/{bundle_id}": {
                "get": {
                    "summary": "Retrieve specific evidence bundle",
                    "parameters": [
                        {"name": "bundle_id", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {"description": "Full evidence bundle with correlated telemetry snapshot"},
                        "404": {"description": "Evidence bundle not found"},
                    },
                }
            },
            "/api/evidence/{bundle_id}/verify": {
                "post": {
                    "summary": "Verify SHA-256 integrity checksum of evidence bundle",
                    "parameters": [
                        {"name": "bundle_id", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {"description": "Verification result (VERIFIED or CORRUPTED)"},
                    },
                }
            },
            "/api/sepolia/status": {
                "get": {
                    "summary": "Ethereum Sepolia Testnet connectivity and monitor status",
                    "responses": {
                        "200": {
                            "description": "Chain ID, latest block height, RPC health, and contract configuration state",
                        }
                    },
                }
            },
            "/api/sepolia/transactions": {
                "get": {
                    "summary": "List observed public Sepolia transactions",
                    "parameters": [
                        {"name": "filter", "in": "query", "schema": {"type": "string", "enum": ["detected", "benign", "unclassified"]}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    ],
                    "responses": {
                        "200": {"description": "Observed Sepolia transactions buffer"},
                    },
                }
            },
            "/api/sepolia/poll": {
                "post": {
                    "summary": "Manually poll latest mined Sepolia blocks",
                    "responses": {
                        "200": {"description": "Polled block count and newly observed transactions"},
                    },
                }
            },
            "/api/sepolia/catch-up": {
                "post": {
                    "summary": "Manually trigger bounded catch-up of Sepolia monitoring cursor",
                    "parameters": [
                        {"name": "max_blocks", "in": "query", "schema": {"type": "integer", "default": 10}}
                    ],
                    "responses": {
                        "200": {"description": "Catch-up results, lag reduced, and transactions observed"},
                    },
                }
            },
            "/api/sepolia/alerts": {
                "get": {
                    "summary": "List Sepolia detection alerts",
                    "responses": {
                        "200": {"description": "Detection alerts triggered by cross-layer correlation"},
                    },
                }
            },
            "/api/sepolia/experiments": {
                "get": {
                    "summary": "List Sepolia correlated experiment history",
                    "responses": {
                        "200": {"description": "List of executed Sepolia experiment summaries"},
                    },
                }
            },
            "/api/sepolia/mitigations": {
                "get": {
                    "summary": "List Sepolia defensive mitigation records",
                    "responses": {
                        "200": {"description": "Mitigation actions executed, targets, and verification status"},
                    },
                }
            },
            "/api/sepolia/execute": {
                "post": {
                    "summary": "Execute controlled experiment with Sepolia correlation",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "experiment_type": {
                                            "type": "string",
                                            "enum": ["positive_c2", "benign_web3", "legitimate_dapp", "incomplete_sequence"],
                                            "default": "positive_c2",
                                        }
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Experiment executed and evaluated"},
                    },
                }
            },
            "/api/sepolia/rollback": {
                "post": {
                    "summary": "Rollback active defensive mitigations to restore baseline state",
                    "responses": {
                        "200": {"description": "Rollback status and action count reverted"},
                    },
                }
            },
            "/api/sepolia/verify-tx/{tx_hash}": {
                "get": {
                    "summary": "Independently verify transaction existence and contract target on Sepolia",
                    "parameters": [
                        {"name": "tx_hash", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "expected_contract", "in": "query", "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {"description": "On-chain verification status against Sepolia RPC receipt"},
                    },
                }
            },
            "/api/cloudscale/budget": {
                "get": {
                    "summary": "Zoho Catalyst CloudScale budget and safety monitor",
                    "responses": {
                        "200": {"description": "Authorized credit cap, remaining credits, and circuit breaker state"},
                    },
                }
            },
            "/api/cloudscale/status": {
                "get": {
                    "summary": "Zoho Catalyst CloudScale overall operational status",
                    "responses": {
                        "200": {"description": "CloudScale runtime environment, budget state, and cursor metadata"},
                    },
                }
            },
            "/api/cloudscale/cron/trigger": {
                "post": {
                    "summary": "Trigger a single bounded autonomous Catalyst Cron observer cycle",
                    "responses": {
                        "200": {"description": "Cycle result, blocks polled, and transactions cached"},
                    },
                }
            },
            "/api/alerts": {
                "get": {
                    "summary": "List all active detection alerts",
                    "parameters": [
                        {"name": "severity", "in": "query", "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    ],
                    "responses": {
                        "200": {"description": "List of detection alerts"},
                    },
                }
            },
            "/api/alerts/{alert_id}": {
                "get": {
                    "summary": "Retrieve specific alert detail",
                    "parameters": [
                        {"name": "alert_id", "in": "path", "required": True, "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {"description": "Alert record details and linked investigation ID"},
                        "404": {"description": "Alert not found"},
                    },
                }
            },
            "/api/investigations": {
                "get": {
                    "summary": "List all forensic investigation records",
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    ],
                    "responses": {
                        "200": {"description": "List of investigation records"},
                    },
                }
            },
            "/api/investigations/{investigation_id}": {
                "get": {
                    "summary": "Retrieve comprehensive investigation record with multi-layer evidence chain and timeline",
                    "parameters": [
                        {"name": "investigation_id", "in": "path", "required": True, "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {"description": "Granular investigation record"},
                        "404": {"description": "Investigation not found"},
                    },
                }
            },
            "/api/mitigations": {
                "get": {
                    "summary": "List defensive mitigation audit records",
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    ],
                    "responses": {
                        "200": {"description": "List of mitigation records with verification evidence"},
                    },
                }
            },
            "/api/system/health": {
                "get": {
                    "summary": "Retrieve system component health across monitor, RPC, persistence, and generator",
                    "responses": {
                        "200": {"description": "Component-by-component operational health status"},
                    },
                }
            },
            "/api/generator/status": {
                "get": {
                    "summary": "Operational status of the independent controlled generator",
                    "responses": {
                        "200": {"description": "Generator state, current scenario, and cycle counters"},
                    },
                }
            },
            "/api/generator/start": {
                "post": {
                    "summary": "Start the independent generator daemon or execute a single step",
                    "responses": {
                        "200": {"description": "Generator started or step completed"},
                    },
                }
            },
            "/api/generator/stop": {
                "post": {
                    "summary": "Stop the independent generator daemon",
                    "responses": {
                        "200": {"description": "Generator stopped"},
                    },
                }
            },
            "/api/generator/step": {
                "post": {
                    "summary": "Execute a single workload rotation cycle on-demand",
                    "responses": {
                        "200": {"description": "Single scenario cycle executed"},
                    },
                }
            },
            "/api/evaluation/post-run": {
                "get": {
                    "summary": "Evaluate detector performance against isolated generator ground-truth records",
                    "responses": {
                        "200": {"description": "Post-run confusion matrix, precision, recall, and F1 score"},
                    },
                }
            },
        },
    }
