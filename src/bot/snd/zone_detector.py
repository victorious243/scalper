from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from bot.core.models import Bar
from bot.utils.indicators import atr as atr_calc
from bot.snd.zone_models import Zone, ZoneType, ZoneConfig
from bot.snd.zone_scoring import score_zone


@dataclass
class ZoneDetectionResult:
    zones: List[Zone]
    atr: float


def _body_high(bar: Bar) -> float:
    return max(bar.open, bar.close)


def _body_low(bar: Bar) -> float:
    return min(bar.open, bar.close)


def _impulsive_candles(bars: List[Bar], direction: int) -> int:
    count = 0
    for b in bars:
        if direction > 0 and b.close > b.open:
            count += 1
        elif direction < 0 and b.close < b.open:
            count += 1
    return count


def _overlap_ratio(a: Zone, b: Zone) -> float:
    if a.upper <= b.lower or b.upper <= a.lower:
        return 0.0
    overlap = min(a.upper, b.upper) - max(a.lower, b.lower)
    return overlap / max(a.width(), b.width(), 1e-9)


def detect_zones(
    symbol: str,
    timeframe: str,
    bars: List[Bar],
    cfg: ZoneConfig,
    atr_period: int = 14,
    pip_size: float = 0.0001,
) -> ZoneDetectionResult:
    zones: List[Zone] = []
    if len(bars) < cfg.base_max + cfg.impulsive_min_candles + 2:
        return ZoneDetectionResult(zones=zones, atr=0.0)

    atr_val = atr_calc(bars, period=atr_period)

    for i in range(cfg.base_min, len(bars) - cfg.impulsive_min_candles - 1):
        # Base window at [i - base_len + 1 : i]
        for base_len in range(cfg.base_min, cfg.base_max + 1):
            start = i - base_len + 1
            if start < 1:
                continue
            base = bars[start : i + 1]
            base_high = max(b.high for b in base)
            base_low = min(b.low for b in base)
            base_range = base_high - base_low
            if atr_val > 0 and base_range > cfg.max_base_atr_mult * atr_val:
                continue

            before = bars[start - 1]
            after = bars[i + 1 : i + 1 + cfg.impulsive_min_candles]

            # Demand: Drop -> Base -> Rally (DBR)
            drop = before.close < before.open
            rally = _impulsive_candles(after, direction=1) >= cfg.impulsive_min_candles
            move_away = after[-1].close - base_high
            if drop and rally:
                impulse_ok = (
                    move_away >= cfg.impulse_atr_mult * atr_val
                    or move_away >= cfg.impulse_min_pips * pip_size
                )
                if impulse_ok:
                    if cfg.zone_body_rule == "wick":
                        lower = base_low
                        upper = base_high
                    else:
                        lower = base_low
                        upper = max(_body_high(b) for b in base)
                    zone = Zone(
                        id=f"{symbol}-{timeframe}-D-{bars[i].time.timestamp():.0f}",
                        symbol=symbol,
                        zone_type=ZoneType.DEMAND,
                        timeframe=timeframe,
                        created_at=bars[i].time,
                        lower=lower,
                        upper=upper,
                        base_start=base[0].time,
                        base_end=base[-1].time,
                        impulse_size=move_away,
                        atr=atr_val,
                        score=0.0,
                        notes=["DBR"],
                    )
                    zone.score = score_zone(zone)
                    zones.append(zone)

            # Supply: Rally -> Base -> Drop (RBD)
            rally_before = before.close > before.open
            drop_after = _impulsive_candles(after, direction=-1) >= cfg.impulsive_min_candles
            move_away_supply = base_low - after[-1].close
            if rally_before and drop_after:
                impulse_ok = (
                    move_away_supply >= cfg.impulse_atr_mult * atr_val
                    or move_away_supply >= cfg.impulse_min_pips * pip_size
                )
                if impulse_ok:
                    if cfg.zone_body_rule == "wick":
                        lower = base_low
                        upper = base_high
                    else:
                        upper = base_high
                        lower = min(_body_low(b) for b in base)
                    zone = Zone(
                        id=f"{symbol}-{timeframe}-S-{bars[i].time.timestamp():.0f}",
                        symbol=symbol,
                        zone_type=ZoneType.SUPPLY,
                        timeframe=timeframe,
                        created_at=bars[i].time,
                        lower=lower,
                        upper=upper,
                        base_start=base[0].time,
                        base_end=base[-1].time,
                        impulse_size=move_away_supply,
                        atr=atr_val,
                        score=0.0,
                        notes=["RBD"],
                    )
                    zone.score = score_zone(zone)
                    zones.append(zone)

    # De-duplicate overlapping zones by keeping best score
    filtered: List[Zone] = []
    for z in sorted(zones, key=lambda x: x.score, reverse=True):
        overlap = any(_overlap_ratio(z, other) >= cfg.overlap_threshold for other in filtered)
        if not overlap:
            filtered.append(z)

    return ZoneDetectionResult(zones=filtered, atr=atr_val)


def update_zone_touches(zone: Zone, price: float, cfg: ZoneConfig) -> Zone:
    if not zone.active:
        return zone
    if zone.contains(price):
        zone.touches += 1
        if zone.touches > cfg.max_touches:
            zone.active = False
    return zone
