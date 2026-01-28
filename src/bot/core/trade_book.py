from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from bot.core.models import TradeRecord, OrderSide, Position


@dataclass
class OpenTrade:
    trade: TradeRecord
    position_id: str


class TradeBook:
    def __init__(self) -> None:
        self.open_trades: Dict[str, OpenTrade] = {}

    def register_open(self, position_id: str, trade: TradeRecord) -> None:
        self.open_trades[position_id] = OpenTrade(trade=trade, position_id=position_id)

    def close(self, position_id: str, exit_price: float, exit_time: datetime, reason: str) -> TradeRecord | None:
        open_trade = self.open_trades.pop(position_id, None)
        if not open_trade:
            return None
        trade = open_trade.trade
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.hold_minutes = (exit_time - trade.entry_time).total_seconds() / 60.0
        if trade.side == OrderSide.BUY:
            trade.pnl = (exit_price - trade.entry_price) * trade.volume * trade.contract_size
        else:
            trade.pnl = (trade.entry_price - exit_price) * trade.volume * trade.contract_size
        trade.reason = reason
        return trade

    def reconcile(self, current_positions: List[Position], tick_map: Dict[str, float], now: datetime) -> List[TradeRecord]:
        closed: List[TradeRecord] = []
        current_ids = {p.broker_position_id for p in current_positions if p.broker_position_id}
        for position_id in list(self.open_trades.keys()):
            if position_id not in current_ids:
                trade = self.open_trades[position_id].trade
                price = tick_map.get(trade.symbol, trade.entry_price)
                trade = self.close(position_id, price, now, "broker_exit")
                if trade:
                    closed.append(trade)
        return closed
