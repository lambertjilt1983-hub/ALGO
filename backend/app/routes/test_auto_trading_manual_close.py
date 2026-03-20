import asyncio
from datetime import datetime
import pytest

from app.routes import auto_trading_simple as ats


@pytest.fixture(autouse=True)
def _disable_db_sync(monkeypatch):
    # These tests seed in-memory trades directly; keep them isolated from DB sync side effects.
    monkeypatch.setattr(ats, "_sync_active_trades_from_db", lambda: None)


def _open_trade(symbol: str = "NFO:NIFTYTESTCE", **overrides):
    base = {
        "id": 101,
        "symbol": symbol,
        "side": "BUY",
        "price": 100.0,
        "entry_price": 100.0,
        "current_price": 105.0,
        "quantity": 2,
        "status": "OPEN",
        "entry_time": datetime.utcnow().isoformat(),
        "target": 110.0,
        "stop_loss": 95.0,
    }
    base.update(overrides)
    return base


def test_manual_close_moves_trade_from_active_to_history_immediately():
    ats.active_trades.clear()
    ats.history.clear()
    trade = _open_trade()
    ats.active_trades.append(trade)

    payload = ats.CloseTradeRequest(trade_id=trade["id"], symbol=trade["symbol"])
    result = asyncio.run(ats.close_live_trade(payload))

    assert result["success"] is True
    assert result["active_count"] == 0
    assert len(ats.active_trades) == 0
    assert len(ats.history) == 1
    closed = ats.history[-1]
    assert closed["status"] == "MANUAL_CLOSE"
    assert closed["exit_reason"] == "MANUAL_CLOSE"
    assert closed.get("exit_time")


def test_update_prices_closes_trade_on_stop_hit(monkeypatch):
    ats.active_trades.clear()
    ats.history.clear()

    trade = _open_trade(symbol="SIM:NIFTY-SL", current_price=100.0, stop_loss=95.0)
    ats.active_trades.append(trade)

    class _FakeKite:
        def ltp(self, symbols):
            return {symbol: {"last_price": 90.0} for symbol in symbols}

        def quote(self, symbols):
            return {symbol: {"last_price": 90.0} for symbol in symbols}

    monkeypatch.setattr(ats, "_get_kite", lambda: _FakeKite())
    monkeypatch.setattr(ats, "_quote_symbol", lambda symbol, index=None: symbol)

    result = asyncio.run(ats.update_live_trade_prices())

    assert result["success"] is True
    assert result["updated_count"] == 1
    assert result["closed_count"] == 1
    assert len(ats.active_trades) == 0
    assert len(ats.history) == 1
    closed = ats.history[-1]
    assert closed["status"] == "SL_HIT"
    assert closed["exit_reason"] == "SL_HIT"


def test_manual_close_by_symbol_without_trade_id():
    ats.active_trades.clear()
    ats.history.clear()

    trade = _open_trade(id=202, symbol="NFO:BANKNIFTYTESTPE", current_price=111.0)
    ats.active_trades.append(trade)

    payload = ats.CloseTradeRequest(symbol=trade["symbol"])
    result = asyncio.run(ats.close_live_trade(payload))

    assert result["success"] is True
    assert result["active_count"] == 0
    assert len(ats.active_trades) == 0
    assert len(ats.history) == 1
    assert ats.history[-1]["status"] == "MANUAL_CLOSE"


def test_update_prices_handles_multiple_trades_and_closes_only_triggered_one(monkeypatch):
    ats.active_trades.clear()
    ats.history.clear()

    stop_hit_trade = _open_trade(id=301, symbol="SIM:NIFTY-SL-MULTI", current_price=100.0, stop_loss=95.0)
    still_open_trade = _open_trade(
        id=302,
        symbol="SIM:BANKNIFTY-OPEN-MULTI",
        current_price=100.0,
        stop_loss=90.0,
        target=120.0,
    )
    ats.active_trades.extend([stop_hit_trade, still_open_trade])

    class _FakeKite:
        def ltp(self, symbols):
            return {
                "SIM:NIFTY-SL-MULTI": {"last_price": 90.0},
                "SIM:BANKNIFTY-OPEN-MULTI": {"last_price": 103.0},
            }

        def quote(self, symbols):
            return self.ltp(symbols)

    monkeypatch.setattr(ats, "_get_kite", lambda: _FakeKite())
    monkeypatch.setattr(ats, "_quote_symbol", lambda symbol, index=None: symbol)

    result = asyncio.run(ats.update_live_trade_prices())

    assert result["success"] is True
    assert result["updated_count"] == 2
    assert result["closed_count"] == 1
    assert len(ats.history) == 1
    assert ats.history[-1]["status"] == "SL_HIT"
    assert len(ats.active_trades) == 1
    assert ats.active_trades[0]["id"] == 302
    assert ats.active_trades[0]["status"] == "OPEN"


def test_update_trade_price_closes_on_target_exit_reason(monkeypatch):
    ats.active_trades.clear()
    ats.history.clear()

    trade = _open_trade(id=401, symbol="SIM:NIFTY-TARGET-EXIT", current_price=101.0)
    ats.active_trades.append(trade)

    # Force deterministic target-style exit path for this route-level test.
    monkeypatch.setattr(ats, "_should_exit_by_currency", lambda _trade, _price: "TARGET_HIT")

    result = asyncio.run(ats.update_trade_price(symbol=trade["symbol"], price=111.0))

    assert result["updated"] == 1
    assert result["closed"] == 1
    assert len(ats.active_trades) == 0
    assert len(ats.history) == 1
    assert ats.history[-1]["status"] == "TARGET_HIT"
    assert ats.history[-1]["exit_reason"] == "TARGET_HIT"


def test_update_trade_price_uses_trailing_stop_for_sl_hit():
    ats.active_trades.clear()
    ats.history.clear()

    trade = _open_trade(
        id=402,
        symbol="SIM:NIFTY-TRAIL-SL",
        current_price=102.0,
        stop_loss=95.0,
        trail_active=True,
        trail_stop=100.0,
        trail_start=101.0,
        trail_step=0.5,
    )
    ats.active_trades.append(trade)

    result = asyncio.run(ats.update_trade_price(symbol=trade["symbol"], price=99.0))

    assert result["updated"] == 1
    assert result["closed"] == 1
    assert len(ats.active_trades) == 0
    assert len(ats.history) == 1
    assert ats.history[-1]["status"] == "SL_HIT"
    assert ats.history[-1]["exit_reason"] == "SL_HIT"


def test_maybe_place_exit_order_uses_trade_mode_not_global_state(monkeypatch):
    # Global mode may flip to demo later, but a LIVE trade must still attempt broker exit.
    ats.state["is_demo_mode"] = True
    trade = _open_trade(
        id=500,
        symbol="SIM:LIVE-EXIT-MODE",
        trade_mode="LIVE",
        exchange="NFO",
        product="MIS",
    )

    captured = {}

    def _fake_order(**kwargs):
        captured.update(kwargs)
        return {"success": True, "order_id": "EXIT-OK-1"}

    monkeypatch.setattr(ats, "place_zerodha_order", _fake_order)

    ats._maybe_place_exit_order(trade, 101.0)

    assert captured.get("symbol") == "SIM:LIVE-EXIT-MODE"
    assert captured.get("side") == "SELL"
    assert trade.get("exit_order_id") == "EXIT-OK-1"


def test_close_trade_always_cleans_active_snapshot_even_if_report_fails(monkeypatch):
    trade = _open_trade(id=501, symbol="SIM:REPORT-FAIL", trade_uid="uid-report-fail")
    trade["trade_mode"] = "LIVE"

    class _FailingDb:
        def add(self, _obj):
            pass

        def commit(self):
            raise RuntimeError("db write failed")

        def rollback(self):
            pass

        def close(self):
            pass

    cleaned = {"called": False}

    monkeypatch.setattr(ats, "SessionLocal", lambda: _FailingDb())
    monkeypatch.setattr(
        ats,
        "_delete_active_trade_record",
        lambda _trade: cleaned.__setitem__("called", True),
    )

    ats._close_trade(trade, 98.0)

    assert cleaned["called"] is True
