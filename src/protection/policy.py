# ChainC2 Sentinel — Defensive Response Policy Engine
"""Defensive response policy engine for Milestone 8.

Formulates auditable, layered DefensePlan objects strictly from factual
DetectionResult candidate alerts. Enforces laboratory safety boundaries.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.correlation.models import CorrelatedSequence
from src.detection.models import DetectionResult, DetectionStatus
from src.protection.models import (
    DefensePlan,
    DefensePlanStatus,
    MitigationAction,
    MitigationStatus,
    MitigationType,
)
from src.utils.identifiers import generate_event_id

logger = logging.getLogger("chainc2_sentinel.protection.policy")


class DefensivePolicyEngine:
    """Translates detection verdicts into structured, auditable defense plans."""

    def __init__(
        self,
        enable_evidence_preservation: bool = True,
        enable_rpc_filter: bool = True,
        enable_network_containment: bool = True,
        enable_process_isolation: bool = True,
    ) -> None:
        """Initialize defense policy configuration.

        Args:
            enable_evidence_preservation: Enable evidence snapshot action.
            enable_rpc_filter: Enable proxy-layer RPC filter action.
            enable_network_containment: Enable local HTTP target beacon containment.
            enable_process_isolation: Enable laboratory process containment signaling.
        """
        self.enable_evidence_preservation = enable_evidence_preservation
        self.enable_rpc_filter = enable_rpc_filter
        self.enable_network_containment = enable_network_containment
        self.enable_process_isolation = enable_process_isolation

    def create_defense_plan(
        self,
        detection_result: DetectionResult,
        sequence: Optional[CorrelatedSequence] = None,
    ) -> DefensePlan:
        """Formulate a DefensePlan from a factual DetectionResult.

        CRITICAL SAFETY RULE:
        Only TRIGGERED detection results warrant defensive action.
        Non-triggered sequences (e.g. Scenario A) produce a SKIPPED plan with zero actions.

        Args:
            detection_result: Factual output from Milestone 6 detection engine.
            sequence: Optional underlying CorrelatedSequence from Milestone 5.

        Returns:
            DefensePlan containing the planned mitigation actions or a SKIPPED notice.
        """
        # Rule 1: Non-triggered results require zero defensive response
        if detection_result.status != DetectionStatus.TRIGGERED or not detection_result.triggered:
            logger.info(
                "DetectionResult for correlation_id=%s was not triggered (%s). Skipping defense response.",
                detection_result.correlation_id,
                detection_result.status.value,
            )
            return DefensePlan(
                plan_id=generate_event_id(),
                detection_correlation_id=detection_result.correlation_id,
                run_id=detection_result.run_id,
                scenario_id=detection_result.scenario_id,
                rule_id=detection_result.rule_id,
                status=DefensePlanStatus.SKIPPED,
                actions=[],
                evidence_summary="No defensive response required: detection rule did not trigger.",
                safety_boundary_verified=True,
                notes=["Negative control or non-candidate sequence correctly bypassed."],
            )

        # Rule 2: Verify laboratory safety boundaries
        evidence = detection_result.evidence or {}
        dest_host = evidence.get("network_destination_host", "127.0.0.1")
        if dest_host not in ("127.0.0.1", "localhost"):
            raise ValueError(
                f"Safety violation: Destination host {dest_host} is not a controlled local laboratory host."
            )

        contract_addr = evidence.get("contract_address", "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512")
        dest_port = evidence.get("network_destination_port", 8080)
        proc_name = evidence.get("process_name", "synthetic_c2_client")
        proc_pid = evidence.get("process_pid", 4096)

        actions: list[MitigationAction] = []

        # Layer 1: Evidence Preservation
        if self.enable_evidence_preservation:
            actions.append(
                MitigationAction(
                    mitigation_type=MitigationType.EVIDENCE_PRESERVATION,
                    target_layer="evidence",
                    target_resource=f"evidence-{detection_result.correlation_id}",
                    status=MitigationStatus.REQUESTED,
                    parameters={
                        "correlation_id": detection_result.correlation_id,
                        "run_id": detection_result.run_id,
                        "rule_id": detection_result.rule_id,
                        "matched_conditions": detection_result.matched_conditions,
                    },
                    verification_strategy="Verify immutable JSON snapshot exists on disk and hash matches",
                    is_reversible=False,  # Evidence preservation is permanent audit log
                )
            )

        # Layer 2: RPC Access Restriction (Proxy-Level)
        if self.enable_rpc_filter:
            actions.append(
                MitigationAction(
                    mitigation_type=MitigationType.RPC_FILTER,
                    target_layer="rpc",
                    target_resource=contract_addr,
                    status=MitigationStatus.REQUESTED,
                    parameters={
                        "contract_address": contract_addr,
                        "contract_name": evidence.get("contract_name", "C2DataStore"),
                        "filter_action": "BLOCK_CONTRACT_QUERIES",
                        "proxy_scope": "application_proxy",
                    },
                    verification_strategy="Probe proxy with eth_call targeting contract; expect RPC error",
                    is_reversible=True,
                )
            )

        # Layer 3: Controlled Network Containment (Local Target Server)
        if self.enable_network_containment:
            actions.append(
                MitigationAction(
                    mitigation_type=MitigationType.NETWORK_CONTAINMENT,
                    target_layer="network",
                    target_resource=f"{dest_host}:{dest_port}",
                    status=MitigationStatus.REQUESTED,
                    parameters={
                        "destination_host": dest_host,
                        "destination_port": dest_port,
                        "containment_action": "REJECT_BEACON",
                        "target_scope": "local_http_target_server",
                    },
                    verification_strategy="Probe local target /beacon endpoint; expect HTTP 403 Forbidden",
                    is_reversible=True,
                )
            )

        # Layer 4: Controlled Process-Level Containment
        if self.enable_process_isolation:
            actions.append(
                MitigationAction(
                    mitigation_type=MitigationType.PROCESS_ISOLATION,
                    target_layer="process",
                    target_resource=proc_name,
                    status=MitigationStatus.REQUESTED,
                    parameters={
                        "process_name": proc_name,
                        "pid": proc_pid,
                        "isolation_action": "CONTAINMENT_SIGNAL",
                        "scope": "laboratory_scenario_worker",
                    },
                    verification_strategy="Verify scenario process state registry records ISOLATED status",
                    is_reversible=True,
                )
            )

        summary = (
            f"Formulated {len(actions)} defensive actions based on detection candidate "
            f"{detection_result.rule_id} (correlation_id={detection_result.correlation_id})."
        )

        return DefensePlan(
            plan_id=generate_event_id(),
            detection_correlation_id=detection_result.correlation_id,
            run_id=detection_result.run_id,
            scenario_id=detection_result.scenario_id,
            rule_id=detection_result.rule_id,
            status=DefensePlanStatus.PENDING,
            actions=actions,
            evidence_summary=summary,
            safety_boundary_verified=True,
            notes=[
                "Defensive response planned for controlled laboratory components only.",
                "Zero OS-level firewall modifications or arbitrary process terminations.",
            ],
        )
