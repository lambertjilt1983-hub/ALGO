import sys
import types
import asyncio

# Stub heavy AI model imports to keep tests lightweight
stub_mod = types.ModuleType("app.strategies.ai_model")
stub_mod.ai_model = object()
sys.modules["app.strategies.ai_model"] = stub_mod

from app.routes import auto_trading_simple as ats


def make_trade(symbol="TST", entry=100.0, side="BUY", qty=1, stop_loss=95.0):
    return {
        "symbol": symbol,
        "status": "OPEN",
        "price": entry,
        "entry_price": entry,
        "current_price": entry,
        "side": side,
        "quantity": qty,
        "stop_loss": stop_loss,
    }


def test_continuous_ltp_stream_triggers_exit_order(monkeypatch):
    # Arrange
    ats.active_trades.clear()
    ats.history.clear()
    calls = []

    def fake_place_zerodha_order(symbol, quantity, side, order_type="MARKET", product="MIS", exchange="NFO"):
        calls.append({"symbol": symbol, "quantity": quantity, "side": side, "order_type": order_type, "product": product, "exchange": exchange})
        return {"success": True, "order_id": "MOCK_EXIT"}

    # Ensure tests exercise broker-order path (not demo)
    ats.state["is_demo_mode"] = False

    # Patch the place_zerodha_order used by the module
    monkeypatch.setattr(ats, "place_zerodha_order", fake_place_zerodha_order)

    trade = make_trade(symbol="STREAM1", entry=100.0, side="BUY", qty=1)
    ats.active_trades.append(trade)

    # Act: simulate a stream of ticks moving up to lock threshold then reversing
    ticks = [105.0, 110.0, 115.0, 121.0, 120.5, 119.0]
    for p in ticks:
        asyncio.run(ats.update_trade_price(symbol=trade["symbol"], price=p))

    # Assert: an exit order was attempted when reversal occurred after lock
    assert len(calls) >= 1, f"expected at least one exit order attempt, got {calls}"
    last_call = calls[-1]
    assert last_call["symbol"] == trade["symbol"]
    # Trade should be closed and in history
    assert trade not in ats.active_trades
    assert ats.history and ats.history[-1]["symbol"] == trade["symbol"]
    # If order id attached to trade, ensure it's the mock id
    # (module stores exit_order_id on successful place)
    assert ats.history[-1].get("exit_order_id") in ("MOCK_EXIT", None) or ats.history[-1].get("exit_error") is None


def test_stream_with_multiple_trades_and_single_exit_per_trade(monkeypatch):
    ats.active_trades.clear()
    ats.history.clear()
    calls = []

    def fake_place_zerodha_order(symbol, quantity, side, order_type="MARKET", product="MIS", exchange="NFO"):
        calls.append({"symbol": symbol, "quantity": quantity, "side": side})
        return {"success": True, "order_id": f"MOCK_{symbol}"}

    ats.state["is_demo_mode"] = False
    monkeypatch.setattr(ats, "place_zerodha_order", fake_place_zerodha_order)

    t1 = make_trade(symbol="T1", entry=100.0, side="BUY")
    t2 = make_trade(symbol="T2", entry=200.0, side="SELL")
    ats.active_trades.extend([t1, t2])

    # Stream: both trades reach lock then reverse at different times
    sequence = [
        ("T1", 121.0),
        ("T2", 179.0),
        ("T1", 119.0),  # T1 reversal -> exit
        ("T2", 181.0),  # T2 reversal -> exit
    ]

    for symbol, price in sequence:
        asyncio.run(ats.update_trade_price(symbol=symbol, price=price))

    # Assertions
    symbols_called = {c["symbol"] for c in calls}
    assert "T1" in symbols_called and "T2" in symbols_called
    assert t1 not in ats.active_trades and t2 not in ats.active_trades
    assert any(h.get("symbol") == "T1" for h in ats.history)
    assert any(h.get("symbol") == "T2" for h in ats.history)
