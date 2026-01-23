import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from app.strategies.base import Strategy, Signal
from app.core.logger import logger

@dataclass
class BacktestMetrics:
    """Backtest performance metrics"""
    total_return: float = 0
    annual_return: float = 0
    sharpe_ratio: float = 0
    max_drawdown: float = 0
    win_rate: float = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0
    avg_loss: float = 0
    profit_factor: float = 0
    trades: List[Dict[str, Any]] = field(default_factory=list)

class Backtester:
    """Backtesting engine for strategies"""
    
    def __init__(self, strategy: Strategy, initial_capital: float = 100000):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, Dict] = {}
        self.trades: List[Dict[str, Any]] = []
    
    def backtest(
        self,
        data: pd.DataFrame,
        symbol: str = "TEST"
    ) -> BacktestMetrics:
        """Run backtest on historical data"""
        
        if not self.strategy.validate_data(data):
            logger.log_error("Invalid data for backtesting", {"symbol": symbol})
            return BacktestMetrics()
        
        metrics = BacktestMetrics()
        equity_curve = [self.initial_capital]
        
        for i in range(len(data)):
            current_data = data.iloc[:i+1].copy()
            
            # Generate signal
            signal = self.strategy.generate_signal(current_data)
            signal.symbol = symbol
            
            # Process signal
            current_price = data["close"].iloc[i]
            
            if signal.action == "buy" and symbol not in self.positions:
                # Open long position
                position_size = (self.current_capital * 0.95) / current_price  # Use 95% of capital
                self.positions[symbol] = {
                    "type": "long",
                    "entry_price": current_price,
                    "quantity": position_size,
                    "entry_time": data.index[i],
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit
                }
                self.current_capital -= position_size * current_price
                
            elif signal.action == "sell" and symbol in self.positions:
                # Close position
                position = self.positions[symbol]
                pnl = (current_price - position["entry_price"]) * position["quantity"]
                pnl_percent = (pnl / (position["entry_price"] * position["quantity"])) * 100
                
                self.trades.append({
                    "symbol": symbol,
                    "entry_price": position["entry_price"],
                    "exit_price": current_price,
                    "quantity": position["quantity"],
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                    "entry_time": position["entry_time"],
                    "exit_time": data.index[i]
                })
                
                self.current_capital += position["quantity"] * current_price + pnl
                del self.positions[symbol]
            
            # Check stop loss and take profit
            if symbol in self.positions:
                position = self.positions[symbol]
                if position["stop_loss"] and current_price <= position["stop_loss"]:
                    # Hit stop loss
                    pnl = (current_price - position["entry_price"]) * position["quantity"]
                    self.trades.append({
                        "symbol": symbol,
                        "entry_price": position["entry_price"],
                        "exit_price": current_price,
                        "quantity": position["quantity"],
                        "pnl": pnl,
                        "pnl_percent": (pnl / (position["entry_price"] * position["quantity"])) * 100,
                        "entry_time": position["entry_time"],
                        "exit_time": data.index[i],
                        "reason": "stop_loss"
                    })
                    self.current_capital += position["quantity"] * current_price + pnl
                    del self.positions[symbol]
                
                elif position["take_profit"] and current_price >= position["take_profit"]:
                    # Hit take profit
                    pnl = (current_price - position["entry_price"]) * position["quantity"]
                    self.trades.append({
                        "symbol": symbol,
                        "entry_price": position["entry_price"],
                        "exit_price": current_price,
                        "quantity": position["quantity"],
                        "pnl": pnl,
                        "pnl_percent": (pnl / (position["entry_price"] * position["quantity"])) * 100,
                        "entry_time": position["entry_time"],
                        "exit_time": data.index[i],
                        "reason": "take_profit"
                    })
                    self.current_capital += position["quantity"] * current_price + pnl
                    del self.positions[symbol]
            
            equity_curve.append(self.current_capital)
        
        # Close any remaining positions at last price
        last_price = data["close"].iloc[-1]
        for symbol, position in self.positions.items():
            pnl = (last_price - position["entry_price"]) * position["quantity"]
            self.trades.append({
                "symbol": symbol,
                "entry_price": position["entry_price"],
                "exit_price": last_price,
                "quantity": position["quantity"],
                "pnl": pnl,
                "pnl_percent": (pnl / (position["entry_price"] * position["quantity"])) * 100,
                "entry_time": position["entry_time"],
                "exit_time": data.index[-1]
            })
            self.current_capital += position["quantity"] * last_price + pnl
        
        # Calculate metrics
        metrics = self._calculate_metrics(equity_curve)
        metrics.trades = self.trades
        
        logger.log_trade({
            "strategy": self.strategy.name,
            "total_return": metrics.total_return,
            "sharpe_ratio": metrics.sharpe_ratio,
            "trades": len(self.trades)
        })
        
        return metrics
    
    def _calculate_metrics(self, equity_curve: List[float]) -> BacktestMetrics:
        """Calculate backtest metrics"""
        metrics = BacktestMetrics()
        
        equity_array = np.array(equity_curve)
        returns = np.diff(equity_array) / equity_array[:-1]
        
        # Total return
        total_return = (equity_curve[-1] - self.initial_capital) / self.initial_capital
        metrics.total_return = total_return
        
        # Annual return (approximate)
        periods = len(equity_curve)
        annual_return = (1 + total_return) ** (252 / max(periods, 1)) - 1
        metrics.annual_return = annual_return
        
        # Sharpe ratio
        daily_returns = returns
        if len(daily_returns) > 0:
            sharpe_ratio = np.sqrt(252) * daily_returns.mean() / (daily_returns.std() + 1e-8)
            metrics.sharpe_ratio = sharpe_ratio
        
        # Max drawdown
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        metrics.max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        
        # Trade statistics
        metrics.total_trades = len(self.trades)
        metrics.winning_trades = sum(1 for t in self.trades if t.get("pnl", 0) > 0)
        metrics.losing_trades = sum(1 for t in self.trades if t.get("pnl", 0) <= 0)
        
        if metrics.total_trades > 0:
            metrics.win_rate = metrics.winning_trades / metrics.total_trades
        
        winning_pnl = sum(t.get("pnl", 0) for t in self.trades if t.get("pnl", 0) > 0)
        losing_pnl = sum(abs(t.get("pnl", 0)) for t in self.trades if t.get("pnl", 0) <= 0)
        
        if metrics.winning_trades > 0:
            metrics.avg_win = winning_pnl / metrics.winning_trades
        if metrics.losing_trades > 0:
            metrics.avg_loss = losing_pnl / metrics.losing_trades
        
        if losing_pnl > 0:
            metrics.profit_factor = winning_pnl / losing_pnl
        
        return metrics
