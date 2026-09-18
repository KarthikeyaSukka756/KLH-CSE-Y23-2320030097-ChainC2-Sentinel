# ChainC2 Sentinel — Evidence Discovery & Forensic Verification Service
"""Service for inspecting preserved forensic evidence bundles and computing cryptographic SHA-256 integrity verification.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

from src.dashboard.services import get_repo_root

logger = logging.getLogger("chainc2_sentinel.dashboard.evidence_service")


class EvidenceService:
    """Service for discovering evidence bundles and validating forensic checksum integrity."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or get_repo_root()
        self.evidence_dir = self.repo_root / "data" / "evidence"

    def list_evidence_bundles(self) -> list[dict[str, Any]]:
        """List all discovered evidence bundles with extracted metadata."""
        if not self.evidence_dir.exists():
            return []

        bundles: list[dict[str, Any]] = []
        for file_path in sorted(self.evidence_dir.glob("*.json")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                stat = file_path.stat()
                bundles.append({
                    "evidence_bundle_id": data.get("evidence_bundle_id", file_path.stem),
                    "bundle_id": data.get("evidence_bundle_id", file_path.stem),
                    "filename": file_path.name,
                    "file_path": str(file_path.relative_to(self.repo_root)),
                    "file_size_bytes": stat.st_size,
                    "preserved_at": data.get("preserved_at"),
                    "correlation_id": data.get("correlation_id"),
                    "run_id": data.get("run_id"),
                    "rule_id": data.get("rule_id", "RULE-CHAINC2-001"),
                    "matched_conditions": data.get("matched_conditions", []),
                    "action_id": data.get("action_id"),
                    "sha256_checksum": data.get("sha256_checksum", ""),
                })
            except Exception as e:
                logger.error("Failed to read evidence bundle %s: %s", file_path, e)

        # Sort newest first
        bundles.sort(key=lambda b: b.get("preserved_at") or "", reverse=True)
        return bundles

    def get_evidence_bundle(self, bundle_or_corr_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a specific evidence bundle by bundle ID, correlation ID, or filename."""
        if not self.evidence_dir.exists():
            return None

        # Sanitize against path traversal
        clean_id = Path(bundle_or_corr_id).name

        for file_path in self.evidence_dir.glob("*.json"):
            if clean_id in file_path.name:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["_filename"] = file_path.name
                    data["_file_path"] = str(file_path.relative_to(self.repo_root))
                    return data
                except Exception as e:
                    logger.error("Failed to read bundle %s: %s", file_path, e)
                    return None

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if (
                    data.get("evidence_bundle_id") == bundle_or_corr_id
                    or data.get("correlation_id") == bundle_or_corr_id
                    or data.get("run_id") == bundle_or_corr_id
                ):
                    data["_filename"] = file_path.name
                    data["_file_path"] = str(file_path.relative_to(self.repo_root))
                    data["bundle_id"] = data.get("evidence_bundle_id", file_path.stem)
                    return data
            except Exception:
                continue

        return None

    def verify_checksum(self, bundle_or_corr_id: str) -> dict[str, Any]:
        """Verify the SHA-256 cryptographic digest of an evidence snapshot file.

        The digest is computed over the serialized bundle content without the 'sha256_checksum' key,
        matching the exact algorithm used in EvidenceSnapshotHandler.
        """
        bundle = self.get_evidence_bundle(bundle_or_corr_id)
        if not bundle:
            return {
                "status": "NOT_FOUND",
                "verified": False,
                "error": f"Evidence bundle '{bundle_or_corr_id}' not found",
            }

        expected_checksum = bundle.get("sha256_checksum")
        if not expected_checksum:
            return {
                "status": "NO_CHECKSUM",
                "verified": False,
                "error": "Evidence bundle does not contain a recorded sha256_checksum field",
            }

        # Make clean copy omitting metadata helpers and sha256_checksum
        payload_copy = {
            k: v for k, v in bundle.items()
            if not k.startswith("_") and k != "sha256_checksum" and k != "bundle_id"
        }

        content_bytes = json.dumps(payload_copy, indent=2).encode("utf-8")
        calculated_checksum = hashlib.sha256(content_bytes).hexdigest()

        is_verified = (calculated_checksum.lower() == expected_checksum.lower())

        return {
            "status": "VERIFIED" if is_verified else "MISMATCH",
            "verified": is_verified,
            "evidence_bundle_id": bundle.get("evidence_bundle_id"),
            "bundle_id": bundle.get("evidence_bundle_id"),
            "filename": bundle.get("_filename"),
            "expected_checksum": expected_checksum,
            "recorded_checksum": expected_checksum,
            "calculated_checksum": calculated_checksum,
            "algorithm": "SHA-256",
            "preserved_at": bundle.get("preserved_at"),
            "run_id": bundle.get("run_id"),
        }
