from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from bot.core.models import Bar, Tick, OrderRequest, OrderResult, Position, AccountInfo


class PaperBroker:
    def __init__(self, initial_balance: float = 10000.0) -> None:
        self.balance = initial_balance
        self.equity = initial_balance
        self.margin_free = initial_balance
        self.currency = "USD"
        self.positions: Dict[str, Position] = {}
        self.last_tick: Dict[str, Tick] = {}
        self.bars: Dict[str, Dict[str, List[Bar]]] = {}

    def connect(self) -> bool:
        return True

    def is_connected(self) -> bool:
        return True

    def shutdown(self) -> None:
        return None

    def seed_bars(self, symbol: str, timeframe: str, bars: List[Bar]) -> None:
        self.bars.setdefault(symbol, {})[timeframe] = bars

    def seed_tick(self, symbol: str, tick: Tick) -> None:
        self.last_tick[symbol] = tick
        # Simulate SL/TP hits for paper trading.
        for pid, pos in list(self.positions.items()):
            if pos.symbol != symbol:
                continue
            if pos.side.value == "BUY":
                if tick.bid <= pos.stop_loss or tick.bid >= pos.take_profit:
                    self.close_position(pid)
            else:
                if tick.ask >= pos.stop_loss or tick.ask <= pos.take_profit:
                    self.close_position(pid)

    def get_bars(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        return list(self.bars.get(symbol, {}).get(timeframe, []))[-count:]

    def get_tick(self, symbol: str) -> Tick:
        return self.last_tick[symbol]

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(
            equity=self.equity,
            balance=self.balance,
            margin_free=self.margin_free,
            currency=self.currency,
        )

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        if symbol:
            return [p for p in self.positions.values() if p.symbol == symbol]
        return list(self.positions.values())

    def place_order(self, order: OrderRequest) -> OrderResult:
        position_id = order.client_order_id
        self.positions[position_id] = Position(
            symbol=order.symbol,
            side=order.side,
            volume=order.volume,
            entry_price=order.entry_price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            open_time=order.time,
            broker_position_id=position_id,
        )
        return OrderResult(True, position_id, "FILLED", "Paper fill")

    def modify_position(self, position_id: str, stop_loss: float, take_profit: float) -> OrderResult:
        pos = self.positions.get(position_id)
        if not pos:
            return OrderResult(False, None, "NOT_FOUND", "Position not found")
        pos.stop_loss = stop_loss
        pos.take_profit = take_profit
        return OrderResult(True, position_id, "MODIFIED", "Paper modify")

    def close_position(self, position_id: str) -> OrderResult:
        if position_id not in self.positions:
            return OrderResult(False, None, "NOT_FOUND", "Position not found")
        del self.positions[position_id]
        return OrderResult(True, position_id, "CLOSED", "Paper close")

    def symbol_info(self, symbol: str) -> dict:
        symbol_upper = (symbol or "").upper()
        contract_size = 100000.0
        point = 0.0001
        digits = 5
        if "JPY" in symbol_upper:
            point = 0.001
            digits = 3
        if "XAU" in symbol_upper:
            contract_size = 100.0
            point = 0.01
            digits = 2
        if "XAG" in symbol_upper:
            contract_size = 5000.0
            point = 0.01
            digits = 2
        tick_size = point
        tick_value = contract_size * tick_size
        return {
            "point": point,
            "digits": digits,
            "trade_contract_size": contract_size,
            "trade_tick_size": tick_size,
            "trade_tick_value": tick_value,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01,
            "trade_stops_level": 10,
            "trade_freeze_level": 0,
            "trade_mode": 1,
        }
