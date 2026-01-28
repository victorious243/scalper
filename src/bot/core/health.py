from __future__ import annotations

from bot.utils.logging import log_event
from bot.core.interfaces import BrokerAdapter


def health_check(adapter: BrokerAdapter, logger) -> bool:
    ok = adapter.is_connected()
    if not ok:
        log_event(logger, "health", status="disconnected")
    return ok
