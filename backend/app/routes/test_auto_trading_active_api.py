import pytest

pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.trade_metrics import normalize_active_trade_metrics


def test_active_trades_api_response_shape_contract():
    app = FastAPI()

    @app.get("/autotrade/trades/active")
    def active_trades_contract():
        raw = [
            {
                "symbol": "NFO:NIFTY26MAR22500CE",
                "side": "BUY",
                "entry_price": 100.0,
                "current_price": 110.0,
                "quantity": 10,
                "status": "OPEN",
            }
        ]
        trades = [normalize_active_trade_metrics(t) for t in raw]
        return {"trades": trades, "is_demo_mode": False, "count": len(trades)}

    client = TestClient(app)
    response = client.get("/autotrade/trades/active")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"trades", "is_demo_mode", "count"}
    assert body["count"] == 1
    assert body["is_demo_mode"] is False

    trade = body["trades"][0]
    assert trade["symbol"] == "NFO:NIFTY26MAR22500CE"
    assert trade["status"] == "OPEN"
    assert trade["entry_price"] == 100.0
    assert trade["current_price"] == 110.0
    assert trade["pnl"] == 100.0
    assert trade["unrealized_pnl"] == 100.0
    assert trade["profit_loss"] == 100.0
    assert trade["pnl_percentage"] == 10.0
    assert trade["pnl_percent"] == 10.0
    assert trade["profit_percentage"] == 10.0
