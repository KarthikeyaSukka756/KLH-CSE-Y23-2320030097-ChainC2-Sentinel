# ChainC2 Sentinel — Detection Rules
"""Rule-based detection algorithms that evaluate CorrelatedSequence evidence chains.

Each rule defines explicit, observable conditions based on multi-source laboratory telemetry.
"""

from __future__ import annotations

import abc
import logging
from typing import Any

from src.correlation.models import CorrelatedSequence
from src.detection.models import (
    DetectionConditionMatch,
    DetectionResult,
    DetectionStatus,
)
from src.detection.scoring import RuleBasedScorer

logger = logging.getLogger("chainc2_sentinel.detection.rules")


class BaseDetectionRule(abc.ABC):
    """Abstract base class for explainable detection rules."""

    rule_id: str = "BASE-RULE"
    rule_name: str = "Base Detection Rule"
    rule_version: str = "1.0.0"
    description: str = "Abstract detection rule base"

    @abc.abstractmethod
    def evaluate(self, sequence: CorrelatedSequence) -> DetectionResult:
        """Evaluate observable conditions on a CorrelatedSequence.

        Args:
            sequence: The correlated behavioral sequence.

        Returns:
            DetectionResult documenting matched/unmatched conditions and factual explanation.
        """
        pass


class SyntheticC2SequenceRule(BaseDetectionRule):
    """Detects the multi-layer synthetic blockchain-mediated C2 behavioral pattern.

    Evaluation Conditions:
        1. cond_endpoint: Endpoint process event exists.
        2. cond_rpc: Client-facing RPC proxy interaction exists.
        3. cond_blockchain: Smart contract interaction exists.
        4. cond_c2datastore: Blockchain event targets C2DataStore (synthetic C2 data store).
        5. cond_network: Outbound network activity event exists.
        6. cond_network_timing: Network event occurs strictly at or after blockchain interaction (Δt >= 0).
        7. cond_causal_timeline: Full multi-layer timeline causality is preserved (t_endpoint <= t_rpc <= t_bc <= t_net).

    Negative Control Guarantees:
        - Benign Web3 baseline (BenignDAppContract) fails condition 4 (and 5).
        - Blockchain interaction alone with no network follow-up fails condition 5 and 6.
        - Out-of-order network activity preceding blockchain reads fails condition 6 and 7.
        - Incomplete sequences fail missing layer conditions.
    """

    rule_id = "RULE-CHAINC2-001"
    rule_name = "Synthetic Blockchain-Mediated C2 Pattern"
    rule_version = "1.0.0"
    description = (
        "Identifies correlated multi-layer behavior where an endpoint executes an RPC call to "
        "retrieve synthetic C2 configuration from C2DataStore followed by local network communication."
    )

    def __init__(self, scorer: Optional[RuleBasedScorer] = None) -> None:
        self.scorer = scorer or RuleBasedScorer()

    def evaluate(self, sequence: CorrelatedSequence) -> DetectionResult:
        """Evaluate the 7 observable conditions and calculate explainable weighted score."""
        conditions: list[DetectionConditionMatch] = []
        evidence: dict[str, Any] = {
            "correlation_id": sequence.correlation_id,
            "run_id": sequence.run_id,
            "scenario_id": sequence.scenario_id,
            "duration_ms": sequence.duration_ms,
        }

        # Calculate explainable weighted score
        scoring_result = self.scorer.score(sequence)

        # Condition 1: Endpoint process event exists
        has_endpoint = sequence.endpoint_event is not None
        proc_name = (
            sequence.endpoint_event.process.process_name
            if (has_endpoint and sequence.endpoint_event and sequence.endpoint_event.process)
            else None
        )
        conditions.append(
            DetectionConditionMatch(
                condition_id="cond_endpoint",
                description="Endpoint/process telemetry event exists in sequence",
                satisfied=has_endpoint,
                evidence_detail=f"Process: '{proc_name}'" if has_endpoint else "No endpoint event",
            )
        )
        if proc_name:
            evidence["process_name"] = proc_name

        # Condition 2: RPC interaction exists
        has_rpc = sequence.rpc_event is not None
        rpc_method = (
            sequence.rpc_event.rpc.rpc_method
            if (has_rpc and sequence.rpc_event and sequence.rpc_event.rpc)
            else None
        )
        conditions.append(
            DetectionConditionMatch(
                condition_id="cond_rpc",
                description="JSON-RPC interaction event exists in sequence",
                satisfied=has_rpc,
                evidence_detail=f"RPC method: '{rpc_method}'" if has_rpc else "No RPC event",
            )
        )
        if rpc_method:
            evidence["rpc_method"] = rpc_method

        # Condition 3: Blockchain interaction exists
        has_bc = sequence.blockchain_event is not None
        contract = sequence.contract_name
        func = sequence.function_name
        conditions.append(
            DetectionConditionMatch(
                condition_id="cond_blockchain",
                description="Smart-contract interaction event exists in sequence",
                satisfied=has_bc,
                evidence_detail=f"Contract: '{contract}'" if has_bc else "No blockchain event",
            )
        )

        # Condition 4: Blockchain targets C2DataStore (synthetic C2 contract)
        is_c2_contract = has_bc and contract == "C2DataStore"
        conditions.append(
            DetectionConditionMatch(
                condition_id="cond_c2datastore",
                description="Smart-contract interaction targets synthetic C2DataStore",
                satisfied=is_c2_contract,
                evidence_detail=(
                    f"Target is '{contract}' (function: '{func}')"
                    if has_bc
                    else "No blockchain event to evaluate"
                ),
            )
        )
        if contract:
            evidence["contract_name"] = contract
        if func:
            evidence["function_name"] = func

        # Condition 5: Network event exists
        has_net = sequence.network_event is not None
        net_dest = (
            f"{sequence.network_event.network.destination_host}:{sequence.network_event.network.destination_port}"
            if (has_net and sequence.network_event and sequence.network_event.network)
            else None
        )
        conditions.append(
            DetectionConditionMatch(
                condition_id="cond_network",
                description="Outbound network telemetry event exists in sequence",
                satisfied=has_net,
                evidence_detail=f"Destination: '{net_dest}'" if has_net else "No network event observed",
            )
        )
        if net_dest:
            evidence["network_destination"] = net_dest

        # Condition 6: Network activity occurs at or after blockchain read (Δt >= 0)
        net_after_bc = False
        net_delta_detail = "Cannot evaluate: missing blockchain or network event"
        if has_bc and has_net and sequence.blockchain_event and sequence.network_event:
            delta_ms = (
                sequence.network_event.timestamp - sequence.blockchain_event.timestamp
            ).total_seconds() * 1000.0
            evidence["blockchain_to_network_latency_ms"] = round(delta_ms, 3)
            if delta_ms >= 0:
                net_after_bc = True
                net_delta_detail = f"Network event occurred {round(delta_ms, 2)}ms after blockchain read"
            else:
                net_delta_detail = (
                    f"Causality violation: network event occurred {round(abs(delta_ms), 2)}ms BEFORE blockchain read"
                )

        conditions.append(
            DetectionConditionMatch(
                condition_id="cond_network_timing",
                description="Network event occurs chronologically at or after blockchain interaction (Δt >= 0)",
                satisfied=net_after_bc,
                evidence_detail=net_delta_detail,
            )
        )

        # Condition 7: Causal timeline consistency
        causal_consistent = False
        if has_endpoint and has_rpc and has_bc and has_net:
            assert sequence.endpoint_event and sequence.rpc_event and sequence.blockchain_event and sequence.network_event
            t_ep = sequence.endpoint_event.timestamp
            t_rpc = sequence.rpc_event.timestamp
            t_bc = sequence.blockchain_event.timestamp
            t_net = sequence.network_event.timestamp
            if t_ep <= t_rpc and t_rpc <= t_bc and t_bc <= t_net:
                causal_consistent = True

        conditions.append(
            DetectionConditionMatch(
                condition_id="cond_causal_timeline",
                description="Events follow proper multi-layer causal order (Endpoint <= RPC <= Blockchain <= Network)",
                satisfied=causal_consistent,
                evidence_detail=(
                    "Timeline causality verified across all 4 layers"
                    if causal_consistent
                    else "Incomplete sequence or causality order violation"
                ),
            )
        )

        # Evaluation aggregation
        matched = [c.condition_id for c in conditions if c.satisfied]
        unmatched = [c.condition_id for c in conditions if not c.satisfied]
        all_satisfied = len(unmatched) == 0

        # Construct transparent explanation
        if all_satisfied:
            status = DetectionStatus.TRIGGERED
            triggered = True
            explanation = (
                f"Detection candidate identified by {self.rule_id}: "
                f"Observed complete synthetic C2 behavioral pattern for process '{proc_name}' "
                f"querying '{contract}' via RPC followed by network communication to '{net_dest}' "
                f"with latency {evidence.get('blockchain_to_network_latency_ms')}ms."
            )
        else:
            status = DetectionStatus.NOT_TRIGGERED
            triggered = False
            failed_reasons = []
            if not has_endpoint:
                failed_reasons.append("missing endpoint process telemetry")
            if not has_rpc:
                failed_reasons.append("missing RPC telemetry")
            if not has_bc:
                failed_reasons.append("missing smart contract telemetry")
            elif not is_c2_contract:
                failed_reasons.append(f"contract '{contract}' is benign baseline (not C2DataStore)")
            if not has_net:
                failed_reasons.append("no follow-up network activity observed (negative control)")
            elif not net_after_bc:
                failed_reasons.append("network activity did not follow blockchain interaction")
            elif not causal_consistent:
                failed_reasons.append("causal timeline order broken")

            explanation = (
                f"Rule {self.rule_id} did not trigger: "
                + "; ".join(failed_reasons)
                + "."
            )

        return DetectionResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            rule_version=self.rule_version,
            status=status,
            triggered=triggered,
            correlation_id=sequence.correlation_id,
            run_id=sequence.run_id,
            scenario_id=sequence.scenario_id,
            observed_stages=sequence.stages_present,
            conditions=conditions,
            matched_conditions=matched,
            unmatched_conditions=unmatched,
            evidence=evidence,
            total_score=scoring_result.total_score,
            threshold=scoring_result.threshold,
            score_contributions=scoring_result.contributions,
            matched_scoring_rules=scoring_result.matched_scoring_rules,
            unmatched_scoring_rules=scoring_result.unmatched_scoring_rules,
            explanation=explanation,
        )
