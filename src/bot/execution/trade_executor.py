from __future__ import annotations

from dataclasses import dataclass

from bot.core.execution import ExecutionEngine
from bot.core.models import Signal, OrderResult


@dataclass
class ExecutionResult:
    success: bool
    message: str
    order_id: str | None


class TradeExecutor:
    def __init__(self, engine: ExecutionEngine) -> None:
        self.engine = engine

    def execute(self, signal: Signal, volume: float) -> ExecutionResult:
        result: OrderResult = self.engine.place(signal, volume)
        return ExecutionResult(
            success=result.success,
            message=result.message,
            order_id=result.broker_order_id,
        )
