"""
SL-hit analysis script for recent trades.
Run with: PYTHONPATH=backend python backend/tools/sl_analysis.py

This script prints a short report (SL hit rate, avg SL loss, per-symbol breakdown,
hour-of-day analysis, and correlation with signal metrics if available).
"""
from datetime import datetime, timedelta, timezone
import json
from collections import defaultdict, Counter

try:
    from app.core.database import SessionLocal
    from app.models.trading import TradeReport, PaperTrade
except Exception as e:
    print('Failed to import project modules:', e)
    raise


def get_recent_closed_trades(session, days=30):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    # Try both live TradeReport and paper PaperTrade
    trades = []
    try:
        live = session.query(TradeReport).filter(TradeReport.exit_time != None, TradeReport.exit_time >= since).all()
        trades.extend(live)
    except Exception:
        pass
    try:
        paper = session.query(PaperTrade).filter(PaperTrade.exit_time != None, PaperTrade.exit_time >= since).all()
        trades.extend(paper)
    except Exception:
        pass
    return trades


def safe_get(obj, key, default=None):
    try:
        return getattr(obj, key)
    except Exception:
        try:
            return obj.get(key, default)
        except Exception:
            return default


def parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except Exception:
            return None
    return None


def is_simulated_symbol(symbol: str) -> bool:
    s = str(symbol or '').upper()
    return s.startswith('SIM:') or 'TEST' in s


def analyze(trades):
    total = len(trades)
    if total == 0:
        print('No closed trades found in range.')
        return

    sl_hits = [t for t in trades if str(safe_get(t, 'status') or '').upper() == 'SL_HIT']
    target_hits = [t for t in trades if str(safe_get(t, 'status') or '').upper() == 'TARGET_HIT']
    manual = [t for t in trades if str(safe_get(t, 'status') or '').upper() in ('MANUAL_CLOSE','CLOSED','EXPIRED')]
    real_trades = [t for t in trades if not is_simulated_symbol(safe_get(t, 'symbol') or safe_get(t, 'trade_symbol'))]

    def pnl_of(t):
        p = safe_get(t, 'pnl')
        try:
            return float(p or 0)
        except Exception:
            return 0.0

    sl_count = len(sl_hits)
    sl_rate = sl_count / total * 100
    avg_sl_loss = - (sum([pnl_of(t) for t in sl_hits]) / sl_count) if sl_count else 0.0

    by_symbol = defaultdict(lambda: {'count':0,'sl':0,'pnl_sum':0.0})
    by_hour = Counter()
    quality_buckets = defaultdict(lambda: {'count':0,'sl':0})

    for t in trades:
        sym = safe_get(t, 'symbol') or safe_get(t, 'trade_symbol') or 'UNKNOWN'
        status = str(safe_get(t, 'status') or '').upper()
        exit_time = safe_get(t, 'exit_time')
        if exit_time is None:
            continue
        exit_time = parse_dt(exit_time)
        if exit_time:
            hour = exit_time.hour
            by_hour[hour] += 1
        pnl = pnl_of(t)
        by_symbol[sym]['count'] += 1
        by_symbol[sym]['pnl_sum'] += pnl
        if status == 'SL_HIT':
            by_symbol[sym]['sl'] += 1
        # try to get quality/edge from signal_data if present
        sd = safe_get(t, 'signal_data') or safe_get(t, 'signal') or {}
        try:
            q = float(sd.get('quality') or sd.get('quality_score') or sd.get('confirmation_score') or sd.get('confidence') or 0)
        except Exception:
            q = 0
        qb = int(q // 10) * 10
        quality_buckets[qb]['count'] += 1
        if status == 'SL_HIT':
            quality_buckets[qb]['sl'] += 1

    # per-symbol SL rate
    symbol_stats = []
    for s,v in by_symbol.items():
        cnt = v['count']
        sls = v['sl']
        symbol_stats.append({'symbol':s,'trades':cnt,'sl_hits':sls,'sl_rate_pct': (sls/cnt*100) if cnt else 0,'avg_pnl': (v['pnl_sum']/cnt) if cnt else 0})
    symbol_stats.sort(key=lambda x: x['sl_rate_pct'], reverse=True)

    # quality bucket rates
    quality_stats = []
    for k,v in sorted(quality_buckets.items()):
        cnt = v['count']
        sls = v['sl']
        quality_stats.append({'quality_bucket':k,'count':cnt,'sl_hits':sls,'sl_rate_pct': (sls/cnt*100) if cnt else 0})

    report = {
        'period_days': 30,
        'total_closed_trades': total,
        'real_closed_trades': len(real_trades),
        'simulated_or_test_trades': total - len(real_trades),
        'sl_hits': sl_count,
        'sl_rate_pct': round(sl_rate,2),
        'avg_sl_loss': round(avg_sl_loss,2),
        'target_hits': len(target_hits),
        'manual_closes': len(manual),
        'top_symbols_by_sl_rate': symbol_stats[:20],
        'hourly_counts': dict(sorted(by_hour.items())),
        'quality_buckets': quality_stats,
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    session = SessionLocal()
    trades = get_recent_closed_trades(session, days=30)
    analyze(trades)
    session.close()
