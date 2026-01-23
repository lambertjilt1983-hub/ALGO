from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON
from datetime import datetime
from app.core.database import Base

class Order(Base):
    """Order execution model"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    broker_id = Column(Integer, index=True)
    symbol = Column(String, index=True)
    order_type = Column(String)  # market, limit, stop_loss
    side = Column(String)  # buy, sell
    quantity = Column(Float)
    price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    status = Column(String, default="pending")  # pending, filled, cancelled, rejected
    filled_quantity = Column(Float, default=0)
    average_price = Column(Float, nullable=True)
    broker_order_id = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)

class Position(Base):
    """Current trading positions"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    broker_id = Column(Integer, index=True)
    symbol = Column(String, index=True)
    quantity = Column(Float)
    average_cost = Column(Float)
    current_price = Column(Float)
    pnl = Column(Float, nullable=True)
    pnl_percentage = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Strategy(Base):
    """Trading strategy definitions"""
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    strategy_type = Column(String)  # ma_crossover, rsi, momentum, etc.
    parameters = Column(JSON)  # Store strategy parameters as JSON
    status = Column(String, default="inactive")  # inactive, backtesting, live, paused
    is_live = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BacktestResult(Base):
    """Backtest results storage"""
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, index=True)
    user_id = Column(Integer, index=True)
    total_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    results_data = Column(JSON)  # Detailed results
    created_at = Column(DateTime, default=datetime.utcnow)
