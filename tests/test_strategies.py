from datetime import datetime, timedelta

from bot.core.models import Bar, MarketState, Regime
from bot.strategies.trend import TrendStrategy
from bot.strategies.range import RangeStrategy


def _bars(start: datetime, count: int, step: float, base: float = 1.1000) -> list[Bar]:
    bars = []
    price = base
    for i in range(count):
        time = start + timedelta(minutes=15 * i)
        price += step
        bars.append(Bar(time=time, open=price - step, high=price + 0.0005, low=price - 0.0005, close=price, volume=100))
    return bars


def test_trend_strategy_generates_signal():
    h1 = _bars(datetime(2026, 1, 28, 0, 0), 60, 0.0002)
    # Build a gentle uptrend with a shallow pullback to trigger the pullback logic.
    m15 = []
    price = 1.1000
    start = datetime(2026, 1, 28, 0, 0)
    for i in range(80):
        price += 0.00005
        m15.append(Bar(time=start + timedelta(minutes=15 * i), open=price - 0.00004, high=price + 0.0002, low=price - 0.0002, close=price, volume=100))
    for i in range(80, 100):
        price -= 0.00002 if i < 99 else -0.00003
        m15.append(Bar(time=start + timedelta(minutes=15 * i), open=price - 0.00002, high=price + 0.0002, low=price - 0.0002, close=price, volume=100))
    state = MarketState(
        symbol="EURUSD",
        time=m15[-1].time,
        regime_primary=Regime.TREND,
        regime_secondary=Regime.LOW_VOL,
        trend_strength=0.001,
        volatility=0.001,
        range_compression=0.001,
        return_1=0.0001,
        session="LONDON_NY",
        confidence=0.9,
    )
    strat = TrendStrategy()
    signal = strat.generate(state, m15, h1)
    assert signal is not None


def test_range_strategy_generates_signal():
    bars = []
    base = 1.1000
    start = datetime(2026, 1, 28, 0, 0)
    # Create a range with a final dip near the low to trigger oversold.
    for i in range(25):
        price = base + (0.0005 if i % 2 == 0 else -0.0005)
        bars.append(Bar(time=start + timedelta(minutes=15 * i), open=price, high=price + 0.0003, low=price - 0.0003, close=price, volume=100))
    for i in range(25, 30):
        price = base - 0.0007 - (i - 25) * 0.00005
        bars.append(Bar(time=start + timedelta(minutes=15 * i), open=price + 0.0001, high=price + 0.0002, low=price - 0.0003, close=price, volume=100))
    state = MarketState(
        symbol="EURUSD",
        time=bars[-1].time,
        regime_primary=Regime.RANGE,
        regime_secondary=Regime.LOW_VOL,
        trend_strength=0.0,
        volatility=0.0008,
        range_compression=0.001,
        return_1=-0.0001,
        session="LONDON_NY",
        confidence=0.8,
    )
    strat = RangeStrategy()
    signal = strat.generate(state, bars, [])
    assert signal is not None
