import asyncio
import types
import sys

# Stub heavy modules
stub_mod = types.ModuleType("app.strategies.ai_model")
stub_mod.ai_model = object()
sys.modules["app.strategies.ai_model"] = stub_mod

from fastapi import HTTPException

from app.routes import auto_trading_simple as ats
from app.routes import paper_trading as pt


def test_live_execute_blocked_by_confirmation(monkeypatch):
    # Ensure market window always open for test
    ats.trade_window["start"] = (0, 0)
    ats.trade_window["end"] = (23, 59)

    # Not demo mode so guard applies
    ats.state["is_demo_mode"] = False

    # Force confirmation to fail
    monkeypatch.setattr(ats, "_require_multi_tick_confirmation", lambda u, p, s, required_ticks=3: False)

    # Call execute and expect HTTPException due to guard
    try:
        asyncio.run(ats.execute(symbol="NIFTYTESTCE", price=100.0, quantity=1, side="BUY"))
        assert False, "Expected HTTPException due to failed confirmation"
    except HTTPException as e:
        assert e.status_code == 403
        assert 'failed multi-tick confirmation' in str(e.detail).lower()


def test_live_execute_allowed_when_confirmed(monkeypatch):
    ats.trade_window["start"] = (0, 0)
    ats.trade_window["end"] = (23, 59)
    ats.state["is_demo_mode"] = False

    # Force confirmation to pass
    monkeypatch.setattr(ats, "_require_multi_tick_confirmation", lambda u, p, s, required_ticks=3: True)

    # Stub broker order placement to avoid external calls
    monkeypatch.setattr(ats, "place_zerodha_order", lambda **k: {"order_id": 12345, "status": "OK"})

    # Call execute - should not raise
    res = asyncio.run(ats.execute(symbol="NIFTYTESTCE", price=100.0, quantity=1, side="BUY"))
    # execute returns a dict on success - check for success key or no exception
    assert isinstance(res, dict) or res is None


def test_paper_trade_block_and_allow(monkeypatch):
    # For paper trades, create_paper_trade should block when confirmation fails
    monkeypatch.setattr(pt, "_require_multi_tick_confirmation", lambda u, p, s, required_ticks=3: False)
    # Build payload
    trade = pt.PaperTradeCreate(
        symbol="NIFTYTESTCE",
        index_name="NIFTY",
        side="BUY",
        quantity=1,
        entry_price=100.0,
        stop_loss=95.0,
    )

    # Use a real DB session via dependency requires; call the route function directly with a test DB session
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        # Ensure market is considered open for test
        monkeypatch.setattr(pt, "market_status", lambda *a, **k: {"is_open": True, "current_time": "now"})

        # Clear any existing open paper trades to avoid max-trades blocking
        try:
            db.query(pt.PaperTrade).filter(pt.PaperTrade.status == "OPEN").delete()
            db.commit()
        except Exception:
            db.rollback()
        res = pt.create_paper_trade(trade, db=db)
        assert res["success"] is False
        assert 'blocked' in res["message"].lower() or 'confirmation' in str(res).lower()

        # Now allow
        monkeypatch.setattr(pt, "_require_multi_tick_confirmation", lambda u, p, s, required_ticks=3: True)
        res2 = pt.create_paper_trade(trade, db=db)
        assert res2["success"] is True
    finally:
        db.close()
