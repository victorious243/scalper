from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

from bot.snd.zone_models import ZoneConfig
from bot.snd.confirmation import ConfirmationConfig


@dataclass
class SupplyDemandConfig:
    enable: bool = False
    htf_timeframes: List[str] = field(default_factory=lambda: ["H4"])
    ltf_timeframe: str = "M15"
    scan_on_close: bool = True
    top_k_zones: int = 3
    allow_neutral_trend: bool = False
    allow_blind_entries: bool = False
    sl_buffer_atr: float = 0.3
    sl_buffer_pips: float = 5.0
    sl_buffer_spread_mult: float = 1.5
    min_rr: float = 2.0
    partial_tp: bool = True
    partial_tp_rr: float = 1.0
    partial_tp_pct: float = 0.5
    confirmation: ConfirmationConfig = ConfirmationConfig()
    zone: ZoneConfig = ZoneConfig()


def load_supply_demand_config(path: Optional[str]) -> SupplyDemandConfig:
    if not path:
        return SupplyDemandConfig()
    if not Path(path).exists():
        return SupplyDemandConfig()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    zone = raw.get("zone", {})
    confirm = raw.get("confirmation", {})
    cfg = SupplyDemandConfig(
        enable=bool(raw.get("enable", False)),
        htf_timeframes=raw.get("htf_timeframes", ["H4"]),
        ltf_timeframe=raw.get("ltf_timeframe", "M15"),
        scan_on_close=bool(raw.get("scan_on_close", True)),
        top_k_zones=int(raw.get("top_k_zones", 3)),
        allow_neutral_trend=bool(raw.get("allow_neutral_trend", False)),
        allow_blind_entries=bool(raw.get("allow_blind_entries", False)),
        sl_buffer_atr=float(raw.get("sl_buffer_atr", 0.3)),
        sl_buffer_pips=float(raw.get("sl_buffer_pips", 5.0)),
        sl_buffer_spread_mult=float(raw.get("sl_buffer_spread_mult", 1.5)),
        min_rr=float(raw.get("min_rr", 2.0)),
        partial_tp=bool(raw.get("partial_tp", True)),
        partial_tp_rr=float(raw.get("partial_tp_rr", 1.0)),
        partial_tp_pct=float(raw.get("partial_tp_pct", 0.5)),
        confirmation=ConfirmationConfig(
            require_bos=bool(confirm.get("require_bos", True)),
            require_rejection=bool(confirm.get("require_rejection", False)),
            require_nested_zone=bool(confirm.get("require_nested_zone", False)),
            wick_body_ratio=float(confirm.get("wick_body_ratio", 2.0)),
            swing_lookback=int(confirm.get("swing_lookback", 5)),
        ),
        zone=ZoneConfig(
            base_min=int(zone.get("base_min", 1)),
            base_max=int(zone.get("base_max", 4)),
            impulsive_min_candles=int(zone.get("impulsive_min_candles", 2)),
            impulse_atr_mult=float(zone.get("impulse_atr_mult", 1.5)),
            impulse_min_pips=float(zone.get("impulse_min_pips", 8.0)),
            max_base_atr_mult=float(zone.get("max_base_atr_mult", 1.0)),
            max_touches=int(zone.get("max_touches", 2)),
            overlap_threshold=float(zone.get("overlap_threshold", 0.4)),
            zone_body_rule=str(zone.get("zone_body_rule", "body")),
        ),
    )
    return cfg
