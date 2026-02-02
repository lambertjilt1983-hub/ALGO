import requests
from typing import List, Dict
import functools
import threading
import time
from kiteconnect import KiteConnect
import os
from app.core.database import SessionLocal
from app.models.auth import BrokerCredential
from app.core.security import encryption_manager

# Example: You would replace this with actual NSE/BSE/3rd party API endpoints
OPTION_CHAIN_URLS = {
    'BANKNIFTY': 'https://api.example.com/banknifty/option-chain',
    'NIFTY': 'https://api.example.com/nifty/option-chain',
    'SENSEX': 'https://api.example.com/sensex/option-chain',
    'FINNIFTY': 'https://api.example.com/finnifty/option-chain',
}

# Zerodha Kite Connect (lazy initialized)
_kite_cache = None
_kite_cache_time = 0
_kite_cache_ttl = 60  # seconds
_kite_lock = threading.Lock()


def _safe_decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        decrypted = encryption_manager.decrypt_credentials(value)
    except Exception:
        decrypted = value
    return decrypted.strip() if isinstance(decrypted, str) else decrypted


def _load_zerodha_credentials() -> tuple[str | None, str | None]:
    api_key = os.getenv("ZERODHA_API_KEY")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN")
    if api_key and access_token:
        return api_key.strip(), access_token.strip()

    db = SessionLocal()
    try:
        cred = (
            db.query(BrokerCredential)
            .filter(BrokerCredential.broker_name.ilike("%zerodha%"), BrokerCredential.is_active == True)
            .order_by(BrokerCredential.updated_at.desc())
            .first()
        )
        if not cred:
            return None, None
        api_key = _safe_decrypt(getattr(cred, "api_key", None))
        access_token = _safe_decrypt(getattr(cred, "access_token", None))
        return api_key, access_token
    finally:
        db.close()


def _build_kite(api_key: str, access_token: str) -> KiteConnect:
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    # Add timeouts + retries to avoid hanging calls
    from requests.adapters import HTTPAdapter, Retry
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    def custom_request(*args, **kwargs):
        kwargs.pop('timeout', None)
        return requests.Session.request(session, *args, timeout=10, **kwargs)

    session.request = custom_request
    kite.reqsession = session
    return kite


def _get_kite() -> KiteConnect | None:
    global _kite_cache, _kite_cache_time
    now = time.time()
    with _kite_lock:
        if _kite_cache is not None and (now - _kite_cache_time) < _kite_cache_ttl:
            return _kite_cache
        api_key, access_token = _load_zerodha_credentials()
        if not api_key or not access_token:
            _kite_cache = None
            return None
        _kite_cache = _build_kite(api_key, access_token)
        _kite_cache_time = now
        return _kite_cache

def fetch_option_chain(index: str) -> Dict:
    url = OPTION_CHAIN_URLS.get(index.upper())
    if not url:
        raise ValueError(f"No option chain URL for {index}")
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

# Helper to get live option chain for Bank Nifty
def fetch_banknifty_option_chain(kite: KiteConnect, instruments: list[dict]):
    # Get all instruments
    # Filter for BANKNIFTY options
    banknifty_options = [i for i in instruments if i["name"] == "BANKNIFTY" and i["segment"] == "NFO-OPT"]
    # Get current price
    quote = kite.quote(["NSE:BANKNIFTY"])
    spot_price = quote["NSE:BANKNIFTY"]["last_price"]
    # Find nearest expiry and strikes
    expiries = sorted(set(i["expiry"] for i in banknifty_options))
    nearest_expiry = expiries[0]
    strikes = sorted(set(i["strike"] for i in banknifty_options if i["expiry"] == nearest_expiry))
    # Pick ATM strike
    atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
    # Get CE and PE symbols
    ce_symbol = next(i["tradingsymbol"] for i in banknifty_options if i["strike"] == atm_strike and i["expiry"] == nearest_expiry and i["instrument_type"] == "CE")
    pe_symbol = next(i["tradingsymbol"] for i in banknifty_options if i["strike"] == atm_strike and i["expiry"] == nearest_expiry and i["instrument_type"] == "PE")
    # Get option prices
    ce_quote = kite.quote([f"NFO:{ce_symbol}"])[f"NFO:{ce_symbol}"]["last_price"]
    pe_quote = kite.quote([f"NFO:{pe_symbol}"])[f"NFO:{pe_symbol}"]["last_price"]
    return {
        "index": "BANKNIFTY",
        "strike": atm_strike,
        "ce_signal": f"CE LTP: {ce_quote}",
        "pe_signal": f"PE LTP: {pe_quote}",
        "sentiment": "LIVE",
        "expiry_zone": nearest_expiry,
        "risk_note": "Live data",
        "entry_price": ce_quote,
        "target": ce_quote + 25,
        "stop_loss": ce_quote - 20,
        "confidence": 85,
        "strategy": "ATM Option",
        "action": "BUY",
        "symbol": ce_symbol,
        "quantity": 15,
        "expiry_date": str(nearest_expiry),
        "potential_profit": 25 * 15,
        "risk": 20 * 15
    }

def fetch_index_option_chain(
    index_name,
    kite: KiteConnect,
    instruments_nfo: list[dict],
    instruments_bfo: list[dict] | None = None,
    instruments_all: list[dict] | None = None,
    bfo_error_reason: str | None = None,
):
    # Map index_name to correct Zerodha symbol for quote
    symbol_map = {
        "BANKNIFTY": "NSE:NIFTY BANK",
        "NIFTY": "NSE:NIFTY 50",
        "SENSEX": "BSE:SENSEX",
        "FINNIFTY": "NSE:NIFTY FIN SERVICE"
    }
    try:
        if index_name == "SENSEX":
            instruments = instruments_bfo or []
            segment = "BFO-OPT"
            name = "SENSEX"
            if not instruments:
                return {"index": index_name, "error": "BFO instruments unavailable for SENSEX."}
        else:
            instruments = instruments_nfo
            segment = "NFO-OPT"
            name = index_name

        options = [i for i in instruments if i["name"] == name and i["segment"] == segment]
        if index_name == "SENSEX" and not options:
            # Fallback: some BFO instruments may not use name="SENSEX"
            options = [
                i for i in instruments
                if i.get("segment") == segment
                and (
                    "SENSEX" in str(i.get("tradingsymbol", ""))
                    or "SENSEX" in str(i.get("name", ""))
                )
            ]
        if index_name == "SENSEX" and not options and instruments_all:
            # Final fallback: scan full instruments list for BFO-OPT SENSEX
            options = [
                i for i in instruments_all
                if i.get("segment") == "BFO-OPT"
                and (
                    "SENSEX" in str(i.get("tradingsymbol", ""))
                    or "SENSEX" in str(i.get("name", ""))
                )
            ]
        if not options:
            if index_name == "SENSEX" and bfo_error_reason:
                return {
                    "index": index_name,
                    "error": "BFO options not доступ: BFO permissions not enabled for this account.",
                    "detail": bfo_error_reason,
                }
            bfo_count = len(instruments_bfo or []) if index_name == "SENSEX" else None
            all_count = len(instruments_all or []) if index_name == "SENSEX" else None
            return {
                "index": index_name,
                "error": "No options available for this index. Ensure BFO options are enabled in Kite.",
                "debug": {
                    "bfo_instruments": bfo_count,
                    "all_instruments": all_count,
                    "segment": segment,
                } if index_name == "SENSEX" else None,
            }
        quote_symbol = symbol_map.get(index_name, f"NSE:{index_name}")
        try:
            quote = kite.quote([quote_symbol])
            spot_price = quote[quote_symbol]["last_price"]
        except Exception as e:
            return {"index": index_name, "error": f"Quote error: {str(e)}"}
        from datetime import datetime, date
        expiries = sorted(set(i["expiry"] for i in options))
        if not expiries:
            return {"index": index_name, "error": "No expiries found for this index."}
        # Filter for expiry dates that are today or in the future
        today = date.today()
        valid_expiries = [e for e in expiries if isinstance(e, date) and e >= today]
        if not valid_expiries:
            return {"index": index_name, "error": "No valid (future) expiries found for this index."}
        nearest_expiry = valid_expiries[0]
        strikes = sorted(set(i["strike"] for i in options if i["expiry"] == nearest_expiry))
        if not strikes:
            return {"index": index_name, "error": "No strikes found for this expiry."}
        atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
        try:
            ce_symbol = next(i["tradingsymbol"] for i in options if i["strike"] == atm_strike and i["expiry"] == nearest_expiry and i["instrument_type"] == "CE")
            pe_symbol = next(i["tradingsymbol"] for i in options if i["strike"] == atm_strike and i["expiry"] == nearest_expiry and i["instrument_type"] == "PE")
        except StopIteration:
            return {"index": index_name, "error": "No CE/PE symbol found for ATM strike."}
        try:
            quote_prefix = "BFO" if segment == "BFO-OPT" else "NFO"
            ce_key = f"{quote_prefix}:{ce_symbol}"
            pe_key = f"{quote_prefix}:{pe_symbol}"
            ce_quote = kite.quote([ce_key])[ce_key]["last_price"]
            pe_quote = kite.quote([pe_key])[pe_key]["last_price"]
        except Exception as e:
            err_text = str(e)
            if index_name == "SENSEX" and "Invalid `api_key` or `access_token`" in err_text:
                return {
                    "index": index_name,
                    "error": "BFO options not доступ: BFO permissions not enabled for this account.",
                    "detail": err_text,
                }
            return {"index": index_name, "error": f"Option quote error: {err_text}"}
        
        # Get lot size from instrument data
        ce_instrument = next((i for i in options if i["tradingsymbol"] == ce_symbol), None)
        lot_size = ce_instrument.get("lot_size", 15) if ce_instrument else 15
        
        # Index-specific lot sizes (fallback if not in instrument data)
        lot_size_map = {
            "BANKNIFTY": 30,
            "NIFTY": 50,
            "FINNIFTY": 40,
            "SENSEX": 10
        }
        if lot_size == 15:  # If we got default, use index-specific
            lot_size = lot_size_map.get(index_name, 15)
        
        return {
            "index": index_name,
            "strike": atm_strike,
            "ce_signal": f"CE LTP: {ce_quote}",
            "pe_signal": f"PE LTP: {pe_quote}",
            "sentiment": "LIVE",
            "expiry_zone": nearest_expiry,
            "risk_note": "Live data",
            "entry_price": ce_quote,
            "target": ce_quote + 25,
            "stop_loss": ce_quote - 20,
            "confidence": 85,
            "strategy": "ATM Option",
            "action": "BUY",
            "symbol": ce_symbol,
            "quantity": lot_size,
            "expiry_date": str(nearest_expiry),
            "potential_profit": 25 * lot_size,
            "risk": 20 * lot_size
        }
    except Exception as e:
        return {"index": index_name, "error": str(e)}

def analyze_option_chain(chain: Dict) -> Dict:
    # This is a stub. You would implement OI, PCR, IV, Max Pain logic here.
    # For demonstration, we return a dummy signal.
    return {
        'strike': 48000,
        'ce_signal': 'Strong OI Build',
        'pe_signal': 'Weak OI Unwind',
        'sentiment': 'Bullish',
        'expiry_zone': 48000,
        'risk_note': 'High IV: Options expensive',
    }


# --- Simple in-memory cache and rate limiter ---
_signals_cache = None
_signals_cache_time = 0
_signals_cache_lock = threading.Lock()
_signals_cache_ttl = 30  # seconds
_signals_rate_limit = 10  # seconds between calls
_signals_last_call = 0

def generate_signals() -> List[Dict]:
    global _signals_cache, _signals_cache_time, _signals_last_call
    now = time.time()
    with _signals_cache_lock:
        # Serve from cache if not expired
        if _signals_cache is not None and (now - _signals_cache_time) < _signals_cache_ttl:
            return _signals_cache
        # Rate limit: if last call was too recent, return error signals
        if (now - _signals_last_call) < _signals_rate_limit:
            return [
                {"index": idx, "error": "Too many requests (rate limited)"}
                for idx in ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
            ]
        _signals_last_call = now
        # Actual signal generation
        kite = _get_kite()
        if not kite:
            return [
                {"index": idx, "error": "Zerodha credentials missing or invalid"}
                for idx in ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
            ]

        try:
            instruments_nfo = kite.instruments("NFO")
        except Exception as e:
            return [
                {"index": idx, "error": f"Failed to load instruments: {str(e)}"}
                for idx in ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
            ]

        bfo_error_reason = None
        try:
            instruments_bfo = kite.instruments("BFO")
        except Exception as e:
            bfo_error_reason = str(e)
            instruments_bfo = []

        instruments_all = None
        if not instruments_bfo:
            try:
                instruments_all = kite.instruments()
            except Exception:
                instruments_all = None

        indices = ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
        signals = []
        for idx in indices:
            signals.append(fetch_index_option_chain(
                idx,
                kite,
                instruments_nfo,
                instruments_bfo,
                instruments_all,
                bfo_error_reason,
            ))
        _signals_cache = signals
        _signals_cache_time = now
        return signals

if __name__ == "__main__":
    from pprint import pprint
    pprint(generate_signals())
