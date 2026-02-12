from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

from bot.core.interfaces import BrokerAdapter
from bot.core.models import MarketState, Position
from bot.core.risk import HardRiskManager


@dataclass
class PositionMeta:
    max_hold_minutes: int
    entry_time: datetime
    entry_price: float
    atr_at_entry: float


class TradeSupervisor:
    def __init__(self, adapter: BrokerAdapter, risk: HardRiskManager) -> None:
        self.adapter = adapter
        self.risk = risk
        self.meta: Dict[str, PositionMeta] = {}

    def register(self, position_id: str, meta: PositionMeta) -> None:
        self.meta[position_id] = meta

    def evaluate(self, state: MarketState, positions: List[Position]) -> None:
        for pos in positions:
            if pos.broker_position_id is None:
                continue
            meta = self.meta.get(pos.broker_position_id)
            decision = self.risk.approve_adjustment(pos.symbol, state.time)
            if not decision.approved:
                continue

            tick = self.adapter.get_tick(pos.symbol)
            current_price = tick.bid if pos.side.value == "BUY" else tick.ask
            pnl = (current_price - pos.entry_price) if pos.side.value == "BUY" else (pos.entry_price - current_price)

            if meta:
                if state.time - meta.entry_time > timedelta(minutes=meta.max_hold_minutes):
                    self.adapter.close_position(pos.broker_position_id)
                    continue

                # Break-even after 1R or 1 ATR
                if pnl > max(meta.atr_at_entry, abs(pos.entry_price - pos.stop_loss)):
                    new_sl = pos.entry_price if pos.side.value == "BUY" else pos.entry_price
                    if (pos.side.value == "BUY" and new_sl > pos.stop_loss) or (pos.side.value == "SELL" and new_sl < pos.stop_loss):
                        self.adapter.modify_position(pos.broker_position_id, new_sl, pos.take_profit)

                # Conservative trailing after profit protected
                trail_distance = meta.atr_at_entry * 0.8
                if pnl > trail_distance:
                    if pos.side.value == "BUY":
                        trail_sl = current_price - trail_distance
                        if trail_sl > pos.stop_loss:
                            self.adapter.modify_position(pos.broker_position_id, trail_sl, pos.take_profit)
                    else:
                        trail_sl = current_price + trail_distance
                        if trail_sl < pos.stop_loss:
                            self.adapter.modify_position(pos.broker_position_id, trail_sl, pos.take_profit)

            # Exit if regime flips hard
            if state.regime_primary.value == "RANGE" and abs(state.trend_strength) < 0.0002:
                self.adapter.close_position(pos.broker_position_id)
