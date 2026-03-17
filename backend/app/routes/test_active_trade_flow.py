import pytest
import types
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.auto_trading_simple import (
    active_trades,
    history,
    state,
    place_zerodha_order,
)

# stub heavy modules if any
stub_mod = types.ModuleType("app.strategies.ai_model")
stub_mod.ai_model = object()
sys.modules["app.strategies.ai_model"] = stub_mod

@pytest.fixture(autouse=True)
def reset_state():
    # clear trades and history before each test
    active_trades.clear()
    history.clear()
    # default demo mode
    state["is_demo_mode"] = True
    state["live_armed"] = False
    yield
    active_trades.clear()
    history.clear()


def test_demo_trade_execution_and_active_api():
    app = FastAPI()
    # mount the real routes
    from app.routes.auto_trading_simple import router as at_router
    app.include_router(at_router, prefix="/autotrade")
    client = TestClient(app)

    # execute a demo trade by forcing demo via payload
    resp = client.post(
        "/autotrade/execute",
        json={"symbol": "TEST1", "price": 100.0, "quantity": 2, "side": "BUY", "force_demo": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["is_demo_mode"] is True

    # active trades should contain the new trade
    resp2 = client.get("/autotrade/trades/active")
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["count"] == 1
    trade = body["trades"][0]
    assert trade["symbol"] == "TEST1"
    assert trade["entry_price"] == 100.0
    assert trade["current_price"] == 100.0

    # update price via price endpoint
    upd = client.post("/autotrade/trades/price", params={"symbol": "TEST1", "price": 105.0})
    assert upd.status_code == 200
    # fetch again
    resp3 = client.get("/autotrade/trades/active")
    trade2 = resp3.json()["trades"][0]
    assert trade2["current_price"] == 105.0

    # now push price below stop to trigger SL exit (stop_loss default 95)
    close_resp = client.post("/autotrade/trades/price", params={"symbol": "TEST1", "price": 90.0})
    assert close_resp.status_code == 200
    # active list should now be empty
    resp4 = client.get("/autotrade/trades/active")
    assert resp4.json()["count"] == 0
    # history should contain the closed trade
    assert history, "expected history to record the closed trade"
    assert history[-1]["symbol"] == "TEST1"
    assert history[-1]["status"] in ("SL_HIT", "CLOSED")


def test_live_trade_execution_and_update(monkeypatch):
    # arrange: switch to live mode and arm
    state["is_demo_mode"] = False
    state["live_armed"] = True

    # keep test deterministic regardless of wall-clock market hours
    monkeypatch.setattr("app.routes.auto_trading_simple._within_trade_window", lambda: True)

    # monkeypatch Zerodha order placement to avoid real API calls
    monkeypatch.setattr(
        "app.routes.auto_trading_simple.place_zerodha_order",
        lambda **kwargs: {"success": True, "order_id": "FAKE123"},
    )

    app = FastAPI()
    from app.routes.auto_trading_simple import router as at_router
    app.include_router(at_router, prefix="/autotrade")
    client = TestClient(app)

    # execute a live trade (will actually append via patched order)
    resp = client.post(
        "/autotrade/execute",
        json={
            "symbol": "SBIN26MAR800CE",
            "price": 100.0,
            "balance": 50000,
            "quantity": 1,
            "side": "BUY",
            "stop_loss": 99.0,
            "target": 101.4,
            "quality_score": 67,
            "confirmation_score": 71,
            "ai_edge_score": 37,
            "breakout_score": 62,
            "momentum_score": 62,
            "breakout_confirmed": True,
            "momentum_confirmed": True,
            "breakout_hold_confirmed": True,
            "signal_type": "stock",
            "is_stock": True,
            "start_trade_allowed": False,
            "start_trade_decision": "NO",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # should report demo mode false
    assert data["is_demo_mode"] is False

    # confirm active trades API
    resp2 = client.get("/autotrade/trades/active")
    assert resp2.json()["count"] == 1
    tr = resp2.json()["trades"][0]
    assert tr["symbol"] == "SBIN26MAR800CE"
    assert tr["current_price"] == 100.0

    # price update
    client.post("/autotrade/trades/price", params={"symbol": "SBIN26MAR800CE", "price": 101.2})
    resp3 = client.get("/autotrade/trades/active")
    assert resp3.json()["trades"][0]["current_price"] == 101.2

    # close it by forcing price below stop (stop default=195)
    client.post("/autotrade/trades/price", params={"symbol": "SBIN26MAR800CE", "price": 98.5})
    resp4 = client.get("/autotrade/trades/active")
    assert resp4.json()["count"] == 0
    assert history and history[-1]["symbol"] == "SBIN26MAR800CE"
    assert history[-1]["status"] in ("SL_HIT", "CLOSED")


def test_execute_flat_json_payload_does_not_500_and_keeps_cors(monkeypatch):
    # Arrange a predictable live execution path.
    state["is_demo_mode"] = False
    state["live_armed"] = True

    monkeypatch.setattr("app.routes.auto_trading_simple._within_trade_window", lambda: True)
    monkeypatch.setattr("app.routes.auto_trading_simple._require_multi_tick_confirmation", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.routes.auto_trading_simple.place_zerodha_order",
        lambda **kwargs: {"success": True, "order_id": "FAKE-CORS-1"},
    )

    app = FastAPI()
    from app.routes.auto_trading_simple import router as at_router
    from app.main import log_cors_request
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(log_cors_request)
    app.include_router(at_router, prefix="/autotrade")
    client = TestClient(app)

    # Flat payload matches the frontend request format.
    resp = client.post(
        "/autotrade/execute",
        headers={"Origin": "http://localhost:3000"},
        json={
            "symbol": "SENSEX2631277300PE",
            "price": 476.5,
            "balance": 10323.1,
            "quantity": 1,
            "side": "BUY",
            "stop_loss": 450,
            "target": 510,
            "broker_id": 3,
        },
    )

    # Regression guard: this used to crash with NameError / payload parsing mismatch.
    assert resp.status_code != 500
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_main_origin_normalization_strips_trailing_slash():
    from app.main import _build_allowed_origins, _normalize_origin

    class DummySettings:
        ALLOWED_ORIGINS = "https://algo-theta-nine.vercel.app/, https://algo-mlcb.onrender.com/"
        FRONTEND_URL = "https://algo-theta-nine.vercel.app/"
        FRONTEND_ALT_URL = "https://algo-theta-nine.vercel.app/"

    allowed = _build_allowed_origins(DummySettings())

    assert _normalize_origin("https://algo-theta-nine.vercel.app/") == "https://algo-theta-nine.vercel.app"
    assert "https://algo-theta-nine.vercel.app" in allowed
    assert "https://algo-theta-nine.vercel.app/" not in allowed


def test_live_execute_uses_stock_thresholds_and_ignores_stale_start_trade_flags(monkeypatch):
    active_trades.clear()
    history.clear()
    state["symbol_cooldowns"] = {}
    state["recent_exit_contexts"] = {}
    state["is_demo_mode"] = False
    state["live_armed"] = True

    monkeypatch.setattr("app.routes.auto_trading_simple._within_trade_window", lambda: True)
    monkeypatch.setattr(
        "app.routes.auto_trading_simple._loss_brake_profile",
        lambda: {"enabled": False, "stage": "OFF", "block_new_entries": False},
    )
    monkeypatch.setattr("app.routes.auto_trading_simple._require_multi_tick_confirmation", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.routes.auto_trading_simple.place_zerodha_order",
        lambda **kwargs: {"success": True, "order_id": "FAKE-STOCK-1"},
    )

    app = FastAPI()
    from app.routes.auto_trading_simple import router as at_router
    app.include_router(at_router, prefix="/autotrade")
    client = TestClient(app)

    resp = client.post(
        "/autotrade/execute",
        json={
            "symbol": "SBIN26MAR800CE",
            "price": 100.0,
            "balance": 50000,
            "quantity": 1,
            "side": "BUY",
            "stop_loss": 99.0,
            "target": 101.4,
            "quality_score": 67,
            "confirmation_score": 71,
            "ai_edge_score": 37,
            "breakout_score": 62,
            "momentum_score": 62,
            "breakout_confirmed": True,
            "momentum_confirmed": True,
            "breakout_hold_confirmed": True,
            "signal_type": "stock",
            "is_stock": True,
            "start_trade_allowed": False,
            "start_trade_decision": "NO",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["is_demo_mode"] is False


def test_live_execute_rejects_missing_ai_context(monkeypatch):
    state["is_demo_mode"] = False
    state["live_armed"] = True

    monkeypatch.setattr("app.routes.auto_trading_simple._within_trade_window", lambda: True)
    monkeypatch.setattr(
        "app.routes.auto_trading_simple._loss_brake_profile",
        lambda: {"enabled": False, "stage": "OFF", "block_new_entries": False},
    )
    monkeypatch.setattr("app.routes.auto_trading_simple._require_multi_tick_confirmation", lambda *args, **kwargs: True)

    app = FastAPI()
    from app.routes.auto_trading_simple import router as at_router
    app.include_router(at_router, prefix="/autotrade")
    client = TestClient(app)

    # Minimal live payload (no AI metadata) must be rejected by server-side gate.
    resp = client.post(
        "/autotrade/execute",
        json={
            "symbol": "LIVE_NO_AI_1",
            "price": 200.0,
            "balance": 50000,
            "quantity": 1,
            "side": "BUY",
            "stop_loss": 195.0,
            "target": 210.0,
            "broker_id": 1,
        },
    )

    assert resp.status_code == 422
    data = resp.json()
    detail = data.get("detail") if isinstance(data, dict) else {}
    assert isinstance(detail, dict)
    assert "missing ai context" in str(detail.get("message", "")).lower()
    assert "required_fields" in detail
