"""
High-Performance Intraday Trading Strategy Module
Asset: Nifty 50 (can be adapted)
Timeframe: 5-minute
Indicators: VWAP, EMA(9/21), RSI(14), MACD(12,26,9), Supertrend(10,3)
"""
import numpy as np
import pandas as pd

# --- Indicator Functions ---
def vwap(df):
    q = df['volume']
    p = df['close']
    vwap = (p * q).cumsum() / q.cumsum()
    return vwap

def ema(df, period, col='close'):
    return df[col].ewm(span=period, adjust=False).mean()

def rsi(df, period=14, col='close'):
    delta = df[col].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def macd(df, fast=12, slow=26, signal=9, col='close'):
    ema_fast = ema(df, fast, col)
    ema_slow = ema(df, slow, col)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def supertrend(df, period=10, multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    atr = df['high'].combine(df['low'], max) - df['low'].combine(df['high'], min)
    atr = atr.rolling(window=period).mean()
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)
    supertrend = np.zeros(len(df))
    in_uptrend = True
    for i in range(1, len(df)):
        if df['close'][i] > upperband[i-1]:
            in_uptrend = True
        elif df['close'][i] < lowerband[i-1]:
            in_uptrend = False
        supertrend[i] = upperband[i] if in_uptrend else lowerband[i]
    return pd.Series(supertrend, index=df.index)

# --- Signal Logic ---
def generate_signals(df, capital=0):
    df = df.copy()
    df['VWAP'] = vwap(df)
    df['EMA9'] = ema(df, 9)
    df['EMA21'] = ema(df, 21)
    df['RSI'] = rsi(df, 14)
    df['MACD'], df['MACD_signal'], df['MACD_hist'] = macd(df)
    df['Supertrend'] = supertrend(df, 10, 3)
    df['Signal'] = ''
    df['Debug'] = ''
    last_signal = None
    for i in range(21, len(df)):
        price = df['close'][i]
        above_vwap = price > df['VWAP'][i]
        ema9 = df['EMA9'][i]
        ema21 = df['EMA21'][i]
        ema9_prev = df['EMA9'][i-1]
        ema21_prev = df['EMA21'][i-1]
        
        # More sensitive trend detection
        ema_bullish = ema9 > ema21 and (ema9 - ema9_prev) > 0
        ema_bearish = ema9 < ema21 and (ema9 - ema9_prev) < 0
        ema_cross_up = ema9_prev <= ema21_prev and ema9 > ema21
        ema_cross_down = ema9_prev >= ema21_prev and ema9 < ema21
        
        rsi_val = df['RSI'][i]
        macd_hist = df['MACD_hist'][i]
        macd_hist_prev = df['MACD_hist'][i-1]
        macd_rising = macd_hist > macd_hist_prev
        macd_falling = macd_hist < macd_hist_prev
        supertrend_val = df['Supertrend'][i]
        
        # IMPROVED Entry Logic - Stricter conditions for better win rate
        # Long Entry - ALL conditions must align for high-probability setup
        if (above_vwap and 
            (ema_cross_up or (ema_bullish and ema9 > ema21 * 1.002)) and  # Stronger EMA separation
            35 < rsi_val < 65 and  # Tighter RSI range to avoid extremes
            macd_hist > 0 and macd_rising and  # Both MACD conditions required
            price > supertrend_val):  # Price must be above Supertrend for confirmation
            df.at[df.index[i], 'Signal'] = 'LONG'
            last_signal = 'LONG'
        # Short Entry - ALL conditions must align
        elif (not above_vwap and 
              (ema_cross_down or (ema_bearish and ema9 < ema21 * 0.998)) and  # Stronger EMA separation
              35 < rsi_val < 65 and  # Tighter RSI range  
              macd_hist < 0 and macd_falling and  # Both MACD conditions required
              price < supertrend_val):  # Price must be below Supertrend for confirmation
            df.at[df.index[i], 'Signal'] = 'SHORT'
            last_signal = 'SHORT'
        # Exit with tighter conditions to lock profits
        elif last_signal == 'LONG' and (price < supertrend_val or rsi_val > 70 or macd_hist < 0):
            df.at[df.index[i], 'Signal'] = 'EXIT LONG'
            last_signal = None
        elif last_signal == 'SHORT' and (price > supertrend_val or rsi_val < 30 or macd_hist > 0):
            df.at[df.index[i], 'Signal'] = 'EXIT SHORT'
            last_signal = None
        # Debug info with more details
        debug_msg = f"Price={price:.2f}, VWAP={df['VWAP'][i]:.2f}, above_vwap={above_vwap}, "
        debug_msg += f"EMA9={ema9:.2f}, EMA21={ema21:.2f}, ema_bullish={ema_bullish}, ema_bearish={ema_bearish}, "
        debug_msg += f"RSI={rsi_val:.2f}, MACD_hist={macd_hist:.4f}, macd_rising={macd_rising}, "
        debug_msg += f"Supertrend={supertrend_val:.2f}, Signal={df.at[df.index[i], 'Signal']}"
        df.at[df.index[i], 'Debug'] = debug_msg
    return df

# --- Backtesting Module ---
def backtest(df, capital=100000):
    trades = []
    position = None
    entry_price = 0
    risk_per_trade = capital * 0.02
    for i, row in df.iterrows():
        if row['Signal'] == 'LONG' and position is None:
            position = 'LONG'
            entry_price = row['close']
            stop_loss = row['Supertrend']
            target = entry_price + 2 * (entry_price - stop_loss)
        elif row['Signal'] == 'SHORT' and position is None:
            position = 'SHORT'
            entry_price = row['close']
            stop_loss = row['Supertrend']
            target = entry_price - 2 * (stop_loss - entry_price)
        elif row['Signal'] == 'EXIT LONG' and position == 'LONG':
            pnl = row['close'] - entry_price
            trades.append(pnl)
            position = None
        elif row['Signal'] == 'EXIT SHORT' and position == 'SHORT':
            pnl = entry_price - row['close']
            trades.append(pnl)
            position = None
    # Calculate metrics
    returns = np.array(trades)
    win_rate = np.mean(returns > 0) if len(returns) > 0 else 0
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
    return {'Sharpe Ratio': sharpe, 'Win Rate': win_rate, 'Trades': len(trades)}

# --- Example Usage ---
if __name__ == "__main__":
    # Load your 5-min OHLCV data as a DataFrame with columns: ['open','high','low','close','volume']
    df = pd.read_csv('nifty_5min.csv')
    df = generate_signals(df)
    print(df[['close','Signal','Debug']].tail(20))
    results = backtest(df)
    print('Backtest Results:', results)
