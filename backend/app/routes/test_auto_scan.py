import asyncio
import types
import sys
import pytest


def _inject_minimal_stubs(monkeypatch):
    """Insert minimal stub modules into sys.modules to avoid heavy external imports."""
    def _set_stub(name, module_obj, force=False):
        # Keep real modules intact when already loaded; only inject when missing unless forced.
        if force or name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, module_obj)

    # Create package anchors
    _set_stub("app", types.ModuleType("app"))
    _set_stub("app.routes", types.ModuleType("app.routes"))
    _set_stub("app.strategies", types.ModuleType("app.strategies"))
    _set_stub("app.engine", types.ModuleType("app.engine"))
    _set_stub("app.core", types.ModuleType("app.core"))
    _set_stub("app.models", types.ModuleType("app.models"))

    # option_chain_utils.get_option_chain
    m = types.ModuleType("app.routes.option_chain_utils")
    async def _get_option_chain(sym, expiry, auth):
        return {"CE": [], "PE": []}
    m.get_option_chain = _get_option_chain
    _set_stub("app.routes.option_chain_utils", m)

    # ai_model with predict
    m = types.ModuleType("app.strategies.ai_model")
    class DummyAI:
        def predict(self, arr):
            return 1
    m.ai_model = DummyAI()
    _set_stub("app.strategies.ai_model", m)

    # market_intelligence trend_analyzer
    m = types.ModuleType("app.strategies.market_intelligence")
    async def _get_market_trends():
        return {"indices": {"NIFTY": {"current": 100.0, "change_percent": 0.5, "trend": "uptrend"}}}
    m.get_market_trends = _get_market_trends
    _set_stub("app.strategies.market_intelligence", m)

    # other lightweight stubs
    _set_stub("app.engine.option_signal_generator", types.ModuleType("app.engine.option_signal_generator"))
    _set_stub("app.engine.paper_trade_updater", types.ModuleType("app.engine.paper_trade_updater"))
    _set_stub("app.core.database", types.ModuleType("app.core.database"))
    # SessionLocal stub
    def _SessionLocal():
        class DB:
            def add(self, *a, **k):
                pass
            def commit(self):
                pass
            def close(self):
                pass
        return DB()
    monkeypatch.setattr(sys.modules["app.core.database"], "SessionLocal", _SessionLocal, raising=False)

    # TradeReport stub
    m = types.ModuleType("app.models.trading")
    class TradeReport:
        def __init__(self, **kwargs):
            pass
    m.TradeReport = TradeReport
    _set_stub("app.models.trading", m)

    # market hours
    m = types.ModuleType("app.core.market_hours")
    from datetime import datetime
    m.ist_now = lambda: datetime.utcnow()
    m.is_market_open = lambda s, e: True
    m.market_status = lambda s, e: {"is_open": True, "reason": "open", "current_time": "09:00", "current_date": str(datetime.utcnow().date())}
    _set_stub("app.core.market_hours", m)

    # trade_metrics and signal_scoring
    _set_stub("app.routes.trade_metrics", types.ModuleType("app.routes.trade_metrics"))
    _set_stub("app.routes.signal_scoring", types.ModuleType("app.routes.signal_scoring"))

    # zerodha order util
    m = types.ModuleType("app.engine.zerodha_order_util")
    def place_zerodha_order(**kwargs):
        return {"success": True, "order_id": "MOCK-1"}
    m.place_zerodha_order = place_zerodha_order
    _set_stub("app.engine.zerodha_order_util", m)


@pytest.mark.asyncio
async def test_scan_once_triggers_execute(monkeypatch):
    _inject_minimal_stubs(monkeypatch)
    # Import module after stubs injected
    import importlib
    ats = importlib.import_module("app.routes.auto_trading_simple")

    calls = {"execute": 0}

    async def fake_analyze(*args, **kwargs):
        # first call returns WAIT, second returns start allowed
        if calls.get("analyze_count", 0) == 0:
            calls["analyze_count"] = 1
            return {"recommendation": {"start_trade_allowed": False, "symbol": "NIFTY263"}}
        else:
            return {"recommendation": {"start_trade_allowed": True, "symbol": "NIFTY263", "entry_price": 100, "quantity": 1, "action": "BUY", "stop_loss": 90, "target": 110}}

    async def fake_execute(*args, **kwargs):
        calls["execute"] += 1
        return {"success": True}

    monkeypatch.setattr(ats, "analyze", fake_analyze)
    monkeypatch.setattr(ats, "execute", fake_execute)

    # First scan: should not execute
    res1 = await ats._scan_once(["NIFTY"], "weekly_option", 50000)
    assert res1.get("executed") is False

    # Second scan: should execute once
    res2 = await ats._scan_once(["NIFTY"], "weekly_option", 50000)
    assert res2.get("executed") is True
    assert calls["execute"] == 1
