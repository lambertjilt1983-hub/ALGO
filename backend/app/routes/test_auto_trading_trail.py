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


def test_maybe_update_trail_buy_never_moves_trail_stop_down():
    trade = {
        "side": "BUY",
        "price": 100.0,
        "stop_loss": 99.0,
        "trail_active": True,
        "trail_start": 100.8,
        "trail_stop": 100.4,
        "trail_step": 0.15,
        # Low support should never force trail_stop down.
        "support": 99.0,
        "resistance": None,
    }

    _maybe_update_trail(trade, 101.4)

    assert trade["trail_stop"] >= 100.4


def test_maybe_update_trail_sell_never_moves_trail_stop_up():
    trade = {
        "side": "SELL",
        "price": 100.0,
        "stop_loss": 101.0,
        "trail_active": True,
        "trail_start": 99.2,
        "trail_stop": 99.7,
        "trail_step": 0.15,
        "support": None,
        # High resistance should never force trail_stop up.
        "resistance": 101.0,
    }

    _maybe_update_trail(trade, 98.5)

    assert trade["trail_stop"] <= 99.7
