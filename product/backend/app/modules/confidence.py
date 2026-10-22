from typing import Protocol

from app.domain.money import Confidence
from app.modules.leakage_rules import LeakageCandidate


class ConfidenceScorer(Protocol):
    """Future calibrated scoring; no arbitrary default score or model yet."""

    def score(self, candidate: LeakageCandidate) -> Confidence: ...
