import aiohttp
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.brokers.base import BrokerInterface, OrderData, OrderResponse, Position, Account, BrokerFactory
from app.core.logger import logger

class AngelSmartAPI(BrokerInterface):
    """Angel One SmartAPI integration"""
    
    BASE_URL = "https://api.smartapi.angelbroking.com"
    
    async def authenticate(self) -> bool:
        """Authenticate with Angel One"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.get(f"{self.BASE_URL}/secure/profiler", headers=headers) as resp:
                    if resp.status == 200:
                        logger.log_api_call("angel_one", "authenticate", "success")
                        return True
            return False
        except Exception as e:
            logger.log_error("Angel One auth failed", {"error": str(e)})
            return False
    
    async def place_order(self, order: OrderData) -> OrderResponse:
        """Place order on Angel One"""
        try:
            payload = {
                "mode": "FULL",
                "exchangeTokens": order.symbol,
                "transactionType": order.side.upper(),
                "orderType": order.order_type.upper(),
                "quantity": str(int(order.quantity)),
                "price": str(order.price or 0),
                "productType": "MIS"
            }
            
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.post(
                    f"{self.BASE_URL}/orders/secure/orderbook",
                    json=payload,
                    headers=headers
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        logger.log_api_call("angel_one", "place_order", "success")
                        return OrderResponse(
                            order_id=data.get("data", {}).get("orderId"),
                            status="pending",
                            filled_quantity=0,
                            average_price=None,
                            message="Order placed successfully"
                        )
            return OrderResponse("", "failed", 0, None, "Order placement failed")
        except Exception as e:
            logger.log_error("Angel One order placement failed", {"error": str(e)})
            return OrderResponse("", "failed", 0, None, str(e))
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order on Angel One"""
        try:
            payload = {"orderId": order_id}
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.post(
                    f"{self.BASE_URL}/orders/secure/orderbook/{order_id}",
                    json=payload,
                    headers=headers
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.log_error("Angel One cancel failed", {"error": str(e)})
            return False
    
    async def modify_order(self, order_id: str, order: OrderData) -> OrderResponse:
        """Modify order on Angel One"""
        return OrderResponse("", "not_implemented", 0, None, "Not implemented")
    
    async def get_positions(self) -> List[Position]:
        """Get positions from Angel One"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.get(f"{self.BASE_URL}/portfolio/secure/positions", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return []
        except Exception as e:
            logger.log_error("Angel One positions fetch failed", {"error": str(e)})
        return []
    
    async def get_account_info(self) -> Account:
        """Get account info from Angel One"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.get(f"{self.BASE_URL}/secure/customer", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return Account(0, 0, 0, 0, 0)
        except Exception as e:
            logger.log_error("Angel One account info fetch failed", {"error": str(e)})
        return Account(0, 0, 0, 0, 0)
    
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get order status from Angel One"""
        return OrderResponse("", "not_implemented", 0, None, "Not implemented")
    
    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical data from Angel One"""
        return []
    
    async def subscribe_to_stream(self, symbols: List[str]) -> None:
        """Subscribe to market data"""
        pass
    
    def disconnect(self) -> None:
        """Disconnect from Angel One"""
        pass

BrokerFactory.register_broker("angel_one", AngelSmartAPI)
