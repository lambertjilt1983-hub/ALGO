from abc import ABC, abstractmethod
from typing import Any, Dict

class BrokerInterface(ABC):
    """Abstract base class for all broker integrations."""

    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """Connect to the broker using provided credentials."""
        pass

    @abstractmethod
    def place_order(self, order_details: Dict[str, Any]) -> Dict[str, Any]:
        """Place an order with the broker."""
        pass

    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """Fetch account balance and positions."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the broker."""
        pass
