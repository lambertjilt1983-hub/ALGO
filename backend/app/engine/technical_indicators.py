"""
Technical Indicators for AI Algo Trading
Comprehensive implementation of key technical analysis indicators
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple


def calculate_rsi(prices: list, period: int = 14) -> float:
    """
    Calculate Relative Strength Index (RSI)
    Returns: RSI value between 0-100
    """
    if len(prices) < period + 1:
        return 50.0  # Neutral if insufficient data
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
    """
    Calculate MACD (Moving Average Convergence Divergence)
    Returns: dict with macd, signal, and histogram values
    """
    if len(prices) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    
    prices_series = pd.Series(prices)
    
    # Calculate EMAs
    ema_fast = prices_series.ewm(span=fast, adjust=False).mean()
    ema_slow = prices_series.ewm(span=slow, adjust=False).mean()
    
    # MACD line
    macd_line = ema_fast - ema_slow
    
    # Signal line
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    
    # Histogram
    histogram = macd_line - signal_line
    
    return {
        "macd": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "histogram": float(histogram.iloc[-1]),
        "crossover": "bullish" if histogram.iloc[-1] > 0 and histogram.iloc[-2] <= 0 else 
                     "bearish" if histogram.iloc[-1] < 0 and histogram.iloc[-2] >= 0 else "none"
    }


def calculate_bollinger_bands(prices: list, period: int = 20, std_dev: int = 2) -> Dict[str, float]:
    """
    Calculate Bollinger Bands
    Returns: dict with upper, middle, lower bands and position
    """
    if len(prices) < period:
        current = prices[-1] if prices else 0
        return {
            "upper": current * 1.02,
            "middle": current,
            "lower": current * 0.98,
            "position": 0.5
        }
    
    prices_array = np.array(prices[-period:])
    middle = np.mean(prices_array)
    std = np.std(prices_array)
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    current_price = prices[-1]
    
    # Calculate position (0 = at lower band, 0.5 = at middle, 1 = at upper band)
    if upper != lower:
        position = (current_price - lower) / (upper - lower)
    else:
        position = 0.5
    
    return {
        "upper": float(upper),
        "middle": float(middle),
        "lower": float(lower),
        "position": float(position),
        "squeeze": "tight" if (upper - lower) / middle < 0.02 else "normal"
    }


def calculate_volatility(prices: list, period: int = 20) -> float:
    """
    Calculate historical volatility (annualized)
    Returns: volatility percentage
    """
    if len(prices) < 2:
        return 0.0
    
    returns = np.diff(prices) / prices[:-1]
    
    if len(returns) < period:
        std_dev = np.std(returns)
    else:
        std_dev = np.std(returns[-period:])
    
    # Annualize (assume 252 trading days)
    volatility = std_dev * np.sqrt(252) * 100
    return float(volatility)


def calculate_moving_averages(prices: list) -> Dict[str, float]:
    """
    Calculate multiple moving averages
    Returns: dict with SMA and EMA values
    """
    if len(prices) < 5:
        current = prices[-1] if prices else 0
        return {
            "sma_5": current,
            "sma_10": current,
            "sma_20": current,
            "sma_50": current,
            "ema_9": current,
            "ema_21": current
        }
    
    prices_series = pd.Series(prices)
    
    return {
        "sma_5": float(prices_series.rolling(window=5).mean().iloc[-1]) if len(prices) >= 5 else prices[-1],
        "sma_10": float(prices_series.rolling(window=10).mean().iloc[-1]) if len(prices) >= 10 else prices[-1],
        "sma_20": float(prices_series.rolling(window=20).mean().iloc[-1]) if len(prices) >= 20 else prices[-1],
        "sma_50": float(prices_series.rolling(window=50).mean().iloc[-1]) if len(prices) >= 50 else prices[-1],
        "ema_9": float(prices_series.ewm(span=9, adjust=False).mean().iloc[-1]),
        "ema_21": float(prices_series.ewm(span=21, adjust=False).mean().iloc[-1])
    }


def detect_support_resistance(prices: list, highs: list, lows: list) -> Dict[str, float]:
    """
    Detect support and resistance levels
    Returns: dict with support and resistance prices
    """
    if len(prices) < 20:
        current = prices[-1] if prices else 0
        return {
            "support": current * 0.98,
            "resistance": current * 1.02,
            "at_support": False,
            "at_resistance": False
        }
    
    # Find recent highs and lows
    recent_highs = sorted(highs[-20:], reverse=True)[:3]
    recent_lows = sorted(lows[-20:])[:3]
    
    resistance = np.mean(recent_highs)
    support = np.mean(recent_lows)
    
    current_price = prices[-1]
    tolerance = 0.005  # 0.5% tolerance
    
    return {
        "support": float(support),
        "resistance": float(resistance),
        "at_support": abs(current_price - support) / support < tolerance,
        "at_resistance": abs(current_price - resistance) / resistance < tolerance
    }


def calculate_comprehensive_signals(
    prices: list,
    highs: list = None,
    lows: list = None,
    volumes: list = None
) -> Dict[str, any]:
    """
    Calculate all technical indicators and generate comprehensive signal
    Returns: Complete technical analysis with buy/sell recommendation
    """
    if not prices or len(prices) < 2:
        return {"error": "Insufficient data"}
    
    # Ensure we have highs/lows/volumes
    if highs is None:
        highs = prices.copy()
    if lows is None:
        lows = prices.copy()
    if volumes is None:
        volumes = [1000000] * len(prices)  # Dummy volume
    
    # Calculate all indicators
    rsi = calculate_rsi(prices)
    macd = calculate_macd(prices)
    bollinger = calculate_bollinger_bands(prices)
    volatility = calculate_volatility(prices)
    moving_avgs = calculate_moving_averages(prices)
    support_resistance = detect_support_resistance(prices, highs, lows)
    
    # Signal strength calculation (0-100)
    signal_strength = 0
    signals = []
    
    # RSI signals (25 points)
    if rsi > 70:
        signals.append("⚠️ Overbought (RSI > 70)")
    elif rsi > 50:
        signal_strength += 25
        signals.append("✓ Bullish RSI")
    elif rsi < 30:
        signal_strength += 25
        signals.append("✓ Oversold - Reversal opportunity")
    else:
        signals.append("~ Neutral RSI")
    
    # MACD signals (25 points)
    if macd["crossover"] == "bullish":
        signal_strength += 25
        signals.append("✓ MACD Bullish Crossover")
    elif macd["crossover"] == "bearish":
        signals.append("⚠️ MACD Bearish Crossover")
    elif macd["histogram"] > 0:
        signal_strength += 15
        signals.append("~ MACD Positive")
    
    # Bollinger Bands (25 points)
    if bollinger["position"] < 0.2:
        signal_strength += 25
        signals.append("✓ At Lower Band - Mean Reversion")
    elif bollinger["position"] > 0.8:
        signals.append("⚠️ At Upper Band - Overbought")
    elif 0.4 <= bollinger["position"] <= 0.6:
        signal_strength += 10
        signals.append("~ Mid-range")
    
    # Support/Resistance (25 points)
    if support_resistance["at_support"]:
        signal_strength += 25
        signals.append("✓ At Support Level - Bounce opportunity")
    elif support_resistance["at_resistance"]:
        signals.append("⚠️ At Resistance - Rejection risk")
    
    # Volume confirmation
    if len(volumes) >= 2 and volumes[-1] > np.mean(volumes[-20:]) * 1.2:
        signal_strength += 10
        signals.append("✓ High Volume Confirmation")
    
    # Final recommendation
    if signal_strength >= 75:
        recommendation = "STRONG BUY"
    elif signal_strength >= 60:
        recommendation = "BUY"
    elif signal_strength >= 40:
        recommendation = "HOLD"
    else:
        recommendation = "AVOID"
    
    return {
        "rsi": rsi,
        "macd": macd,
        "bollinger_bands": bollinger,
        "volatility": volatility,
        "moving_averages": moving_avgs,
        "support_resistance": support_resistance,
        "signal_strength": signal_strength,
        "signals": signals,
        "recommendation": recommendation,
        "timestamp": pd.Timestamp.now().isoformat()
    }
