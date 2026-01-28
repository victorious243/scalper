from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bot.core.models import Signal, MarketState


@dataclass
class MLDecision:
    approved: bool
    score: float
    reason: str


class MLFilter:
    def score(self, signal: Signal, state: MarketState) -> MLDecision:
        return MLDecision(approved=True, score=0.5, reason="ml_disabled")


class PlaceholderMLFilter(MLFilter):
    def __init__(self, min_score: float = 0.6) -> None:
        self.min_score = min_score

    def score(self, signal: Signal, state: MarketState) -> MLDecision:
        # Placeholder: acts as a gate only if manually toggled with high threshold.
        score = max(0.0, min(1.0, signal.confidence))
        return MLDecision(approved=score >= self.min_score, score=score, reason="rule_proxy")
