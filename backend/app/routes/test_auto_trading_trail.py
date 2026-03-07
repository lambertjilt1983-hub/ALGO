from app.routes.auto_trading_simple import _init_trailing_fields, _maybe_update_trail


def test_init_trailing_fields_buy_starts_above_entry():
    fields = _init_trailing_fields(100.0, "BUY")
    assert fields["trail_start"] > 100.0
    assert fields["trail_stop"] < fields["trail_start"]


def test_init_trailing_fields_sell_starts_below_entry():
    fields = _init_trailing_fields(100.0, "SELL")
    assert fields["trail_start"] < 100.0
    assert fields["trail_stop"] > fields["trail_start"]


def test_maybe_update_trail_repairs_legacy_buy_anchor_and_moves_stop():
    trade = {
        "side": "BUY",
        "price": 100.0,
        "stop_loss": 99.0,
        # Legacy/bad anchor (below entry for BUY)
        "trail_active": False,
        "trail_start": 99.7,
        "trail_stop": 99.6,
        "trail_step": 0.15,
        "support": None,
        "resistance": None,
    }

    # Favorable move should activate repaired trailing logic and lift stop.
    _maybe_update_trail(trade, 101.0)

    assert trade["trail_start"] > 100.0
    assert trade["trail_active"] is True
    assert trade["stop_loss"] >= 100.0
