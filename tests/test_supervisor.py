from datetime import datetime

from bot.core.models import MarketState, Position, OrderSide, Regime, Tick, RiskDecision, OrderResult
from bot.core.supervisor import TradeSupervisor, PositionMeta


class _Adapter:
    def __init__(self) -> None:
        self.closed: list[str] = []

    def get_tick(self, symbol: str) -> Tick:
        return Tick(time=datetime.utcnow(), bid=1.1012, ask=1.1013)

    def close_position(self, position_id: str) -> OrderResult:
        self.closed.append(position_id)
        return OrderResult(success=True, broker_order_id=position_id, status="CLOSED", message="ok")

    def modify_position(self, position_id: str, stop_loss: float, take_profit: float) -> OrderResult:
        return OrderResult(success=True, broker_order_id=position_id, status="MODIFIED", message="ok")


class _Risk:
    def approve_adjustment(self, symbol: str, now: datetime) -> RiskDecision:
        return RiskDecision(True, "approved")


def test_supervisor_closes_trade_when_good_profit_reached():
    adapter = _Adapter()
    sup = TradeSupervisor(adapter, _Risk(), close_on_good_profit=True, good_profit_rr=1.0)
    pos = Position(
        symbol="EURUSD",
        side=OrderSide.BUY,
        volume=0.1,
        entry_price=1.1000,
        stop_loss=1.0990,
        take_profit=1.1020,
        open_time=datetime(2026, 1, 28, 9, 0, 0),
        broker_position_id="p1",
    )
    sup.register(
        "p1",
        PositionMeta(
            max_hold_minutes=60,
            entry_time=datetime(2026, 1, 28, 9, 0, 0),
            entry_price=1.1000,
            atr_at_entry=0.0008,
        ),
    )
    state = MarketState(
        symbol="EURUSD",
        time=datetime(2026, 1, 28, 9, 20, 0),
        regime_primary=Regime.TREND,
        regime_secondary=Regime.LOW_VOL,
        trend_strength=0.001,
        volatility=0.001,
        range_compression=0.001,
        return_1=0.0001,
        session="LONDON",
        confidence=0.8,
    )
    sup.evaluate(state, [pos])
    assert "p1" in adapter.closed
