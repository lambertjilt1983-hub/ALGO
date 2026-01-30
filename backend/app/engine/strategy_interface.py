from abc import ABC, abstractmethod
from typing import Any, Dict, List

class StrategyInterface(ABC):
    """Abstract base class for trading strategies."""

    @abstractmethod
    def scan(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan the market for potential opportunities."""
        pass

    @abstractmethod
    def identify(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify actionable signals from scanned opportunities."""
        pass

    @abstractmethod
    def analyze(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze signals for risk, reward, and context."""
        pass

    @abstractmethod
    def execute(self, signals: List[Dict[str, Any]], engine: Any) -> List[Dict[str, Any]]:
        """Execute trades based on analyzed signals using the trading engine."""
        pass
