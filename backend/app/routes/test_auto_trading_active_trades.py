from app.routes.trade_metrics import normalize_active_trade_metrics


def test_normalize_active_trade_metrics_for_buy_and_sell():
    buy_trade = {
        "symbol": "NFO:NIFTY26MAR22500CE",
        "side": "BUY",
        "entry_price": 100.0,
        "current_price": 120.0,
        "quantity": 10,
    }
    sell_trade = {
        "symbol": "NFO:NIFTY26MAR22500PE",
        "side": "SELL",
        "entry_price": 200.0,
        "current_price": 180.0,
        "quantity": 5,
    }

    buy_row = normalize_active_trade_metrics(buy_trade)
    assert buy_row["pnl"] == 200.0
    assert buy_row["unrealized_pnl"] == 200.0
    assert buy_row["profit_loss"] == 200.0
    assert buy_row["pnl_percentage"] == 20.0
    assert buy_row["pnl_percent"] == 20.0
    assert buy_row["profit_percentage"] == 20.0

    sell_row = normalize_active_trade_metrics(sell_trade)
    assert sell_row["pnl"] == 100.0
    assert sell_row["unrealized_pnl"] == 100.0
    assert sell_row["profit_loss"] == 100.0
    assert sell_row["pnl_percentage"] == 10.0
    assert sell_row["pnl_percent"] == 10.0
    assert sell_row["profit_percentage"] == 10.0


def test_normalize_active_trade_metrics_handles_price_fallback_and_defaults():
    trade = {
        "symbol": "NFO:BANKNIFTY26MAR48000CE",
        "action": "BUY",
        "price": 50.0,
        "quantity": 2,
    }

    row = normalize_active_trade_metrics(trade)

    assert row["entry_price"] == 50.0
    assert row["current_price"] == 50.0
    assert row["side"] == "BUY"
    assert row["pnl"] == 0.0
    assert row["pnl_percentage"] == 0.0
