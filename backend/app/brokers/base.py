from abc import ABC, abstractmethod
import importlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class OrderData:
    """Standard order data format"""
    symbol: str
    order_type: str  # market, limit, stop_loss
    side: str  # buy, sell
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None

@dataclass
class OrderResponse:
    """Standard order response"""
    order_id: str
    status: str
    filled_quantity: float
    average_price: Optional[float]
    message: str

@dataclass
class Position:
    """Trading position data"""
    symbol: str
    quantity: float
    average_cost: float
    current_price: float
    pnl: float
    pnl_percentage: float

@dataclass
class Account:
    """Account details"""
    balance: float
    available_balance: float
    used_margin: float
    free_margin: float
    net_worth: float

class BrokerInterface(ABC):
    """Abstract base class for broker integrations"""
    
    def __init__(self, api_key: str, api_secret: str, access_token: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with broker API"""
        pass
    
    @abstractmethod
    async def place_order(self, order: OrderData) -> OrderResponse:
        """Place an order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        pass
    
    @abstractmethod
    async def modify_order(self, order_id: str, order: OrderData) -> OrderResponse:
        """Modify an existing order"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get all open positions"""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> Account:
        """Get account information"""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get status of a specific order"""
        pass
    
    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical OHLCV data"""
        pass
    
    @abstractmethod
    async def subscribe_to_stream(self, symbols: List[str]) -> None:
        """Subscribe to real-time market data stream"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker"""
        pass

class BrokerFactory:
    """Factory to create broker instances"""
    
    _brokers = {}
    _broker_modules = {
        "zerodha": "app.brokers.zerodha",
        "upstox": "app.brokers.upstox",
        "groww": "app.brokers.groww",
        "angel_one": "app.brokers.angel_one",
    }
    
    @classmethod
    def register_broker(cls, broker_name: str, broker_class):
        """Register a new broker implementation"""
        cls._brokers[broker_name.lower()] = broker_class

    @classmethod
    def _ensure_broker_registered(cls, broker_name: str) -> None:
        if broker_name in cls._brokers:
            return
        module_path = cls._broker_modules.get(broker_name)
        if module_path:
            importlib.import_module(module_path)
    
    @classmethod
    def create_broker(
        cls,
        broker_name: str,
        api_key: str,
        api_secret: str,
        access_token: Optional[str] = None
    ) -> BrokerInterface:
        """Create broker instance"""
        broker_key = broker_name.lower()
        cls._ensure_broker_registered(broker_key)
        broker_class = cls._brokers.get(broker_key)
        if not broker_class:
            raise ValueError(f"Unknown broker: {broker_name}")
        
        return broker_class(api_key, api_secret, access_token)
