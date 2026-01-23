from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.auth.service import AuthService
from app.models.schemas import StrategyCreate, StrategyResponse, BacktestRequest, BacktestResponse
from app.models.auth import User
from app.models.trading import Strategy, BacktestResult
from app.core.database import get_db
from app.strategies.base import StrategyFactory
from app.strategies.backtester import Backtester
from app.core.logger import logger
import pandas as pd
from datetime import datetime

router = APIRouter(prefix="/strategies", tags=["strategies"])

@router.post("/", response_model=StrategyResponse)
async def create_strategy(
    strategy_data: StrategyCreate,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Create a new trading strategy"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    strategy = Strategy(
        user_id=user_id,
        name=strategy_data.name,
        description=strategy_data.description,
        strategy_type=strategy_data.strategy_type,
        parameters=strategy_data.parameters
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy

@router.get("/", response_model=List[StrategyResponse])
async def list_strategies(
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """List all strategies for current user"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    strategies = db.query(Strategy).filter(Strategy.user_id == user_id).all()
    return strategies

@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Get strategy details"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    strategy = db.query(Strategy).filter(
        (Strategy.id == strategy_id) & (Strategy.user_id == user_id)
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    return strategy

@router.post("/{strategy_id}/backtest", response_model=BacktestResponse)
async def backtest_strategy(
    strategy_id: int,
    backtest_req: BacktestRequest,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Backtest a strategy"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    strategy = db.query(Strategy).filter(
        (Strategy.id == strategy_id) & (Strategy.user_id == user_id)
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    try:
        # Create strategy instance
        strat = StrategyFactory.create_strategy(
            strategy.strategy_type,
            strategy.parameters
        )
        
        # Create sample data (in production, fetch from data provider)
        # This is a placeholder - replace with actual historical data
        dates = pd.date_range(start=backtest_req.start_date, end=backtest_req.end_date)
        data = pd.DataFrame({
            "open": [100 + i*0.1 for i in range(len(dates))],
            "high": [101 + i*0.1 for i in range(len(dates))],
            "low": [99 + i*0.1 for i in range(len(dates))],
            "close": [100.5 + i*0.1 for i in range(len(dates))],
            "volume": [1000000] * len(dates)
        }, index=dates)
        
        # Run backtest
        backtester = Backtester(strat, backtest_req.initial_capital)
        metrics = backtester.backtest(data)
        
        # Store results
        result = BacktestResult(
            strategy_id=strategy_id,
            user_id=user_id,
            total_return=metrics.total_return,
            sharpe_ratio=metrics.sharpe_ratio,
            max_drawdown=metrics.max_drawdown,
            win_rate=metrics.win_rate,
            total_trades=metrics.total_trades,
            results_data={
                "annual_return": metrics.annual_return,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "avg_win": metrics.avg_win,
                "avg_loss": metrics.avg_loss,
                "profit_factor": metrics.profit_factor
            }
        )
        
        db.add(result)
        db.commit()
        db.refresh(result)
        
        logger.log_trade({
            "strategy": strategy.name,
            "backtest": "completed",
            "total_return": metrics.total_return
        })
        
        return result
    except Exception as e:
        logger.log_error("Backtest failed", {"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    strategy_data: StrategyCreate,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Update strategy"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    strategy = db.query(Strategy).filter(
        (Strategy.id == strategy_id) & (Strategy.user_id == user_id)
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    strategy.name = strategy_data.name
    strategy.description = strategy_data.description
    strategy.parameters = strategy_data.parameters
    strategy.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(strategy)
    return strategy

@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Delete strategy"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    strategy = db.query(Strategy).filter(
        (Strategy.id == strategy_id) & (Strategy.user_id == user_id)
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    db.delete(strategy)
    db.commit()
    return {"message": "Strategy deleted"}
