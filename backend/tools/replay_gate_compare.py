"""
Replay historical signal payloads through old vs new gate policies.

Uses PaperTrade.signal_data as the canonical historical signal store and compares
acceptance rates for both LIVE and DEMO policy variants.

Usage:
  PYTHONPATH=backend python backend/tools/replay_gate_compare.py --days 180
  PYTHONPATH=backend python backend/tools/replay_gate_compare.py --limit 2000 --out backend/tools/gate_replay_report.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.core.database import SessionLocal
from app.models.trading import PaperTrade, TradeReport


@dataclass(frozen=True)
class GatePolicy:
    name: str
    quality_min: float
    confidence_min: float
    ai_edge_min: float
    rr_min: float
    require_both_confirmations: bool
    require_ai_validation: bool
    confirmation_fallback_score: float
    max_fake_move_risk: float
    max_news_risk: float
    max_liquidity_spike_risk: float
    max_premium_distortion: float
    reject_low_volatility: bool
    reject_choppy: bool


OLD_LIVE = GatePolicy(
    name="old_live",
    quality_min=66.0,
    confidence_min=70.0,
    ai_edge_min=35.0,
    rr_min=1.30,
    require_both_confirmations=True,
    require_ai_validation=False,
    confirmation_fallback_score=58.0,
    max_fake_move_risk=16.0,
    max_news_risk=18.0,
    max_liquidity_spike_risk=16.0,
    max_premium_distortion=14.0,
    reject_low_volatility=True,
    reject_choppy=False,
)

NEW_LIVE = GatePolicy(
    name="new_live",
    quality_min=72.0,
    confidence_min=76.0,
    ai_edge_min=42.0,
    rr_min=1.45,
    require_both_confirmations=True,
    require_ai_validation=True,
    confirmation_fallback_score=62.0,
    max_fake_move_risk=14.0,
    max_news_risk=16.0,
    max_liquidity_spike_risk=14.0,
    max_premium_distortion=12.0,
    reject_low_volatility=True,
    reject_choppy=True,
)

# Demo is intentionally aligned with live baseline for parity.
OLD_DEMO = GatePolicy(name="old_demo", **{k: v for k, v in OLD_LIVE.__dict__.items() if k != "name"})
NEW_DEMO = GatePolicy(name="new_demo", **{k: v for k, v in NEW_LIVE.__dict__.items() if k != "name"})


def _num(value: Any, default: float = 0.0) -> float:
    try:
        n = float(value)
        return n
    except Exception:
        return default


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _boolish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def _compute_rr(entry_price: Any, target: Any, stop_loss: Any) -> float:
    try:
        entry = float(entry_price or 0)
        tgt = float(target or 0)
        sl = float(stop_loss or 0)
        risk = abs(entry - sl)
        reward = abs(tgt - entry)
        return (reward / risk) if risk > 0 else 0.0
    except Exception:
        return 0.0


def _evaluate_signal(signal: Dict[str, Any], policy: GatePolicy) -> Tuple[bool, str]:
    quality_raw = signal.get("quality_score")
    if not _has_value(quality_raw):
        quality_raw = signal.get("quality")
    confidence_raw = signal.get("confirmation_score")
    if not _has_value(confidence_raw):
        confidence_raw = signal.get("confidence")
    ai_edge_raw = signal.get("ai_edge_score")
    breakout_score_raw = signal.get("breakout_score")
    momentum_score_raw = signal.get("momentum_score")

    quality = _num(quality_raw)
    confidence = _num(confidence_raw)
    ai_edge = _num(ai_edge_raw)
    breakout_score = _num(breakout_score_raw)
    momentum_score = _num(momentum_score_raw)

    rr_available = _has_value(signal.get("entry_price")) and _has_value(signal.get("target")) and _has_value(signal.get("stop_loss"))
    rr = _compute_rr(signal.get("entry_price"), signal.get("target"), signal.get("stop_loss")) if rr_available else None

    signal_is_stock = signal.get("signal_type") == "stock" or signal.get("is_stock") is True
    quality_min = max(0.0, policy.quality_min - 5.0) if signal_is_stock else policy.quality_min
    confidence_min = max(0.0, policy.confidence_min - 5.0) if signal_is_stock else policy.confidence_min
    ai_edge_min = max(0.0, policy.ai_edge_min - 5.0) if signal_is_stock else policy.ai_edge_min
    rr_min = max(0.0, policy.rr_min - 0.10) if signal_is_stock else policy.rr_min

    if _has_value(quality_raw) and quality < quality_min:
        return False, "quality"
    if _has_value(confidence_raw) and confidence < confidence_min:
        return False, "confidence"
    if _has_value(ai_edge_raw) and ai_edge < ai_edge_min:
        return False, "ai_edge"
    if rr is not None and rr < rr_min:
        return False, "rr"

    breakout_confirmed = _boolish(signal.get("breakout_confirmed"))
    momentum_confirmed = _boolish(signal.get("momentum_confirmed"))
    has_confirmation_context = (
        _has_value(signal.get("breakout_confirmed"))
        or _has_value(signal.get("momentum_confirmed"))
        or _has_value(breakout_score_raw)
        or _has_value(momentum_score_raw)
    )
    if policy.require_both_confirmations and has_confirmation_context:
        breakout_ok = (breakout_confirmed is True) or (
            breakout_confirmed is None and breakout_score >= policy.confirmation_fallback_score
        )
        momentum_ok = (momentum_confirmed is True) or (
            momentum_confirmed is None and momentum_score >= policy.confirmation_fallback_score
        )
        if not (breakout_ok and momentum_ok):
            return False, "confirmations"

    breakout_hold_confirmed = _boolish(signal.get("breakout_hold_confirmed"))
    if breakout_hold_confirmed is False:
        return False, "breakout_hold"

    timing_risk = str(
        signal.get("timing_risk")
        or (signal.get("timing_risk_profile") or {}).get("window")
        or ""
    ).upper()
    if _has_value(signal.get("timing_risk")) and timing_risk == "HIGH":
        return False, "timing_risk"

    market_bias = str(signal.get("market_bias") or signal.get("trend_direction") or "").upper()
    if _has_value(signal.get("market_bias") or signal.get("trend_direction")) and market_bias == "WEAK_BOTH" and not (quality >= 90.0 and confidence >= 92.0):
        return False, "market_bias"

    fake_move_risk = _num(signal.get("fake_move_risk") or signal.get("fake_move_risk_score"))
    news_risk = _num(signal.get("news_risk") or signal.get("sudden_news_risk") or signal.get("news_risk_score"))
    liquidity_spike_risk = _num(signal.get("liquidity_spike_risk") or signal.get("liquidity_spike_risk_score"))
    premium_distortion = _num(signal.get("premium_distortion") or signal.get("premium_distortion_risk") or signal.get("premium_distortion_score"))

    if _has_value(signal.get("fake_move_risk") or signal.get("fake_move_risk_score")) and fake_move_risk > policy.max_fake_move_risk:
        return False, "fake_move_risk"
    if _has_value(signal.get("news_risk") or signal.get("sudden_news_risk") or signal.get("news_risk_score")) and news_risk > policy.max_news_risk:
        return False, "news_risk"
    if _has_value(signal.get("liquidity_spike_risk") or signal.get("liquidity_spike_risk_score")) and liquidity_spike_risk > policy.max_liquidity_spike_risk:
        return False, "liquidity_spike_risk"
    if _has_value(signal.get("premium_distortion") or signal.get("premium_distortion_risk") or signal.get("premium_distortion_score")) and premium_distortion > policy.max_premium_distortion:
        return False, "premium_distortion"

    market_regime = str(signal.get("market_regime") or "").upper()
    if _has_value(signal.get("market_regime")) and policy.reject_low_volatility and market_regime == "LOW_VOLATILITY":
        return False, "low_volatility"
    if _has_value(signal.get("market_regime")) and policy.reject_choppy and market_regime == "CHOPPY":
        return False, "choppy"

    return True, "accepted"


def _build_signal(row: PaperTrade) -> Dict[str, Any]:
    payload = row.signal_data if isinstance(row.signal_data, dict) else {}
    return {
        **payload,
        "entry_price": row.entry_price,
        "target": row.target,
        "stop_loss": row.stop_loss,
        "signal_type": payload.get("signal_type") or row.signal_type,
    }


def _build_live_signal(row: TradeReport) -> Dict[str, Any]:
    meta = row.meta if isinstance(row.meta, dict) else {}
    return {
        **meta,
        "symbol": row.symbol,
        "entry_price": row.entry_price,
        # target/stop are often unavailable in historical live reports.
        "target": meta.get("target"),
        "stop_loss": meta.get("stop_loss"),
    }


def _run_compare(signals: List[Dict[str, Any]], old_policy: GatePolicy, new_policy: GatePolicy) -> Dict[str, Any]:
    old_accept = 0
    new_accept = 0
    kept = 0
    dropped = 0
    newly_allowed = 0
    old_reasons: Counter = Counter()
    new_reasons: Counter = Counter()

    for sig in signals:
        old_ok, old_reason = _evaluate_signal(sig, old_policy)
        new_ok, new_reason = _evaluate_signal(sig, new_policy)

        old_accept += int(old_ok)
        new_accept += int(new_ok)
        old_reasons[old_reason] += 1
        new_reasons[new_reason] += 1

        if old_ok and new_ok:
            kept += 1
        elif old_ok and not new_ok:
            dropped += 1
        elif (not old_ok) and new_ok:
            newly_allowed += 1

    total = max(1, len(signals))
    return {
        "sample_size": len(signals),
        "old_policy": old_policy.name,
        "new_policy": new_policy.name,
        "old_accept_count": old_accept,
        "new_accept_count": new_accept,
        "old_accept_rate": round(old_accept / total, 4),
        "new_accept_rate": round(new_accept / total, 4),
        "delta_accept_count": new_accept - old_accept,
        "delta_accept_rate": round((new_accept - old_accept) / total, 4),
        "kept_count": kept,
        "dropped_count": dropped,
        "newly_allowed_count": newly_allowed,
        "top_old_rejections": old_reasons.most_common(8),
        "top_new_rejections": new_reasons.most_common(8),
    }


def _run_compare_daily(
    records: List[Tuple[datetime, Dict[str, Any]]],
    old_policy: GatePolicy,
    new_policy: GatePolicy,
) -> List[Dict[str, Any]]:
    by_day: Dict[str, Dict[str, int]] = {}
    for ts, sig in records:
        day_key = ts.date().isoformat()
        if day_key not in by_day:
            by_day[day_key] = {
                "signals": 0,
                "old_accept": 0,
                "new_accept": 0,
            }
        old_ok, _ = _evaluate_signal(sig, old_policy)
        new_ok, _ = _evaluate_signal(sig, new_policy)
        by_day[day_key]["signals"] += 1
        by_day[day_key]["old_accept"] += int(old_ok)
        by_day[day_key]["new_accept"] += int(new_ok)

    rows: List[Dict[str, Any]] = []
    for day_key in sorted(by_day.keys()):
        total = max(1, by_day[day_key]["signals"])
        old_accept = by_day[day_key]["old_accept"]
        new_accept = by_day[day_key]["new_accept"]
        rows.append(
            {
                "date": day_key,
                "signals": by_day[day_key]["signals"],
                "old_accept": old_accept,
                "new_accept": new_accept,
                "old_accept_rate": round(old_accept / total, 4),
                "new_accept_rate": round(new_accept / total, 4),
                "delta_accept": new_accept - old_accept,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay gate compare on historical paper signals")
    parser.add_argument("--days", type=int, default=180, help="Lookback window in days")
    parser.add_argument("--limit", type=int, default=5000, help="Max rows to replay")
    parser.add_argument("--out", default="backend/tools/gate_replay_report.json", help="Output JSON file")
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max(1, args.days))

    db = SessionLocal()
    try:
        paper_rows = (
            db.query(PaperTrade)
            .filter(PaperTrade.entry_time >= cutoff)
            .order_by(PaperTrade.entry_time.desc())
            .limit(max(1, args.limit))
            .all()
        )
        live_rows = (
            db.query(TradeReport)
            .filter(TradeReport.exit_time >= cutoff)
            .order_by(TradeReport.exit_time.desc())
            .limit(max(1, args.limit))
            .all()
        )
    finally:
        db.close()

    paper_signals = []
    paper_records: List[Tuple[datetime, Dict[str, Any]]] = []
    for row in paper_rows:
        if not isinstance(row.signal_data, dict):
            continue
        if not row.entry_price or not row.target or not row.stop_loss:
            continue
        sig = _build_signal(row)
        paper_signals.append(sig)
        entry_ts = row.entry_time or row.updated_at or datetime.min
        paper_records.append((entry_ts, sig))

    live_signals = []
    live_records: List[Tuple[datetime, Dict[str, Any]]] = []
    for row in live_rows:
        if not isinstance(row.meta, dict):
            continue
        sig = _build_live_signal(row)
        live_signals.append(sig)
        exit_ts = row.exit_time or row.entry_time or datetime.min
        live_records.append((exit_ts, sig))

    # Prefer native mode datasets; fallback to whichever has usable signals.
    live_replay_signals = live_signals if live_signals else paper_signals
    demo_replay_signals = paper_signals if paper_signals else live_signals
    live_replay_records = live_records if live_records else paper_records
    demo_replay_records = paper_records if paper_records else live_records

    live_compare = _run_compare(live_replay_signals, OLD_LIVE, NEW_LIVE)
    demo_compare = _run_compare(demo_replay_signals, OLD_DEMO, NEW_DEMO)
    live_daily = _run_compare_daily(live_replay_records, OLD_LIVE, NEW_LIVE)
    demo_daily = _run_compare_daily(demo_replay_records, OLD_DEMO, NEW_DEMO)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lookback_days": args.days,
        "limit": args.limit,
        "rows_fetched": {
            "paper_trades": len(paper_rows),
            "live_trade_reports": len(live_rows),
        },
        "signals_replayed": {
            "paper_signals": len(paper_signals),
            "live_signals": len(live_signals),
            "live_replay_source": "live_signals" if live_signals else ("paper_signals" if paper_signals else "none"),
            "demo_replay_source": "paper_signals" if paper_signals else ("live_signals" if live_signals else "none"),
        },
        "live": live_compare,
        "live_daily": live_daily,
        "demo": demo_compare,
        "demo_daily": demo_daily,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))
    print(f"\nSaved replay report: {out_path}")


if __name__ == "__main__":
    main()
