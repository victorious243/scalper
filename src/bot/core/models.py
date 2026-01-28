from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class Regime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    HIGH_VOL = "HIGH_VOL"
    LOW_VOL = "LOW_VOL"
    MIXED = "MIXED"


@dataclass
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Tick:
    time: datetime
    bid: float
    ask: float

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass
class MarketState:
    symbol: str
    time: datetime
    regime_primary: Regime
    regime_secondary: Regime
    trend_strength: float
    volatility: float
    range_compression: float
    return_1: float
    session: str
    confidence: float
    notes: List[str] = field(default_factory=list)


@dataclass
class Signal:
    symbol: str
    time: datetime
    strategy: str
    side: OrderSide
    order_type: OrderType
    entry_price: float
    stop_loss: float
    take_profit: float
    max_hold_minutes: int
    confidence: float
    rationale: List[str]

    @property
    def rr(self) -> float:
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        return reward / risk if risk > 0 else 0.0


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    adjusted_size: float = 0.0
    warnings: List[str] = field(default_factory=list)


@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    client_order_id: str
    time: datetime


@dataclass
class OrderResult:
    success: bool
    broker_order_id: Optional[str]
    status: str
    message: str


@dataclass
class Position:
    symbol: str
    side: OrderSide
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    open_time: datetime
    broker_position_id: Optional[str] = None


@dataclass
class TradeRecord:
    symbol: str
    strategy: str
    side: OrderSide
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime]
    exit_price: Optional[float]
    volume: float
    pnl: float
    reason: str
    rr: float
    tags: List[str]
    contract_size: float = 100000.0
    hold_minutes: float = 0.0


@dataclass
class AccountInfo:
    equity: float
    balance: float
    margin_free: float
    currency: str
