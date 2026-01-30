import requests
from typing import List, Dict
from kiteconnect import KiteConnect
import os

# Example: You would replace this with actual NSE/BSE/3rd party API endpoints
OPTION_CHAIN_URLS = {
    'BANKNIFTY': 'https://api.example.com/banknifty/option-chain',
    'NIFTY': 'https://api.example.com/nifty/option-chain',
    'SENSEX': 'https://api.example.com/sensex/option-chain',
    'FINNIFTY': 'https://api.example.com/finnifty/option-chain',
}

# Zerodha Kite Connect
KITE_API_KEY = os.getenv("ZERODHA_API_KEY", "your_api_key")
KITE_ACCESS_TOKEN = os.getenv("ZERODHA_ACCESS_TOKEN", "your_access_token")
kite = KiteConnect(api_key=KITE_API_KEY)
kite.set_access_token(KITE_ACCESS_TOKEN)

def fetch_option_chain(index: str) -> Dict:
    url = OPTION_CHAIN_URLS.get(index.upper())
    if not url:
        raise ValueError(f"No option chain URL for {index}")
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

# Helper to get live option chain for Bank Nifty
def fetch_banknifty_option_chain():
    # Get all instruments
    instruments = kite.instruments("NFO")
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

def fetch_index_option_chain(index_name):
    # Map index_name to correct Zerodha symbol for quote
    symbol_map = {
        "BANKNIFTY": "NSE:NIFTY BANK",
        "NIFTY": "NSE:NIFTY 50",
        "SENSEX": "BSE:SENSEX",
        "FINNIFTY": "NSE:FINNIFTY"
    }
    try:
        # Add FINNIFTY symbol mapping for Zerodha
        symbol_map = {
            "BANKNIFTY": "NSE:NIFTY BANK",
            "NIFTY": "NSE:NIFTY 50",
            "SENSEX": "BSE:SENSEX",
            "FINNIFTY": "NSE:FINNIFTY"
        }
        instruments = kite.instruments("NFO")
        options = [i for i in instruments if i["name"] == index_name and i["segment"] == "NFO-OPT"]
        if not options:
            return {"index": index_name, "error": "No options available for this index."}
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
            ce_quote = kite.quote([f"NFO:{ce_symbol}"])[f"NFO:{ce_symbol}"]["last_price"]
            pe_quote = kite.quote([f"NFO:{pe_symbol}"])[f"NFO:{pe_symbol}"]["last_price"]
        except Exception as e:
            return {"index": index_name, "error": f"Option quote error: {str(e)}"}
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
            "quantity": 15,
            "expiry_date": str(nearest_expiry),
            "potential_profit": 25 * 15,
            "risk": 20 * 15
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

def generate_signals() -> List[Dict]:
    # Dynamically discover all available index names with options
    try:
        kite_indices = set()
        instruments = kite.instruments("NFO")
        for i in instruments:
            if i.get("segment") == "NFO-OPT" and i.get("name"):
                kite_indices.add(i["name"])
        indices = sorted(kite_indices)
    except Exception as e:
        indices = ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
    signals = []
    for idx in indices:
        signals.append(fetch_index_option_chain(idx))
    return signals

if __name__ == "__main__":
    from pprint import pprint
    pprint(generate_signals())
