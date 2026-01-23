import logging
import json
import os
from datetime import datetime
from typing import Any, Dict

class TradingLogger:
    """Centralized logging for trading operations"""
    
    def __init__(self, name: str = "trading_bot"):
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Configure logger with file and console handlers"""
        os.makedirs("logs", exist_ok=True)
        handler = logging.FileHandler("logs/trading.log")
        console_handler = logging.StreamHandler()
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.addHandler(console_handler)
        self.logger.setLevel(logging.INFO)
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """Log trade execution"""
        self.logger.info(f"TRADE_EXECUTED: {json.dumps(trade_data)}")
    
    def log_error(self, error: str, context: Dict[str, Any] = None):
        """Log errors with context"""
        context = context or {}
        self.logger.error(f"ERROR: {error} | Context: {json.dumps(context)}")
    
    def log_api_call(self, broker: str, endpoint: str, status: str):
        """Log API calls"""
        self.logger.info(f"API_CALL: Broker={broker}, Endpoint={endpoint}, Status={status}")

    def log_info(self, message: str, context: Dict[str, Any] = None):
        """Generic info logging with optional context."""
        context = context or {}
        try:
            ctx = json.dumps(context)
        except Exception:
            ctx = str(context)
        self.logger.info(f"INFO: {message} | Context: {ctx}")

logger = TradingLogger()
