"""
Multiple Auto Trades Demo - Show Win/Loss Distribution
"""

import asyncio
from test_live_trade import fetch_live_nifty_price, fetch_live_banknifty_price
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.strategies.auto_trader import auto_trader
from datetime import datetime
import random

async def run_multiple_trades(num_trades=5):
    """Run multiple demo trades to show statistics"""
    print("\n" + "="*80)
    print("     AUTO TRADING ENGINE - MULTIPLE TRADES DEMO")
    print("="*80)
    
    now = datetime.now()
    print(f"\n⏰ Demo Time: {now.strftime('%I:%M %p, %d %B %Y')}")
    print(f"📊 Executing {num_trades} Demo Trades...\n")
    
    # Reset statistics
    auto_trader.enabled = True
    auto_trader.total_trades = 0
    auto_trader.winning_trades = 0
    auto_trader.losing_trades = 0
    auto_trader.daily_pnl = 0.0
    
    starting_balance = 100000
    current_balance = starting_balance
    
    trades_summary = []
    
    for i in range(num_trades):
        print(f"\n{'─'*80}")
        print(f"🎯 TRADE #{i+1}/{num_trades}")
        print(f"{'─'*80}")
        
        # Fetch prices
        if i % 2 == 0:
            symbol = 'NIFTY'
            price = await fetch_live_nifty_price()
        else:
            symbol = 'BANKNIFTY'
            price = await fetch_live_banknifty_price()
        
        print(f"\n📊 Analyzing {symbol} at ₹{price:.2f}")
        
        # Analyze market
        market_data = {
            'symbol': symbol,
            'price': price,
            'balance': current_balance
        }
        
        signals = auto_trader.analyze_all_strategies(market_data)
        best_signal = auto_trader.aggregate_signals(signals)
        
        if not best_signal:
            print(f"⚠ No signal - Skipping trade {i+1}")
            continue
        
        print(f"  ✓ Signal: {best_signal.action} - Confidence: {best_signal.confidence*100:.1f}%")
        print(f"  ✓ Entry: ₹{best_signal.entry_price:.2f}")
        print(f"  ✓ Target: ₹{best_signal.target_price:.2f}")
        print(f"  ✓ Stop Loss: ₹{best_signal.stop_loss:.2f}")
        print(f"  ✓ Quantity: {best_signal.quantity}")
        
        investment = best_signal.entry_price * best_signal.quantity
        
        # Simulate execution
        exit_scenario = random.choice(['TARGET', 'TARGET', 'STOP', 'PARTIAL', 'PARTIAL'])
        
        if exit_scenario == 'TARGET':
            exit_price = best_signal.target_price
            if best_signal.action == 'BUY':
                pnl = (exit_price - best_signal.entry_price) * best_signal.quantity
            else:
                pnl = (best_signal.entry_price - exit_price) * best_signal.quantity
            status = "✅ TARGET"
        elif exit_scenario == 'STOP':
            exit_price = best_signal.stop_loss
            if best_signal.action == 'BUY':
                pnl = (exit_price - best_signal.entry_price) * best_signal.quantity
            else:
                pnl = (best_signal.entry_price - exit_price) * best_signal.quantity
            status = "❌ STOP LOSS"
        else:
            # Partial profit
            pct = random.uniform(0.5, 0.8)
            if best_signal.action == 'BUY':
                exit_price = best_signal.entry_price + (best_signal.target_price - best_signal.entry_price) * pct
                pnl = (exit_price - best_signal.entry_price) * best_signal.quantity
            else:
                exit_price = best_signal.entry_price - (best_signal.entry_price - best_signal.target_price) * pct
                pnl = (best_signal.entry_price - exit_price) * best_signal.quantity
            status = "🎯 PARTIAL"
        
        pnl_pct = (pnl / investment) * 100
        
        print(f"\n  {status}")
        print(f"  Exit: ₹{exit_price:.2f}")
        print(f"  P&L: ₹{pnl:,.2f} ({pnl_pct:+.2f}%)")
        
        # Update stats
        auto_trader.total_trades += 1
        current_balance += pnl
        auto_trader.daily_pnl += pnl
        
        if pnl > 0:
            auto_trader.winning_trades += 1
        else:
            auto_trader.losing_trades += 1
        
        trades_summary.append({
            'trade_num': i+1,
            'symbol': symbol,
            'action': best_signal.action,
            'entry': best_signal.entry_price,
            'exit': exit_price,
            'qty': best_signal.quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'status': status
        })
        
        await asyncio.sleep(0.5)
    
    # Final Summary
    print(f"\n\n{'═'*80}")
    print(f"📊 FINAL TRADING SESSION SUMMARY")
    print(f"{'═'*80}")
    
    print(f"\n💰 FINANCIAL PERFORMANCE:")
    print(f"  Starting Balance:  ₹{starting_balance:,.2f}")
    print(f"  Ending Balance:    ₹{current_balance:,.2f}")
    print(f"  Total P&L:         ₹{auto_trader.daily_pnl:,.2f}")
    print(f"  Return:            {(auto_trader.daily_pnl/starting_balance)*100:+.2f}%")
    
    print(f"\n📈 TRADE STATISTICS:")
    print(f"  Total Trades:      {auto_trader.total_trades}")
    print(f"  Winning Trades:    {auto_trader.winning_trades}")
    print(f"  Losing Trades:     {auto_trader.losing_trades}")
    
    if auto_trader.total_trades > 0:
        win_rate = (auto_trader.winning_trades / auto_trader.total_trades) * 100
        print(f"  Win Rate:          {win_rate:.1f}%")
        avg_pnl = auto_trader.daily_pnl / auto_trader.total_trades
        print(f"  Average P&L:       ₹{avg_pnl:,.2f}")
    
    # Trade-by-trade breakdown
    print(f"\n📋 TRADE-BY-TRADE BREAKDOWN:")
    print(f"{'─'*80}")
    print(f"  #  Symbol       Action  Entry       Exit        Qty   P&L         Status")
    print(f"{'─'*80}")
    
    for t in trades_summary:
        print(f"  {t['trade_num']}  {t['symbol']:<11} {t['action']:<6}  "
              f"₹{t['entry']:>8.2f}  ₹{t['exit']:>8.2f}  {t['qty']:<3}   "
              f"₹{t['pnl']:>8.2f}  {t['status']}")
    
    print(f"{'─'*80}")
    
    # Performance Rating
    print(f"\n⭐ PERFORMANCE RATING:")
    if auto_trader.daily_pnl > 0:
        if win_rate >= 60:
            rating = "🌟🌟🌟🌟🌟 EXCELLENT"
        elif win_rate >= 50:
            rating = "🌟🌟🌟🌟 GOOD"
        else:
            rating = "🌟🌟🌟 FAIR"
    else:
        rating = "🌟🌟 NEEDS IMPROVEMENT"
    
    print(f"  {rating}")
    print(f"\n{'═'*80}\n")

if __name__ == "__main__":
    asyncio.run(run_multiple_trades(5))
