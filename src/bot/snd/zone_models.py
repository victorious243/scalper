from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List


class ZoneType(str, Enum):
    DEMAND = "DEMAND"
    SUPPLY = "SUPPLY"


@dataclass
class Zone:
    id: str
    symbol: str
    zone_type: ZoneType
    timeframe: str
    created_at: datetime
    lower: float
    upper: float
    base_start: datetime
    base_end: datetime
    impulse_size: float
    atr: float
    score: float
    touches: int = 0
    active: bool = True
    notes: List[str] = field(default_factory=list)

    def width(self) -> float:
        return max(0.0, self.upper - self.lower)

    def contains(self, price: float) -> bool:
        return self.lower <= price <= self.upper


@dataclass
class ZoneConfig:
    base_min: int = 1
    base_max: int = 4
    impulsive_min_candles: int = 2
    impulse_atr_mult: float = 1.5
    impulse_min_pips: float = 8.0
    max_base_atr_mult: float = 1.0
    max_touches: int = 2
    overlap_threshold: float = 0.4
    zone_body_rule: str = "body"  # body|wick
