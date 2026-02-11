from typing import Dict, Any, Optional
from .broker_interface import BrokerInterface

class AutoTradingEngine:
    """Core engine to manage brokers, strategies, and trading operations."""
    def __init__(self):
        self.brokers: Dict[str, BrokerInterface] = {}
        self.active_trades: list = []
        self.trade_history: list = []

    def register_broker(self, name: str, broker: BrokerInterface):
        self.brokers[name] = broker

    def connect_broker(self, name: str, credentials: Dict[str, Any]) -> bool:
        broker = self.brokers.get(name)
        if broker:
            return broker.connect(credentials)
        return False

    def place_order(self, broker_name: str, order_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        broker = self.brokers.get(broker_name)
        if broker:
            result = broker.place_order(order_details)
            if result.get('success'):
                self.active_trades.append(result)
            else:
                import logging
                logger = logging.getLogger("trading_bot")
                logger.error(f"[AutoTradingEngine] ERROR: Failed to place order with broker '{broker_name}'. Details: {result}")
            return result
        else:
            import logging
            logger = logging.getLogger("trading_bot")
            logger.error(f"[AutoTradingEngine] ERROR: Broker '{broker_name}' not found or not connected.")
        return None

    def get_balance(self, broker_name: str) -> Optional[Dict[str, Any]]:
        broker = self.brokers.get(broker_name)
        if broker:
            return broker.get_balance()
        return None

    def disconnect_broker(self, name: str):
        broker = self.brokers.get(name)
        if broker:
            broker.disconnect()
