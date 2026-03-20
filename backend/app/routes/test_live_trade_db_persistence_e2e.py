import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.trading import ActiveTrade, TradeReport
from app.routes import auto_trading_simple as ats


@pytest.fixture(autouse=True)
def reset_runtime_and_db(monkeypatch):
    ats.active_trades.clear()
    ats.history.clear()
    ats.state["is_demo_mode"] = False
    ats.state["live_armed"] = True

    db = SessionLocal()
    try:
        db.query(ActiveTrade).delete()
        db.query(TradeReport).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    monkeypatch.setattr("app.routes.auto_trading_simple._within_trade_window", lambda: True)
    monkeypatch.setattr(
        "app.routes.auto_trading_simple.place_zerodha_order",
        lambda **kwargs: {"success": True, "order_id": "LIVE-E2E-ENTRY-1"},
    )

    yield

    ats.active_trades.clear()
    ats.history.clear()
    db = SessionLocal()
    try:
        db.query(ActiveTrade).delete()
        db.query(TradeReport).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_live_execute_manual_close_persists_and_cleans_active_snapshot():
    app = FastAPI()
    app.include_router(ats.router, prefix="/autotrade")
    client = TestClient(app)

    symbol = "SBIN26MAR810CE"

    execute_resp = client.post(
        "/autotrade/execute",
        json={
            "symbol": symbol,
            "price": 120.0,
            "balance": 50000,
            "quantity": 1,
            "side": "BUY",
            "stop_loss": 116.0,
            "target": 128.0,
            "broker_id": 1,
            "quality_score": 90,
            "confirmation_score": 88,
            "ai_edge_score": 65,
            "momentum_score": 70,
            "breakout_score": 72,
            "market_bias": "STRONG_ONE_SIDE",
            "market_regime": "TRENDING",
            "breakout_confirmed": True,
            "momentum_confirmed": True,
            "breakout_hold_confirmed": True,
            "timing_risk": "NORMAL",
            "sudden_news_risk": 4,
            "liquidity_spike_risk": 5,
            "premium_distortion_risk": 4,
            "fake_breakout_by_candle": False,
            "close_back_in_range": False,
        },
    )
    assert execute_resp.status_code == 200
    assert execute_resp.json().get("success") is True
    assert execute_resp.json().get("is_demo_mode") is False

    db = SessionLocal()
    try:
        active_rows = db.query(ActiveTrade).all()
        assert len(active_rows) == 1
        assert active_rows[0].symbol == symbol
        assert active_rows[0].status == "OPEN"
        assert active_rows[0].trade_mode == "LIVE"
    finally:
        db.close()

    close_resp = client.post(
        "/autotrade/trades/close",
        json={"symbol": symbol},
    )
    assert close_resp.status_code == 200
    assert close_resp.json().get("success") is True

    active_api = client.get("/autotrade/trades/active")
    assert active_api.status_code == 200
    assert active_api.json().get("count") == 0

    db = SessionLocal()
    try:
        assert db.query(ActiveTrade).count() == 0
        reports = db.query(TradeReport).filter(TradeReport.symbol == symbol).all()
        assert len(reports) == 1
        report = reports[0]
        assert report.status == "MANUAL_CLOSE"
        assert report.meta.get("trade_mode") == "LIVE"
        assert report.exit_time is not None
    finally:
        db.close()
