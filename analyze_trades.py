"""Analyze recent trading performance"""
import sys
sys.path.insert(0, 'F:/ALGO/backend')

from app.core.database import SessionLocal
from app.models.trading import TradeReport, PaperTrade
from datetime import datetime, timedelta

db = SessionLocal()
try:
    yesterday = datetime.now() - timedelta(days=1)
    
    # Query both PaperTrade and TradeReport
    paper_trades = db.query(PaperTrade).filter(
        PaperTrade.entry_time >= yesterday
    ).order_by(PaperTrade.entry_time.desc()).all()
    
    trade_reports = db.query(TradeReport).filter(
        TradeReport.exit_time >= yesterday
    ).order_by(TradeReport.exit_time.desc()).all()
    
    print(f"\n{'='*120}")
    print(f"RECENT TRADES ANALYSIS (Last 24 hours)")
    print(f"{'='*120}\n")
    print(f"Paper Trades: {len(paper_trades)}")
    print(f"Trade Reports: {len(trade_reports)}")
    
    # Analyze Paper Trades
    if paper_trades:
        wins = [t for t in paper_trades if t.status == 'TARGET_HIT']
        losses = [t for t in paper_trades if t.status == 'SL_HIT']
        open_trades = [t for t in paper_trades if t.status == 'OPEN']
        
        print(f"\nPAPER TRADES:")
        print(f"  Wins: {len(wins)}")
        print(f"  Losses: {len(losses)}")
        print(f"  Open: {len(open_trades)}")
        
        if (len(wins) + len(losses)) > 0:
            win_rate = len(wins) / (len(wins) + len(losses)) * 100
            print(f"  Win Rate: {win_rate:.1f}%")
        
        # P&L analysis
        total_pnl = sum(float(t.pnl or 0) for t in paper_trades if t.pnl is not None)
        avg_win = sum(float(t.pnl or 0) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(float(t.pnl or 0) for t in losses) / len(losses) if losses else 0
        
        print(f"  Total P&L: ₹{total_pnl:.2f}")
        print(f"  Average Win: ₹{avg_win:.2f}")
        print(f"  Average Loss: ₹{avg_loss:.2f}")
        
        if avg_loss != 0:
            risk_reward = abs(avg_win / avg_loss)
            print(f"  Risk:Reward Ratio: 1:{risk_reward:.2f}")
        
        # Recent trades table
        print(f"\n{'='*140}")
        print("RECENT PAPER TRADES (Last 20 closed):")
        print(f"{'='*140}")
        print(f"{'ID':<6} {'Symbol':<30} {'Side':<5} {'Entry':>10} {'Exit':>10} {'SL':>10} {'Target':>10} {'PnL':>10} {'Status':<15} {'Time'}")
        print(f"{'-'*140}")
        
        closed = [t for t in paper_trades if t.status in ['TARGET_HIT', 'SL_HIT', 'EXPIRED']][:20]
        for t in closed:
            pnl_str = f"₹{float(t.pnl or 0):.2f}" if t.pnl else "N/A"
            exit_price = float(t.exit_price) if t.exit_price else 0
            print(f"{t.id:<6} {t.symbol[:29]:<30} {t.side:<5} {float(t.entry_price):>10.2f} {exit_price:>10.2f} {float(t.stop_loss or 0):>10.2f} {float(t.target or 0):>10.2f} {pnl_str:>10} {t.status:<15} {t.entry_time.strftime('%H:%M:%S')}")
        
        # Problem analysis
        print(f"\n{'='*120}")
        print("PROBLEM ANALYSIS:")
        print(f"{'='*120}")
        
        if len(losses) > len(wins):
            print("⚠️ More losses than wins!")
            if losses:
                print(f"\nTotal stop losses hit: {len(losses)}")
                
                # Check if stops are too tight
                stop_distances = []
                for t in losses:
                    if t.stop_loss and t.entry_price:
                        dist = abs(float(t.entry_price) - float(t.stop_loss)) / float(t.entry_price) * 100
                        stop_distances.append(dist)
                
                if stop_distances:
                    avg_stop_dist = sum(stop_distances) / len(stop_distances)
                    print(f"  - Average stop distance: {avg_stop_dist:.2f}%")
                    if avg_stop_dist < 0.5:
                        print(f"  ⚠️ Stops are TOO TIGHT! Consider 0.8-1.0% minimum")
                
        if avg_loss and abs(avg_loss) > avg_win:
            print("⚠️ Average loss is larger than average win!")
            print("  - Current risk:reward is unfavorable")
            print("  - Consider: Wider stops (0.8-1%), tighter entry timing")
        
        if (len(wins) + len(losses)) > 0:
            win_rate_val = len(wins) / (len(wins) + len(losses)) * 100
            if win_rate_val < 50:
                print(f"⚠️ Win rate below 50% ({win_rate_val:.1f}%)!")
                print("  - Signal quality needs improvement")
                print("  - Add momentum filters, check RSI range")
                print("  - Avoid choppy/sideways markets")
        
        # Signal quality analysis
        print(f"\n{'='*120}")
        print("SIGNAL QUALITY ANALYSIS:")
        print(f"{'='*120}")
        
        # Check entry times - are we entering at bad times?
        morning_trades = [t for t in closed if t.entry_time and t.entry_time.hour < 11]
        afternoon_trades = [t for t in closed if t.entry_time and 11 <= t.entry_time.hour < 14]
        late_trades = [t for t in closed if t.entry_time and t.entry_time.hour >= 14]
        
        print(f"Morning trades (9-11): {len(morning_trades)}")
        print(f"Afternoon trades (11-14): {len(afternoon_trades)}")
        print(f"Late trades (14+): {len(late_trades)}")
        
        # Check signal types
        ce_trades = [t for t in closed if 'CE' in (t.symbol or '')]
        pe_trades = [t for t in closed if 'PE' in (t.symbol or '')]
        
        ce_wins = sum(1 for t in ce_trades if t.status == 'TARGET_HIT')
        pe_wins = sum(1 for t in pe_trades if t.status == 'TARGET_HIT')
        
        print(f"\nCE trades: {len(ce_trades)} (Wins: {ce_wins}, Rate: {ce_wins/len(ce_trades)*100:.1f}%)" if ce_trades else "CE trades: 0")
        print(f"PE trades: {len(pe_trades)} (Wins: {pe_wins}, Rate: {pe_wins/len(pe_trades)*100:.1f}%)" if pe_trades else "PE trades: 0")

finally:
    db.close()
