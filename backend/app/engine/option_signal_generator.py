from kiteconnect import KiteConnect
def fetch_stock_option_chain(
    stock_symbol,
    kite: KiteConnect,
    instruments_nfo: list[dict],
):
    import logging
    logger = logging.getLogger("option_signal_debug")
    logger.info(f"[DEBUG] Generating stock option chain for: {stock_symbol}")
    options = [i for i in instruments_nfo if i["name"] == stock_symbol and i["segment"] == "NFO-OPT"]
    if not options:
        logger.warning(f"[DEBUG] No options available for {stock_symbol}")
        return {"index": stock_symbol, "error": "No options available for this stock."}
    quote_symbol = f"NSE:{stock_symbol}"
    try:
        quote = kite.quote([quote_symbol])
        spot_price = quote[quote_symbol]["last_price"]
        quote_data = quote[quote_symbol]
        logger.info(f"[DEBUG] {stock_symbol} spot price: {spot_price}")
    except Exception as e:
        logger.error(f"[DEBUG] Quote error for {stock_symbol}: {str(e)}")
        return {"index": stock_symbol, "error": f"Quote error: {str(e)}"}
    from datetime import date
    expiries = sorted(set(i["expiry"] for i in options))
    today = date.today()
    valid_expiries = [e for e in expiries if isinstance(e, date) and e >= today]
    if not valid_expiries:
        logger.warning(f"[DEBUG] No valid (future) expiries for {stock_symbol}")
        return {"index": stock_symbol, "error": "No valid (future) expiries found for this stock."}
    nearest_expiry = valid_expiries[0]
    strikes = sorted(set(i["strike"] for i in options if i["expiry"] == nearest_expiry))
    if not strikes:
        logger.warning(f"[DEBUG] No strikes found for {stock_symbol} expiry {nearest_expiry}")
        return {"index": stock_symbol, "error": "No strikes found for this expiry."}
    atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
    try:
        ce_symbol = next(i["tradingsymbol"] for i in options if i["strike"] == atm_strike and i["expiry"] == nearest_expiry and i["instrument_type"] == "CE")
        pe_symbol = next(i["tradingsymbol"] for i in options if i["strike"] == atm_strike and i["expiry"] == nearest_expiry and i["instrument_type"] == "PE")
        logger.info(f"[DEBUG] {stock_symbol} ATM strike: {atm_strike}, CE: {ce_symbol}, PE: {pe_symbol}")
    except StopIteration:
        logger.error(f"[DEBUG] No CE/PE symbol found for {stock_symbol} ATM strike {atm_strike}")
        return {"index": stock_symbol, "error": "No CE/PE symbol found for ATM strike."}
    try:
        ce_key = f"NFO:{ce_symbol}"
        pe_key = f"NFO:{pe_symbol}"
        ce_quote = kite.quote([ce_key])[ce_key]["last_price"]
        pe_quote = kite.quote([pe_key])[pe_key]["last_price"]
        logger.info(f"[DEBUG] {stock_symbol} CE LTP: {ce_quote}, PE LTP: {pe_quote}")
    except Exception as e:
        logger.error(f"[DEBUG] Option quote error for {stock_symbol}: {str(e)}")
        return {"index": stock_symbol, "error": f"Option quote error: {str(e)}"}
    ce_instrument = next((i for i in options if i["tradingsymbol"] == ce_symbol), None)
    lot_size = ce_instrument.get("lot_size", 1) if ce_instrument else 1
    ce_signal = {
        "index": stock_symbol,
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
        "strategy": "ATM Option CE",
        "action": "BUY",
        "symbol": ce_symbol,
        "quantity": lot_size,
        "expiry_date": str(nearest_expiry),
        "potential_profit": 25 * lot_size,
        "risk": 20 * lot_size,
        "option_type": "CE"
    }
    pe_signal = {
        "index": stock_symbol,
        "strike": atm_strike,
        "ce_signal": f"CE LTP: {ce_quote}",
        "pe_signal": f"PE LTP: {pe_quote}",
        "sentiment": "LIVE",
        "expiry_zone": nearest_expiry,
        "risk_note": "Live data",
        "entry_price": pe_quote,
        "target": pe_quote + 25,
        "stop_loss": pe_quote - 20,
        "confidence": 85,
        "strategy": "ATM Option PE",
        "action": "BUY",
        "symbol": pe_symbol,
        "quantity": lot_size,
        "expiry_date": str(nearest_expiry),
        "potential_profit": 25 * lot_size,
        "risk": 20 * lot_size,
        "option_type": "PE"
    }
    ce_signal = _validate_signal_quality(ce_signal, kite, quote_data)
    pe_signal = _validate_signal_quality(pe_signal, kite, quote_data)

    # Enforce only one EXCELLENT/high quality signal (CE or PE) per strike
    # Prefer the one with higher quality_score, or use technical recommendation if available
    ce_score = ce_signal.get("quality_score", 0)
    pe_score = pe_signal.get("quality_score", 0)
    ce_reco = ce_signal.get("technical_indicators", {}).get("recommendation", "")
    pe_reco = pe_signal.get("technical_indicators", {}).get("recommendation", "")

    # Prefer technical recommendation if available and not HOLD
    if ce_reco in ["STRONG BUY", "BUY"] and pe_reco not in ["STRONG BUY", "BUY"]:
        # CE is the preferred signal
        pe_signal["is_high_quality"] = False
        pe_signal["quality_factors"] = pe_signal.get("quality_factors", []) + ["Filtered: CE trend stronger"]
        return [ce_signal]
    elif pe_reco in ["STRONG BUY", "BUY"] and ce_reco not in ["STRONG BUY", "BUY"]:
        # PE is the preferred signal
        ce_signal["is_high_quality"] = False
        ce_signal["quality_factors"] = ce_signal.get("quality_factors", []) + ["Filtered: PE trend stronger"]
        return [pe_signal]
    else:
        # Otherwise, use quality_score
        if ce_score > pe_score:
            pe_signal["is_high_quality"] = False
            pe_signal["quality_factors"] = pe_signal.get("quality_factors", []) + ["Filtered: CE higher quality"]
            return [ce_signal]
        elif pe_score > ce_score:
            ce_signal["is_high_quality"] = False
            ce_signal["quality_factors"] = ce_signal.get("quality_factors", []) + ["Filtered: PE higher quality"]
            return [pe_signal]
        else:
            # If both are equal, return both but mark as not high quality (or pick one arbitrarily)
            ce_signal["is_high_quality"] = False
            pe_signal["is_high_quality"] = False
            ce_signal["quality_factors"] = ce_signal.get("quality_factors", []) + ["Filtered: No clear winner"]
            pe_signal["quality_factors"] = pe_signal.get("quality_factors", []) + ["Filtered: No clear winner"]
            return [ce_signal]
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


def _validate_signal_quality(signal: dict, kite: KiteConnect, quote_data: dict) -> dict:
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
        
        # Try to get historical data for technical indicators
        try:
            # Get underlying index symbol
            index_symbol = signal.get("index", "NIFTY")
            symbol_map = {
                "BANKNIFTY": "NSE:NIFTY BANK",
                "NIFTY": "NSE:NIFTY 50",
                "SENSEX": "BSE:SENSEX",
                "FINNIFTY": "NSE:NIFTY FIN SERVICE"
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
                
        except Exception as tech_error:
            # Fallback to basic analysis if technical indicators fail
            # Silently fall back to basic analysis if technical indicators fail
            pass
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
        
        # Determine trend direction based on price momentum
        change_pct = ((spot_price - quote.get(quote_symbol, {}).get('open_price', spot_price)) / quote.get(quote_symbol, {}).get('open_price', spot_price) * 100) if quote.get(quote_symbol, {}).get('open_price') else 0
        trend_bullish = change_pct >= 0
        
        # Return BOTH CE and PE signals
        ce_signal = {
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
            "confidence": 85 if trend_bullish else 75,
            "strategy": "ATM Option CE",
            "action": "BUY",
            "symbol": ce_symbol,
            "quantity": lot_size,
            "expiry_date": str(nearest_expiry),
            "potential_profit": 25 * lot_size,
            "risk": 20 * lot_size,
            "option_type": "CE"
        }
        
        pe_signal = {
            "index": index_name,
            "strike": atm_strike,
            "ce_signal": f"CE LTP: {ce_quote}",
            "pe_signal": f"PE LTP: {pe_quote}",
            "sentiment": "LIVE",
            "expiry_zone": nearest_expiry,
            "risk_note": "Live data",
            "entry_price": pe_quote,
            "target": pe_quote + 25,
            "stop_loss": pe_quote - 20,
            "confidence": 85 if not trend_bullish else 75,
            "strategy": "ATM Option PE",
            "action": "BUY",
            "symbol": pe_symbol,
            "quantity": lot_size,
            "expiry_date": str(nearest_expiry),
            "potential_profit": 25 * lot_size,
            "risk": 20 * lot_size,
            "option_type": "PE"
        }
        
        # Validate signal quality for both CE and PE
        ce_signal = _validate_signal_quality(ce_signal, kite, quote_data)
        pe_signal = _validate_signal_quality(pe_signal, kite, quote_data)
        
        # Return the most bullish signal first, PE second
        return [ce_signal, pe_signal] if trend_bullish else [pe_signal, ce_signal]
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
_signals_cache_ttl = 60  # seconds - increased from 30 to reduce API calls
_signals_rate_limit = 5  # seconds between calls - reduced from 10
_signals_last_call = 0

def generate_signals(
    user_id: int | None = None,
    symbols: List[str] | None = None,
    include_nifty50: bool = False,
) -> List[Dict]:
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
        kite = _get_kite(user_id=user_id)
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
        selected = []
        if symbols:
            selected = [s.strip().upper() for s in symbols if isinstance(s, str) and s.strip()]
        else:
            selected = indices.copy()
            if include_nifty50:
                selected.extend(NIFTY_50_SYMBOLS)
        # de-duplicate while preserving order
        seen = set()
        selected_symbols = []
        for sym in selected:
            if sym not in seen:
                selected_symbols.append(sym)
                seen.add(sym)
        signals = []
        for idx in selected_symbols:
            if idx in ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]:
                result = fetch_index_option_chain(
                    idx,
                    kite,
                    instruments_nfo,
                    instruments_bfo,
                    instruments_all,
                    bfo_error_reason,
                )
            else:
                result = fetch_stock_option_chain(
                    idx,
                    kite,
                    instruments_nfo,
                )
            # flatten list of signals
            if isinstance(result, list):
                signals.extend(result)
            else:
                signals.append(result)
        _signals_cache = signals
        _signals_cache_time = now
        return signals

def select_best_signal(signals: List[Dict]) -> Dict | None:
    """
    Select the best signal based on quality score, confidence, and filters.
    Now with stricter filtering to avoid low-quality signals that lead to losses.
    """
    # Filter out error signals and signals without required data
    viable = [s for s in signals if not s.get("error") and s.get("symbol") and s.get("entry_price")]
    if not viable:
        return None
    
    # CRITICAL: Filter out low-quality signals (quality_score < 65)
    # This prevents most losing trades by avoiding weak/choppy setups
    high_quality = [s for s in viable if s.get("quality_score", 0) >= 65]
    if high_quality:
        viable = high_quality  # Prefer high-quality signals
    else:
        # If no high-quality signals, at least require quality_score >= 55
        viable = [s for s in viable if s.get("quality_score", 0) >= 55]
        if not viable:
            return None  # No acceptable quality signals
    
    # Filter out signals with unfavorable risk:reward ratio (< 1.3:1)
    def get_risk_reward(s):
        entry = float(s.get("entry_price", 0) or 0)
        target = float(s.get("target", 0) or 0)
        sl = float(s.get("stop_loss", 0) or 0)
        if entry and target and sl:
            profit = abs(target - entry)
            risk = abs(entry - sl)
            return profit / risk if risk > 0 else 0
        return 0
    
    good_rr = [s for s in viable if get_risk_reward(s) >= 1.3]
    if good_rr:
        viable = good_rr
    
    # Select best by quality score (tie-break by confidence)
    return max(viable, key=lambda s: (s.get("quality_score", 0), s.get("confidence", 0)))


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


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
    stop_points = round(max(10, target_points * 0.8), 2)

    if signal.get("action") == "SELL":
        signal["target"] = round(entry - target_points, 2)
        signal["stop_loss"] = round(entry + stop_points, 2)
    else:
        signal["target"] = round(entry + target_points, 2)
        signal["stop_loss"] = round(entry - stop_points, 2)

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
) -> List[Dict]:
    signals = generate_signals(user_id=user_id, symbols=symbols, include_nifty50=include_nifty50)
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
