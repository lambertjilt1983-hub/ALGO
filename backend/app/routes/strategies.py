from datetime import datetime
from typing import List

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.service import AuthService
from app.core.database import get_db
from app.engine.option_signal_generator import generate_signals_advanced, select_best_signal
from app.models.auth import User
from app.models.schemas import (
    BacktestRequest,
    BacktestResponse,
    StrategyCreate,
    StrategyResponse,
)
from app.models.trading import BacktestResult, Strategy
from app.strategies.backtester import Backtester
from app.strategies.base import StrategyFactory

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("/live/professional-signal")
async def get_live_professional_signal(
    current_user: User = Depends(AuthService.get_current_user),
):
    """Return the same best live signal used by option signals and auto-trade analyze."""
    signals = await generate_signals_advanced(user_id=getattr(current_user, "id", None))
    best = select_best_signal(signals)
    if not best:
        raise HTTPException(status_code=503, detail="No live option signals available.")

    action = (best.get("action") or "HOLD").lower()
    return {
        "symbol": best.get("symbol"),
        "signal": action,
        "entry_price": best.get("entry_price"),
        "stop_loss": best.get("stop_loss"),
        "source": "zerodha_option_chain",
    }


@router.post("/", response_model=StrategyResponse)
def create_strategy(
    payload: StrategyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    strategy = Strategy(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        strategy_type=payload.strategy_type,
        parameters=payload.parameters,
        status="inactive",
        is_live=False,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


@router.get("/", response_model=List[StrategyResponse])
def list_strategies(
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    return (
        db.query(Strategy)
        .filter(Strategy.user_id == current_user.id)
        .order_by(Strategy.created_at.desc())
        .all()
    )


@router.get("/{strategy_id}", response_model=StrategyResponse)
def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == current_user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
def update_strategy(
    strategy_id: int,
    payload: StrategyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == current_user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy.name = payload.name
    strategy.description = payload.description
    strategy.strategy_type = payload.strategy_type
    strategy.parameters = payload.parameters
    db.commit()
    db.refresh(strategy)
    return strategy


@router.delete("/{strategy_id}")
def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == current_user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    db.delete(strategy)
    db.commit()
    return {"message": "Strategy deleted"}


@router.post(
    "/{strategy_id}/backtest",
    response_model=BacktestResponse,
    status_code=status.HTTP_201_CREATED,
)
def backtest_strategy(
    strategy_id: int,
    payload: BacktestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == current_user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        strat = StrategyFactory.create_strategy(strategy.strategy_type, strategy.parameters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Generate a simple synthetic OHLC dataset for backtest window
    try:
        start = pd.to_datetime(payload.start_date)
        end = pd.to_datetime(payload.end_date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date range")

    if start >= end:
        raise HTTPException(status_code=400, detail="Invalid date range")

    dates = pd.date_range(start=start, end=end, freq="D")
    if len(dates) < 10:
        raise HTTPException(status_code=400, detail="Backtest range too short")

    prices = 100 + np.cumsum(np.random.normal(0, 1, len(dates)))
    data = pd.DataFrame(
        {
            "open": prices + np.random.normal(0, 0.5, len(dates)),
            "high": prices + np.random.normal(0.5, 0.5, len(dates)),
            "low": prices - np.random.normal(0.5, 0.5, len(dates)),
            "close": prices,
            "volume": np.random.randint(1000, 5000, len(dates)),
        },
        index=dates,
    )

    backtester = Backtester(strat, initial_capital=payload.initial_capital)
    metrics = backtester.backtest(data, symbol=strategy.name)

    result = BacktestResult(
        strategy_id=strategy.id,
        user_id=current_user.id,
        total_return=metrics.total_return,
        sharpe_ratio=metrics.sharpe_ratio,
        max_drawdown=metrics.max_drawdown,
        win_rate=metrics.win_rate,
        total_trades=metrics.total_trades,
        results_data={"trades": metrics.trades},
        created_at=datetime.utcnow(),
    )
    db.add(result)
    db.commit()

    return {
        "total_return": metrics.total_return,
        "sharpe_ratio": metrics.sharpe_ratio,
        "max_drawdown": metrics.max_drawdown,
        "win_rate": metrics.win_rate,
        "total_trades": metrics.total_trades,
        "created_at": result.created_at,
    }
