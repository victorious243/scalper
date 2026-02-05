from bot.risk.position_sizer import PositionSizeInput, size_position


def test_position_sizing():
    inp = PositionSizeInput(
        equity=10000,
        risk_pct=0.005,
        stop_distance=0.0010,
        tick_size=0.00001,
        tick_value=1.0,
        min_lot=0.01,
        step=0.01,
        max_lot=100.0,
    )
    vol = size_position(inp)
    assert vol >= 0.01
