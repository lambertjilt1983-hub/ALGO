from typing import Any, Dict
from .broker_interface import BrokerInterface

class ZerodhaBroker(BrokerInterface):
    """Concrete implementation of BrokerInterface for Zerodha."""
    def __init__(self):
        self.api = None
        self.connected = False
        self.session = None

    def connect(self, credentials: Dict[str, Any]) -> bool:
        try:
            from kiteconnect import KiteConnect
            api_key = credentials.get('api_key')
            access_token = credentials.get('access_token')
            if not api_key or not access_token:
                return False
            self.api = KiteConnect(api_key=api_key)
            self.api.set_access_token(access_token)
            self.connected = True
            return True
        except Exception as e:
            print(f"[ZerodhaBroker] Connection failed: {e}")
            self.connected = False
            return False

    def place_order(self, order_details: Dict[str, Any]) -> Dict[str, Any]:
        if not self.connected or not self.api:
            return {"success": False, "error": "Not connected"}
        try:
            # Example: order_details should contain all required KiteConnect params
            order_id = self.api.place_order(
                variety=order_details.get('variety', 'regular'),
                exchange=order_details['exchange'],
                tradingsymbol=order_details['tradingsymbol'],
                transaction_type=order_details['transaction_type'],
                quantity=order_details['quantity'],
                order_type=order_details['order_type'],
                product=order_details['product'],
                price=order_details.get('price'),
                trigger_price=order_details.get('trigger_price'),
                validity=order_details.get('validity', 'DAY')
            )
            return {"success": True, "order_id": order_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_balance(self) -> Dict[str, Any]:
        if not self.connected or not self.api:
            return {"success": False, "error": "Not connected"}
        try:
            profile = self.api.profile()
            funds = self.api.margins('equity')
            return {"success": True, "profile": profile, "funds": funds}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disconnect(self) -> None:
        self.api = None
        self.connected = False
        self.session = None
