from __future__ import annotations

from bot.snd.zone_models import Zone


def score_zone(zone: Zone) -> float:
    # Simple deterministic score based on impulse and freshness
    impulse_score = min(1.0, zone.impulse_size / max(zone.atr * 2.0, 1e-6))
    freshness_score = max(0.0, 1.0 - (zone.touches * 0.4))
    width_penalty = min(1.0, zone.width() / max(zone.atr * 2.0, 1e-6))
    score = (0.6 * impulse_score) + (0.3 * freshness_score) + (0.1 * (1.0 - width_penalty))
    return max(0.0, min(1.0, score))
