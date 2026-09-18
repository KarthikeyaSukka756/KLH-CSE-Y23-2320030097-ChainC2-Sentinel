# ChainC2 Sentinel — Detection Package
"""Rule-based, explainable detection layer for ChainC2 Sentinel.

Consumes correlated evidence chains (CorrelatedSequence) and evaluates observable
laboratory conditions to identify synthetic blockchain-mediated C2-like behavior.
"""

from src.detection.detector import DetectionEngine
from src.detection.models import (
    DetectionConditionMatch,
    DetectionResult,
    DetectionStatus,
)
from src.detection.rules import BaseDetectionRule, SyntheticC2SequenceRule

__all__ = [
    "DetectionEngine",
    "BaseDetectionRule",
    "SyntheticC2SequenceRule",
    "DetectionResult",
    "DetectionConditionMatch",
    "DetectionStatus",
]
