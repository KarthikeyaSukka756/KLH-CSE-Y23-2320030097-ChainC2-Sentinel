# ChainC2 Sentinel — Detection Evaluation Package
"""Evaluation framework for Milestone 7 — Detection Evaluation."""

from src.evaluation.evaluator import DetectionEvaluator
from src.evaluation.models import (
    AggregateEvaluationResult,
    ClassificationVerdict,
    EvaluationMetrics,
    ExperimentRecord,
    GroundTruth,
)

__all__ = [
    "GroundTruth",
    "ClassificationVerdict",
    "ExperimentRecord",
    "EvaluationMetrics",
    "AggregateEvaluationResult",
    "DetectionEvaluator",
]
