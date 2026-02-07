import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.brokers.base import BrokerInterface, OrderData, OrderResponse, Position, Account, BrokerFactory

import os
from app.core.logger import logger
def get_zerodha_access_token():
    """
    Fetch Zerodha access token from environment variable or return a placeholder.
    Update this logic as per your actual token management.
    """
    return os.getenv("ZERODHA_ACCESS_TOKEN")


from app.routes.broker import get_broker_credentials
from app.core.database import SessionLocal
from datetime import datetime

class ZerodhaKite(BrokerInterface):
    """Zerodha Kite Connect API integration (always loads credentials from DB)"""
    BASE_URL = "https://api.kite.trade"

    @classmethod
    async def from_user_context(cls, authorization: str = None):
        """Factory: Load credentials from DB, handle expiry/refresh."""
        from app.core.token_manager import TokenManager
        db = SessionLocal()
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ", 1)[1]
        elif authorization:
            token = authorization
        # Always pass only the JWT token string
        broker_cred = await get_broker_credentials(broker_name="zerodha", db=db, token=token)
        api_key = broker_cred.api_key
        api_secret = broker_cred.api_secret
        access_token = broker_cred.access_token
        refresh_token = getattr(broker_cred, 'refresh_token', None)
        token_expiry = getattr(broker_cred, 'token_expiry', None)
        broker_id = getattr(broker_cred, 'id', None)
        # Check expiry and refresh if needed
        if token_expiry and datetime.utcnow() >= token_expiry and broker_id:
            print(f"[ZERODHA] Access token expired, refreshing...")
            refresh_result = TokenManager.refresh_zerodha_token(broker_id, db)
            if refresh_result.get("status") == "success":
                # Reload credential from DB to get new access_token
                broker_cred = db.query(type(broker_cred)).filter_by(id=broker_id).first()
                access_token = broker_cred.access_token
                print(f"[ZERODHA] Token refreshed for broker_id={broker_id}")
            else:
                print(f"[ZERODHA] Token refresh failed: {refresh_result}")
        return cls(api_key, api_secret, access_token)

    def __init__(self, api_key: str, api_secret: str, access_token: Optional[str] = None):
        super().__init__(api_key, api_secret, access_token)
    
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
                        import sys
                        if text is None:
                            print(f"[ZERODHA] instruments text is None!", file=sys.stderr)
                            return []
                        if not isinstance(text, str):
                            print(f"[ZERODHA] instruments text is not a string: {text} (type={type(text)})", file=sys.stderr)
                            return []
                        print(f"[ZERODHA] instruments text type: {type(text)} length: {len(text)}", file=sys.stderr)
                        def safe_float(val):
                            try:
                                return float(val)
                            except Exception:
                                return 0
                        def safe_int(val):
                            try:
                                return int(val)
                            except Exception:
                                return 1
                        for idx, line in enumerate(text.split('\n')[1:], 2):  # Skip header, line numbers start at 2
                            if line is None:
                                print(f"[ZERODHA] Skipping None line at {idx}", file=sys.stderr)
                                continue
                            if not isinstance(line, str):
                                print(f"[ZERODHA] Skipping non-string line at {idx}: {line} (type={type(line)})", file=sys.stderr)
                                continue
                            if not line.strip():
                                continue
                            print(f"[ZERODHA] line before split: {line[:80]} (type={type(line)})", file=sys.stderr)
                            parts = line.split(',')
                            if len(parts) < 12:
                                print(f"[ZERODHA] Skipping malformed instrument line {idx}: {line}", file=sys.stderr)
                                continue
                            try:
                                tradingsymbol = parts[1]
                                name = parts[2]
                                lot_size = safe_int(parts[11]) if len(parts) > 11 else 1
                                expiry = parts[9] if len(parts) > 9 else None
                                strike = safe_float(parts[10]) if len(parts) > 10 else 0
                                instrument_type = parts[8] if len(parts) > 8 else None
                                # Defensive: skip if any required field is None
                                if not tradingsymbol or not name or not instrument_type:
                                    print(f"[ZERODHA] Skipping instrument with missing fields at line {idx}: {parts}", file=sys.stderr)
                                    continue
                                instruments.append({
                                    'tradingsymbol': tradingsymbol,
                                    'name': name,
                                    'lot_size': lot_size,
                                    'expiry': expiry,
                                    'strike': strike,
                                    'instrument_type': instrument_type
                                })
                            except Exception as parse_e:
                                print(f"[ZERODHA] Exception parsing instrument line {idx}: {line} | Error: {parse_e}", file=sys.stderr)
                                continue
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
