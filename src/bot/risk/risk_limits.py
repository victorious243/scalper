from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_daily_loss_pct: float = 0.02
    max_trades_per_day: int = 3
    max_concurrent_trades: int = 1
