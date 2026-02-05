from bot.risk.position_sizer import PositionSizeInput, size_position


def test_position_sizing():
    inp = PositionSizeInput(
        equity=10000,
        risk_pct=0.005,
        stop_distance=0.0010,
        contract_size=100000,
        min_lot=0.01,
        step=0.01,
    )
    vol = size_position(inp)
    assert vol >= 0.01
