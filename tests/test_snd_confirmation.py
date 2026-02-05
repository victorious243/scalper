from datetime import datetime, timedelta

from bot.core.models import Bar
from bot.snd.zone_models import Zone, ZoneType
from bot.snd.confirmation import ConfirmationConfig, bos_confirmed, rejection_confirmed


def _bars_bos():
    bars = []
    t = datetime(2026, 1, 1, 0, 0)
    price = 1.1000
    for _ in range(6):
        price += 0.0002
        bars.append(Bar(time=t, open=price - 0.0001, high=price + 0.0002, low=price - 0.0002, close=price, volume=100))
        t += timedelta(minutes=15)
    # Break high
    price += 0.0005
    bars.append(Bar(time=t, open=price - 0.0001, high=price + 0.0003, low=price - 0.0002, close=price, volume=100))
    return bars


def test_bos_confirmation():
    bars = _bars_bos()
    zone = Zone(
        id="z1",
        symbol="EURUSD",
        zone_type=ZoneType.DEMAND,
        timeframe="H4",
        created_at=bars[0].time,
        lower=1.095,
        upper=1.097,
        base_start=bars[0].time,
        base_end=bars[0].time,
        impulse_size=0.01,
        atr=0.001,
        score=0.8,
    )
    cfg = ConfirmationConfig(require_bos=True)
    assert bos_confirmed(bars, zone, cfg) is True


def test_rejection_confirmation():
    t = datetime(2026, 1, 1, 0, 0)
    bar = Bar(time=t, open=1.1000, high=1.1010, low=1.0970, close=1.1005, volume=100)
    zone = Zone(
        id="z2",
        symbol="EURUSD",
        zone_type=ZoneType.DEMAND,
        timeframe="H4",
        created_at=t,
        lower=1.098,
        upper=1.099,
        base_start=t,
        base_end=t,
        impulse_size=0.01,
        atr=0.001,
        score=0.8,
    )
    cfg = ConfirmationConfig(require_rejection=True, wick_body_ratio=2.0)
    assert rejection_confirmed([bar], zone, cfg) is True
