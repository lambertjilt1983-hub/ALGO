"""
Test Live Auto Trading with Real Market Data
Execute a demo trade before market closes at 3:30 PM
"""

import asyncio
import aiohttp
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.strategies.auto_trader import auto_trader, TradeSignal
import random

async def fetch_live_nifty_price():
    """Fetch live NIFTY price from NSE"""
    try:
        # NSE Website for live data
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        async with aiohttp.ClientSession() as session:
            # First get cookies
            async with session.get("https://www.nseindia.com", headers=headers) as resp:
                pass
            
            # Now fetch option chain data which has underlying value
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get('records', {}).get('underlyingValue', 0)
                    if price > 0:
                        print(f"✓ Live NIFTY Price from NSE: ₹{price}")
                        return price
    except Exception as e:
        print(f"⚠ Error fetching live price: {e}")
    
    # Fallback: Use simulated realistic price
    now = datetime.now()
    base_price = 22000 + (now.day * 10) + (now.hour * 5)
    price = base_price + random.uniform(-200, 200)
    print(f"⚠ Using simulated NIFTY price: ₹{price:.2f}")
    return price

async def fetch_live_banknifty_price():
    """Fetch live BANK NIFTY price"""
    try:
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.nseindia.com", headers=headers) as resp:
                pass
            
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get('records', {}).get('underlyingValue', 0)
                    if price > 0:
                        print(f"✓ Live BANK NIFTY Price from NSE: ₹{price}")
                        return price
    except Exception as e:
        print(f"⚠ Error fetching BANK NIFTY: {e}")
    
    # Fallback
    now = datetime.now()
    base_price = 46000 + (now.day * 15) + (now.hour * 8)
    price = base_price + random.uniform(-300, 300)
    print(f"⚠ Using simulated BANK NIFTY price: ₹{price:.2f}")
    return price

async def execute_demo_trade():
    """Execute a demo auto trade"""
    print("\n" + "="*70)
    print("          LIVE AUTO TRADING ENGINE - DEMO EXECUTION")
    print("="*70)
    
    now = datetime.now()
    print(f"\n⏰ Current Time: {now.strftime('%I:%M %p, %d %B %Y')}")
    
    market_close = now.replace(hour=15, minute=30, second=0)
    if now > market_close:
        print("⚠ WARNING: Market is CLOSED (closes at 3:30 PM)")
        print("   This is a DEMO trade with simulated execution\n")
    else:
        time_left = market_close - now
        minutes_left = int(time_left.total_seconds() / 60)
        print(f"✓ Market is OPEN - {minutes_left} minutes until close (3:30 PM)\n")
    
    # Enable auto trading
    auto_trader.enabled = True
    
    # Fetch live prices
    print("📊 Fetching Live Market Data...")
    print("-" * 70)
    nifty_price = await fetch_live_nifty_price()
    banknifty_price = await fetch_live_banknifty_price()
    print("-" * 70)
    
    # Test with NIFTY
    print("\n🎯 Analyzing NIFTY with Auto Trading Strategies...")
    print("-" * 70)
    
    market_data = {
        'symbol': 'NIFTY',
        'price': nifty_price,
        'balance': 100000  # Demo balance: ₹1,00,000
    }
    
    # Get signals from all strategies
    signals = auto_trader.analyze_all_strategies(market_data)
    
    print(f"\n📈 Signals Generated: {len(signals)}")
    for i, signal in enumerate(signals, 1):
        print(f"\n  Signal {i}: {signal.strategy_name}")
        print(f"    Action: {signal.action}")
        print(f"    Confidence: {signal.confidence*100:.1f}%")
        print(f"    Entry Price: ₹{signal.entry_price:.2f}")
        print(f"    Stop Loss: ₹{signal.stop_loss:.2f}")
        print(f"    Target: ₹{signal.target_price:.2f}")
        print(f"    Quantity: {signal.quantity}")
        risk = abs(signal.entry_price - signal.stop_loss) * signal.quantity
        reward = abs(signal.target_price - signal.entry_price) * signal.quantity
        print(f"    Risk: ₹{risk:.2f} | Reward: ₹{reward:.2f} | R:R = 1:{reward/risk:.2f}")
    
    # Get best signal
    best_signal = auto_trader.aggregate_signals(signals)
    
    if best_signal:
        print("\n" + "="*70)
        print("🎯 RECOMMENDED TRADE (Best Signal)")
        print("="*70)
        print(f"  Symbol: {best_signal.symbol}")
        print(f"  Action: {best_signal.action}")
        print(f"  Strategy: {best_signal.strategy_name}")
        print(f"  Confidence: {best_signal.confidence*100:.1f}%")
        print(f"  Entry Price: ₹{best_signal.entry_price:.2f}")
        print(f"  Stop Loss: ₹{best_signal.stop_loss:.2f} ({abs(best_signal.entry_price - best_signal.stop_loss)/best_signal.entry_price*100:.2f}%)")
        print(f"  Target Price: ₹{best_signal.target_price:.2f} ({abs(best_signal.target_price - best_signal.entry_price)/best_signal.entry_price*100:.2f}%)")
        print(f"  Quantity: {best_signal.quantity}")
        
        # Calculate potential P&L
        if best_signal.action == 'BUY':
            potential_profit = (best_signal.target_price - best_signal.entry_price) * best_signal.quantity
            potential_loss = (best_signal.entry_price - best_signal.stop_loss) * best_signal.quantity
        else:
            potential_profit = (best_signal.entry_price - best_signal.target_price) * best_signal.quantity
            potential_loss = (best_signal.stop_loss - best_signal.entry_price) * best_signal.quantity
        
        investment = best_signal.entry_price * best_signal.quantity
        
        print(f"\n💰 Financial Analysis:")
        print(f"  Investment: ₹{investment:,.2f}")
        print(f"  Potential Profit: ₹{potential_profit:,.2f} ({potential_profit/investment*100:.2f}%)")
        print(f"  Potential Loss: ₹{potential_loss:,.2f} ({potential_loss/investment*100:.2f}%)")
        print(f"  Risk-Reward Ratio: 1:{potential_profit/potential_loss:.2f}")
        
        # Simulate trade execution
        print("\n" + "="*70)
        print("⚡ EXECUTING DEMO TRADE...")
        print("="*70)
        
        await asyncio.sleep(1)
        
        # Simulate market movement
        exit_scenario = random.choice(['TARGET_HIT', 'STOP_LOSS', 'PARTIAL_PROFIT'])
        
        if exit_scenario == 'TARGET_HIT':
            exit_price = best_signal.target_price
            actual_pnl = potential_profit
            status = "✅ TARGET HIT"
        elif exit_scenario == 'STOP_LOSS':
            exit_price = best_signal.stop_loss
            actual_pnl = -potential_loss
            status = "❌ STOP LOSS"
        else:
            # Partial profit
            if best_signal.action == 'BUY':
                exit_price = best_signal.entry_price + (best_signal.target_price - best_signal.entry_price) * 0.6
            else:
                exit_price = best_signal.entry_price - (best_signal.entry_price - best_signal.target_price) * 0.6
            
            if best_signal.action == 'BUY':
                actual_pnl = (exit_price - best_signal.entry_price) * best_signal.quantity
            else:
                actual_pnl = (best_signal.entry_price - exit_price) * best_signal.quantity
            
            status = "🎯 PARTIAL PROFIT"
        
        print(f"\n{status}")
        print(f"  Entry: ₹{best_signal.entry_price:.2f}")
        print(f"  Exit: ₹{exit_price:.2f}")
        print(f"  Quantity: {best_signal.quantity}")
        print(f"  P&L: ₹{actual_pnl:,.2f}")
        print(f"  Return: {actual_pnl/investment*100:.2f}%")
        
        # Update statistics
        auto_trader.total_trades += 1
        if actual_pnl > 0:
            auto_trader.winning_trades += 1
        else:
            auto_trader.losing_trades += 1
        auto_trader.daily_pnl += actual_pnl
        
        print("\n" + "="*70)
        print("📊 TRADING SESSION SUMMARY")
        print("="*70)
        print(f"  Total Trades: {auto_trader.total_trades}")
        print(f"  Winning Trades: {auto_trader.winning_trades}")
        print(f"  Losing Trades: {auto_trader.losing_trades}")
        if auto_trader.total_trades > 0:
            win_rate = auto_trader.winning_trades / auto_trader.total_trades * 100
            print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Daily P&L: ₹{auto_trader.daily_pnl:,.2f}")
        print("="*70)
        
    else:
        print("\n⚠ No high-confidence trading signal found.")
        print("   Market conditions not favorable for trading.")
        print("   Auto-trader will wait for better opportunities.")
    
    print("\n✓ Demo trade execution completed!\n")

if __name__ == "__main__":
    asyncio.run(execute_demo_trade())
