import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from backend.app.engine.auto_trading_engine import AutoTradingEngine
from backend.app.engine.zerodha_broker import ZerodhaBroker
from backend.app.engine.simple_momentum_strategy import SimpleMomentumStrategy

class DummyBroker(ZerodhaBroker):
    def connect(self, credentials):
        self.connected = True
        return True
    def place_order(self, order_details):
        return {"success": True, "order_id": "dummy123"}
    def get_balance(self):
        return {"success": True, "funds": 100000}
    def disconnect(self):
        self.connected = False

def test_strategy_workflow():
    engine = AutoTradingEngine()
    broker = DummyBroker()
    engine.register_broker("zerodha", broker)
    strategy = SimpleMomentumStrategy()
    # Simulated market data
    market_data = {
        "indices": {
            "NIFTY": {"change_percent": 1.2, "trend": "Uptrend"},
            "BANKNIFTY": {"change_percent": -1.0, "trend": "Downtrend"},
            "SENSEX": {"change_percent": 0.2, "trend": "Flat"}
        }
    }
    credentials = {"api_key": "dummy", "access_token": "dummy"}
    assert engine.connect_broker("zerodha", credentials)
    opportunities = strategy.scan(market_data)
    assert len(opportunities) == 2
    signals = strategy.identify(opportunities)
    assert any(s["action"] == "BUY" for s in signals)
    assert any(s["action"] == "SELL" for s in signals)
    analyzed = strategy.analyze(signals)
    results = strategy.execute(analyzed, engine)
    assert all(r["result"]["success"] for r in results)
    engine.disconnect_broker("zerodha")
