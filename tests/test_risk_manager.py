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
                max_trades_per_day=2,
                max_consecutive_losses=2,
                min_rr=1.2,
                news_sensitivity="high",
            )
        ],
        sessions=[SessionConfig(name="LONDON_NY", start=datetime.strptime("08:00", "%H:%M").time(), end=datetime.strptime("17:00", "%H:%M").time())],
        default_timezone="UTC",
    )


def test_risk_rejects_low_rr():
    broker = PaperBroker()
    broker.seed_tick("EURUSD", Tick(datetime.utcnow(), 1.1000, 1.1001))
    cfg = _config()
    risk = HardRiskManager(cfg, broker)
    signal = Signal(
        symbol="EURUSD",
        time=datetime(2026, 1, 28, 9, 0, 0),
        strategy="trend",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        entry_price=1.1000,
        stop_loss=1.0990,
        take_profit=1.1005,
        max_hold_minutes=60,
        confidence=0.9,
        rationale=["test"],
    )
    state = MarketState(
        symbol="EURUSD",
        time=signal.time,
        regime_primary=Regime.TREND,
        regime_secondary=Regime.LOW_VOL,
        trend_strength=0.001,
        volatility=0.001,
        range_compression=0.001,
        return_1=0.0001,
        session="LONDON_NY",
        confidence=0.9,
    )
    decision = risk.approve(signal, state)
    assert decision.approved is False
    assert decision.reason == "rr_too_low"


def test_risk_accepts_valid_trade():
    broker = PaperBroker()
    broker.seed_tick("EURUSD", Tick(datetime.utcnow(), 1.1000, 1.1001))
    cfg = _config()
    risk = HardRiskManager(cfg, broker)
    signal = Signal(
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
    state = MarketState(
        symbol="EURUSD",
        time=signal.time,
        regime_primary=Regime.TREND,
        regime_secondary=Regime.LOW_VOL,
        trend_strength=0.001,
        volatility=0.001,
        range_compression=0.001,
        return_1=0.0001,
        session="LONDON_NY",
        confidence=0.9,
    )
    decision = risk.approve(signal, state)
    assert decision.approved is True
    assert decision.adjusted_size > 0
