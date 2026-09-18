# ChainC2 Sentinel — Explainable Rule-Based Weighted Scoring
"""Explainable rule-based weighted scoring engine for cross-layer evidence chains.

Architecture:
    Telemetry
        ↓
    Normalization
        ↓
    CorrelationEngine
        ↓
    CorrelatedSequence
        ↓
    Weighted Rule-Based Scoring
        ↓
    DetectionEngine
        ↓
    DetectionResult

IMPORTANT METHODOLOGICAL DECLARATION:
These weights are CONFIGURABLE HEURISTIC WEIGHTS designed to quantify observable
evidence alignment with a multi-layer blockchain C2 sequence pattern.
They are NOT:
- probabilities
- machine learning parameters
- universal constants
- proof of maliciousness

The scoring engine strictly evaluates factual observable telemetry attributes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.correlation.models import CorrelatedSequence
from src.models.events import TelemetrySource

logger = logging.getLogger("chainc2_sentinel.detection.scoring")


# --- Default Heuristic Weight Table ---
DEFAULT_WEIGHT_ENDPOINT_CONTEXT = 10.0
DEFAULT_WEIGHT_RPC_INTERACTION = 10.0
DEFAULT_WEIGHT_CONTRACT_INTERACTION = 15.0
DEFAULT_WEIGHT_SUSPICIOUS_RETRIEVAL = 20.0
DEFAULT_WEIGHT_C2_CONFIGURATION = 20.0
DEFAULT_WEIGHT_NETWORK_FOLLOWUP = 25.0
DEFAULT_DETECTION_THRESHOLD = 80.0


class ScoringRuleContribution(BaseModel):
    """Factual contribution of a specific heuristic scoring rule."""

    model_config = ConfigDict(extra="forbid")

    rule: str = Field(..., description="Scoring rule identifier")
    weight: float = Field(..., description="Assigned heuristic weight")
    description: str = Field(..., description="Human-readable rule description")
    satisfied: bool = Field(..., description="Whether this scoring condition was met")
    evidence_detail: Optional[str] = Field(
        default=None, description="Observable value or reason supporting satisfaction/failure"
    )


class ScoringResult(BaseModel):
    """Explainable result of weighted scoring against a CorrelatedSequence."""

    model_config = ConfigDict(extra="forbid")

    total_score: float = Field(..., description="Sum of satisfied weights (0-100)")
    threshold: float = Field(..., description="Deterministic decision threshold")
    contributions: list[dict[str, Any]] = Field(
        default_factory=list, description="List of rule contribution dicts"
    )
    matched_scoring_rules: list[str] = Field(
        default_factory=list, description="IDs of satisfied scoring rules"
    )
    unmatched_scoring_rules: list[str] = Field(
        default_factory=list, description="IDs of unsatisfied scoring rules"
    )
    is_triggered: bool = Field(
        ..., description="True if total_score >= threshold, False otherwise"
    )
    explanation: str = Field(..., description="Human-readable scoring explanation")


class RuleBasedScorer:
    """Calculates explainable, deterministic weighted scores from correlated behavioral evidence."""

    def __init__(
        self,
        weight_endpoint: float = DEFAULT_WEIGHT_ENDPOINT_CONTEXT,
        weight_rpc: float = DEFAULT_WEIGHT_RPC_INTERACTION,
        weight_contract: float = DEFAULT_WEIGHT_CONTRACT_INTERACTION,
        weight_retrieval: float = DEFAULT_WEIGHT_SUSPICIOUS_RETRIEVAL,
        weight_c2_config: float = DEFAULT_WEIGHT_C2_CONFIGURATION,
        weight_network: float = DEFAULT_WEIGHT_NETWORK_FOLLOWUP,
        threshold: float = DEFAULT_DETECTION_THRESHOLD,
    ) -> None:
        self.weight_endpoint = weight_endpoint
        self.weight_rpc = weight_rpc
        self.weight_contract = weight_contract
        self.weight_retrieval = weight_retrieval
        self.weight_c2_config = weight_c2_config
        self.weight_network = weight_network
        self.threshold = threshold

    def score(self, sequence: CorrelatedSequence) -> ScoringResult:
        """Evaluate observable sequence evidence and calculate deterministic score."""
        contributions: list[ScoringRuleContribution] = []

        # 1. Endpoint/Process Context (+10)
        has_endpoint = sequence.endpoint_event is not None
        proc_name = (
            sequence.endpoint_event.process.process_name
            if (has_endpoint and sequence.endpoint_event and sequence.endpoint_event.process)
            else None
        )
        contributions.append(
            ScoringRuleContribution(
                rule="endpoint_context",
                weight=self.weight_endpoint,
                description="Endpoint/process context identified in sequence",
                satisfied=has_endpoint,
                evidence_detail=f"Process: '{proc_name}'" if has_endpoint else "No endpoint telemetry",
            )
        )

        # 2. RPC Interaction (+10)
        has_rpc = sequence.rpc_event is not None
        rpc_method = (
            sequence.rpc_event.rpc.rpc_method
            if (has_rpc and sequence.rpc_event and sequence.rpc_event.rpc)
            else None
        )
        contributions.append(
            ScoringRuleContribution(
                rule="rpc_interaction",
                weight=self.weight_rpc,
                description="Client JSON-RPC interaction observed",
                satisfied=has_rpc,
                evidence_detail=f"Method: '{rpc_method}'" if has_rpc else "No RPC telemetry",
            )
        )

        # 3. Contract Interaction (+15)
        has_bc = sequence.blockchain_event is not None
        contract = sequence.contract_name
        func = sequence.function_name
        contributions.append(
            ScoringRuleContribution(
                rule="contract_interaction",
                weight=self.weight_contract,
                description="Smart contract interaction observed on blockchain layer",
                satisfied=has_bc,
                evidence_detail=f"Contract: '{contract}'" if has_bc else "No blockchain telemetry",
            )
        )

        # 4. Suspicious Data Retrieval (+20)
        # Evaluates whether the contract targeted is a known dead-drop / command store
        is_suspicious_retrieval = False
        retrieval_detail = "Target contract is not a command or dead-drop store"
        if has_bc and contract:
            if contract == "C2DataStore" or (func and ("command" in func.lower() or "c2" in func.lower())):
                is_suspicious_retrieval = True
                retrieval_detail = f"Target '{contract}' acts as a dead-drop command data store"
        contributions.append(
            ScoringRuleContribution(
                rule="suspicious_retrieval",
                weight=self.weight_retrieval,
                description="Smart contract interaction targets a dead-drop / command store",
                satisfied=is_suspicious_retrieval,
                evidence_detail=retrieval_detail,
            )
        )

        # 5. C2 / Configuration Indicator (+20)
        # Evaluates whether retrieved data or parameters contain synthetic C2 command structures
        has_c2_indicator = False
        c2_detail = "No C2 command structure or configuration indicator detected"
        if is_suspicious_retrieval:
            # Check for synthetic command markers in events or metadata
            for ev in sequence.events:
                # Check metadata or event args
                meta_str = str(ev.metadata).lower()
                if "cmd:" in meta_str or "synthetic_c2" in meta_str or "beacon" in meta_str:
                    has_c2_indicator = True
                    c2_detail = "Synthetic C2 payload/command structure identified"
                    break
                if ev.blockchain and ev.blockchain.event_args:
                    args_str = str(ev.blockchain.event_args).lower()
                    if "cmd:" in args_str or "synthetic" in args_str:
                        has_c2_indicator = True
                        c2_detail = "Synthetic C2 command structure in event args"
                        break
        contributions.append(
            ScoringRuleContribution(
                rule="c2_configuration",
                weight=self.weight_c2_config,
                description="Retrieved data or event contains C2 command/configuration indicator",
                satisfied=has_c2_indicator,
                evidence_detail=c2_detail,
            )
        )

        # 6. Matched Subsequent Network Activity (+25)
        # Requires outbound network event strictly chronologically at/after blockchain read (Δt >= 0)
        # and conforming to full causal sequence
        has_net = sequence.network_event is not None
        has_matched_net = False
        net_detail = "No subsequent network activity observed"
        if has_bc and has_net and sequence.blockchain_event and sequence.network_event:
            delta_ms = (
                sequence.network_event.timestamp - sequence.blockchain_event.timestamp
            ).total_seconds() * 1000.0
            if delta_ms >= 0:
                # Also verify causal ordering: endpoint <= rpc <= bc <= net
                if has_endpoint and has_rpc and sequence.endpoint_event and sequence.rpc_event:
                    t_ep = sequence.endpoint_event.timestamp
                    t_rpc = sequence.rpc_event.timestamp
                    t_bc = sequence.blockchain_event.timestamp
                    t_net = sequence.network_event.timestamp
                    if t_ep <= t_rpc and t_rpc <= t_bc and t_bc <= t_net:
                        has_matched_net = True
                        net_dest = (
                            f"{sequence.network_event.network.destination_host}:{sequence.network_event.network.destination_port}"
                            if sequence.network_event.network
                            else "local target"
                        )
                        net_detail = f"Network communication to '{net_dest}' occurred {round(delta_ms, 2)}ms after blockchain read with verified multi-layer causality"
                    else:
                        net_detail = "Network event present but multi-layer causal order was violated"
                else:
                    net_detail = f"Network event occurred {round(delta_ms, 2)}ms after blockchain read (incomplete prior layers)"
            else:
                net_detail = f"Causality violation: network event occurred {round(abs(delta_ms), 2)}ms BEFORE blockchain interaction"

        contributions.append(
            ScoringRuleContribution(
                rule="network_followup",
                weight=self.weight_network,
                description="Subsequent network activity chronologically following blockchain interaction (Δt >= 0)",
                satisfied=has_matched_net,
                evidence_detail=net_detail,
            )
        )

        # Calculate total score
        total_score = sum(c.weight for c in contributions if c.satisfied)
        matched_rules = [c.rule for c in contributions if c.satisfied]
        unmatched_rules = [c.rule for c in contributions if not c.satisfied]
        is_triggered = total_score >= self.threshold

        # Structured contribution dictionaries matching prompt schema
        contrib_dicts = [
            {
                "rule": c.rule,
                "weight": c.weight,
                "description": c.description,
                "satisfied": c.satisfied,
                "evidence_detail": c.evidence_detail,
            }
            for c in contributions
        ]

        # Transparent explanation
        if is_triggered:
            explanation = (
                f"Detection threshold exceeded: Total score {total_score:.1f}/{self.threshold:.1f}. "
                f"Matched behavioral rules: {', '.join(matched_rules)}."
            )
        else:
            explanation = (
                f"Detection threshold not met: Total score {total_score:.1f}/{self.threshold:.1f}. "
                f"Unmatched rules: {', '.join(unmatched_rules)}."
            )

        return ScoringResult(
            total_score=total_score,
            threshold=self.threshold,
            contributions=contrib_dicts,
            matched_scoring_rules=matched_rules,
            unmatched_scoring_rules=unmatched_rules,
            is_triggered=is_triggered,
            explanation=explanation,
        )
