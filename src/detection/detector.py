# ChainC2 Sentinel — Detection Engine
"""Detection engine that coordinates rule evaluations across correlated sequences.

Provides high-level evaluation workflows:
- Evaluating individual CorrelatedSequence objects
- Evaluating batches of CorrelatedSequence objects
- End-to-end evaluation directly from raw SentinelEvent streams via correlation
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.correlation.engine import CrossLayerCorrelationEngine
from src.correlation.models import CorrelatedSequence
from src.detection.models import DetectionResult, DetectionStatus
from src.detection.rules import BaseDetectionRule, SyntheticC2SequenceRule
from src.models.events import SentinelEvent

logger = logging.getLogger("chainc2_sentinel.detection")


class DetectionEngine:
    """Manages explainable detection rules and evaluates correlated evidence chains."""

    def __init__(self, rules: Optional[list[BaseDetectionRule]] = None) -> None:
        """Initialize detection engine with rules.

        Args:
            rules: List of detection rules. If None, defaults to [SyntheticC2SequenceRule()].
        """
        self.rules: list[BaseDetectionRule] = (
            rules if rules is not None else [SyntheticC2SequenceRule()]
        )
        self._correlation_engine = CrossLayerCorrelationEngine()

    def add_rule(self, rule: BaseDetectionRule) -> None:
        """Register a new detection rule."""
        self.rules.append(rule)

    def evaluate_sequence(self, sequence: CorrelatedSequence) -> list[DetectionResult]:
        """Evaluate all registered detection rules against a single CorrelatedSequence.

        Args:
            sequence: The correlated behavioral sequence.

        Returns:
            List of DetectionResult objects, one per rule evaluated.
        """
        results: list[DetectionResult] = []
        for rule in self.rules:
            result = rule.evaluate(sequence)
            results.append(result)
            if result.triggered:
                logger.info(
                    "Detection rule %s TRIGGERED on sequence %s (run_id: %s)",
                    rule.rule_id,
                    sequence.correlation_id,
                    sequence.run_id,
                )
            else:
                logger.debug(
                    "Detection rule %s did not trigger on sequence %s",
                    rule.rule_id,
                    sequence.correlation_id,
                )
        return results

    def evaluate_sequences(
        self, sequences: list[CorrelatedSequence]
    ) -> list[DetectionResult]:
        """Evaluate all registered detection rules against a batch of CorrelatedSequences.

        Args:
            sequences: List of correlated behavioral sequences.

        Returns:
            List of all DetectionResult objects.
        """
        all_results: list[DetectionResult] = []
        for seq in sequences:
            all_results.extend(self.evaluate_sequence(seq))
        return all_results

    def evaluate_events(self, events: list[SentinelEvent]) -> list[DetectionResult]:
        """End-to-end evaluation: correlate raw telemetry events and run detection rules.

        Args:
            events: List of raw SentinelEvents from any scenario or collector.

        Returns:
            List of DetectionResult objects for all reconstructed sequences.
        """
        sequences = self._correlation_engine.correlate(events)
        return self.evaluate_sequences(sequences)

    @staticmethod
    def summarize(results: list[DetectionResult]) -> dict[str, Any]:
        """Generate a structured factual summary of detection results."""
        total_evaluations = len(results)
        triggered_count = sum(1 for r in results if r.triggered)
        not_triggered_count = total_evaluations - triggered_count

        candidates = [
            {
                "rule_id": r.rule_id,
                "correlation_id": r.correlation_id,
                "run_id": r.run_id,
                "scenario_id": r.scenario_id,
                "evidence": r.evidence,
                "explanation": r.explanation,
            }
            for r in results
            if r.triggered
        ]

        return {
            "total_evaluations": total_evaluations,
            "triggered_candidates": triggered_count,
            "non_triggered": not_triggered_count,
            "candidates": candidates,
        }
