from bot.utils.pips import pip_size, spread_in_pips, spread_in_points


def test_pip_size_eurusd():
    assert pip_size("EURUSD", digits=5, point=0.00001) == 0.0001
    assert pip_size("EURUSDm", digits=5, point=0.00001) == 0.0001


def test_spread_usdjpy_pips():
    # USDJPY 3-digit pricing, pip = 0.01
    spread = spread_in_pips(150.00, 150.02, "USDJPY", digits=3, point=0.001)
    assert round(spread, 2) == 2.0


def test_spread_xauusd_points():
    # XAUUSD point-based spread
    spread = spread_in_points(2000.00, 2000.50, point=0.01)
    assert round(spread, 1) == 50.0
