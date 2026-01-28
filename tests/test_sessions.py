from datetime import datetime, timezone

from bot.core.config import SessionConfig
from bot.utils.time import in_sessions


def test_dublin_sessions():
    sessions = [
        SessionConfig(name="LONDON", start=datetime.strptime("07:00", "%H:%M").time(), end=datetime.strptime("11:30", "%H:%M").time()),
        SessionConfig(name="NY_OVERLAP", start=datetime.strptime("12:30", "%H:%M").time(), end=datetime.strptime("16:00", "%H:%M").time()),
    ]
    dt_london = datetime(2026, 1, 28, 8, 0, tzinfo=timezone.utc)
    dt_off = datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc)
    dt_ny = datetime(2026, 1, 28, 13, 0, tzinfo=timezone.utc)

    assert in_sessions(dt_london, sessions, "Europe/Dublin") == "LONDON"
    assert in_sessions(dt_off, sessions, "Europe/Dublin") == "OFF"
    assert in_sessions(dt_ny, sessions, "Europe/Dublin") == "NY_OVERLAP"
