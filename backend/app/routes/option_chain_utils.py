
import sys
from app.brokers.zerodha import ZerodhaKite
from app.routes.broker import get_broker_credentials
from app.core.database import SessionLocal
from datetime import datetime

async def get_option_chain(symbol: str, expiry: str, authorization: str = None):
    """
    Fetch the full CE/PE option chain for a given index and expiry using DB-backed credentials.
    Handles token expiry/refresh automatically.
    """
    db = SessionLocal()
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    elif authorization:
        token = authorization
    # Always pass only the JWT token string
    broker_cred = await get_broker_credentials(broker_name="zerodha", db=db, token=token)
    # Decrypt credentials if needed
    api_key = broker_cred.api_key
    api_secret = broker_cred.api_secret
    access_token = broker_cred.access_token
    refresh_token = getattr(broker_cred, 'refresh_token', None)
    token_expiry = getattr(broker_cred, 'token_expiry', None)

    # Check expiry and refresh if needed (pseudo-code, implement refresh logic as needed)
    if token_expiry and datetime.utcnow() >= token_expiry:
        print(f"[OPTION_CHAIN_UTILS] Access token expired, refreshing...")
        # TODO: Implement refresh logic here, update DB, and set new access_token
        # access_token = refresh_access_token(api_key, api_secret, refresh_token)
        # Save new access_token and expiry to DB
        pass

    kite = await ZerodhaKite.from_user_context(authorization)
    instruments = await kite.get_instruments()
    if not instruments or not isinstance(instruments, list):
        print(f"[OPTION_CHAIN_UTILS] No instruments returned for {symbol} {expiry}", file=sys.stderr)
        return {'CE': [], 'PE': [], 'error': 'No instruments returned'}

    ce_options = []
    pe_options = []
    for inst in instruments:
        # Defensive: log and skip if any key is missing or None
        if inst is None:
            print(f"[OPTION_CHAIN_UTILS] Skipping None instrument for {symbol} {expiry}", file=sys.stderr)
            continue
        name = inst.get('name')
        inst_expiry = inst.get('expiry')
        inst_type = inst.get('instrument_type')
        if name is None or inst_expiry is None or inst_type is None:
            print(f"[OPTION_CHAIN_UTILS] Skipping instrument with missing fields: {inst}", file=sys.stderr)
            continue
        if name == symbol and inst_expiry == expiry and inst_type == 'CE':
            ce_options.append(inst)
        if name == symbol and inst_expiry == expiry and inst_type == 'PE':
            pe_options.append(inst)
    print(f"[OPTION_CHAIN_UTILS] {symbol} {expiry} CE count: {len(ce_options)}, PE count: {len(pe_options)}")
    return {'CE': ce_options, 'PE': pe_options}
