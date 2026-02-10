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
        # Prevent auto trade if market is closed
        from datetime import time
        from app.core.market_hours import is_market_open
        # NSE equity/derivatives: 9:15am to 3:30pm IST
        market_start = time(9, 15)
        market_end = time(15, 30)
        if not is_market_open(market_start, market_end):
            return [{"error": "Market is closed. No trades executed."}]
        results = []
        for signal in signals:
            order_details = {
                "exchange": "NSE",
                "tradingsymbol": signal['symbol'],
                "transaction_type": signal['action'],
                "quantity": 1,
                "order_type": "MARKET",
                "product": "MIS",
            }
            # Add stoploss and target if present in signal
            if 'stop_loss' in signal:
                order_details['stoploss'] = abs(signal['stop_loss'] - signal['entry_price'])
            if 'target' in signal:
                order_details['squareoff'] = abs(signal['target'] - signal['entry_price'])
            result = engine.place_order("zerodha", order_details)
            results.append({"signal": signal, "result": result})
        return results
