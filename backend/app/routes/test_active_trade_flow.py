import pytest
import types
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.database import SessionLocal
from app.models.trading import ActiveTrade

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
    db = SessionLocal()
    try:
        try:
            db.query(ActiveTrade).delete()
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
    # default demo mode
    state["is_demo_mode"] = True
    state["live_armed"] = False
    yield
    active_trades.clear()
    history.clear()
    db = SessionLocal()
    try:
        try:
            db.query(ActiveTrade).delete()
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


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


def test_main_origin_allowed_supports_regex_and_never_throws_on_bad_regex():
    from app.main import _is_origin_allowed

    allowed_origins = ["https://algo-theta-nine.vercel.app"]
    regex = r"^https://algo(?:-[a-z0-9-]+)?\.vercel\.app$"

    assert _is_origin_allowed("https://algo-theta-nine.vercel.app", allowed_origins, regex) is True
    assert _is_origin_allowed("https://algo-preview-123.vercel.app", allowed_origins, regex) is True
    assert _is_origin_allowed("https://evil.example.com", allowed_origins, regex) is False

    # Invalid regex should fail closed instead of raising.
    assert _is_origin_allowed("https://algo-preview-123.vercel.app", allowed_origins, "[") is False


def test_log_cors_request_adds_origin_header_for_regex_origin_on_500(monkeypatch):
    from app import main as main_mod

    # Simulate production regex-only allow-list path.
    monkeypatch.setattr(main_mod, "allowed_origins", [])
    monkeypatch.setattr(main_mod, "allowed_origin_regex", r"^https://algo(?:-[a-z0-9-]+)?\.vercel\.app$")

    app = FastAPI()
    app.middleware("http")(main_mod.log_cors_request)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    client = TestClient(app)
    resp = client.get("/boom", headers={"Origin": "https://algo-theta-nine.vercel.app"})

    assert resp.status_code == 500
    assert resp.headers.get("access-control-allow-origin") == "https://algo-theta-nine.vercel.app"


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


def test_demo_trade_history_mode_not_mislabeled_live(monkeypatch):
    state["is_demo_mode"] = True
    state["live_armed"] = False
    active_trades.clear()
    history.clear()

    app = FastAPI()
    from app.routes.auto_trading_simple import router as at_router
    app.include_router(at_router, prefix="/autotrade")
    client = TestClient(app)

    symbol = "DEMO_MODE_HISTORY_CHECK"

    create_resp = client.post(
        "/autotrade/execute",
        json={
            "symbol": symbol,
            "price": 100.0,
            "balance": 0,
            "quantity": 1,
            "side": "BUY",
            "stop_loss": 95.0,
            "target": 110.0,
            "force_demo": True,
        },
    )
    assert create_resp.status_code == 200
    assert create_resp.json().get("is_demo_mode") is True

    # Force close by moving below SL.
    close_resp = client.post("/autotrade/trades/price", params={"symbol": symbol, "price": 94.0})
    assert close_resp.status_code == 200

    demo_history = client.get("/autotrade/trades/history", params={"mode": "DEMO", "limit": 200})
    assert demo_history.status_code == 200
    demo_trades = demo_history.json().get("trades", [])
    matching_demo = [t for t in demo_trades if t.get("symbol") == symbol]
    assert matching_demo, "Expected demo trade to appear in DEMO history"
    assert all(str(t.get("trade_mode")).upper() == "DEMO" for t in matching_demo)

    live_history = client.get("/autotrade/trades/history", params={"mode": "LIVE", "limit": 200})
    assert live_history.status_code == 200
    live_trades = live_history.json().get("trades", [])
    assert all(t.get("symbol") != symbol for t in live_trades)


def test_active_trades_endpoint_shows_live_and_demo_modes(monkeypatch):
    active_trades.clear()
    history.clear()
    state["is_demo_mode"] = True
    state["live_armed"] = False

    # Keep this unit test DB-independent: bypass DB sync and seed in-memory rows.
    monkeypatch.setattr("app.routes.auto_trading_simple._sync_active_trades_from_db", lambda: None)
    active_trades.extend(
        [
            {
                "id": 1001,
                "symbol": "DEMO_ACTIVE_MODE_CHECK",
                "side": "BUY",
                "price": 100.0,
                "entry_price": 100.0,
                "current_price": 101.0,
                "quantity": 1,
                "status": "OPEN",
                "trade_mode": "DEMO",
            },
            {
                "id": 1002,
                "symbol": "LIVE_ACTIVE_MODE_CHECK",
                "side": "BUY",
                "price": 200.0,
                "entry_price": 200.0,
                "current_price": 201.0,
                "quantity": 1,
                "status": "OPEN",
                "trade_mode": "LIVE",
            },
        ]
    )

    app = FastAPI()
    from app.routes.auto_trading_simple import router as at_router
    app.include_router(at_router, prefix="/autotrade")
    client = TestClient(app)

    resp = client.get("/autotrade/trades/active")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("count") == 2

    modes = {str(t.get("trade_mode", "")).upper() for t in body.get("trades", [])}
    assert "DEMO" in modes
    assert "LIVE" in modes


def test_trade_history_mode_filters_live_and_demo_end_to_end(monkeypatch):
    active_trades.clear()
    history.clear()
    state["symbol_cooldowns"] = {}
    state["recent_exit_contexts"] = {}

    app = FastAPI()
    from app.routes.auto_trading_simple import router as at_router
    app.include_router(at_router, prefix="/autotrade")
    client = TestClient(app)

    demo_symbol = "DEMO_HISTORY_FILTER_CHECK"
    live_symbol = "LIVE_HISTORY_FILTER_CHECK"

    # 1) Create and close a DEMO trade.
    state["is_demo_mode"] = True
    state["live_armed"] = False
    demo_create = client.post(
        "/autotrade/execute",
        json={
            "symbol": demo_symbol,
            "price": 120.0,
            "balance": 0,
            "quantity": 1,
            "side": "BUY",
            "stop_loss": 115.0,
            "target": 130.0,
            "force_demo": True,
        },
    )
    assert demo_create.status_code == 200
    assert demo_create.json().get("is_demo_mode") is True

    demo_close = client.post("/autotrade/trades/price", params={"symbol": demo_symbol, "price": 114.0})
    assert demo_close.status_code == 200

    # 2) Create and close a LIVE trade.
    state["is_demo_mode"] = False
    state["live_armed"] = True
    monkeypatch.setattr("app.routes.auto_trading_simple._within_trade_window", lambda: True)
    monkeypatch.setattr("app.routes.auto_trading_simple._require_multi_tick_confirmation", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.routes.auto_trading_simple.place_zerodha_order",
        lambda **kwargs: {"success": True, "order_id": "LIVE-HISTORY-1"},
    )

    live_create = client.post(
        "/autotrade/execute",
        json={
            "symbol": live_symbol,
            "price": 300.0,
            "balance": 50000,
            "quantity": 1,
            "side": "BUY",
            "stop_loss": 295.0,
            "target": 310.0,
            "broker_id": 1,
            "quality_score": 90,
            "confirmation_score": 90,
            "ai_edge_score": 70,
            "momentum_score": 70,
            "breakout_score": 70,
            "market_bias": "STRONG_ONE_SIDE",
            "market_regime": "TRENDING",
            "breakout_confirmed": True,
            "momentum_confirmed": True,
            "breakout_hold_confirmed": True,
            "timing_risk": "NORMAL",
            "sudden_news_risk": 5,
            "liquidity_spike_risk": 5,
            "premium_distortion_risk": 5,
            "fake_breakout_by_candle": False,
            "close_back_in_range": False,
        },
    )
    assert live_create.status_code == 200
    assert live_create.json().get("is_demo_mode") is False

    live_close = client.post("/autotrade/trades/price", params={"symbol": live_symbol, "price": 294.0})
    assert live_close.status_code == 200

    # 3) Verify mode-filtered history.
    demo_history = client.get("/autotrade/trades/history", params={"mode": "DEMO", "limit": 300})
    assert demo_history.status_code == 200
    demo_trades = demo_history.json().get("trades", [])
    assert any(t.get("symbol") == demo_symbol for t in demo_trades)
    assert all(t.get("symbol") != live_symbol for t in demo_trades)

    live_history = client.get("/autotrade/trades/history", params={"mode": "LIVE", "limit": 300})
    assert live_history.status_code == 200
    live_trades = live_history.json().get("trades", [])
    assert any(t.get("symbol") == live_symbol for t in live_trades)
    assert all(t.get("symbol") != demo_symbol for t in live_trades)
