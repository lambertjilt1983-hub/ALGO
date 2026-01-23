import asyncio
from typing import Optional, Dict, List
from datetime import datetime
from app.brokers.base import BrokerFactory, OrderData, OrderResponse, Account, Position
from app.core.logger import logger
from app.models.trading import Order
from sqlalchemy.orm import Session

class OrderExecutor:
    """Handles order execution through brokers"""
    
    def __init__(self, broker_name: str, credentials: Dict):
        self.broker_name = broker_name
        self.broker = BrokerFactory.create_broker(
            broker_name,
            credentials["api_key"],
            credentials["api_secret"],
            credentials.get("access_token")
        )
    
    async def execute_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> OrderResponse:
        """Execute trade order"""
        try:
            # Authenticate if needed
            auth_success = await self.broker.authenticate()
            if not auth_success:
                logger.log_error("Broker authentication failed", {"broker": self.broker_name})
                return OrderResponse("", "failed", 0, None, "Authentication failed")
            
            # Create order
            order = OrderData(
                symbol=symbol,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                stop_price=stop_price
            )
            
            # Place order
            response = await self.broker.place_order(order)
            
            logger.log_trade({
                "broker": self.broker_name,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "status": response.status,
                "order_id": response.order_id
            })
            
            return response
        except Exception as e:
            logger.log_error("Order execution failed", {
                "broker": self.broker_name,
                "symbol": symbol,
                "error": str(e)
            })
            return OrderResponse("", "failed", 0, None, str(e))
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel existing order"""
        try:
            auth_success = await self.broker.authenticate()
            if not auth_success:
                logger.log_error("Broker authentication failed", {"broker": self.broker_name})
                return False
            
            success = await self.broker.cancel_order(order_id)
            logger.log_api_call(self.broker_name, "cancel_order", "success" if success else "failed")
            return success
        except Exception as e:
            logger.log_error("Order cancellation failed", {"error": str(e)})
            return False
    
    async def get_positions(self) -> List[Position]:
        """Get all positions"""
        try:
            auth_success = await self.broker.authenticate()
            if not auth_success:
                logger.log_error("Broker authentication failed", {"broker": self.broker_name})
                return []
            
            positions = await self.broker.get_positions()
            return positions
        except Exception as e:
            logger.log_error("Failed to fetch positions", {"error": str(e)})
            return []
    
    async def get_account_info(self) -> Account:
        """Get account information"""
        try:
            auth_success = await self.broker.authenticate()
            if not auth_success:
                logger.log_error("Broker authentication failed", {"broker": self.broker_name})
                return Account(0, 0, 0, 0, 0)
            
            account = await self.broker.get_account_info()
            return account
        except Exception as e:
            logger.log_error("Failed to fetch account info", {"error": str(e)})
            return Account(0, 0, 0, 0, 0)

class RiskManager:
    """Manages risk parameters for trades"""
    
    def __init__(self, 
                 max_position_size: float = 0.1,
                 max_daily_loss: float = 0.05,
                 default_stop_loss_percent: float = 2,
                 default_take_profit_percent: float = 5):
        self.max_position_size = max_position_size  # Max 10% per position
        self.max_daily_loss = max_daily_loss  # Max 5% daily loss
        self.default_stop_loss_percent = default_stop_loss_percent
        self.default_take_profit_percent = default_take_profit_percent
        self.daily_pnl = 0
        self.trades_today: List[Dict] = []
    
    def validate_trade(
        self,
        account_balance: float,
        position_value: float,
        symbol: str
    ) -> tuple[bool, str]:
        """Validate if trade is within risk parameters"""
        
        # Check position size
        position_size_ratio = position_value / account_balance
        if position_size_ratio > self.max_position_size:
            return False, f"Position size exceeds maximum ({position_size_ratio:.2%} > {self.max_position_size:.2%})"
        
        # Check daily loss limit
        if self.daily_pnl < (-account_balance * self.max_daily_loss):
            return False, f"Daily loss limit reached ({self.daily_pnl:.2f})"
        
        return True, "Trade approved"
    
    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """Calculate position size based on risk"""
        risk_per_trade = account_balance * 0.02  # Risk 2% per trade
        price_risk = abs(entry_price - stop_loss_price)
        
        if price_risk == 0:
            return 0
        
        position_size = risk_per_trade / price_risk
        return position_size
    
    def record_trade(self, pnl: float):
        """Record trade P&L"""
        self.daily_pnl += pnl
        self.trades_today.append({
            "timestamp": datetime.now(),
            "pnl": pnl
        })
    
    def reset_daily_metrics(self):
        """Reset daily metrics"""
        self.daily_pnl = 0
        self.trades_today = []
