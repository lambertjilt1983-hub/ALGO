import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.brokers.base import BrokerInterface, OrderData, OrderResponse, Position, Account, BrokerFactory
from app.core.logger import logger

class ZerodhaKite(BrokerInterface):
    """Zerodha Kite Connect API integration"""
    
    BASE_URL = "https://api.kite.trade"
    
    async def authenticate(self) -> bool:
        """Authenticate with Zerodha"""
        try:
            async with aiohttp.ClientSession() as session:
                # Zerodha uses OAuth2, this is simplified
                headers = {
                    "X-Kite-Version": "3",
                    "Authorization": f"token {self.api_key}:{self.access_token}"
                }
                async with session.get(f"{self.BASE_URL}/profile", headers=headers) as resp:
                    if resp.status == 200:
                        logger.log_api_call("zerodha", "authenticate", "success")
                        return True
            return False
        except Exception as e:
            logger.log_error("Zerodha auth failed", {"error": str(e)})
            return False
    
    async def place_order(self, order: OrderData) -> OrderResponse:
        """Place order on Zerodha"""
        try:
            payload = {
                "tradingsymbol": order.symbol,
                "exchange": "NSE",
                "order_type": order.order_type.upper(),
                "transaction_type": order.side.upper(),
                "quantity": int(order.quantity),
                "price": order.price or 0,
                "variety": "regular"
            }
            
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"token {self.api_key}:{self.access_token}"}
                async with session.post(
                    f"{self.BASE_URL}/orders/regular",
                    json=payload,
                    headers=headers
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        logger.log_api_call("zerodha", "place_order", "success")
                        return OrderResponse(
                            order_id=data.get("data", {}).get("order_id"),
                            status="pending",
                            filled_quantity=0,
                            average_price=None,
                            message="Order placed successfully"
                        )
            return OrderResponse("", "failed", 0, None, "Order placement failed")
        except Exception as e:
            logger.log_error("Zerodha order placement failed", {"error": str(e)})
            return OrderResponse("", "failed", 0, None, str(e))
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order on Zerodha"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"token {self.api_key}:{self.access_token}"}
                async with session.delete(
                    f"{self.BASE_URL}/orders/regular/{order_id}",
                    headers=headers
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.log_error("Zerodha cancel failed", {"error": str(e)})
            return False
    
    async def modify_order(self, order_id: str, order: OrderData) -> OrderResponse:
        """Modify order on Zerodha"""
        # Implementation depends on Zerodha's API specifics
        return OrderResponse("", "not_implemented", 0, None, "Not implemented")
    
    async def get_positions(self) -> List[Position]:
        """Get all positions from Zerodha"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"token {self.api_key}:{self.access_token}"}
                async with session.get(f"{self.BASE_URL}/portfolio/positions", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        positions = []
                        for pos in data.get("data", {}).get("day", []):
                            positions.append(Position(
                                symbol=pos["tradingsymbol"],
                                quantity=pos["quantity"],
                                average_cost=pos["average_price"],
                                current_price=pos["last_price"],
                                pnl=pos["pnl"],
                                pnl_percentage=(pos["pnl"] / (pos["average_price"] * pos["quantity"]) * 100) if pos["average_price"] > 0 else 0
                            ))
                        return positions
        except Exception as e:
            logger.log_error("Zerodha positions fetch failed", {"error": str(e)})
        return []
    
    async def get_account_info(self) -> Account:
        """Get account info from Zerodha"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"token {self.api_key}:{self.access_token}"}
                async with session.get(f"{self.BASE_URL}/user/margins", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        margin = data.get("data", {}).get("equity", {})
                        return Account(
                            balance=margin.get("cash", 0),
                            available_balance=margin.get("available", 0),
                            used_margin=margin.get("used", 0),
                            free_margin=margin.get("available", 0),
                            net_worth=margin.get("equity", 0)
                        )
        except Exception as e:
            logger.log_error("Zerodha account info fetch failed", {"error": str(e)})
        return Account(0, 0, 0, 0, 0)
    
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get order status from Zerodha"""
        return OrderResponse("", "not_implemented", 0, None, "Not implemented")
    
    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical OHLCV data from Zerodha"""
        return []
    
    async def get_instruments(self) -> List[Dict[str, Any]]:
        """Get list of all tradable instruments from Zerodha"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"token {self.api_key}:{self.access_token}"}
                async with session.get(f"{self.BASE_URL}/instruments", headers=headers) as resp:
                    if resp.status == 200:
                        # Returns CSV data, parse it
                        text = await resp.text()
                        instruments = []
                        for line in text.split('\n')[1:]:  # Skip header
                            if line.strip():
                                parts = line.split(',')
                                if len(parts) >= 12:
                                    instruments.append({
                                        'tradingsymbol': parts[1],
                                        'name': parts[2],
                                        'lot_size': int(parts[11]) if parts[11].isdigit() else 1,
                                        'expiry': parts[9] if len(parts) > 9 else None,
                                        'strike': float(parts[10]) if len(parts) > 10 and parts[10] else 0,
                                        'instrument_type': parts[8] if len(parts) > 8 else None
                                    })
                        logger.log_api_call("zerodha", "get_instruments", "success", {"count": len(instruments)})
                        return instruments
        except Exception as e:
            logger.log_error("Zerodha instruments fetch failed", {"error": str(e)})
        return []
    
    async def get_instrument_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific instrument including lot size"""
        try:
            instruments = await self.get_instruments()
            for instrument in instruments:
                if symbol in instrument.get('tradingsymbol', ''):
                    return instrument
            return None
        except Exception as e:
            logger.log_error("Zerodha instrument details fetch failed", {"error": str(e), "symbol": symbol})
            return None
    
    async def subscribe_to_stream(self, symbols: List[str]) -> None:
        """Subscribe to market data stream"""
        pass
    
    def disconnect(self) -> None:
        """Disconnect from Zerodha"""
        pass

# Register Zerodha broker
BrokerFactory.register_broker("zerodha", ZerodhaKite)
