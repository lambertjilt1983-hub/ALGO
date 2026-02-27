"""
SL Recovery Manager - Intelligent recovery from stop loss hits
Implements:
1. 5-minute waiting period after SL hit
2. >95% confidence signal requirement for re-entry
3. Avoids same option symbol re-entry
4. Switches to opposite option type (CE to PE or vice versa)
5. Market trend analysis before re-entry
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger("trading_bot")

@dataclass
class SLHitRecord:
    """Record of a stop loss hit"""
    symbol: str
    base_symbol: str  # e.g., 'FINNIFTY26MAR28000' without CE/PE
    option_type: str  # 'CE' or 'PE'
    exit_price: float
    exit_time: datetime
    entry_price: float
    entry_time: datetime
    pnl: float


@dataclass
class RecoverySignal:
    """Recovery signal after SL hit"""
    symbol: str
    option_type: str
    confidence: float
    market_trend: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    trend_strength: float  # 0.0 to 1.0
    recommendation: str  # 'BUY', 'SELL', 'WAIT'
    reason: str
    wait_until: Optional[datetime]


class SLRecoveryManager:
    """Manages intelligent recovery from stop loss hits"""
    
    def __init__(self, wait_minutes: int = 5, min_confidence: float = 0.95):
        """
        Initialize SL Recovery Manager
        
        Args:
            wait_minutes: Minutes to wait after SL hit (default 5)
            min_confidence: Minimum confidence signal required (default 0.95)
        """
        self.wait_minutes = wait_minutes
        self.min_confidence = min_confidence
        
        # Track SL hits: {base_symbol: [SLHitRecord, ...]}
        self.sl_hit_history: Dict[str, List[SLHitRecord]] = {}
        
        # Track retry attempts to avoid infinite loops
        self.retry_attempts: Dict[str, int] = {}
        self.max_retries_per_day = 3
        
    def record_sl_hit(
        self,
        symbol: str,
        option_type: str,
        entry_price: float,
        exit_price: float,
        entry_time: datetime,
        exit_time: datetime
    ) -> SLHitRecord:
        """
        Record a stop loss hit
        Returns the SLHitRecord for tracking
        """
        # Extract base symbol (e.g., 'FINNIFTY26MAR28000' from 'FINNIFTY26MAR28000CE')
        base_symbol = symbol.replace('CE', '').replace('PE', '')
        
        record = SLHitRecord(
            symbol=symbol,
            base_symbol=base_symbol,
            option_type=option_type,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=exit_price - entry_price if option_type == 'PE' else entry_price - exit_price
        )
        
        if base_symbol not in self.sl_hit_history:
            self.sl_hit_history[base_symbol] = []
        
        self.sl_hit_history[base_symbol].append(record)
        self.retry_attempts[base_symbol] = self.retry_attempts.get(base_symbol, 0)
        
        logger.info(f"[SL_RECOVERY] Recorded SL hit: {symbol} at ₹{exit_price:.2f}")
        
        return record
    
    def can_retry(self, base_symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Check if we can retry trading for this symbol
        Returns (can_retry: bool, reason: str)
        """
        if base_symbol not in self.sl_hit_history:
            return True, None
        
        sl_records = self.sl_hit_history[base_symbol]
        if not sl_records:
            return True, None
        
        latest_hit = sl_records[-1]
        time_since_hit = datetime.now() - latest_hit.exit_time
        
        # Check if wait period has passed
        if time_since_hit < timedelta(minutes=self.wait_minutes):
            wait_until = latest_hit.exit_time + timedelta(minutes=self.wait_minutes)
            remaining = (wait_until - datetime.now()).total_seconds() / 60
            reason = f"Waiting {remaining:.1f} min after SL hit (required 5 min)"
            logger.info(f"[SL_RECOVERY] Cannot retry {base_symbol}: {reason}")
            return False, reason
        
        # Check daily retry limit
        retries_today = self.retry_attempts.get(base_symbol, 0)
        if retries_today >= self.max_retries_per_day:
            reason = f"Max {self.max_retries_per_day} retries per day reached for {base_symbol}"
            logger.warning(f"[SL_RECOVERY] {reason}")
            return False, reason
        
        return True, None
    
    def get_alternative_option_type(self, current_type: str) -> str:
        """
        Get the alternative option type
        CE -> PE, PE -> CE
        """
        return 'PE' if current_type == 'CE' else 'CE'
    
    def can_trade_same_symbol(self, symbol: str) -> bool:
        """
        Check if we can trade the same symbol again (not recommended)
        Returns False to prevent exact same symbol re-entry
        """
        base_symbol = symbol.replace('CE', '').replace('PE', '')
        
        if base_symbol not in self.sl_hit_history:
            return True
        
        # Get the most recent SL hit for this symbol
        sl_records = self.sl_hit_history[base_symbol]
        if not sl_records:
            return True
        
        latest_hit = sl_records[-1]
        
        # Don't trade the exact same symbol again
        if symbol == latest_hit.symbol:
            logger.warning(
                f"[SL_RECOVERY] Avoiding same symbol {symbol} after SL hit. "
                f"Recommend {self.get_alternative_option_type(latest_hit.option_type)} instead."
            )
            return False
        
        return True
    
    def analyze_market_trend(
        self,
        current_price: float,
        recent_prices: List[float],
        signal_type: str  # 'CE' or 'PE'
    ) -> Tuple[str, float]:
        """
        Analyze market trend from recent price data
        Returns (trend: 'BULLISH'|'BEARISH'|'NEUTRAL', strength: 0.0-1.0)
        """
        if len(recent_prices) < 2:
            return 'NEUTRAL', 0.3
        
        # Simple trend analysis
        price_changes = [recent_prices[i] - recent_prices[i-1] for i in range(1, len(recent_prices))]
        bullish_count = sum(1 for change in price_changes if change > 0)
        bearish_count = sum(1 for change in price_changes if change < 0)
        
        trend_ratio = bullish_count / len(price_changes) if price_changes else 0.5
        
        # Determine trend
        if trend_ratio > 0.6:
            trend = 'BULLISH'
            strength = min(0.95, trend_ratio)
        elif trend_ratio < 0.4:
            trend = 'BEARISH'
            strength = min(0.95, 1 - trend_ratio)
        else:
            trend = 'NEUTRAL'
            strength = 0.5
        
        logger.info(f"[SL_RECOVERY] Market trend: {trend} (strength: {strength:.2f})")
        
        return trend, strength
    
    def generate_recovery_signal(
        self,
        base_symbol: str,
        signal_confidence: float,
        current_price: float,
        recent_prices: Optional[List[float]] = None,
        last_sl_option_type: Optional[str] = None
    ) -> RecoverySignal:
        """
        Generate a recovery signal after SL hit
        
        Args:
            base_symbol: Base symbol without CE/PE (e.g., 'FINNIFTY26MAR28000')
            signal_confidence: Confidence of the new signal (0.0 to 1.0)
            current_price: Current market price
            recent_prices: List of recent prices for trend analysis
            last_sl_option_type: The option type that hit SL (CE or PE)
        """
        can_retry, reason = self.can_retry(base_symbol)
        
        if not can_retry:
            return RecoverySignal(
                symbol=base_symbol,
                option_type=None,
                confidence=signal_confidence,
                market_trend='NEUTRAL',
                trend_strength=0.0,
                recommendation='WAIT',
                reason=reason,
                wait_until=None
            )
        
        # Check confidence threshold
        if signal_confidence < self.min_confidence:
            reason = f"Signal confidence {signal_confidence:.2%} below minimum {self.min_confidence:.2%}"
            logger.info(f"[SL_RECOVERY] {reason}")
            return RecoverySignal(
                symbol=base_symbol,
                option_type=None,
                confidence=signal_confidence,
                market_trend='NEUTRAL',
                trend_strength=0.0,
                recommendation='WAIT',
                reason=reason,
                wait_until=None
            )
        
        # Analyze market trend
        trend, trend_strength = self.analyze_market_trend(
            current_price,
            recent_prices or [current_price],
            signal_type='CE'
        )
        
        # Determine recommendation based on trend and signal
        recommendation = 'BUY' if trend == 'BULLISH' or signal_confidence >= 0.97 else 'WAIT'
        
        # Suggest alternative option type
        suggested_type = self.get_alternative_option_type(last_sl_option_type) if last_sl_option_type else 'CE'
        
        logger.info(
            f"[SL_RECOVERY] Recovery signal for {base_symbol}: "
            f"{recommendation} {suggested_type} "
            f"(confidence: {signal_confidence:.2%}, trend: {trend}, strength: {trend_strength:.2f})"
        )
        
        return RecoverySignal(
            symbol=base_symbol,
            option_type=suggested_type,
            confidence=signal_confidence,
            market_trend=trend,
            trend_strength=trend_strength,
            recommendation=recommendation,
            reason=f"Recovery signal: {trend} market, confidence {signal_confidence:.2%}, trend strength {trend_strength:.2f}",
            wait_until=None
        )
    
    def should_execute_recovery_trade(
        self,
        recovery_signal: RecoverySignal
    ) -> Tuple[bool, str]:
        """
        Determine if recovery trade should be executed
        Returns (should_execute: bool, reason: str)
        """
        if recovery_signal.recommendation != 'BUY':
            return False, f"Recommendation is {recovery_signal.recommendation}, not BUY"
        
        if recovery_signal.confidence < self.min_confidence:
            return False, f"Confidence {recovery_signal.confidence:.2f} < {self.min_confidence}"
        
        if recovery_signal.market_trend == 'BEARISH' and recovery_signal.option_type == 'CE':
            return False, "CE trade in BEARISH market - risky"
        
        if recovery_signal.market_trend == 'BULLISH' and recovery_signal.option_type == 'PE':
            return False, "PE trade in BULLISH market - risky"
        
        return True, "All checks passed"
    
    def reset_daily_stats(self):
        """Reset daily retry attempts (call once per day)"""
        self.retry_attempts.clear()
        logger.info("[SL_RECOVERY] Daily stats reset")
    
    def get_recovery_stats(self) -> Dict:
        """Get recovery statistics"""
        total_sl_hits = sum(len(records) for records in self.sl_hit_history.values())
        
        stats = {
            'total_sl_hits': total_sl_hits,
            'symbols_with_sl': list(self.sl_hit_history.keys()),
            'retry_attempts': self.retry_attempts.copy(),
            'wait_minutes': self.wait_minutes,
            'min_confidence': self.min_confidence,
            'max_retries_per_day': self.max_retries_per_day
        }
        
        return stats


# Global instance
sl_recovery_manager = SLRecoveryManager(wait_minutes=5, min_confidence=0.95)
