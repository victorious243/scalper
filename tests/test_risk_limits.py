from datetime import datetime

from bot.adapters.paper_broker import PaperBroker
from bot.core.config import BotConfig, SessionConfig, SymbolConfig
from bot.core.models import Signal, MarketState, OrderSide, OrderType, Regime, Tick
from bot.core.risk import HardRiskManager


def _config():
    return BotConfig(
        symbols=[
            SymbolConfig(
                symbol="EURUSD",
                spread_mode="pips",
                max_spread=1.5,
                min_spread_checks=2,
                spread_spike_cooldown_minutes=10,
                min_atr=0.0005,
                max_atr=0.005,
                min_stop_atr=0.5,
                min_regime_confidence=0.5,
                risk_per_trade=0.005,
                max_daily_loss=0.02,
                max_trades_per_day=5,
                max_consecutive_losses=5,
                min_rr=1.2,
                news_sensitivity="high",
            )
        ],
        sessions=[SessionConfig(name="LONDON", start=datetime.strptime("07:00", "%H:%M").time(), end=datetime.strptime("11:30", "%H:%M").time())],
        default_timezone="UTC",
        max_daily_trades=1,
        max_daily_loss=0.02,
        max_consecutive_losses=2,
    )


def _signal():
    return Signal(
        symbol="EURUSD",
        time=datetime(2026, 1, 28, 9, 0, 0),
        strategy="trend",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        entry_price=1.1000,
        stop_loss=1.0985,
        take_profit=1.1025,
        max_hold_minutes=60,
        confidence=0.9,
        rationale=["test"],
    )


def _state():
    return MarketState(
        symbol="EURUSD",
        time=datetime(2026, 1, 28, 9, 0, 0),
        regime_primary=Regime.TREND,
        regime_secondary=Regime.LOW_VOL,
        trend_strength=0.001,
        volatility=0.001,
        range_compression=0.001,
        return_1=0.0001,
        session="LONDON",
        confidence=0.9,
    )


def test_global_max_trades():
    broker = PaperBroker()
    broker.seed_tick("EURUSD", Tick(datetime.utcnow(), 1.1000, 1.1001))
    risk = HardRiskManager(_config(), broker)
    signal = _signal()
    state = _state()
    decision = risk.approve(signal, state)
    assert decision.approved is True
    risk.register_trade_open(signal.symbol, signal.time)

    decision2 = risk.approve(signal, state)
    assert decision2.approved is False
    assert decision2.reason == "global_max_trades"


def test_global_consecutive_losses():
    broker = PaperBroker()
    broker.seed_tick("EURUSD", Tick(datetime.utcnow(), 1.1000, 1.1001))
    cfg = _config()
    risk = HardRiskManager(cfg, broker)
    signal = _signal()
    state = _state()
    risk.register_trade_result({"symbol": "EURUSD", "pnl": -10, "close_time": signal.time})
    risk.register_trade_result({"symbol": "EURUSD", "pnl": -5, "close_time": signal.time})

    decision = risk.approve(signal, state)
    assert decision.approved is False
    assert decision.reason == "global_consecutive_losses"
