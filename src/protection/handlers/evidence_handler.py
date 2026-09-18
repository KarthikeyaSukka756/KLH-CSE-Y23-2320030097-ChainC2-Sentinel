# ChainC2 Sentinel — Evidence Snapshot Mitigation Handler
"""Evidence preservation handler for Milestone 9.

Serializes factual detection results and telemetry context into immutable
structured evidence bundles under data/evidence/.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.correlation.models import CorrelatedSequence
from src.detection.models import DetectionResult
from src.protection.interfaces import BaseEvidencePreserver, BaseMitigationHandler
from src.protection.models import MitigationAction, MitigationStatus, MitigationType
from src.utils.identifiers import generate_event_id

logger = logging.getLogger("chainc2_sentinel.protection.handlers.evidence")


class EvidenceSnapshotHandler(BaseMitigationHandler, BaseEvidencePreserver):
    """Mitigation handler managing immutable evidence bundle generation."""

    def __init__(self, output_dir: str = "data/evidence") -> None:
        """Initialize handler with output directory.

        Args:
            output_dir: Directory where immutable evidence bundles will be stored.
        """
        self.output_dir = Path(output_dir)

    @property
    def mitigation_type(self) -> MitigationType:
        return MitigationType.EVIDENCE_PRESERVATION

    def preserve_evidence(
        self,
        detection_result: DetectionResult,
        sequence: Optional[CorrelatedSequence] = None,
    ) -> str:
        """Preserve an immutable structured evidence snapshot.

        Args:
            detection_result: The factual detection result.
            sequence: Optional underlying correlated sequence.

        Returns:
            Path to the saved evidence bundle JSON file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        corr_id = detection_result.correlation_id
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"evidence_{corr_id}_{timestamp_str}.json"
        target_file = self.output_dir / filename

        # Compile factual evidence bundle (strictly zero credentials or secrets)
        bundle: dict[str, Any] = {
            "evidence_bundle_id": generate_event_id(),
            "preserved_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": corr_id,
            "run_id": detection_result.run_id,
            "scenario_id": detection_result.scenario_id,
            "rule_id": detection_result.rule_id,
            "rule_version": detection_result.rule_version,
            "detection_status": detection_result.status.value,
            "triggered": detection_result.triggered,
            "matched_conditions": detection_result.matched_conditions,
            "unmatched_conditions": detection_result.unmatched_conditions,
            "evidence_details": detection_result.evidence,
            "explanation": detection_result.explanation,
            "stages_observed": detection_result.observed_stages,
            "sequence_summary": {
                "start_time": sequence.start_time.isoformat() if sequence else None,
                "end_time": sequence.end_time.isoformat() if sequence else None,
                "duration_ms": sequence.duration_ms if sequence else None,
                "event_count": len(sequence.events) if sequence else None,
                "has_network_followup": sequence.has_network_followup if sequence else None,
            } if sequence else None,
            "research_declaration": (
                "Laboratory detection evidence snapshot. Captures observable synthetic "
                "telemetry for defensive audit and reproducibility. Does not assert real-world C2 attribution."
            ),
        }

        content_bytes = json.dumps(bundle, indent=2).encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        bundle["sha256_checksum"] = content_hash

        # Re-write with hash included
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)

        logger.info("EvidenceSnapshotHandler: Preserved snapshot at %s (SHA-256: %s)", target_file, content_hash[:12])
        return str(target_file)

    def execute(self, action: MitigationAction) -> bool:
        """Execute evidence preservation action.

        Args:
            action: The mitigation action.

        Returns:
            True if snapshot saved, False otherwise.
        """
        # Snapshot path can be generated or passed in
        corr_id = action.parameters.get("correlation_id", action.target_resource)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_file = self.output_dir / f"evidence_{corr_id}_{timestamp_str}.json"

        bundle = {
            "evidence_bundle_id": generate_event_id(),
            "preserved_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": corr_id,
            "run_id": action.parameters.get("run_id"),
            "rule_id": action.parameters.get("rule_id", "RULE-CHAINC2-001"),
            "matched_conditions": action.parameters.get("matched_conditions", []),
            "action_id": action.action_id,
        }
        content_bytes = json.dumps(bundle, indent=2).encode("utf-8")
        bundle["sha256_checksum"] = hashlib.sha256(content_bytes).hexdigest()

        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)

        action.parameters["snapshot_path"] = str(target_file)
        action.parameters["sha256_checksum"] = bundle["sha256_checksum"]
        action.status = MitigationStatus.EXECUTED
        action.execution_timestamp = datetime.now(timezone.utc)
        logger.info("EvidenceSnapshotHandler: Executed snapshot for %s", corr_id)
        return True

    def verify(self, action: MitigationAction) -> bool:
        """Verify that the evidence snapshot exists on disk and is non-empty.

        Args:
            action: The executed mitigation action.

        Returns:
            True if verified, False otherwise.
        """
        snapshot_path_str = action.parameters.get("snapshot_path")
        if not snapshot_path_str:
            action.status = MitigationStatus.FAILED
            action.verification_details = "Missing snapshot_path in action parameters"
            return False

        path = Path(snapshot_path_str)
        if not path.exists() or path.stat().st_size == 0:
            action.status = MitigationStatus.FAILED
            action.verification_details = f"Snapshot file not found or empty at {path}"
            return False

        action.status = MitigationStatus.VERIFIED
        action.verification_timestamp = datetime.now(timezone.utc)
        action.verification_details = f"Verified immutable evidence bundle exists at {path.name} ({path.stat().st_size} bytes)"
        logger.info("EvidenceSnapshotHandler: Verified snapshot %s", path.name)
        return True

    def rollback(self, action: MitigationAction) -> bool:
        """Rollback routine for evidence preservation.

        Evidence preservation is an immutable permanent audit record and is NOT deleted.
        Returns True to confirm harmless non-reversion.
        """
        logger.info("EvidenceSnapshotHandler: Evidence snapshot is an immutable audit log; preserving file.")
        return True
