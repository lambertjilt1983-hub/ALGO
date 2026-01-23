import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Signal:
    """Trading signal from strategy"""
    timestamp: datetime
    symbol: str
    action: str  # buy, sell, hold
    strength: float  # 0-1 signal strength
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class Strategy(ABC):
    """Abstract base class for trading strategies"""
    
    def __init__(self, name: str, parameters: Dict[str, Any]):
        self.name = name
        self.parameters = parameters
        self.signals: List[Signal] = []
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate trading signal based on market data"""
        pass
    
    @abstractmethod
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate that required data is available"""
        pass

class MovingAverageCrossover(Strategy):
    """Moving Average Crossover Strategy"""
    
    def __init__(self, parameters: Dict[str, Any]):
        super().__init__("MA Crossover", parameters)
        self.fast_period = parameters.get("fast_period", 20)
        self.slow_period = parameters.get("slow_period", 50)
        self.stop_loss_percent = parameters.get("stop_loss_percent", 2)
        self.take_profit_percent = parameters.get("take_profit_percent", 5)
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate OHLCV data"""
        required_cols = ["open", "high", "low", "close", "volume"]
        return all(col in data.columns for col in required_cols)
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate signal based on MA crossover"""
        if len(data) < self.slow_period:
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="hold",
                strength=0
            )
        
        # Calculate moving averages
        fast_ma = data["close"].rolling(window=self.fast_period).mean()
        slow_ma = data["close"].rolling(window=self.slow_period).mean()
        
        # Get latest values
        current_price = data["close"].iloc[-1]
        fast_ma_val = fast_ma.iloc[-1]
        slow_ma_val = slow_ma.iloc[-1]
        
        prev_fast_ma = fast_ma.iloc[-2]
        prev_slow_ma = slow_ma.iloc[-2]
        
        # Determine signal
        if prev_fast_ma <= prev_slow_ma and fast_ma_val > slow_ma_val:
            # Bullish crossover
            stop_loss = current_price * (1 - self.stop_loss_percent / 100)
            take_profit = current_price * (1 + self.take_profit_percent / 100)
            
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="buy",
                strength=0.8,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
        elif prev_fast_ma >= prev_slow_ma and fast_ma_val < slow_ma_val:
            # Bearish crossover
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="sell",
                strength=0.8
            )
        
        return Signal(
            timestamp=datetime.now(),
            symbol="",
            action="hold",
            strength=0
        )

class RSIStrategy(Strategy):
    """Relative Strength Index (RSI) Strategy"""
    
    def __init__(self, parameters: Dict[str, Any]):
        super().__init__("RSI Strategy", parameters)
        self.period = parameters.get("period", 14)
        self.overbought = parameters.get("overbought", 70)
        self.oversold = parameters.get("oversold", 30)
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate OHLCV data"""
        return "close" in data.columns and len(data) >= self.period
    
    def calculate_rsi(self, data: pd.Series) -> pd.Series:
        """Calculate RSI"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate signal based on RSI"""
        if not self.validate_data(data):
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="hold",
                strength=0
            )
        
        rsi = self.calculate_rsi(data["close"])
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2] if len(rsi) > 1 else current_rsi
        
        if prev_rsi > self.oversold and current_rsi <= self.oversold:
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="buy",
                strength=0.7,
                entry_price=data["close"].iloc[-1]
            )
        elif prev_rsi < self.overbought and current_rsi >= self.overbought:
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="sell",
                strength=0.7
            )
        
        return Signal(
            timestamp=datetime.now(),
            symbol="",
            action="hold",
            strength=0
        )

class MomentumStrategy(Strategy):
    """Momentum-based trading strategy"""
    
    def __init__(self, parameters: Dict[str, Any]):
        super().__init__("Momentum Strategy", parameters)
        self.period = parameters.get("period", 10)
        self.threshold = parameters.get("threshold", 0.02)
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate data"""
        return "close" in data.columns and len(data) >= self.period
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate signal based on momentum"""
        if not self.validate_data(data):
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="hold",
                strength=0
            )
        
        # Calculate momentum
        price_change = (data["close"].iloc[-1] - data["close"].iloc[-self.period-1]) / data["close"].iloc[-self.period-1]
        
        if price_change > self.threshold:
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="buy",
                strength=min(abs(price_change) / 0.1, 1.0),
                entry_price=data["close"].iloc[-1]
            )
        elif price_change < -self.threshold:
            return Signal(
                timestamp=datetime.now(),
                symbol="",
                action="sell",
                strength=min(abs(price_change) / 0.1, 1.0)
            )
        
        return Signal(
            timestamp=datetime.now(),
            symbol="",
            action="hold",
            strength=0
        )

class StrategyFactory:
    """Factory for creating strategy instances"""
    
    _strategies = {
        "ma_crossover": MovingAverageCrossover,
        "rsi": RSIStrategy,
        "momentum": MomentumStrategy
    }
    
    @classmethod
    def create_strategy(cls, strategy_type: str, parameters: Dict[str, Any]) -> Strategy:
        """Create strategy instance"""
        strategy_class = cls._strategies.get(strategy_type.lower())
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {strategy_type}")
        
        return strategy_class(parameters)
