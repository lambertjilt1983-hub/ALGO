import os as _os
print('[DEBUG] strategies.py loaded, _os imported')
from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.auth.service import AuthService
from app.models.schemas import StrategyCreate, StrategyResponse, BacktestRequest, BacktestResponse
from app.models.auth import User
from app.models.trading import Strategy, BacktestResult
from app.core.database import get_db
from app.strategies.base import StrategyFactory
from app.strategies.backtester import Backtester
from app.core.logger import logger
import pandas as pd
from datetime import datetime
from kiteconnect import KiteConnect

router = APIRouter(prefix="/strategies", tags=["strategies"])

# --- Live Signal Endpoint (Zerodha) ---
from fastapi import Depends


@router.get("/live/professional-signal")
async def get_live_professional_signal(
    symbol: str = Query("NSE:NIFTY 50", description="Zerodha symbol, e.g., NSE:NIFTY 50"),
    interval: str = Query("5minute", description="Candle interval, e.g., 5minute"),
    lookback: int = Query(100, description="Number of candles to fetch"),
    current_user: User = Depends(AuthService.get_current_user)
):
    print("[DEBUG] ENTERED /live/professional-signal endpoint")
    print(f"[DEBUG] Request received for user: {getattr(current_user, 'id', None)} username: {getattr(current_user, 'username', None)}")
    """Get live professional strategy signal using Zerodha OHLCV data."""
    # --- Always load Zerodha credentials from DB for current user ---
    from app.core.database import SessionLocal
    from app.models.auth import BrokerCredential
    from app.core.security import encryption_manager
    db = SessionLocal()
    try:
        cred = (
            db.query(BrokerCredential)
            .filter(
                BrokerCredential.user_id == current_user.id,
                BrokerCredential.broker_name.ilike("%zerodha%"),
                BrokerCredential.is_active == True
            )
            .order_by(BrokerCredential.id.desc())
            .first()
        )
        if cred is None:
            print(f"[DEBUG] No Zerodha credentials found for user_id={current_user.id}")
            raise HTTPException(status_code=403, detail=f"No Zerodha credentials found for user_id={current_user.id}")
        raw_api_key = getattr(cred, 'api_key', None)
        raw_access_token = getattr(cred, 'access_token', None)
        print(f"[DEBUG] Raw DB api_key: {raw_api_key}")
        print(f"[DEBUG] Raw DB access_token: {raw_access_token}")
        # Normalize and migrate plaintext/whitespace access tokens
        if isinstance(raw_access_token, str):
            cleaned_access_token = raw_access_token.strip()
            is_encrypted = cleaned_access_token.startswith("gAAAA")
            if cleaned_access_token and (cleaned_access_token != raw_access_token or not is_encrypted):
                cred.access_token = (
                    encryption_manager.encrypt_credentials(cleaned_access_token)
                    if not is_encrypted
                    else cleaned_access_token
                )
                db.add(cred)
                db.commit()
                db.refresh(cred)
                raw_access_token = cred.access_token
        def _dec(val):
            if not val:
                return None
            try:
                decrypted = encryption_manager.decrypt_credentials(val)
            except Exception:
                decrypted = val
            return decrypted.strip() if isinstance(decrypted, str) else decrypted
        api_key = _dec(raw_api_key)
        access_token = _dec(raw_access_token)
        print(f"[DEBUG] Decrypted api_key: {api_key}")
        print(f"[DEBUG] Decrypted access_token: {access_token}")
    finally:
        db.close()
    def _mask(val):
        if not val:
            return 'NONE'
        if len(val) <= 8:
            return val
        return val[:4] + '...' + val[-4:]
    print(f"[ZERODHA DEBUG] Using API_KEY (masked): {_mask(api_key)}")
    print(f"[ZERODHA DEBUG] Using ACCESS_TOKEN (masked): {_mask(access_token)}")
    if not api_key or not access_token:
        print("ERROR: Zerodha API key or access token not found for current user.")
        raise HTTPException(status_code=403, detail="Zerodha API key or access token not found for current user. Please add or refresh your Zerodha credentials.")
    if api_key == '' or access_token == '':
        print(f"ERROR: One of the credentials is an empty string. API_KEY: '{api_key}', ACCESS_TOKEN: '{access_token}'")
        raise HTTPException(status_code=403, detail="Zerodha API key or access token is empty. Please update your credentials.")
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    # --- Set custom timeout and retry logic ---
    import requests
    from requests.adapters import HTTPAdapter, Retry
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    def custom_request(*args, **kwargs):
        kwargs.pop('timeout', None)
        return requests.Session.request(session, *args, timeout=30, **kwargs)
    session.request = custom_request
    kite.reqsession = session

    # --- Disk-based cache for instruments ---
    import json, os, time
    cache_file = "instruments_cache.json"
    cache_max_age = 24 * 3600  # 24 hours
    cache_valid = False
    instruments = None
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if time.time() - mtime < cache_max_age:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    instruments = json.load(f)
                    cache_valid = True
                    print(f"DEBUG: Loaded instruments from disk cache, count={len(instruments)}")
            except Exception as e:
                print(f"ERROR: Failed to load instruments cache: {e}")
    if not cache_valid:
        try:
            print("DEBUG: Fetching instruments from Zerodha API...")
            instruments = kite.instruments()
            # Convert any date/datetime objects to ISO strings for JSON serialization
            def convert_dates(obj):
                if isinstance(obj, dict):
                    return {k: convert_dates(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_dates(i) for i in obj]
                elif hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                else:
                    return obj
            instruments_serializable = convert_dates(instruments)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(instruments_serializable, f)
            print(f"DEBUG: instruments fetched and cached, count={len(instruments)}")
        except Exception as e:
            print(f"ERROR: Failed to fetch instruments: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch instruments: {e}")
    try:
        print(f"DEBUG: symbol={symbol}, interval={interval}, lookback={lookback}")
        # Parse symbol like 'NSE:RELIANCE' or 'BSE:TCS'
        try:
            exch, tradingsymbol = symbol.split(":", 1)
        except Exception:
            exch, tradingsymbol = "NSE", symbol  # fallback
        token = next((i['instrument_token'] for i in instruments if i.get('exchange') == exch and i.get('tradingsymbol') == tradingsymbol), None)
        print(f"DEBUG: instrument token={token} (exchange={exch}, tradingsymbol={tradingsymbol})")
        if not token:
            print(f"ERROR: Instrument not found for symbol {symbol}")
            raise HTTPException(status_code=404, detail=f"Instrument not found for symbol {symbol}")
        from datetime import datetime, timedelta
        to_date = datetime.now()
        from_date = to_date - timedelta(minutes=lookback*5)
        print(f"[ZERODHA DEBUG] Fetching OHLCV for token={token}, symbol={symbol}, interval={interval}, from_date={from_date}, to_date={to_date}")
        ohlcv = kite.historical_data(token, from_date, to_date, interval)
        print(f"DEBUG: OHLCV fetched, count={len(ohlcv) if ohlcv else 0}")
        if not ohlcv:
            print("ERROR: No OHLCV data returned from Zerodha")
            raise HTTPException(status_code=404, detail="No OHLCV data returned from Zerodha")
        df = pd.DataFrame(ohlcv)
        print(f"DEBUG: DataFrame shape={df.shape}")
        df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}, inplace=True)
        strat = StrategyFactory.create_strategy("intraday_professional", {"capital": 100000, "symbol": symbol})
        print("DEBUG: Strategy created")
        signal = strat.generate_signal(df)
        print(f"DEBUG: Signal generated: {signal}")
        
        # Get the enriched DataFrame with indicators from the strategy
        df_with_indicators = strat.data if hasattr(strat, 'data') else df
        print(f"DEBUG: DataFrame columns after signal generation: {df_with_indicators.columns.tolist()}")
        
        # Initialize debug variable
        debug = []
        
        # Show last few rows with indicators
        if 'Debug' in df_with_indicators.columns:
            debug = df_with_indicators[['close', 'Signal', 'Debug']].tail(5).to_dict(orient='records')
            print(f"DEBUG: Last 5 rows with indicators:")
            for i, row in enumerate(debug, 1):
                print(f"  Row {i}: {row}")
        else:
            print("DEBUG: No Debug column found")
            
        # Show latest indicator values
        if len(df_with_indicators) > 0:
            last = df_with_indicators.iloc[-1]
            print(f"DEBUG: Latest indicators - Price: {last['close']:.2f}, "
                  f"EMA9: {last.get('EMA9', 'N/A')}, EMA21: {last.get('EMA21', 'N/A')}, "
                  f"RSI: {last.get('RSI', 'N/A')}, VWAP: {last.get('VWAP', 'N/A')}")
        return {
            "symbol": symbol,
            "signal": signal.action,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "debug": debug
        }
    except HTTPException as e:
        # Re-raise FastAPI HTTPException so correct status is returned
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"ERROR: Exception in professional signal endpoint: {e}")
        print(tb)
        raise HTTPException(status_code=500, detail=f"Internal error: {e}\n{tb}")
## ...existing code for router and endpoints...
