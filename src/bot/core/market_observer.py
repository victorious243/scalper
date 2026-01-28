from __future__ import annotations

from datetime import datetime
from typing import List

from bot.core.models import MarketState, Regime, Bar
from bot.core.config import BotConfig
from bot.utils.indicators import atr, trend_strength, range_compression
from bot.utils.time import in_sessions


class MarketObserver:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def evaluate(self, symbol: str, bars_m15: List[Bar], bars_h1: List[Bar], now: datetime) -> MarketState:
        trend = trend_strength(bars_h1)
        volatility = atr(bars_m15)
        compression = range_compression(bars_m15)
        session = in_sessions(now, self.config.sessions, self.config.default_timezone)
        ret_1 = 0.0
        if len(bars_m15) >= 2:
            ret_1 = (bars_m15[-1].close - bars_m15[-2].close) / (bars_m15[-2].close if bars_m15[-2].close else 1.0)

        regime_primary = Regime.RANGE
        regime_secondary = Regime.LOW_VOL
        notes = []

        if abs(trend) >= 0.0006:
            regime_primary = Regime.TREND
            notes.append("trend_strength")
        if volatility > 0:
            vol_ratio = volatility / (bars_m15[-1].close if bars_m15 else 1.0)
            if vol_ratio > 0.004:
                regime_secondary = Regime.HIGH_VOL
            elif vol_ratio < 0.0015:
                regime_secondary = Regime.LOW_VOL
            else:
                regime_secondary = Regime.MIXED

        if regime_primary == Regime.TREND and compression < 0.001:
            notes.append("clean_trend")
        if regime_primary == Regime.RANGE and compression < 0.001:
            notes.append("tight_range")

        confidence = min(1.0, abs(trend) * 1000 + (0.2 if session != "OFF" else 0.0))
        return MarketState(
            symbol=symbol,
            time=now,
            regime_primary=regime_primary,
            regime_secondary=regime_secondary,
            trend_strength=trend,
            volatility=volatility,
            range_compression=compression,
            return_1=ret_1,
            session=session,
            confidence=confidence,
            notes=notes,
        )
