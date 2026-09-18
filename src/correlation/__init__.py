# ChainC2 Sentinel — Correlation Package
"""Cross-layer telemetry correlation engine and models.

Answers temporal and structural questions to reconstruct evidence chains
from multi-source laboratory telemetry.
"""

from src.correlation.engine import CrossLayerCorrelationEngine
from src.correlation.models import (
    CorrelatedSequence,
    CorrelationRelationship,
    EventTransition,
)

__all__ = [
    "CrossLayerCorrelationEngine",
    "CorrelatedSequence",
    "EventTransition",
    "CorrelationRelationship",
]
