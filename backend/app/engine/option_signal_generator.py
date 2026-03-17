import requests
from typing import List, Dict
import functools
import threading
import time
import re
import asyncio
from kiteconnect import KiteConnect
import os
from app.core.database import SessionLocal
from app.models.auth import BrokerCredential
from app.core.security import encryption_manager
from app.strategies.market_intelligence import news_analyzer, trend_analyzer
from app.engine.technical_indicators import calculate_comprehensive_signals

# Example: You would replace this with actual NSE/BSE/3rd party API endpoints
OPTION_CHAIN_URLS = {
    'BANKNIFTY': 'https://api.example.com/banknifty/option-chain',
    'NIFTY': 'https://api.example.com/nifty/option-chain',
    'SENSEX': 'https://api.example.com/sensex/option-chain',
    'FINNIFTY': 'https://api.example.com/finnifty/option-chain',
}

# NIFTY 50 symbols (cash segment). Used for equity option signals when enabled.
NIFTY_50_SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL",
    "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK",
    "INFY", "ITC", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBIN", "SBILIFE", "SHRIRAMFIN",
    "SUNPHARMA", "TATAMOTORS", "TATASTEEL", "TCS", "TECHM",
    "TITAN", "ULTRACEMCO", "WIPRO"
]

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


def _load_zerodha_credentials(user_id: int | None = None) -> tuple[str | None, str | None]:
    api_key = os.getenv("ZERODHA_API_KEY")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN")
    if api_key and access_token:
        return api_key.strip(), access_token.strip()

    db = SessionLocal()
    try:
        query = db.query(BrokerCredential).filter(
            BrokerCredential.broker_name.ilike("%zerodha%"),
            BrokerCredential.is_active == True,
        )
        if user_id is not None:
            query = query.filter(BrokerCredential.user_id == user_id)
        cred = query.order_by(BrokerCredential.updated_at.desc()).first()
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


def _validate_signal_quality(
    signal: dict,
    kite: KiteConnect,
    quote_data: dict,
    enable_technical: bool = True,
) -> dict:
    """
    Enhanced signal quality validation with technical indicators:
    - Volume: High/rising vs Low/stagnant
    - Trend Context: At support/reversal vs Random
    - Candle Close: Near day's high vs Near day's low
    - Technical Indicators: RSI, MACD, Bollinger Bands
    - Market Sentiment: Broad market bullish vs weak
    """
    quality_score = 0
    quality_factors = []
    
    try:
        # Get OHLCV data for volume and candle analysis
        ohlc = quote_data.get("ohlc", {})
        high = ohlc.get("high", 0)
        low = ohlc.get("low", 0)
        close = ohlc.get("close", signal.get("entry_price", 0))
        open_price = ohlc.get("open", close)
        volume = quote_data.get("volume", 0)
        avg_volume = quote_data.get("average_price", 0)  # Approximate
        
        # Try to get historical data for technical indicators.
        # For wide market scans, callers can disable this expensive pass.
        if enable_technical:
            try:
                # Get underlying index symbol
                index_symbol = signal.get("index", "NIFTY")
                symbol_map = {
                    "BANKNIFTY": "NSE:NIFTY BANK",
                    "NIFTY": "NSE:NIFTY 50",
                    "SENSEX": "BSE:SENSEX",
                    "FINNIFTY": "NSE:NIFTY FIN SERVICE",
                    # NIFTY 50 Stocks - map to their NSE symbols
                    "ADANIENT": "NSE:ADANIENT",
                    "ADANIPORTS": "NSE:ADANIPORTS",
                    "APOLLOHOSP": "NSE:APOLLOHOSP",
                    "ASIANPAINT": "NSE:ASIANPAINT",
                    "AXISBANK": "NSE:AXISBANK",
                    "BAJAJ-AUTO": "NSE:BAJAJAUTOLD",
                    "BAJFINANCE": "NSE:BAJFINANCE",
                    "BAJAJFINSV": "NSE:BAJAJFINSV",
                    "BEL": "NSE:BEL",
                    "BPCL": "NSE:BPCL",
                    "BHARTIARTL": "NSE:BHARTIARTL",
                    "BRITANNIA": "NSE:BRITANNIA",
                    "CIPLA": "NSE:CIPLA",
                    "COALINDIA": "NSE:COALINDIA",
                    "DRREDDY": "NSE:DRREDDY",
                    "EICHERMOT": "NSE:EICHERMOT",
                    "GRASIM": "NSE:GRASIM",
                    "HCLTECH": "NSE:HCLTECH",
                    "HDFCBANK": "NSE:HDFCBANK",
                    "HDFCLIFE": "NSE:HDFCLIFE",
                    "HEROMOTOCO": "NSE:HEROMOTOCO",
                    "HINDALCO": "NSE:HINDALCO",
                    "HINDUNILVR": "NSE:HINDUNILVR",
                    "ICICIBANK": "NSE:ICICIBANK",
                    "INDUSINDBK": "NSE:INDUSINDBK",
                    "INFY": "NSE:INFY",
                    "ITC": "NSE:ITC",
                    "JSWSTEEL": "NSE:JSWSTEEL",
                    "KOTAKBANK": "NSE:KOTAKBANK",
                    "LT": "NSE:LT",
                    "M&M": "NSE:MM",
                    "MARUTI": "NSE:MARUTI",
                    "NESTLEIND": "NSE:NESTLEIND",
                    "NTPC": "NSE:NTPC",
                    "ONGC": "NSE:ONGC",
                    "POWERGRID": "NSE:POWERGRID",
                    "RELIANCE": "NSE:RELIANCE",
                    "SBIN": "NSE:SBIN",
                    "SBILIFE": "NSE:SBILIFE",
                    "SHRIRAMFIN": "NSE:SHRIRAMFIN",
                    "SUNPHARMA": "NSE:SUNPHARMA",
                    "TATAMOTORS": "NSE:TATAMOTORS",
                    "TATASTEEL": "NSE:TATASTEEL",
                    "TCS": "NSE:TCS",
                    "TECHM": "NSE:TECHM",
                    "TITAN": "NSE:TITAN",
                    "ULTRACEMCO": "NSE:ULTRACEMCO",
                    "WIPRO": "NSE:WIPRO",
                }
                underlying_symbol = symbol_map.get(index_symbol, "NSE:NIFTY 50")

                # Get historical data (last 100 candles for indicators)
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)

                historical = kite.historical_data(
                    instrument_token=kite.ltp(underlying_symbol)[underlying_symbol]["instrument_token"],
                    from_date=start_date,
                    to_date=end_date,
                    interval="5minute"
                )

                if historical and len(historical) > 20:
                    prices = [candle["close"] for candle in historical]
                    highs = [candle["high"] for candle in historical]
                    lows = [candle["low"] for candle in historical]
                    volumes = [candle["volume"] for candle in historical]

                    # Calculate comprehensive technical indicators
                    tech_analysis = calculate_comprehensive_signals(prices, highs, lows, volumes)

                    # Store technical indicators in signal
                    signal["technical_indicators"] = {
                        "rsi": tech_analysis.get("rsi", 50),
                        "macd": tech_analysis.get("macd", {}),
                        "bollinger": tech_analysis.get("bollinger_bands", {}),
                        "volatility": tech_analysis.get("volatility", 0),
                        "recommendation": tech_analysis.get("recommendation", "HOLD")
                    }

                    # Enhanced scoring with technical indicators
                    # Factor 1: RSI (0-20 points)
                    rsi = tech_analysis.get("rsi", 50)
                    if 30 <= rsi <= 70:
                        quality_score += 20
                        quality_factors.append(f"✓ RSI healthy ({rsi:.1f})")
                    elif rsi < 30:
                        quality_score += 15
                        quality_factors.append(f"~ RSI oversold ({rsi:.1f})")
                    elif rsi > 70:
                        quality_factors.append(f"⚠️ RSI overbought ({rsi:.1f})")

                    # Factor 2: MACD (0-20 points)
                    macd = tech_analysis.get("macd", {})
                    if macd.get("crossover") == "bullish":
                        quality_score += 20
                        quality_factors.append("✓ MACD bullish crossover")
                    elif macd.get("histogram", 0) > 0:
                        quality_score += 10
                        quality_factors.append("~ MACD positive")

                    # Factor 3: Bollinger Bands (0-20 points)
                    bb = tech_analysis.get("bollinger_bands", {})
                    bb_position = bb.get("position", 0.5)
                    if bb_position < 0.3:
                        quality_score += 20
                        quality_factors.append("✓ At lower BB (reversal)")
                    elif 0.4 <= bb_position <= 0.6:
                        quality_score += 10
                        quality_factors.append("~ Mid-range BB")

                    # Factor 4: Overall Technical Recommendation (0-20 points)
                    recommendation = tech_analysis.get("recommendation", "HOLD")
                    if recommendation in ["STRONG BUY", "BUY"]:
                        quality_score += 20
                        quality_factors.append(f"✓ Tech signal: {recommendation}")
                    elif recommendation == "HOLD":
                        quality_score += 10
                        quality_factors.append(f"~ Tech signal: {recommendation}")

            except Exception:
                # Fallback to basic analysis if technical indicators fail
                pass
        
        # Basic factors (when technical indicators unavailable)
        # Factor 1: Volume Analysis (0-25 points)
        if volume > avg_volume * 1.5:
            quality_score += 10
            quality_factors.append("✓ High volume")
        elif volume > avg_volume * 1.2:
            quality_score += 5
            quality_factors.append("~ Rising volume")
        
        # Factor 2: Candle Close Position (0-25 points)
        if high > low:
            close_position = (close - low) / (high - low)
            if close_position > 0.7:  # Close near high (bullish)
                quality_score += 10
                quality_factors.append("✓ Close near high")
            elif close_position > 0.5:
                quality_score += 5
                quality_factors.append("~ Close above mid")
        
        # Factor 3: Trend Context (0-25 points)
        change_pct = quote_data.get("net_change", 0)
        if abs(change_pct) > 1:  # Strong trend
            quality_score += 10
            quality_factors.append("✓ Strong trend")
        elif abs(change_pct) > 0.5:
            quality_score += 5
            quality_factors.append("~ Moderate trend")

        # Factor 4: Risk/Reward ratio (0-20 points)
        entry_val = float(signal.get("entry_price", 0) or 0)
        target_val = float(signal.get("target", 0) or 0)
        sl_val = float(signal.get("stop_loss", 0) or 0)
        if entry_val > 0 and target_val > 0 and sl_val > 0:
            profit = abs(target_val - entry_val)
            risk = abs(entry_val - sl_val)
            rr = profit / risk if risk > 0 else 0
            if rr >= 1.5:
                quality_score += 20
                quality_factors.append(f"✓ Excellent RR ({rr:.2f}:1)")
            elif rr >= 1.2:
                quality_score += 15
                quality_factors.append(f"✓ Good RR ({rr:.2f}:1)")
            elif rr >= 1.0:
                quality_score += 8
                quality_factors.append(f"~ Acceptable RR ({rr:.2f}:1)")

        # Factor 5: Confirmation score bonus (0-20 points)
        conf = float(signal.get("confirmation_score", 0) or signal.get("confidence", 0))
        if conf >= 80:
            quality_score += 20
            quality_factors.append(f"✓ High confirmation ({conf:.1f}%)")
        elif conf >= 65:
            quality_score += 12
            quality_factors.append(f"~ Good confirmation ({conf:.1f}%)")
        elif conf >= 55:
            quality_score += 6
            quality_factors.append(f"~ Moderate confirmation ({conf:.1f}%)")

        # Factor 6: Trend alignment bonus (0-10 points)
        if signal.get("trend_aligned"):
            quality_score += 10
            quality_factors.append("✓ Trend aligned")

        # Factor 7: Structural spread bonus — reward signals with meaningful targets (0-15 points)
        if entry_val > 0 and target_val > entry_val:
            spread_pct = (target_val - entry_val) / entry_val * 100
            if spread_pct >= 7:
                quality_score += 15
                quality_factors.append(f"✓ Good target spread ({spread_pct:.1f}%)")
            elif spread_pct >= 4:
                quality_score += 8
                quality_factors.append(f"~ Moderate target spread ({spread_pct:.1f}%)")

        # Update signal with quality assessment
        signal["quality_score"] = min(100, quality_score)  # Cap at 100
        signal["quality_factors"] = quality_factors
        signal["is_high_quality"] = quality_score >= 70  # Raised from 60 to 70 for stricter quality
        
        # Adjust confidence based on quality - be more conservative
        if quality_score >= 85:
            signal["confidence"] = min(95, signal.get("confidence", 75) + 8)
        elif quality_score >= 70:
            signal["confidence"] = signal.get("confidence", 75)
        elif quality_score >= 55:
            signal["confidence"] = max(60, signal.get("confidence", 75) - 10)
        else:
            signal["confidence"] = max(50, signal.get("confidence", 75) - 20)
            signal["is_high_quality"] = False  # Mark as low quality if score < 55
            
    except Exception as e:
        signal["quality_score"] = 0
        signal["quality_factors"] = [f"Error: {str(e)}"]
        signal["is_high_quality"] = False
    
    return signal


def _get_kite(user_id: int | None = None) -> KiteConnect | None:
    global _kite_cache, _kite_cache_time
    now = time.time()
    with _kite_lock:
        if _kite_cache is not None and (now - _kite_cache_time) < _kite_cache_ttl:
            return _kite_cache
        api_key, access_token = _load_zerodha_credentials(user_id=user_id)
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
        "stop_loss": _safe_buy_stop(ce_quote, ce_quote - 20),
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
    enable_technical: bool = True,
):
    # Map index/stock name to correct Zerodha symbol for quote
    # Includes both indices and NIFTY 50 stocks
    symbol_map = {
        # Indices
        "BANKNIFTY": "NSE:NIFTY BANK",
        "NIFTY": "NSE:NIFTY 50",
        "SENSEX": "BSE:SENSEX",
        "FINNIFTY": "NSE:NIFTY FIN SERVICE",
        # NIFTY 50 Stocks (for option chain support)
        "ADANIENT": "NSE:ADANIENT",
        "ADANIPORTS": "NSE:ADANIPORTS",
        "APOLLOHOSP": "NSE:APOLLOHOSP",
        "ASIANPAINT": "NSE:ASIANPAINT",
        "AXISBANK": "NSE:AXISBANK",
        "BAJAJ-AUTO": "NSE:BAJAJAUTOLD",
        "BAJFINANCE": "NSE:BAJFINANCE",
        "BAJAJFINSV": "NSE:BAJAJFINSV",
        "BEL": "NSE:BEL",
        "BPCL": "NSE:BPCL",
        "BHARTIARTL": "NSE:BHARTIARTL",
        "BRITANNIA": "NSE:BRITANNIA",
        "CIPLA": "NSE:CIPLA",
        "COALINDIA": "NSE:COALINDIA",
        "DRREDDY": "NSE:DRREDDY",
        "EICHERMOT": "NSE:EICHERMOT",
        "GRASIM": "NSE:GRASIM",
        "HCLTECH": "NSE:HCLTECH",
        "HDFCBANK": "NSE:HDFCBANK",
        "HDFCLIFE": "NSE:HDFCLIFE",
        "HEROMOTOCO": "NSE:HEROMOTOCO",
        "HINDALCO": "NSE:HINDALCO",
        "HINDUNILVR": "NSE:HINDUNILVR",
        "ICICIBANK": "NSE:ICICIBANK",
        "INDUSINDBK": "NSE:INDUSINDBK",
        "INFY": "NSE:INFY",
        "ITC": "NSE:ITC",
        "JSWSTEEL": "NSE:JSWSTEEL",
        "KOTAKBANK": "NSE:KOTAKBANK",
        "LT": "NSE:LT",
        "M&M": "NSE:MM",
        "MARUTI": "NSE:MARUTI",
        "NESTLEIND": "NSE:NESTLEIND",
        "NTPC": "NSE:NTPC",
        "ONGC": "NSE:ONGC",
        "POWERGRID": "NSE:POWERGRID",
        "RELIANCE": "NSE:RELIANCE",
        "SBIN": "NSE:SBIN",
        "SBILIFE": "NSE:SBILIFE",
        "SHRIRAMFIN": "NSE:SHRIRAMFIN",
        "SUNPHARMA": "NSE:SUNPHARMA",
        "TATAMOTORS": "NSE:TATAMOTORS",
        "TATASTEEL": "NSE:TATASTEEL",
        "TCS": "NSE:TCS",
        "TECHM": "NSE:TECHM",
        "TITAN": "NSE:TITAN",
        "ULTRACEMCO": "NSE:ULTRACEMCO",
        "WIPRO": "NSE:WIPRO",
    }
    try:
        if index_name == "SENSEX":
            instruments = instruments_bfo or []
            segment = "BFO-OPT"
            name = "SENSEX"
            is_stock = False
            if not instruments:
                return {"index": index_name, "error": "BFO instruments unavailable for SENSEX."}
        else:
            instruments = instruments_nfo
            segment = "NFO-OPT"
            name = index_name
            # Check if this is a stock symbol (in NIFTY 50) vs an index
            is_stock = index_name in NIFTY_50_SYMBOLS

        # For indices: match by name. For stocks: match by tradingsymbol prefix
        if is_stock:
            # Stock symbols: look for tradingsymbols that start with the stock symbol
            options = [
                i for i in instruments 
                if i.get("tradingsymbol", "").startswith(index_name) 
                and i["segment"] == segment
            ]
        else:
            # Index symbols: match by name
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
            symbol_type = "stock" if is_stock else "index"
            return {
                "index": index_name,
                "error": f"No option chain data available for {symbol_type} {index_name}. Check that this {symbol_type} has listed options.",
                "debug": {
                    "bfo_instruments": bfo_count,
                    "all_instruments": all_count,
                    "segment": segment,
                    "is_stock": is_stock,
                } if index_name == "SENSEX" else {"is_stock": is_stock},
            }
        quote_symbol = symbol_map.get(index_name, f"NSE:{index_name}")
        try:
            quote = kite.quote([quote_symbol])
            spot_price = quote[quote_symbol]["last_price"]
            quote_data = quote[quote_symbol]  # Store full quote data for validation
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
        lot_size = ce_instrument.get("lot_size", 1) if ce_instrument else 1
        
        # Index-specific and stock-specific lot sizes (fallback if not in instrument data)
        lot_size_map = {
            "BANKNIFTY": 30,
            "NIFTY": 50,
            "FINNIFTY": 40,
            "SENSEX": 10,
            # Stock symbols default to 1 (lot_size will be from instrument data)
        }
        if lot_size == 1 and index_name in lot_size_map:  # Only override for indices with special lot sizes
            lot_size = lot_size_map.get(index_name, 1)
        
        # Determine trend direction robustly using open->last move.
        # Prefer OHLC open when available, then fallback to legacy open_price.
        ohlc_open = (quote_data.get("ohlc") or {}).get("open")
        session_open = ohlc_open if ohlc_open not in (None, 0) else quote_data.get("open_price")
        if session_open in (None, 0):
            session_open = spot_price

        change_pct = ((spot_price - session_open) / session_open * 100) if session_open else 0
        trend_bullish = change_pct >= 0
        trend_direction = "UPTREND" if trend_bullish else "DOWNTREND"
        abs_change = abs(change_pct)
        if abs_change >= 1.0:
            trend_strength = "STRONG"
        elif abs_change >= 0.4:
            trend_strength = "MODERATE"
        else:
            trend_strength = "WEAK"
        
        # Return BOTH CE and PE signals
        signal_type = "stock" if is_stock else "index"
        
        # Use percentage-based targets for stocks, fixed points for indices
        # This ensures better RR ratios across different price scales
        if is_stock:
            # For stock options: use percentage-based targeting (8% target, 5% stop)
            target_pct = 1.08  # 8% profit target
            stop_pct = 0.95    # 5% stop loss
            ce_target = round(ce_quote * target_pct, 2)
            ce_stop = _safe_buy_stop(ce_quote, ce_quote * stop_pct)
            pe_target = round(pe_quote * target_pct, 2)
            pe_stop = _safe_buy_stop(pe_quote, pe_quote * stop_pct)
            ce_profit = round((ce_target - ce_quote) * lot_size, 2)
            ce_risk = round((ce_quote - ce_stop) * lot_size, 2)
            pe_profit = round((pe_target - pe_quote) * lot_size, 2)
            pe_risk = round((pe_quote - pe_stop) * lot_size, 2)
        else:
            # For index options: use fixed point targeting (25 points target, 20 points stop)
            ce_target = ce_quote + 25
            ce_stop = _safe_buy_stop(ce_quote, ce_quote - 20)
            pe_target = pe_quote + 25
            pe_stop = _safe_buy_stop(pe_quote, pe_quote - 20)
            ce_profit = 25 * lot_size
            ce_risk = 20 * lot_size
            pe_profit = 25 * lot_size
            pe_risk = 20 * lot_size
        
        ce_signal = {
            "index": index_name,
            "signal_type": signal_type,  # NEW: Mark whether this is stock or index
            "strike": atm_strike,
            "ce_signal": f"CE LTP: {ce_quote}",
            "pe_signal": f"PE LTP: {pe_quote}",
            "sentiment": "LIVE",
            "expiry_zone": nearest_expiry,
            "risk_note": "Live data",
            "entry_price": ce_quote,
            "target": ce_target,
            "stop_loss": ce_stop,
            "confidence": 85 if trend_bullish else 75,
            "strategy": f"ATM Option CE ({'Stock' if is_stock else 'Index'})",
            "action": "BUY",
            "symbol": ce_symbol,
            "quantity": lot_size,
            "expiry_date": str(nearest_expiry),
            "potential_profit": ce_profit,
            "risk": ce_risk,
            "option_type": "CE",
            "trend_direction": trend_direction,
            "trend_strength": trend_strength,
            "trend_change_pct": round(change_pct, 3),
            "trend_aligned": trend_bullish,
        }
        
        pe_signal = {
            "index": index_name,
            "signal_type": signal_type,  # NEW: Mark whether this is stock or index
            "strike": atm_strike,
            "ce_signal": f"CE LTP: {ce_quote}",
            "pe_signal": f"PE LTP: {pe_quote}",
            "sentiment": "LIVE",
            "expiry_zone": nearest_expiry,
            "risk_note": "Live data",
            "entry_price": pe_quote,
            "target": pe_target,
            "stop_loss": pe_stop,
            "confidence": 85 if not trend_bullish else 75,
            "strategy": f"ATM Option PE ({'Stock' if is_stock else 'Index'})",
            "action": "BUY",
            "symbol": pe_symbol,
            "quantity": lot_size,
            "expiry_date": str(nearest_expiry),
            "potential_profit": pe_profit,
            "risk": pe_risk,
            "option_type": "PE",
            "trend_direction": trend_direction,
            "trend_strength": trend_strength,
            "trend_change_pct": round(change_pct, 3),
            "trend_aligned": not trend_bullish,
        }
        
        # Validate signal quality for both CE and PE
        ce_signal = _validate_signal_quality(
            ce_signal,
            kite,
            quote_data,
            enable_technical=enable_technical,
        )
        pe_signal = _validate_signal_quality(
            pe_signal,
            kite,
            quote_data,
            enable_technical=enable_technical,
        )
        
        # Directional enhancement:
        # - Strong trend: return only aligned side.
        # - Moderate/weak trend: include both sides so scanner does not look one-sided.
        preferred = ce_signal if trend_bullish else pe_signal
        counter = pe_signal if trend_bullish else ce_signal
        preferred["trend_logic"] = "directional_primary"
        counter["trend_logic"] = "counter_trend_filtered"
        preferred["counter_signal"] = {
            "symbol": counter.get("symbol"),
            "option_type": counter.get("option_type"),
            "confidence": counter.get("confidence"),
            "trend_aligned": counter.get("trend_aligned"),
        }

        if abs_change >= 1.0:
            # Strong directional day: one-sided output is intentional.
            preferred["market_bias"] = "STRONG_TREND_ONE_SIDE"
            return [preferred]

        if abs_change >= 0.4:
            # Moderate trend: keep primary first, include cautious counter setup.
            counter["confidence"] = max(60, float(counter.get("confidence", 0) or 0))
            preferred["market_bias"] = "MODERATE_TREND_BOTH_SIDES"
            counter["market_bias"] = "MODERATE_TREND_BOTH_SIDES"
            return [preferred, counter]

        # Weak/ranging trend: return both CE/PE to avoid false one-direction bias.
        preferred["market_bias"] = "WEAK_TREND_BOTH_SIDES"
        counter["market_bias"] = "WEAK_TREND_BOTH_SIDES"
        counter["confidence"] = max(65, float(counter.get("confidence", 0) or 0))
        return [preferred, counter]
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
_signals_cache = {}
_signals_cache_lock = threading.Lock()
_signals_cache_ttl = 60  # seconds - increased from 30 to reduce API calls
_signals_rate_limit = 5  # seconds between calls - reduced from 10
_signals_last_call = 0


def _signals_cache_key(
    user_id: int | None,
    symbols: List[str] | None,
    include_nifty50: bool,
    include_fno_universe: bool,
    max_symbols: int,
) -> str:
    normalized_symbols = tuple(sorted(s.strip().upper() for s in (symbols or []) if isinstance(s, str) and s.strip()))
    return (
        f"user={user_id}|nifty50={int(bool(include_nifty50))}|"
        f"fno={int(bool(include_fno_universe))}|max={int(max_symbols)}|"
        f"symbols={','.join(normalized_symbols)}"
    )


def _build_fno_stock_universe(instruments_nfo: List[Dict], max_symbols: int = 120) -> List[str]:
    """Build a broad yet bounded stock option universe from NFO instruments."""
    max_symbols = max(20, min(int(max_symbols or 120), 300))
    index_roots = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"}
    counts: Dict[str, int] = {}

    for ins in instruments_nfo or []:
        if ins.get("segment") != "NFO-OPT":
            continue
        name = str(ins.get("name") or "").upper().strip()
        if not name or name in index_roots:
            continue
        if not re.match(r"^[A-Z0-9-]+$", name):
            continue
        counts[name] = counts.get(name, 0) + 1

    # Deterministic ranking: option-depth first, then symbol name as tie-breaker.
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [sym for sym, _ in ranked[:max_symbols]]


def _build_scan_symbol_universe(
    include_nifty50: bool,
    include_fno_universe: bool,
    max_symbols: int,
    instruments_nfo: List[Dict],
) -> List[str]:
    """Return indices + bounded stock universe for breadth scans."""
    indices = ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
    stock_budget = max(0, min(int(max_symbols or 120), 300))

    stock_candidates: List[str] = []
    if include_nifty50:
        stock_candidates.extend(NIFTY_50_SYMBOLS)
    if include_fno_universe:
        stock_candidates.extend(_build_fno_stock_universe(instruments_nfo, max_symbols=stock_budget))

    # De-duplicate stock candidates, then enforce overall stock budget.
    seen = set()
    bounded_stocks: List[str] = []
    for sym in stock_candidates:
        normalized = str(sym or "").strip().upper()
        if not normalized or normalized in seen or normalized in indices:
            continue
        seen.add(normalized)
        bounded_stocks.append(normalized)
        if len(bounded_stocks) >= stock_budget:
            break

    return indices + bounded_stocks

def generate_signals(
    user_id: int | None = None,
    symbols: List[str] | None = None,
    include_nifty50: bool = False,
    include_fno_universe: bool = False,
    max_symbols: int = 120,
) -> List[Dict]:
    global _signals_cache, _signals_last_call
    now = time.time()
    cache_key = _signals_cache_key(
        user_id=user_id,
        symbols=symbols,
        include_nifty50=include_nifty50,
        include_fno_universe=include_fno_universe,
        max_symbols=max_symbols,
    )
    with _signals_cache_lock:
        # Serve from cache if not expired (cache key includes request parameters).
        cached = _signals_cache.get(cache_key)
        if cached and (now - cached["ts"]) < _signals_cache_ttl:
            return cached["signals"]
        # Rate limit: if last call was too recent, return error signals
        if (now - _signals_last_call) < _signals_rate_limit:
            return [
                {"index": idx, "error": "Too many requests (rate limited)"}
                for idx in ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
            ]
        _signals_last_call = now
        # Actual signal generation
        kite = _get_kite(user_id=user_id)
        if not kite:
            # If credentials are missing, still build the requested symbol universe
            # so frontend can classify indices vs stocks and display informative
            # error rows per-symbol (previous behavior only returned 4 index errors).
            selected = _build_scan_symbol_universe(
                include_nifty50=include_nifty50,
                include_fno_universe=include_fno_universe,
                max_symbols=max_symbols,
                instruments_nfo=[],
            )
            indices = ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
            msg = "Zerodha credentials missing or invalid"
            results = []
            for sym in selected:
                results.append({
                    "index": sym,
                    "signal_type": "index" if sym in indices else "stock",
                    "error": msg,
                })
            return results

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
        selected = []
        if symbols:
            selected = [s.strip().upper() for s in symbols if isinstance(s, str) and s.strip()]
        else:
            selected = _build_scan_symbol_universe(
                include_nifty50=include_nifty50,
                include_fno_universe=include_fno_universe,
                max_symbols=max_symbols,
                instruments_nfo=instruments_nfo,
            )
        # de-duplicate while preserving order
        seen = set()
        selected_symbols = []
        for sym in selected:
            if sym not in seen:
                selected_symbols.append(sym)
                seen.add(sym)
        signals = []
        for idx in selected_symbols:
            use_deep_technical = idx in indices and len(selected_symbols) <= 20
            result = fetch_index_option_chain(
                idx,
                kite,
                instruments_nfo,
                instruments_bfo,
                instruments_all,
                bfo_error_reason,
                enable_technical=use_deep_technical,
            )
            # flatten list of signals
            if isinstance(result, list):
                signals.extend(result)
            else:
                signals.append(result)
        _signals_cache[cache_key] = {"signals": signals, "ts": now}

        # Prevent unbounded growth if many unique keys are requested.
        if len(_signals_cache) > 20:
            oldest_key = min(_signals_cache.items(), key=lambda item: item[1]["ts"])[0]
            _signals_cache.pop(oldest_key, None)

        return signals

def select_best_signal(signals: List[Dict]) -> Dict | None:
    """
    Select the best signal based on quality score, confidence, and filters.
    Now with stricter filtering to avoid low-quality signals that lead to losses.
    
    Filtering stages:
    1. Remove error signals and incomplete signals (missing symbol/entry_price)
    2. Quality filter: prefer 85%+, fallback to 75%+
    3. Risk:Reward filter: require 1.3:1 or better (with fallback if needed)
    4. Rank by quality score, tiebreak by confidence
    
    Returns:
        Selected signal dict with all fields preserved, or None if no viable signal
    """
    import logging
    logger = logging.getLogger("trading_bot")
    
    # Handle None or empty input
    if not signals:
        return None
    
    # Stage 1: Filter out error signals and signals without required data
    viable = []
    for s in signals:
        # Skip error signals
        if not isinstance(s, dict) or s.get("error"):
            continue
        
        # Require symbol
        symbol = s.get("symbol")
        if not symbol or not isinstance(symbol, str) or not symbol.strip():
            continue
        
        # Require entry_price and ensure it's positive
        try:
            entry_price = float(s.get("entry_price") or 0)
            if entry_price <= 0:
                continue
        except (ValueError, TypeError):
            continue
        
        viable.append(s)
    
    if not viable:
        logger.debug(f"[SELECT-BEST-SIGNAL] No viable signals found (0 signals passed basic validation)")
        return None
    
    logger.debug(f"[SELECT-BEST-SIGNAL] {len(viable)} viable signals after basic validation")
    
    # Helper to safely convert to float
    def safe_float(value):
        """Safely convert any value to float, return 0 if fails."""
        try:
            return float(value or 0)
        except (ValueError, TypeError):
            return 0
    
    # Stage 2: Filter by quality score (two-tier)
    high_quality = [
        s for s in viable 
        if safe_float(s.get("quality_score", 0)) >= 85
    ]
    
    if high_quality:
        viable = high_quality
        logger.debug(f"[SELECT-BEST-SIGNAL] {len(viable)} signals with quality >= 85 (strict)")
    else:
        # Fallback: accept 75%+ signals
        viable = [
            s for s in viable 
            if safe_float(s.get("quality_score", 0)) >= 75
        ]
        if viable:
            logger.debug(f"[SELECT-BEST-SIGNAL] Using fallback: {len(viable)} signals with quality >= 75")
        else:
            logger.debug(f"[SELECT-BEST-SIGNAL] No signals passed quality filter (85+ or 75+)")
            return None
    
    # Stage 3: Filter by risk:reward ratio (with fallback)
    def get_risk_reward(s):
        """Calculate risk:reward ratio safely."""
        try:
            entry = safe_float(s.get("entry_price", 0))
            target = safe_float(s.get("target", 0))
            sl = safe_float(s.get("stop_loss", 0))
            
            if not (entry and target and sl):
                return 0
            
            profit = abs(target - entry)
            risk = abs(entry - sl)
            
            # Avoid division by zero
            if risk <= 0:
                return 0
            
            rr = profit / risk
            return rr
        except (ValueError, TypeError):
            return 0
    
    # Try strict RR filter first
    good_rr = [s for s in viable if get_risk_reward(s) >= 1.3]
    
    if good_rr:
        viable = good_rr
        logger.debug(f"[SELECT-BEST-SIGNAL] {len(viable)} signals with RR >= 1.3:1")
    else:
        # Fallback is conditional: only use if we still have signals
        # Don't lower the RR threshold, just keep viable as is
        if not viable:
            logger.debug(f"[SELECT-BEST-SIGNAL] No signals passed RR filter (1.3:1)")
            return None
        logger.debug(f"[SELECT-BEST-SIGNAL] {len(viable)} signals (RR filter relaxed after quality filtering)")
    
    # Stage 4: Select best by quality score, tiebreak by confidence
    best = max(
        viable,
        key=lambda s: (
            safe_float(s.get("quality_score") or 0),
            safe_float(s.get("confidence") or s.get("confirmation_score") or 0)
        )
    )
    
    rr_value = get_risk_reward(best)
    logger.info(
        f"[SELECT-BEST-SIGNAL] Selected: {best.get('symbol')} "
        f"(Q: {safe_float(best.get('quality_score', 0))}, "
        f"C: {safe_float(best.get('confidence', best.get('confirmation_score', 0)))}, "
        f"RR: {rr_value:.2f}:1)"
    )
    
    return best


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _safe_buy_stop(entry: float, desired_stop: float, floor: float = 0.05) -> float:
    """Ensure BUY stop-loss stays positive and below entry."""
    entry = float(entry or 0)
    if entry <= 0:
        return floor
    candidate = float(desired_stop or 0)
    if candidate <= floor or candidate >= entry:
        candidate = max(floor, entry * 0.15)
    return round(min(candidate, entry - floor), 2)


def _trend_strength_bonus(strength: str | None) -> float:
    if strength == "Strong":
        return 0.20
    if strength == "Moderate":
        return 0.10
    if strength == "Weak":
        return 0.05
    return 0.0


def _trend_direction_bonus(direction: str | None, action: str | None) -> float:
    if not direction or not action:
        return 0.0
    action = action.upper()
    if direction == "Uptrend":
        return 0.10 if action == "BUY" else -0.10
    if direction == "Downtrend":
        return -0.10 if action == "BUY" else 0.10
    return 0.0


def _sentiment_bonus(sentiment_score: float | None, action: str | None) -> float:
    if sentiment_score is None or action is None:
        return 0.0
    action = action.upper()
    centered = (sentiment_score - 0.5) * 0.2  # range roughly -0.1 to +0.1
    return centered if action == "BUY" else -centered


def _apply_confirmation(signal: Dict, sentiment: Dict, trend_row: Dict | None, mode: str = "balanced") -> Dict:
    if signal.get("error"):
        return signal

    entry = float(signal.get("entry_price", 0) or 0)
    base_target_points = signal.get("target_points")
    if base_target_points is None and signal.get("target") is not None:
        base_target_points = abs(float(signal.get("target", 0)) - entry)
    base_target_points = float(base_target_points or 25)

    strength = (trend_row or {}).get("strength")
    direction = (trend_row or {}).get("trend")

    trend_bonus = _trend_strength_bonus(strength) + _trend_direction_bonus(direction, signal.get("action"))
    sentiment_bonus = _sentiment_bonus(sentiment.get("sentiment_score"), signal.get("action"))

    mode = (mode or "balanced").lower()
    mode_scale = 1.0
    if mode == "aggressive":
        mode_scale = 1.25
    elif mode == "conservative":
        mode_scale = 0.85

    scale = _clamp((1 + trend_bonus + sentiment_bonus) * mode_scale, 0.6, 1.9)
    target_points = round(base_target_points * scale, 2)
    # Use an entry-percentage floor (capped at 10 pts) so cheap stock options are not
    # burdened with a flat 10-pt stop that dwarfs their target and tanks risk/reward.
    # For expensive options (entry > 200) the cap keeps the existing 10-pt floor.
    min_stop_pts = min(10.0, max(1.0, entry * 0.05)) if entry > 0 else 10.0
    stop_points = round(max(min_stop_pts, target_points * 0.8), 2)
    if entry > 0:
        stop_points = min(stop_points, max(1.0, entry * 0.85))

    if signal.get("action") == "SELL":
        signal["target"] = round(entry - target_points, 2)
        signal["stop_loss"] = round(entry + stop_points, 2)
    else:
        signal["target"] = round(entry + target_points, 2)
        signal["stop_loss"] = _safe_buy_stop(entry, entry - stop_points)

    base_conf = float(signal.get("confidence", 0) or 0)
    confirmation_score = _clamp(base_conf + (trend_bonus + sentiment_bonus) * 100, 45, 98)

    signal["target_points"] = target_points
    signal["confirmation_score"] = round(confirmation_score, 2)
    signal["news_sentiment"] = sentiment.get("overall_sentiment")
    signal["news_sentiment_score"] = sentiment.get("sentiment_score")
    signal["trend_direction"] = direction
    signal["trend_strength"] = strength
    signal["confirmation_mode"] = mode
    return signal


async def generate_signals_advanced(
    user_id: int | None = None,
    mode: str = "balanced",
    symbols: List[str] | None = None,
    include_nifty50: bool = False,
    include_fno_universe: bool = False,
    max_symbols: int = 120,
) -> List[Dict]:
    # Run heavy sync signal generation off the event loop to keep API responsive.
    signals = await asyncio.to_thread(
        generate_signals,
        user_id,
        symbols,
        include_nifty50,
        include_fno_universe,
        max_symbols,
    )
    try:
        sentiment = news_analyzer.get_market_sentiment_summary()
    except Exception:
        sentiment = {"overall_sentiment": "Unknown", "sentiment_score": 0.5}

    trend_data = {}
    try:
        trends = await trend_analyzer.get_market_trends()
        trend_data = trends.get("indices", {}) if isinstance(trends, dict) else {}
    except Exception:
        trend_data = {}

    enhanced = []
    for s in signals:
        idx = s.get("index")
        trend_row = trend_data.get(idx) if idx else None
        enhanced.append(_apply_confirmation(s, sentiment, trend_row, mode=mode))
    return enhanced

if __name__ == "__main__":
    from pprint import pprint
    pprint(generate_signals())
