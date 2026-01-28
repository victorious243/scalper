from __future__ import annotations

import uuid
from typing import Dict

from bot.core.interfaces import BrokerAdapter
from bot.core.models import Signal, OrderRequest, OrderResult
from bot.utils.logging import log_event


class ExecutionEngine:
    def __init__(self, adapter: BrokerAdapter, logger) -> None:
        self.adapter = adapter
        self.logger = logger
        self._idempotency: Dict[str, str] = {}

    def place(self, signal: Signal, volume: float) -> OrderResult:
        client_order_id = f"{signal.symbol}-{signal.strategy}-{uuid.uuid4().hex[:8]}"
        if client_order_id in self._idempotency:
            return OrderResult(False, None, "DUPLICATE", "Duplicate order blocked")

        order = OrderRequest(
            symbol=signal.symbol,
            side=signal.side,
            order_type=signal.order_type,
            volume=volume,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            client_order_id=client_order_id,
            time=signal.time,
        )
        result = None
        retryable = {"10004", "10006", "OFF_QUOTES", "REQUOTE"}
        for _ in range(2):
            result = self.adapter.place_order(order)
            if result.success:
                break
            if result.status not in retryable and result.message.upper() not in retryable:
                break
        if result is None:
            result = OrderResult(False, None, "ERROR", "No response")
        self._idempotency[client_order_id] = result.status
        return result

    def can_open(self, symbol: str, max_positions: int = 1) -> bool:
        open_positions = self.adapter.get_open_positions(symbol)
        return len(open_positions) < max_positions

    def log_result(self, signal: Signal, result: OrderResult, volume: float) -> None:
        log_event(
            self.logger,
            "order_result",
            symbol=signal.symbol,
            strategy=signal.strategy,
            side=signal.side.value,
            volume=volume,
            status=result.status,
            message=result.message,
            success=result.success,
        )
