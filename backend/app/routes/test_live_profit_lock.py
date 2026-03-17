import asyncio
import sys
import types

# Inject a lightweight stub for heavy AI model imports to avoid pulling sklearn/scipy during tests
stub_mod = types.ModuleType("app.strategies.ai_model")
stub_mod.ai_model = object()
sys.modules["app.strategies.ai_model"] = stub_mod

from app.routes.auto_trading_simple import active_trades, history, update_trade_price, state

# Ensure tests run in demo mode to avoid placing real broker orders
state["is_demo_mode"] = True


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


def test_profit_lock_applies_and_moves_stop():
    # Arrange
    active_trades.clear()
    history.clear()
    trade = make_trade()
    active_trades.append(trade)

    # Act: push price above lock threshold (entry + 21)
    asyncio.run(update_trade_price(symbol=trade["symbol"], price=121.0))

    # Assert: profit lock applied and stop loss moved to at least entry+20
    assert trade.get("profit_lock_applied") is True
    assert trade.get("stop_loss") is not None
    assert float(trade.get("stop_loss")) >= 120.0
    assert trade in active_trades


def test_profit_lock_closes_on_reversal():
    # Arrange: start fresh and let first tick apply lock
    active_trades.clear()
    history.clear()
    trade = make_trade()
    active_trades.append(trade)

    asyncio.run(update_trade_price(symbol=trade["symbol"], price=121.0))
    assert trade.get("profit_lock_applied") is True

    # Act: simulate a reversal (price drops from 121 -> 119)
    asyncio.run(update_trade_price(symbol=trade["symbol"], price=119.0))

    # Assert: trade was closed and moved to history with SL_HIT status
    assert trade not in active_trades
    assert history, "expected history to contain closed trade"
    last = history[-1]
    assert last.get("symbol") == trade["symbol"]
    assert last.get("status") in ("SL_HIT", "CLOSED")
    assert last.get("pnl") is not None


def test_sell_side_lock_and_reversal():
    active_trades.clear()
    history.clear()
    trade = make_trade(side="SELL", entry=100.0, stop_loss=105.0)
    active_trades.append(trade)

    # Move price down to trigger SELL profit lock (entry - 21)
    asyncio.run(update_trade_price(symbol=trade["symbol"], price=79.0))
    assert trade.get("profit_lock_applied") is True
    assert float(trade.get("stop_loss")) <= 80.0

    # Reversal up should close the trade
    asyncio.run(update_trade_price(symbol=trade["symbol"], price=81.0))
    assert trade not in active_trades
    last = history[-1]
    assert last.get("status") in ("SL_HIT", "CLOSED")


def test_multiple_quantity_pnl_calculation():
    active_trades.clear()
    history.clear()
    trade = make_trade(entry=100.0, qty=2)
    active_trades.append(trade)

    # Apply lock
    asyncio.run(update_trade_price(symbol=trade["symbol"], price=121.0))
    assert trade.get("profit_lock_applied") is True

    # Reversal to close
    asyncio.run(update_trade_price(symbol=trade["symbol"], price=119.0))
    assert trade not in active_trades
    last = history[-1]
    # Expected pnl = (exit - entry) * qty
    expected_pnl = round((last.get("exit_price") - 100.0) * 2 * 1, 2)
    assert round(last.get("pnl"), 2) == expected_pnl


def test_already_locked_does_not_reapply():
    active_trades.clear()
    history.clear()
    trade = make_trade()
    # Simulate already locked
    trade["profit_lock_applied"] = True
    trade["stop_loss"] = 120.0
    active_trades.append(trade)

    # Another favorable tick should not move stop again in this logic
    asyncio.run(update_trade_price(symbol=trade["symbol"], price=125.0))
    assert trade.get("profit_lock_applied") is True
    assert float(trade.get("stop_loss")) == 120.0


def test_missing_entry_price_safe():
    active_trades.clear()
    history.clear()
    trade = make_trade()
    # Remove entry price to simulate malformed data
    trade.pop("price", None)
    trade.pop("entry_price", None)
    active_trades.append(trade)

    # Call update; should not raise and should leave trade open
    asyncio.run(update_trade_price(symbol=trade["symbol"], price=121.0))
    assert trade in active_trades
