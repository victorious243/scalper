from __future__ import annotations

from typing import List, Optional

from bot.adapters.mt5_adapter import MT5Adapter
from bot.adapters.paper_broker import PaperBroker
from bot.core.models import Bar, Tick, OrderRequest, OrderResult, Position, AccountInfo


class PaperMT5Adapter:
    """Uses MT5 for market data but routes orders to a paper broker."""

    def __init__(self, mt5: MT5Adapter, paper: PaperBroker) -> None:
        self.mt5 = mt5
        self.paper = paper

    def connect(self) -> bool:
        return self.mt5.connect()

    def is_connected(self) -> bool:
        return self.mt5.is_connected()

    def shutdown(self) -> None:
        self.mt5.shutdown()

    def get_bars(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        return self.mt5.get_bars(symbol, timeframe, count)

    def get_tick(self, symbol: str) -> Tick:
        tick = self.mt5.get_tick(symbol)
        self.paper.seed_tick(symbol, tick)
        return tick

    def get_account_info(self) -> AccountInfo:
        return self.paper.get_account_info()

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        return self.paper.get_open_positions(symbol)

    def place_order(self, order: OrderRequest) -> OrderResult:
        return self.paper.place_order(order)

    def modify_position(self, position_id: str, stop_loss: float, take_profit: float) -> OrderResult:
        return self.paper.modify_position(position_id, stop_loss, take_profit)

    def close_position(self, position_id: str) -> OrderResult:
        return self.paper.close_position(position_id)

    def symbol_info(self, symbol: str) -> dict:
        return self.mt5.symbol_info(symbol)
