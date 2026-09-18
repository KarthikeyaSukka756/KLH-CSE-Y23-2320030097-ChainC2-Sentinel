# ChainC2 Sentinel — Mitigation Interfaces
"""Abstract interfaces for Milestone 8 / Milestone 9 defensive responders.

Defines standard contracts for controlled mitigation handlers, verification
routines, and rollback procedures.
"""

from __future__ import annotations

import abc
from typing import Optional

from src.correlation.models import CorrelatedSequence
from src.detection.models import DetectionResult
from src.protection.models import MitigationAction, MitigationType


class BaseMitigationHandler(abc.ABC):
    """Abstract contract for an individual controlled mitigation handler."""

    @property
    @abc.abstractmethod
    def mitigation_type(self) -> MitigationType:
        """The specific type of mitigation managed by this handler."""
        raise NotImplementedError

    @abc.abstractmethod
    def execute(self, action: MitigationAction) -> bool:
        """Execute the planned mitigation action against local laboratory components.

        Args:
            action: The structured mitigation action to execute.

        Returns:
            True if execution succeeded, False otherwise.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def verify(self, action: MitigationAction) -> bool:
        """Independently verify that the mitigation is active and effective.

        Args:
            action: The executed mitigation action to verify.

        Returns:
            True if verification confirmed containment, False otherwise.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self, action: MitigationAction) -> bool:
        """Roll back the mitigation to restore clean baseline state.

        Args:
            action: The mitigation action to revert.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        raise NotImplementedError


class BaseEvidencePreserver(abc.ABC):
    """Abstract contract for snapshotting and preserving detection evidence."""

    @abc.abstractmethod
    def preserve_evidence(
        self,
        detection_result: DetectionResult,
        sequence: Optional[CorrelatedSequence] = None,
    ) -> str:
        """Preserve an immutable snapshot of detection evidence.

        Args:
            detection_result: Factual detection outcome.
            sequence: Optional correlated sequence.

        Returns:
            Artifact file path or persistent identifier of the saved snapshot.
        """
        raise NotImplementedError
