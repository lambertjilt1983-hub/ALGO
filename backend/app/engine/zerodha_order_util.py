# Zerodha order placement utility for backend integration
from kiteconnect import KiteConnect
from app.core.database import SessionLocal
from app.models.auth import BrokerCredential
from app.core.security import encryption_manager


def _load_zerodha_credentials():
    """Load Zerodha credentials from database"""
    db = SessionLocal()
    try:
        cred = (
            db.query(BrokerCredential)
            .filter(
                BrokerCredential.broker_name.ilike("%zerodha%"),
                BrokerCredential.is_active == True
            )
            .order_by(BrokerCredential.updated_at.desc())
            .first()
        )
        if not cred:
            return None, None
        
        def _safe_decrypt(val):
            if not val:
                return None
            try:
                decrypted = encryption_manager.decrypt_credentials(val)
            except Exception:
                decrypted = val
            return decrypted.strip() if isinstance(decrypted, str) else decrypted
        
        api_key = _safe_decrypt(getattr(cred, 'api_key', None))
        access_token = _safe_decrypt(getattr(cred, 'access_token', None))
        return api_key, access_token
    finally:
        db.close()


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
    # Load credentials from database
    api_key, access_token = _load_zerodha_credentials()
    
    if not api_key or not access_token:
        return {"success": False, "error": "Zerodha credentials not found in database. Please configure broker credentials."}
    
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    try:
        # Support for stop loss and target (squareoff)
        import inspect
        frame = inspect.currentframe().f_back
        stoploss = getattr(frame, 'f_locals', lambda:{{}})().get('stoploss')
        squareoff = getattr(frame, 'f_locals', lambda:{{}})().get('target')

        if stoploss is not None or squareoff is not None:
            # Use Bracket Order (BO)
            order_id = kite.place_order(
                variety=kite.VARIETY_BO,
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=kite.TRANSACTION_TYPE_BUY if side.upper() == "BUY" else kite.TRANSACTION_TYPE_SELL,
                quantity=quantity,
                order_type=order_type,
                product=product,
                stoploss=stoploss if stoploss is not None else 0,
                squareoff=squareoff if squareoff is not None else 0
            )
        else:
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
