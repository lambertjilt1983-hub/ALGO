import aiohttp
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.brokers.base import BrokerInterface, OrderData, OrderResponse, Position, Account, BrokerFactory
from app.core.logger import logger

class GrowwAPI(BrokerInterface):
    """Groww Broker API integration"""
    
    BASE_URL = "https://api.groww.in"

    def __init__(self, api_key: str, api_secret: str, access_token: Optional[str] = None):
        super().__init__(api_key, api_secret, access_token)
        self._last_error: Optional[str] = None
    
    async def authenticate(self) -> bool:
        """Authenticate with Groww"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.get(f"{self.BASE_URL}/v1/user/profile", headers=headers) as resp:
                    if resp.status == 200:
                        logger.log_api_call("groww", "authenticate", "success")
                        self._last_error = None
                        return True
                    body = await resp.text()
                    self._last_error = f"HTTP {resp.status}: {body}"
            return False
        except Exception as e:
            logger.log_error("Groww auth failed", {"error": str(e)})
            self._last_error = str(e)
            return False
    
    async def place_order(self, order: OrderData) -> OrderResponse:
        """Place order on Groww"""
        try:
            payload = {
                "symbol": order.symbol,
                "action": order.side.upper(),
                "orderType": order.order_type.upper(),
                "quantity": int(order.quantity),
                "price": order.price or 0,
                "exchange": "NSE"
            }
            
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.post(
                    f"{self.BASE_URL}/v1/orders/place",
                    json=payload,
                    headers=headers
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        logger.log_api_call("groww", "place_order", "success")
                        return OrderResponse(
                            order_id=data.get("data", {}).get("orderId"),
                            status="pending",
                            filled_quantity=0,
                            average_price=None,
                            message="Order placed successfully"
                        )
            return OrderResponse("", "failed", 0, None, "Order placement failed")
        except Exception as e:
            logger.log_error("Groww order placement failed", {"error": str(e)})
            return OrderResponse("", "failed", 0, None, str(e))
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order on Groww"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.delete(
                    f"{self.BASE_URL}/v1/orders/{order_id}",
                    headers=headers
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.log_error("Groww cancel failed", {"error": str(e)})
            return False
    
    async def modify_order(self, order_id: str, order: OrderData) -> OrderResponse:
        """Modify order on Groww"""
        return OrderResponse("", "not_implemented", 0, None, "Not implemented")
    
    async def get_positions(self) -> List[Position]:
        """Get positions from Groww"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.get(f"{self.BASE_URL}/v1/portfolio/positions", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return []
        except Exception as e:
            logger.log_error("Groww positions fetch failed", {"error": str(e)})
        return []
    
    async def get_account_info(self) -> Account:
        """Get account info from Groww"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                async with session.get(f"{self.BASE_URL}/v1/user/margin", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        payload = data.get("data", data) if isinstance(data, dict) else {}

                        available = payload.get("available", payload.get("available_balance", payload.get("availableMargin", 0)))
                        used = payload.get("used", payload.get("used_margin", payload.get("utilised", payload.get("utilized", 0))))
                        free = payload.get("free", payload.get("free_margin", payload.get("freeMargin", 0)))
                        net = payload.get("net", payload.get("total", payload.get("total_balance", 0)))
                        balance = payload.get("balance", payload.get("net", net))

                        return Account(
                            balance=float(balance or 0),
                            available_balance=float(available or 0),
                            used_margin=float(used or 0),
                            free_margin=float(free or 0),
                            net_worth=float(net or 0)
                        )
                    body = await resp.text()
                    self._last_error = f"HTTP {resp.status}: {body}"
        except Exception as e:
            logger.log_error("Groww account info fetch failed", {"error": str(e)})
            self._last_error = str(e)
        return Account(0, 0, 0, 0, 0)
    
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get order status from Groww"""
        return OrderResponse("", "not_implemented", 0, None, "Not implemented")
    
    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical data from Groww"""
        return []
    
    async def subscribe_to_stream(self, symbols: List[str]) -> None:
        """Subscribe to market data"""
        pass
    
    def disconnect(self) -> None:
        """Disconnect from Groww"""
        pass

BrokerFactory.register_broker("groww", GrowwAPI)
