from datetime import datetime, timedelta

from bot.core.models import Bar
from bot.snd.zone_detector import detect_zones, update_zone_touches
from bot.snd.zone_models import ZoneConfig, ZoneType


def _bars_db_rally(count: int = 10):
    bars = []
    t = datetime(2026, 1, 1, 0, 0)
    price = 1.1000
    # Drop
    for _ in range(2):
        price -= 0.0010
        bars.append(Bar(time=t, open=price + 0.0005, high=price + 0.0006, low=price - 0.0002, close=price, volume=100))
        t += timedelta(hours=1)
    # Base
    for _ in range(2):
        bars.append(Bar(time=t, open=price, high=price + 0.0002, low=price - 0.0002, close=price + 0.00005, volume=100))
        t += timedelta(hours=1)
    # Rally
    for _ in range(4):
        price += 0.0010
        bars.append(Bar(time=t, open=price - 0.0005, high=price + 0.0007, low=price - 0.0002, close=price, volume=100))
        t += timedelta(hours=1)
    return bars


def test_zone_detection_demand():
    bars = _bars_db_rally()
    cfg = ZoneConfig(base_min=1, base_max=3, impulsive_min_candles=2, impulse_atr_mult=0.5, impulse_min_pips=5)
    result = detect_zones("EURUSD", "H4", bars, cfg, pip_size=0.0001)
    assert any(z.zone_type == ZoneType.DEMAND for z in result.zones)


def test_zone_touches_disable():
    bars = _bars_db_rally()
    cfg = ZoneConfig(max_touches=1)
    result = detect_zones("EURUSD", "H4", bars, cfg, pip_size=0.0001)
    zone = result.zones[0]
    zone = update_zone_touches(zone, (zone.lower + zone.upper) / 2, cfg)
    zone = update_zone_touches(zone, (zone.lower + zone.upper) / 2, cfg)
    assert zone.active is False
