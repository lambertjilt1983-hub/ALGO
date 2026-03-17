"""
Walk-forward backtest runner using existing strategy + backtester.

Usage examples:
  PYTHONPATH=backend python backend/tools/walkforward_backtest.py --ticker ^NSEI --strategy ma_crossover
  PYTHONPATH=backend python backend/tools/walkforward_backtest.py --ticker ^NSEBANK --strategy momentum --period 5y
  PYTHONPATH=backend python backend/tools/walkforward_backtest.py --csv data/nifty_ohlcv.csv --strategy intraday_professional

CSV must contain OHLCV columns: open, high, low, close, volume (any case).
Optional events CSV format: timestamp,event (ISO-8601 timestamp).
"""

from __future__ import annotations

import argparse
import itertools
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from app.strategies.base import StrategyFactory
from app.strategies.backtester import Backtester, BacktestMetrics


class EntryGuardAtrWrapper:
    """Wraps a strategy to enforce event blackout and ATR-based SL/TP sizing."""

    def __init__(
        self,
        base_strategy: Any,
        events: pd.DataFrame,
        event_blackout_days: int = 0,
        use_atr_wrapper: bool = False,
        atr_period: int = 14,
        atr_mult: float = 1.5,
        tp_mult: float = 2.0,
    ) -> None:
        self.base = base_strategy
        self.name = getattr(base_strategy, "name", "wrapped_strategy")
        self.parameters = getattr(base_strategy, "parameters", {})
        self.events = events if isinstance(events, pd.DataFrame) else pd.DataFrame(columns=["timestamp", "event"])
        self.event_blackout_days = int(max(0, event_blackout_days))
        self.use_atr_wrapper = bool(use_atr_wrapper)
        self.atr_period = int(max(2, atr_period))
        self.atr_mult = float(max(0.1, atr_mult))
        self.tp_mult = float(max(0.5, tp_mult))

    def validate_data(self, data: pd.DataFrame) -> bool:
        return self.base.validate_data(data)

    def _is_event_blackout(self, ts: Any) -> bool:
        if self.event_blackout_days <= 0 or self.events.empty:
            return False
        dt = pd.to_datetime(ts, errors="coerce")
        if pd.isna(dt):
            return False
        win = pd.Timedelta(days=self.event_blackout_days)
        near = self.events[
            (self.events["timestamp"] >= (dt - win))
            & (self.events["timestamp"] <= (dt + win))
        ]
        return not near.empty

    def _atr(self, data: pd.DataFrame) -> float:
        if len(data) < (self.atr_period + 2):
            return 0.0
        high = data["high"].astype(float)
        low = data["low"].astype(float)
        close = data["close"].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                (high - low).abs(),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(self.atr_period).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else 0.0

    def generate_signal(self, data: pd.DataFrame):
        signal = self.base.generate_signal(data)

        current_ts = data.index[-1] if len(data) > 0 else None
        if signal.action == "buy" and self._is_event_blackout(current_ts):
            signal.action = "hold"
            signal.strength = 0.0
            signal.stop_loss = None
            signal.take_profit = None
            return signal

        if self.use_atr_wrapper and signal.action == "buy":
            atr_val = self._atr(data)
            entry = float(signal.entry_price or data["close"].iloc[-1])
            if atr_val > 0 and entry > 0:
                signal.entry_price = entry
                signal.stop_loss = entry - (atr_val * self.atr_mult)
                signal.take_profit = entry + (atr_val * self.atr_mult * self.tp_mult)

        return signal


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {c: str(c).strip().lower() for c in df.columns}
    df = df.rename(columns=rename_map)
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    out = df[required].copy()
    out = out.apply(pd.to_numeric, errors="coerce").dropna()
    return out


def load_price_data(csv_path: str | None, ticker: str | None, period: str, interval: str) -> pd.DataFrame:
    if csv_path:
        df = pd.read_csv(csv_path)
        # Try common datetime columns
        for candidate in ["datetime", "date", "timestamp", "time"]:
            if candidate in df.columns:
                df[candidate] = pd.to_datetime(df[candidate], errors="coerce")
                df = df.set_index(candidate)
                break
        if not isinstance(df.index, pd.DatetimeIndex):
            # fallback to range index if no datetime available
            df.index = pd.RangeIndex(start=0, stop=len(df), step=1)
        return normalize_ohlcv(df)

    if not ticker:
        raise ValueError("Provide either --csv or --ticker")

    try:
        import yfinance as yf
    except Exception as exc:
        raise RuntimeError("yfinance is not installed. Install with: pip install yfinance") from exc

    raw = yf.download(ticker, period=period, interval=interval, auto_adjust=False, progress=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"No data returned for ticker={ticker}, period={period}, interval={interval}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]

    raw = raw.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    return normalize_ohlcv(raw)


def default_param_grid(strategy_type: str) -> List[Dict[str, Any]]:
    st = strategy_type.lower()
    if st == "ma_crossover":
        grid = {
            "fast_period": [9, 12, 20],
            "slow_period": [21, 50, 100],
            "stop_loss_percent": [1.5, 2.0, 2.5],
            "take_profit_percent": [3.0, 5.0, 7.0],
        }
    elif st == "momentum":
        grid = {
            "period": [5, 10, 20],
            "threshold": [0.01, 0.02, 0.03],
        }
    elif st == "rsi":
        grid = {
            "period": [14],
            "overbought": [70, 75],
            "oversold": [25, 30],
        }
    elif st == "intraday_professional":
        grid = {"capital": [100000, 200000]}
    else:
        raise ValueError(f"Unsupported strategy_type: {strategy_type}")

    keys = list(grid.keys())
    values = [grid[k] for k in keys]
    combos = []
    for row in itertools.product(*values):
        combos.append({k: v for k, v in zip(keys, row)})
    return combos


def parse_float_list(csv_value: str, fallback: List[float]) -> List[float]:
    if not csv_value:
        return fallback
    out: List[float] = []
    for part in str(csv_value).split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.append(float(p))
        except Exception:
            continue
    return out or fallback


def build_param_grid(
    strategy_type: str,
    use_atr_wrapper: bool,
    atr_mults: List[float],
    tp_mults: List[float],
) -> List[Dict[str, Any]]:
    base_grid = default_param_grid(strategy_type)
    if not use_atr_wrapper:
        return base_grid
    merged: List[Dict[str, Any]] = []
    for p in base_grid:
        for am in atr_mults:
            for tm in tp_mults:
                merged.append({**p, "atr_mult": float(am), "tp_mult": float(tm)})
    return merged


def run_backtest_once(
    strategy_type: str,
    params: Dict[str, Any],
    df: pd.DataFrame,
    symbol: str,
    events: pd.DataFrame,
    event_blackout_days: int = 0,
    use_atr_wrapper: bool = False,
    atr_period: int = 14,
) -> BacktestMetrics:
    base_params = {k: v for k, v in params.items() if k not in {"atr_mult", "tp_mult"}}
    strategy = StrategyFactory.create_strategy(strategy_type, {**base_params, "symbol": symbol})
    strategy = EntryGuardAtrWrapper(
        base_strategy=strategy,
        events=events,
        event_blackout_days=event_blackout_days,
        use_atr_wrapper=use_atr_wrapper,
        atr_period=atr_period,
        atr_mult=float(params.get("atr_mult", 1.5)),
        tp_mult=float(params.get("tp_mult", 2.0)),
    )
    engine = Backtester(strategy, initial_capital=100000)
    return engine.backtest(df, symbol=symbol)


def choose_best_params(
    strategy_type: str,
    param_grid: List[Dict[str, Any]],
    train_df: pd.DataFrame,
    symbol: str,
    events: pd.DataFrame,
    event_blackout_days: int = 0,
    use_atr_wrapper: bool = False,
    atr_period: int = 14,
) -> Tuple[Dict[str, Any], BacktestMetrics]:
    best_params = param_grid[0]
    best_metrics = run_backtest_once(
        strategy_type,
        best_params,
        train_df,
        symbol,
        events,
        event_blackout_days,
        use_atr_wrapper,
        atr_period,
    )
    best_score = (best_metrics.sharpe_ratio, best_metrics.total_return, best_metrics.win_rate)

    for params in param_grid[1:]:
        m = run_backtest_once(
            strategy_type,
            params,
            train_df,
            symbol,
            events,
            event_blackout_days,
            use_atr_wrapper,
            atr_period,
        )
        score = (m.sharpe_ratio, m.total_return, m.win_rate)
        if score > best_score:
            best_params, best_metrics, best_score = params, m, score

    return best_params, best_metrics


def summarize_windows(windows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not windows:
        return {
            "windows": 0,
            "avg_test_win_rate": 0.0,
            "avg_test_sharpe": 0.0,
            "avg_test_return": 0.0,
            "total_test_trades": 0,
            "weighted_test_win_rate": 0.0,
        }

    total_trades = sum(int(w["test"]["total_trades"]) for w in windows)
    weighted_wins = sum(float(w["test"]["win_rate"]) * int(w["test"]["total_trades"]) for w in windows)

    return {
        "windows": len(windows),
        "avg_test_win_rate": round(sum(float(w["test"]["win_rate"]) for w in windows) / len(windows), 4),
        "avg_test_sharpe": round(sum(float(w["test"]["sharpe_ratio"]) for w in windows) / len(windows), 4),
        "avg_test_return": round(sum(float(w["test"]["total_return"]) for w in windows) / len(windows), 4),
        "total_test_trades": total_trades,
        "weighted_test_win_rate": round((weighted_wins / total_trades), 4) if total_trades > 0 else 0.0,
    }


def load_events(events_csv: str | None) -> pd.DataFrame:
    if not events_csv:
        return pd.DataFrame(columns=["timestamp", "event"])
    path = Path(events_csv)
    if not path.exists():
        raise FileNotFoundError(f"Events CSV not found: {events_csv}")
    ev = pd.read_csv(path)
    if "timestamp" not in ev.columns:
        raise ValueError("events CSV must include 'timestamp' column")
    ev["timestamp"] = pd.to_datetime(ev["timestamp"], errors="coerce")
    ev = ev.dropna(subset=["timestamp"]).sort_values("timestamp")
    if "event" not in ev.columns:
        ev["event"] = "macro_event"
    return ev[["timestamp", "event"]]


def count_trades_near_events(trades: List[Dict[str, Any]], events: pd.DataFrame, days_window: int = 1) -> int:
    if events.empty or not trades:
        return 0
    count = 0
    for t in trades:
        ts = t.get("entry_time") or t.get("exit_time")
        if ts is None:
            continue
        t_dt = pd.to_datetime(ts, errors="coerce")
        if pd.isna(t_dt):
            continue
        near = events[(events["timestamp"] >= t_dt - pd.Timedelta(days=days_window)) & (events["timestamp"] <= t_dt + pd.Timedelta(days=days_window))]
        if not near.empty:
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward backtest for existing ALGO strategies")
    parser.add_argument("--strategy", default="ma_crossover", choices=["ma_crossover", "momentum", "rsi", "intraday_professional"])
    parser.add_argument("--ticker", default="^NSEI", help="Yahoo ticker (ignored when --csv is provided)")
    parser.add_argument("--symbol", default=None, help="Symbol label in reports (defaults to ticker)")
    parser.add_argument("--csv", default=None, help="Path to OHLCV CSV")
    parser.add_argument("--events-csv", default=None, help="Optional macro events CSV with columns timestamp,event")
    parser.add_argument("--event-blackout-days", type=int, default=0, help="Block fresh entries ±N days around macro events")
    parser.add_argument("--use-atr-wrapper", action="store_true", help="Use ATR-based dynamic SL/TP sizing on buy entries")
    parser.add_argument("--atr-period", type=int, default=14, help="ATR period for dynamic SL/TP")
    parser.add_argument("--atr-mults", default="1.2,1.5,1.8", help="Comma-separated ATR multipliers for SL grid")
    parser.add_argument("--tp-mults", default="2.0,2.5,3.0", help="Comma-separated TP multipliers on ATR risk")
    parser.add_argument("--period", default="5y", help="Yahoo download period, e.g., 5y")
    parser.add_argument("--interval", default="1d", help="Yahoo interval, e.g., 1d, 1h")
    parser.add_argument("--train-bars", type=int, default=504, help="Bars in each training window")
    parser.add_argument("--test-bars", type=int, default=126, help="Bars in each testing window")
    parser.add_argument("--step-bars", type=int, default=126, help="Window step size")
    parser.add_argument("--out", default="backend/tools/walkforward_result.json", help="Output JSON file")
    args = parser.parse_args()

    symbol = args.symbol or (args.ticker if args.ticker else "CSV")
    data = load_price_data(args.csv, args.ticker, args.period, args.interval)
    events = load_events(args.events_csv)

    if len(data) < (args.train_bars + args.test_bars + 50):
        raise RuntimeError(
            f"Insufficient bars: have={len(data)}, need at least {args.train_bars + args.test_bars + 50}. "
            "Use longer period or smaller train/test bars."
        )

    atr_mults = parse_float_list(args.atr_mults, [1.2, 1.5, 1.8])
    tp_mults = parse_float_list(args.tp_mults, [2.0, 2.5, 3.0])
    param_grid = build_param_grid(args.strategy, args.use_atr_wrapper, atr_mults, tp_mults)

    windows: List[Dict[str, Any]] = []
    i = 0
    while i + args.train_bars + args.test_bars <= len(data):
        train_df = data.iloc[i : i + args.train_bars]
        test_df = data.iloc[i + args.train_bars : i + args.train_bars + args.test_bars]

        best_params, train_metrics = choose_best_params(
            args.strategy,
            param_grid,
            train_df,
            symbol,
            events,
            args.event_blackout_days,
            args.use_atr_wrapper,
            args.atr_period,
        )
        test_metrics = run_backtest_once(
            args.strategy,
            best_params,
            test_df,
            symbol,
            events,
            args.event_blackout_days,
            args.use_atr_wrapper,
            args.atr_period,
        )

        trades_near_events = count_trades_near_events(test_metrics.trades, events)

        windows.append(
            {
                "window": len(windows) + 1,
                "train_start": str(train_df.index[0]),
                "train_end": str(train_df.index[-1]),
                "test_start": str(test_df.index[0]),
                "test_end": str(test_df.index[-1]),
                "best_params": best_params,
                "train": {
                    "total_return": float(train_metrics.total_return),
                    "sharpe_ratio": float(train_metrics.sharpe_ratio),
                    "max_drawdown": float(train_metrics.max_drawdown),
                    "win_rate": float(train_metrics.win_rate),
                    "total_trades": int(train_metrics.total_trades),
                },
                "test": {
                    "total_return": float(test_metrics.total_return),
                    "sharpe_ratio": float(test_metrics.sharpe_ratio),
                    "max_drawdown": float(test_metrics.max_drawdown),
                    "win_rate": float(test_metrics.win_rate),
                    "total_trades": int(test_metrics.total_trades),
                    "losing_trades": int(test_metrics.losing_trades),
                    "winning_trades": int(test_metrics.winning_trades),
                    "sl_like_loss_rate": float(test_metrics.losing_trades / max(test_metrics.total_trades, 1)),
                    "trades_near_events": int(trades_near_events),
                },
            }
        )

        i += args.step_bars

    summary = summarize_windows(windows)

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "strategy": args.strategy,
        "symbol": symbol,
        "data": {
            "bars": len(data),
            "start": str(data.index[0]),
            "end": str(data.index[-1]),
            "source": args.csv or f"yfinance:{args.ticker}",
            "interval": args.interval,
        },
        "walkforward": {
            "train_bars": args.train_bars,
            "test_bars": args.test_bars,
            "step_bars": args.step_bars,
            "event_blackout_days": args.event_blackout_days,
            "use_atr_wrapper": bool(args.use_atr_wrapper),
            "atr_period": args.atr_period,
            "atr_mults": atr_mults,
            "tp_mults": tp_mults,
            "windows": windows,
            "summary": summary,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload["walkforward"]["summary"], indent=2))
    print(f"\nSaved full report to: {out_path}")


if __name__ == "__main__":
    main()
