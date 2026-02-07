import sys
sys.path.insert(0, 'F:/ALGO/backend')
from app.core.database import SessionLocal
from app.models.trading import PaperTrade
from datetime import datetime, timedelta

db = SessionLocal()
all_trades = db.query(PaperTrade).order_by(PaperTrade.entry_time.desc()).limit(100).all()
print(f'Total paper trades in DB (last 100): {len(all_trades)}')

closed = [t for t in all_trades if t.status in ['TARGET_HIT', 'SL_HIT', 'EXPIRED']]
wins = [t for t in closed if t.status == 'TARGET_HIT']
losses = [t for t in closed if t.status == 'SL_HIT']

print(f'Closed: {len(closed)}, Wins: {len(wins)}, Losses: {len(losses)}')
if closed:
    print(f'Win Rate: {len(wins)/len(closed)*100:.1f}%')
    
    total_pnl = sum(t.pnl or 0 for t in closed)
    avg_win = sum(t.pnl or 0 for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.pnl or 0 for t in losses) / len(losses) if losses else 0
    
    print(f'Total P&L: ₹{total_pnl:.2f}')
    print(f'Avg Win: ₹{avg_win:.2f}, Avg Loss: ₹{avg_loss:.2f}')
    print(f'Risk:Reward: 1:{abs(avg_win/avg_loss):.2f}' if avg_loss else 'N/A')
    
    print('\n' + '='*140)
    print('Recent 15 closed trades:')
    print('='*140)
    print(f"{'ID':<6} {'Symbol':<30} {'Side':<5} {'Entry':>10} {'SL':>10} {'Target':>10} {'PnL':>10} {'Status':<12} {'Entry Time'}")
    print('-'*140)
    for t in closed[:15]:
        print(f"{t.id:<6} {t.symbol[:29]:<30} {t.side:<5} {t.entry_price:>10.2f} {t.stop_loss or 0:>10.2f} {t.target or 0:>10.2f} {t.pnl or 0:>10.2f} {t.status:<12} {t.entry_time.strftime('%Y-%m-%d %H:%M')}")

db.close()
