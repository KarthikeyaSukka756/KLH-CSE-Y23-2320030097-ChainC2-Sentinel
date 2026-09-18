# ChainC2 Sentinel — Event Normalizer Package
"""Event normalization pipeline: transforms raw collector output
into the common SentinelEvent schema and writes to the JSONL event store."""

from src.normalizer.normalizer import EventNormalizer, EventStore, NormalizationResult

__all__ = [
    "EventNormalizer",
    "EventStore",
    "NormalizationResult",
]
