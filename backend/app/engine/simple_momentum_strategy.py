from typing import Any, Dict, List
from .strategy_interface import StrategyInterface

class SimpleMomentumStrategy(StrategyInterface):
    """A sample strategy that demonstrates scan, identify, analyze, execute."""
    def scan(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Scan for indices with strong uptrend or downtrend
        opportunities = []
        for symbol, data in market_data.get('indices', {}).items():
            if abs(data.get('change_percent', 0)) > 0.5:
                opportunities.append({"symbol": symbol, "data": data})
        return opportunities

    def identify(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Identify actionable signals (e.g., strong uptrend = buy, downtrend = sell)
        signals = []
        for opp in opportunities:
            trend = opp['data'].get('trend')
            if trend == 'Uptrend':
                signals.append({"symbol": opp['symbol'], "action": "BUY", "data": opp['data']})
            elif trend == 'Downtrend':
                signals.append({"symbol": opp['symbol'], "action": "SELL", "data": opp['data']})
        return signals

    def analyze(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Add simple risk/reward analysis (placeholder)
        for signal in signals:
            signal['risk'] = 1  # placeholder
            signal['reward'] = 2  # placeholder
        return signals

    def execute(self, signals: List[Dict[str, Any]], engine: Any) -> List[Dict[str, Any]]:
        # Execute trades using the engine and return results
        results = []
        for signal in signals:
            order_details = {
                "exchange": "NSE",
                "tradingsymbol": signal['symbol'],
                "transaction_type": signal['action'],
                "quantity": 1,
                "order_type": "MARKET",
                "product": "MIS"
            }
            result = engine.place_order("zerodha", order_details)
            results.append({"signal": signal, "result": result})
        return results
