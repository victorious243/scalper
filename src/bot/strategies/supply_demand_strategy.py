from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from bot.core.models import Bar, MarketState, Signal, OrderSide, OrderType
from bot.snd.config import SupplyDemandConfig
from bot.snd.zone_detector import detect_zones, update_zone_touches
from bot.snd.zone_models import Zone, ZoneType
from bot.snd.confirmation import confirmation_passed
from bot.utils.pips import pip_size
from bot.utils.logging import log_event


@dataclass
class TrendState:
    direction: str  # "BULL", "BEAR", "NEUTRAL"


class SupplyDemandStrategy:
    name = "supply_demand"

    def __init__(self, cfg: SupplyDemandConfig) -> None:
        self.cfg = cfg
        self.zones: Dict[str, List[Zone]] = {}

    def _trend_state(self, bars: List[Bar]) -> TrendState:
        if len(bars) < 10:
            return TrendState("NEUTRAL")
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        hh = highs[-1] > max(highs[-6:-1])
        hl = lows[-1] > min(lows[-6:-1])
        lh = highs[-1] < max(highs[-6:-1])
        ll = lows[-1] < min(lows[-6:-1])
        if hh and hl:
            return TrendState("BULL")
        if lh and ll:
            return TrendState("BEAR")
        return TrendState("NEUTRAL")

    def _select_zones(self, symbol: str, timeframe: str, bars: List[Bar], pipsize: float) -> List[Zone]:
        result = detect_zones(symbol, timeframe, bars, self.cfg.zone, pip_size=pipsize)
        zones = sorted(result.zones, key=lambda z: z.score, reverse=True)
        return zones[: self.cfg.top_k_zones]

    def generate(
        self,
        state: MarketState,
        bars_m15: List[Bar],
        bars_h1: List[Bar],
        context: Optional[dict] = None,
    ) -> Optional[Signal]:
        if not self.cfg.enable:
            return None

        context = context or {}
        bars_by_tf: Dict[str, List[Bar]] = context.get("bars", {})
        ltf = self.cfg.ltf_timeframe
        htf_list = self.cfg.htf_timeframes
        symbol_info = context.get("symbol_info", {})
        logger = context.get("logger")
        digits = int(symbol_info.get("digits", 5))
        point = float(symbol_info.get("point", 0.0001))
        pipsize = pip_size(state.symbol, digits, point)

        ltf_bars = bars_by_tf.get(ltf) or (bars_m15 if ltf == "M15" else [])
        if not ltf_bars:
            return None

        # Build HTF zones
        all_zones: List[Zone] = []
        for tf in htf_list:
            htf_bars = bars_by_tf.get(tf)
            if not htf_bars:
                continue
            zones = self._select_zones(state.symbol, tf, htf_bars, pipsize)
            all_zones.extend(zones)

        if not all_zones:
            if logger:
                log_event(logger, "snd_skip", symbol=state.symbol, reason="no_zones")
            return None

        trend = self._trend_state(bars_by_tf.get(htf_list[0], bars_h1))
        if trend.direction == "NEUTRAL" and not self.cfg.allow_neutral_trend:
            if logger:
                log_event(logger, "snd_skip", symbol=state.symbol, reason="neutral_trend")
            return None

        last_price = ltf_bars[-1].close
        active_zones: List[Zone] = []
        for zone in all_zones:
            zone = update_zone_touches(zone, last_price, self.cfg.zone)
            if zone.active:
                active_zones.append(zone)

        if logger:
            log_event(
                logger,
                "snd_zones",
                symbol=state.symbol,
                zones=[{"id": z.id, "type": z.zone_type.value, "lower": z.lower, "upper": z.upper, "score": z.score, "touches": z.touches} for z in active_zones],
                trend=trend.direction,
            )

        for zone in sorted(active_zones, key=lambda z: z.score, reverse=True):
            if trend.direction == "BULL" and zone.zone_type != ZoneType.DEMAND:
                continue
            if trend.direction == "BEAR" and zone.zone_type != ZoneType.SUPPLY:
                continue

            if not zone.contains(last_price):
                continue

            if not confirmation_passed(ltf_bars, zone, self.cfg.confirmation):
                if logger:
                    log_event(logger, "snd_skip", symbol=state.symbol, reason="confirmation_failed", zone_id=zone.id)
                continue

            # Entry
            entry_price = last_price
            side = OrderSide.BUY if zone.zone_type == ZoneType.DEMAND else OrderSide.SELL

            buffer = max(
                self.cfg.sl_buffer_atr * max(zone.atr, state.volatility),
                self.cfg.sl_buffer_pips * pipsize,
            )
            if side == OrderSide.BUY:
                stop = zone.lower - buffer
                take = entry_price + (entry_price - stop) * self.cfg.min_rr
            else:
                stop = zone.upper + buffer
                take = entry_price - (stop - entry_price) * self.cfg.min_rr

            return Signal(
                symbol=state.symbol,
                time=ltf_bars[-1].time,
                strategy=self.name,
                side=side,
                order_type=OrderType.MARKET,
                entry_price=entry_price,
                stop_loss=stop,
                take_profit=take,
                max_hold_minutes=240,
                confidence=zone.score,
                rationale=[f"zone:{zone.id}", f"trend:{trend.direction}", f"tf:{zone.timeframe}"],
            )

        if logger:
            log_event(logger, "snd_skip", symbol=state.symbol, reason="no_entry")
        return None
