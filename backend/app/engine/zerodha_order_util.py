# Zerodha order placement utility for backend integration
from kiteconnect import KiteConnect, KiteTicker
import os
from app.brokers.zerodha import get_zerodha_access_token

# Load your API key/secret and access token from environment or config
KITE_API_KEY = os.getenv("ZERODHA_API_KEY", "your_api_key")
KITE_API_SECRET = os.getenv("ZERODHA_API_SECRET", "your_api_secret")
KITE_ACCESS_TOKEN = get_zerodha_access_token()  # Fetch from DB/config

kite = KiteConnect(api_key=KITE_API_KEY)
kite.set_access_token(KITE_ACCESS_TOKEN)

print(f"[ZERODHA DEBUG] API_KEY: {KITE_API_KEY}")
print(f"[ZERODHA DEBUG] ACCESS_TOKEN: {KITE_ACCESS_TOKEN}")

def place_zerodha_order(symbol, quantity, side, order_type="MARKET", product="MIS", exchange="NSE"):
    """
    Place a real order on Zerodha using Kite Connect.
    symbol: e.g. 'BANKNIFTY24FEB48000CE'
    quantity: int
    side: 'BUY' or 'SELL'
    order_type: 'MARKET' or 'LIMIT'
    product: 'MIS' (intraday) or 'NRML' (overnight)
    exchange: 'NSE' or 'NFO' (for options)
    """
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=exchange,
            tradingsymbol=symbol,
            transaction_type=kite.TRANSACTION_TYPE_BUY if side.upper() == "BUY" else kite.TRANSACTION_TYPE_SELL,
            quantity=quantity,
            order_type=order_type,
            product=product
        )
        return {"success": True, "order_id": order_id}
    except Exception as e:
        return {"success": False, "error": str(e)}
