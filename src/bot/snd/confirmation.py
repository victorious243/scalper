from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from bot.core.models import Bar
from bot.snd.zone_models import Zone, ZoneType


@dataclass
class ConfirmationConfig:
    require_bos: bool = True
    require_rejection: bool = False
    require_nested_zone: bool = False
    wick_body_ratio: float = 2.0
    swing_lookback: int = 5


def _swing_high(bars: List[Bar], lookback: int) -> Optional[float]:
    if len(bars) < lookback + 2:
        return None
    highs = [b.high for b in bars[-lookback:]]
    return max(highs) if highs else None


def _swing_low(bars: List[Bar], lookback: int) -> Optional[float]:
    if len(bars) < lookback + 2:
        return None
    lows = [b.low for b in bars[-lookback:]]
    return min(lows) if lows else None


def bos_confirmed(bars: List[Bar], zone: Zone, cfg: ConfirmationConfig) -> bool:
    if len(bars) < cfg.swing_lookback + 2:
        return False
    last = bars[-1]
    prev_swing_high = _swing_high(bars[:-1], cfg.swing_lookback)
    prev_swing_low = _swing_low(bars[:-1], cfg.swing_lookback)
    if zone.zone_type == ZoneType.DEMAND and prev_swing_high is not None:
        return last.close > prev_swing_high
    if zone.zone_type == ZoneType.SUPPLY and prev_swing_low is not None:
        return last.close < prev_swing_low
    return False


def rejection_confirmed(bars: List[Bar], zone: Zone, cfg: ConfirmationConfig) -> bool:
    if not bars:
        return False
    last = bars[-1]
    body = abs(last.close - last.open)
    upper_wick = last.high - max(last.open, last.close)
    lower_wick = min(last.open, last.close) - last.low
    if zone.zone_type == ZoneType.DEMAND:
        return lower_wick > (body * cfg.wick_body_ratio) and last.close > last.open
    return upper_wick > (body * cfg.wick_body_ratio) and last.close < last.open


def confirmation_passed(bars: List[Bar], zone: Zone, cfg: ConfirmationConfig) -> bool:
    checks = []
    if cfg.require_bos:
        checks.append(bos_confirmed(bars, zone, cfg))
    if cfg.require_rejection:
        checks.append(rejection_confirmed(bars, zone, cfg))
    if cfg.require_nested_zone:
        # Placeholder for nested zone detection in LTF
        checks.append(True)
    return all(checks) if checks else True
