import asyncio
from datetime import datetime

from app.routes import auto_trading_simple as ats


def _open_trade(trade_id: int, symbol: str, price: float = 100.0, current_price: float = 100.0):
    return {
        "id": trade_id,
        "symbol": symbol,
        "side": "BUY",
        "price": price,
        "entry_price": price,
        "current_price": current_price,
        "quantity": 2,
        "status": "OPEN",
        "entry_time": datetime.utcnow().isoformat(),
        "target": price + 25,
        "stop_loss": price - 20,
    }


def test_active_trades_endpoint_returns_multiple_rows_with_metrics(monkeypatch):
    ats.active_trades.clear()
    ats.history.clear()
    try:
        ats.active_trades.extend([
            _open_trade(1, "SIM:IDX-A", price=100.0, current_price=101.5),
            _open_trade(2, "SIM:IDX-B", price=200.0, current_price=198.0),
        ])

        # Keep this test in-memory and deterministic.
        monkeypatch.setattr(ats, "_sync_active_trades_from_db", lambda: None)
        body = asyncio.run(ats.get_active_trades())

        assert body["count"] == 2
        assert len(body["trades"]) == 2
        for row in body["trades"]:
            assert "current_price" in row
            assert "entry_price" in row
            assert "pnl" in row
            assert "pnl_percentage" in row
    finally:
        ats.active_trades.clear()
        ats.history.clear()


def test_update_prices_updates_all_open_trades_in_one_cycle(monkeypatch):
    ats.active_trades.clear()
    ats.history.clear()
    try:
        ats.active_trades.extend([
            _open_trade(11, "SIM:FAST-A", price=100.0, current_price=100.0),
            _open_trade(12, "SIM:FAST-B", price=120.0, current_price=120.0),
            _open_trade(13, "SIM:FAST-C", price=140.0, current_price=140.0),
        ])

        class _FakeKite:
            def ltp(self, symbols):
                return {
                    "SIM:FAST-A": {"last_price": 101.0},
                    "SIM:FAST-B": {"last_price": 121.0},
                    "SIM:FAST-C": {"last_price": 141.0},
                }

            def quote(self, symbols):
                return self.ltp(symbols)

        monkeypatch.setattr(ats, "_get_kite", lambda: _FakeKite())
        monkeypatch.setattr(ats, "_quote_symbol", lambda symbol, index=None: symbol)

        result = asyncio.run(ats.update_live_trade_prices())

        assert result["success"] is True
        assert result["updated_count"] == 3
        assert result.get("closed_count", 0) == 0
        assert len(ats.active_trades) == 3
        assert [round(t["current_price"], 2) for t in ats.active_trades] == [101.0, 121.0, 141.0]
    finally:
        ats.active_trades.clear()
        ats.history.clear()


def test_trade_history_returns_closed_rows_after_price_exit():
    ats.active_trades.clear()
    ats.history.clear()
    try:
        trade = _open_trade(21, "SIM:HISTORY-A", price=100.0, current_price=100.0)
        trade["stop_loss"] = 95.0
        ats.active_trades.append(trade)

        close_res = asyncio.run(ats.update_trade_price(symbol="SIM:HISTORY-A", price=90.0))
        assert close_res["closed"] == 1

        hist = asyncio.run(ats.get_trade_history(limit=50))
        assert isinstance(hist["trades"], list)
        match = [t for t in hist["trades"] if t.get("symbol") == "SIM:HISTORY-A"]
        assert match, "Expected closed symbol in trade history"
        assert match[-1]["status"] == "SL_HIT"
        assert "total_profit" in hist
    finally:
        ats.active_trades.clear()
        ats.history.clear()


def test_trade_history_marks_profit_pullback_as_profit_trail():
    ats.active_trades.clear()
    ats.history.clear()
    try:
        trade = _open_trade(31, "NIFTYTESTPE", price=100.0, current_price=130.0)
        trade["stop_loss"] = 96.0
        ats.active_trades.append(trade)

        close_res = asyncio.run(ats.update_trade_price(symbol="NIFTYTESTPE", price=129.0))
        assert close_res["closed"] == 1

        hist = asyncio.run(ats.get_trade_history(limit=50))
        match = [t for t in hist["trades"] if t.get("symbol") == "NIFTYTESTPE"]
        assert match, "Expected closed symbol in trade history"
        assert match[-1]["status"] == "PROFIT_TRAIL"
        assert match[-1]["pnl"] > 0
    finally:
        ats.active_trades.clear()
        ats.history.clear()
        ats.state["recent_exit_contexts"] = {}


def test_same_move_reentry_requires_stronger_signal():
    ats.state["recent_exit_contexts"] = {}
    try:
        ats._record_recent_exit_context({
            "symbol": "NIFTYTESTPE",
            "side": "BUY",
            "status": "PROFIT_TRAIL",
            "quality_score": 82,
            "ai_edge_score": 52,
            "momentum_score": 61,
            "breakout_score": 63,
            "start_trade_allowed": True,
            "breakout_confirmed": True,
            "momentum_confirmed": True,
            "breakout_hold_confirmed": True,
        })

        blocked, detail = ats._same_move_reentry_info({
            "symbol": "NIFTYTESTPE",
            "side": "BUY",
            "quality_score": 83,
            "ai_edge_score": 53,
            "momentum_score": 62,
            "breakout_score": 64,
            "start_trade_allowed": True,
            "breakout_confirmed": True,
            "momentum_confirmed": True,
            "breakout_hold_confirmed": True,
            "close_back_in_range": False,
            "fake_breakout_by_candle": False,
        })
        assert blocked is True
        assert detail["reason"] == "SAME_MOVE_REENTRY_GUARD"

        blocked, detail = ats._same_move_reentry_info({
            "symbol": "NIFTYTESTPE",
            "side": "BUY",
            "quality_score": 88,
            "ai_edge_score": 61,
            "momentum_score": 72,
            "breakout_score": 75,
            "start_trade_allowed": True,
            "breakout_confirmed": True,
            "momentum_confirmed": True,
            "breakout_hold_confirmed": True,
            "close_back_in_range": False,
            "fake_breakout_by_candle": False,
        })
        assert blocked is False
        assert detail["reason"] == "SAME_MOVE_REENTRY_GUARD"
        assert detail["blocked"] is False
    finally:
        ats.state["recent_exit_contexts"] = {}
