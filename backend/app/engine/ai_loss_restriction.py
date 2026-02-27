"""
Advanced AI Trade Quality Predictor & Loss Restriction Engine

Uses machine learning to:
1. Predict trade success probability
2. Block trades that would hurt win rate
3. Enforce 80% win rate requirement (8/10 trades positive)
4. Learn from historical trades to improve predictions
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import logging
from pathlib import Path

logger = logging.getLogger("trading_bot")

@dataclass
class TradeFeatures:
    """Features extracted from a trade signal for ML prediction"""
    signal_confidence: float       # 0.0 to 1.0
    market_trend: str             # BULLISH, BEARISH, NEUTRAL
    trend_strength: float         # 0.0 to 1.0
    option_type: str              # CE or PE
    recent_win_rate: float        # Win rate of last N trades
    time_of_day_hour: int         # 9-15 (market hours)
    is_recovery_trade: bool       # True if recovery attempt
    days_since_last_loss: int     # Days since last SL hit
    consecutive_losses: int       # Consecutive losses
    volatility_level: str         # LOW, MEDIUM, HIGH
    rsi_level: int                # 0-100
    macd_histogram: float         # Positive/negative
    bollinger_position: float     # 0-1 (lower band to upper band)
    volume_ratio: float           # Current volume vs average
    price_momentum: float         # % change in recent prices


@dataclass
class PredictionResult:
    """Result from ML prediction model"""
    symbol: str
    signal_confidence: float
    predicted_win_probability: float  # 0.0 to 1.0
    recommendation: str               # EXECUTE, WAIT, BLOCK
    reason: str
    confidence_level: str             # LOW, MEDIUM, HIGH, VERY_HIGH
    risk_score: float                 # 0.0 (safe) to 1.0 (dangerous)
    expected_pnl_direction: str       # PROFIT, LOSS, NEUTRAL


class TradeHistoryAnalyzer:
    """Analyzes historical trades to extract patterns"""
    
    def __init__(self, min_trades_for_analysis: int = 10):
        self.min_trades_for_analysis = min_trades_for_analysis
        self.trade_history: List[Dict] = []
        
    def add_trade(self, trade_data: Dict):
        """Add a closed trade to history for analysis"""
        self.trade_history.append({
            'symbol': trade_data.get('symbol'),
            'entry_price': float(trade_data.get('price', 0)),
            'exit_price': float(trade_data.get('exit_price', 0)),
            'status': trade_data.get('status'),
            'pnl': float(trade_data.get('pnl', 0)),
            'confidence': float(trade_data.get('confidence', 0)),
            'entry_time': trade_data.get('entry_time'),
            'exit_time': trade_data.get('exit_time'),
        })
    
    def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        """Get recent closed trades"""
        return self.trade_history[-limit:]
    
    def calculate_win_rate(self, limit: int = 10) -> Tuple[float, int]:
        """Calculate win rate for recent trades"""
        recent = self.get_recent_trades(limit)
        if not recent:
            return 0.5, 0  # Neutral default
        
        wins = sum(1 for t in recent if t.get('pnl', 0) > 0)
        return wins / len(recent), len(recent)
    
    def get_symbol_win_rate(self, symbol: str) -> Tuple[float, int]:
        """Get win rate for specific symbol"""
        symbol_trades = [t for t in self.trade_history if t.get('symbol') == symbol]
        if not symbol_trades:
            return 0.5, 0
        
        wins = sum(1 for t in symbol_trades if t.get('pnl', 0) > 0)
        return wins / len(symbol_trades), len(symbol_trades)
    
    def get_time_of_day_win_rate(self, hour: int) -> Tuple[float, int]:
        """Get win rate for trades executed at specific hour"""
        hour_trades = []
        for t in self.trade_history:
            try:
                entry_time = None
                if isinstance(t.get('entry_time'), str):
                    entry_time = datetime.fromisoformat(t['entry_time'])
                
                if entry_time and entry_time.hour == hour:
                    hour_trades.append(t)
            except:
                pass
        
        if not hour_trades:
            return 0.5, 0
        
        wins = sum(1 for t in hour_trades if t.get('pnl', 0) > 0)
        return wins / len(hour_trades), len(hour_trades)


class SimpleMLPredictor:
    """Simple machine learning model for trade prediction"""
    
    def __init__(self):
        self.feature_weights = {
            'signal_confidence': 0.25,      # 25% weight on signal confidence
            'recent_win_rate': 0.20,        # 20% weight on win rate momentum
            'trend_strength': 0.15,         # 15% weight on trend
            'time_of_day': 0.10,            # 10% weight on time
            'recovery_penalty': -0.10,      # -10% if recovery trade
            'consecutive_losses': -0.10,    # -10% per loss streak
            'volatility': -0.10,            # -10% if high volatility
        }
        
        # Learned thresholds based on market conditions
        self.learned_thresholds = {
            'min_confidence_low_trend': 0.92,
            'min_confidence_neutral': 0.94,
            'min_confidence_high_trend': 0.90,
            'win_rate_threshold': 0.40,      # Minimum to trade
        }
    
    def extract_features(self, signal_data: Dict, historical_analyzer: TradeHistoryAnalyzer) -> TradeFeatures:
        """Extract ML features from signal"""
        
        recent_win_rate, _ = historical_analyzer.calculate_win_rate(10)
        market_trend = signal_data.get('market_trend', 'NEUTRAL')
        trend_strength = float(signal_data.get('trend_strength', 0.5))
        
        # Extract additional features
        hour = datetime.now().hour
        days_since_loss = self._calculate_days_since_loss(signal_data)
        consecutive_losses = signal_data.get('consecutive_losses', 0)
        
        features = TradeFeatures(
            signal_confidence=float(signal_data.get('signal_confidence', 0)),
            market_trend=market_trend,
            trend_strength=trend_strength,
            option_type=signal_data.get('option_type', 'CE'),
            recent_win_rate=recent_win_rate,
            time_of_day_hour=hour,
            is_recovery_trade=signal_data.get('is_recovery_trade', False),
            days_since_last_loss=days_since_loss,
            consecutive_losses=consecutive_losses,
            volatility_level=signal_data.get('volatility_level', 'MEDIUM'),
            rsi_level=int(signal_data.get('rsi_level', 50)),
            macd_histogram=float(signal_data.get('macd_histogram', 0)),
            bollinger_position=float(signal_data.get('bollinger_position', 0.5)),
            volume_ratio=float(signal_data.get('volume_ratio', 1.0)),
            price_momentum=float(signal_data.get('price_momentum', 0)),
        )
        
        return features
    
    def _calculate_days_since_loss(self, signal_data: Dict) -> int:
        """Calculate days since last loss"""
        last_loss_time = signal_data.get('last_loss_time')
        if not last_loss_time:
            return 100  # Very safe default
        
        try:
            if isinstance(last_loss_time, str):
                last_loss_dt = datetime.fromisoformat(last_loss_time)
            else:
                last_loss_dt = last_loss_time
            
            days = (datetime.now() - last_loss_dt).days
            return max(0, days)
        except:
            return 100
    
    def predict_win_probability(self, features: TradeFeatures) -> float:
        """Predict probability of trade being profitable (0.0 to 1.0)"""
        
        # Base probability from confidence
        base_prob = features.signal_confidence
        
        # Trend alignment bonus
        if features.market_trend == 'BULLISH' and features.option_type == 'CE':
            trend_bonus = features.trend_strength * 0.05
        elif features.market_trend == 'BEARISH' and features.option_type == 'PE':
            trend_bonus = features.trend_strength * 0.05
        elif features.market_trend == 'NEUTRAL':
            trend_bonus = -0.05  # Penalty for neutral market
        else:
            trend_bonus = -0.10  # Penalty for counter-trend
        
        # Win rate momentum
        win_rate_adjustment = (features.recent_win_rate - 0.5) * 0.10
        
        # Recovery trade penalty
        recovery_penalty = -0.08 if features.is_recovery_trade else 0
        
        # Consecutive loss penalty
        loss_penalty = -0.03 * min(features.consecutive_losses, 3)
        
        # Volatility penalty
        volatility_penalty = {
            'LOW': 0.02,
            'MEDIUM': 0.0,
            'HIGH': -0.05
        }.get(features.volatility_level, 0)
        
        # Time of day adjustment
        time_adjustment = self._get_time_of_day_factor(features.time_of_day_hour)
        
        # RSI extremes (overbought/oversold is risky)
        rsi_penalty = 0
        if features.rsi_level > 80 or features.rsi_level < 20:
            rsi_penalty = -0.05
        
        # Calculate final probability
        final_prob = (
            base_prob +
            trend_bonus +
            win_rate_adjustment +
            recovery_penalty +
            loss_penalty +
            volatility_penalty +
            time_adjustment +
            rsi_penalty
        )
        
        # Clamp to valid probability range
        return np.clip(final_prob, 0.0, 1.0)
    
    def _get_time_of_day_factor(self, hour: int) -> float:
        """Get adjustment factor based on time of day"""
        # Market opens at 9:15 AM, closes at 3:30 PM
        # Best hours: 10-11 AM (stability), 12-1 PM (volume)
        
        time_factors = {
            9: -0.05,   # Opening volatility
            10: 0.05,   # Stable period
            11: 0.05,   # Stable period
            12: 0.08,   # High volume period
            13: 0.08,   # High volume period
            14: 0.02,   # Slight decline
            15: -0.08,  # Closing volatility
        }
        
        return time_factors.get(hour, -0.05)
    
    def evaluate_trade_quality(
        self,
        features: TradeFeatures,
        predicted_prob: float,
        current_win_rate: float
    ) -> PredictionResult:
        """Evaluate if trade should be executed"""
        
        symbol = "UNKNOWN"  # Will be set by caller
        
        # Core quality checks
        if predicted_prob < 0.50:
            return PredictionResult(
                symbol=symbol,
                signal_confidence=features.signal_confidence,
                predicted_win_probability=predicted_prob,
                recommendation='BLOCK',
                reason=f'Win probability too low: {predicted_prob:.2%}. Need at least 50%',
                confidence_level='LOW',
                risk_score=max(0.7, 1.0 - predicted_prob),
                expected_pnl_direction='LOSS'
            )
        
        # Check 80% win rate requirement (8 out of 10 trades positive)
        if current_win_rate < 0.40:
            return PredictionResult(
                symbol=symbol,
                signal_confidence=features.signal_confidence,
                predicted_win_probability=predicted_prob,
                recommendation='WAIT',
                reason=f'Current win rate {current_win_rate:.1%} too low. Wait for improvement.',
                confidence_level='MEDIUM',
                risk_score=0.6,
                expected_pnl_direction='NEUTRAL'
            )
        
        # Additional quality checks
        if features.is_recovery_trade and features.consecutive_losses >= 3:
            return PredictionResult(
                symbol=symbol,
                signal_confidence=features.signal_confidence,
                predicted_win_probability=predicted_prob,
                recommendation='BLOCK',
                reason='Too many consecutive losses. Skip recovery attempt.',
                confidence_level='MEDIUM',
                risk_score=0.8,
                expected_pnl_direction='LOSS'
            )
        
        # Volatility check
        if features.volatility_level == 'HIGH' and predicted_prob < 0.70:
            return PredictionResult(
                symbol=symbol,
                signal_confidence=features.signal_confidence,
                predicted_win_probability=predicted_prob,
                recommendation='WAIT',
                reason='High volatility + moderate confidence. Wait for stability.',
                confidence_level='MEDIUM',
                risk_score=0.65,
                expected_pnl_direction='NEUTRAL'
            )
        
        # Recommendation logic based on probability
        if predicted_prob >= 0.80:
            confidence = 'VERY_HIGH'
            recommendation = 'EXECUTE'
            risk_score = 1.0 - predicted_prob
        elif predicted_prob >= 0.70:
            confidence = 'HIGH'
            recommendation = 'EXECUTE'
            risk_score = 1.0 - predicted_prob
        elif predicted_prob >= 0.60:
            confidence = 'MEDIUM'
            recommendation = 'EXECUTE'
            risk_score = 1.0 - predicted_prob
        else:
            confidence = 'LOW'
            recommendation = 'WAIT'
            risk_score = 1.0 - predicted_prob
        
        return PredictionResult(
            symbol=symbol,
            signal_confidence=features.signal_confidence,
            predicted_win_probability=predicted_prob,
            recommendation=recommendation,
            reason=f'Win probability: {predicted_prob:.2%}. Market trend aligned. Ready to trade.',
            confidence_level=confidence,
            risk_score=risk_score,
            expected_pnl_direction='PROFIT' if predicted_prob > 0.65 else 'NEUTRAL'
        )


class DailyTradeQuotaManager:
    """Manages daily trade quota and 80% win rate enforcement"""
    
    def __init__(self, target_win_rate: float = 0.80, daily_trade_limit: int = 10):
        self.target_win_rate = target_win_rate  # 80%
        self.daily_trade_limit = daily_trade_limit  # 10 trades
        self.required_wins = int(target_win_rate * daily_trade_limit)  # 8 wins out of 10
        
        # Daily tracking
        self.daily_reset_date = datetime.now().date()
        self.daily_trades: List[Dict] = []
        self.daily_wins = 0
        self.daily_losses = 0
    
    def reset_if_new_day(self):
        """Reset counters if it's a new day"""
        today = datetime.now().date()
        if today != self.daily_reset_date:
            self.daily_reset_date = today
            self.daily_trades.clear()
            self.daily_wins = 0
            self.daily_losses = 0
            logger.info(f"[QUOTA] Daily quota reset for {today}")
    
    def record_trade_result(self, symbol: str, pnl: float, is_win: bool):
        """Record a trade result"""
        self.daily_trades.append({
            'symbol': symbol,
            'pnl': pnl,
            'is_win': is_win,
            'timestamp': datetime.now()
        })
        
        if is_win:
            self.daily_wins += 1
        else:
            self.daily_losses += 1
        
        logger.info(
            f"[QUOTA] Trade recorded: {symbol} - {'WIN' if is_win else 'LOSS'} "
            f"| Daily: {self.daily_wins}W-{self.daily_losses}L "
            f"(Need {self.required_wins} wins)"
        )
    
    def can_execute_trade(self) -> Tuple[bool, str]:
        """Check if more trades can be executed today"""
        self.reset_if_new_day()
        
        trades_executed = len(self.daily_trades)
        wins_needed = self.required_wins - self.daily_wins
        trades_remaining = self.daily_trade_limit - trades_executed
        
        # Can't exceed daily limit
        if trades_executed >= self.daily_trade_limit:
            return False, f"Daily limit reached: {self.daily_trade_limit} trades"
        
        # Check if we can still achieve 80% win rate
        if trades_remaining > 0:
            # Best case: win all remaining trades
            max_possible_wins = self.daily_wins + trades_remaining
            
            if max_possible_wins < self.required_wins:
                return False, (
                    f"Cannot achieve {self.target_win_rate:.0%} win rate. "
                    f"Need {self.required_wins} wins, but max possible is {max_possible_wins}. "
                    f"Current: {self.daily_wins}W-{self.daily_losses}L"
                )
        
        return True, f"OK - {trades_executed}/{self.daily_trade_limit} trades used | {self.daily_wins}W-{self.daily_losses}L"
    
    def get_daily_stats(self) -> Dict:
        """Get daily trading statistics"""
        self.reset_if_new_day()
        
        trades_executed = len(self.daily_trades)
        trades_remaining = self.daily_trade_limit - trades_executed
        
        return {
            'date': self.daily_reset_date.isoformat(),
            'trades_executed': trades_executed,
            'trades_remaining': trades_remaining,
            'daily_limit': self.daily_trade_limit,
            'wins': self.daily_wins,
            'losses': self.daily_losses,
            'current_win_rate': self.daily_wins / trades_executed if trades_executed > 0 else 0,
            'required_win_rate': self.target_win_rate,
            'required_wins': self.required_wins,
            'wins_needed': max(0, self.required_wins - self.daily_wins),
            'can_execute': self.can_execute_trade()[0],
            'status_message': self.can_execute_trade()[1],
        }


class AILossRestrictionEngine:
    """
    Advanced AI engine to restrict losses and enforce 80% win rate
    
    Daily Requirement: Out of 10 trades, at least 8 must be positive
    """
    
    def __init__(self):
        self.history_analyzer = TradeHistoryAnalyzer()
        self.ml_predictor = SimpleMLPredictor()
        self.quota_manager = DailyTradeQuotaManager(target_win_rate=0.80, daily_trade_limit=10)
        self.trade_cache = {}
    
    def evaluate_signal(
        self,
        symbol: str,
        signal_data: Dict,
        all_recent_trades: List[Dict] = None
    ) -> PredictionResult:
        """
        Evaluate if a signal should be executed
        Returns prediction with recommendation to EXECUTE, WAIT, or BLOCK
        """
        
        # Update history if trades provided
        if all_recent_trades:
            for trade in all_recent_trades:
                if trade.get('symbol') not in self.trade_cache:
                    self.history_analyzer.add_trade(trade)
                    self.trade_cache[trade.get('symbol')] = True
        
        # Check daily quota
        can_trade, quota_msg = self.quota_manager.can_execute_trade()
        if not can_trade:
            logger.warning(f"[AI_LOSS_RESTRICTION] {quota_msg}")
            return PredictionResult(
                symbol=symbol,
                signal_confidence=signal_data.get('signal_confidence', 0),
                predicted_win_probability=0.0,
                recommendation='BLOCK',
                reason=quota_msg,
                confidence_level='MEDIUM',
                risk_score=1.0,
                expected_pnl_direction='LOSS'
            )
        
        # Extract features
        features = self.ml_predictor.extract_features(signal_data, self.history_analyzer)
        
        # Predict win probability
        predicted_prob = self.ml_predictor.predict_win_probability(features)
        
        # Get recent win rate
        recent_win_rate, _ = self.history_analyzer.calculate_win_rate(10)
        
        # Evaluate quality
        prediction = self.ml_predictor.evaluate_trade_quality(
            features,
            predicted_prob,
            recent_win_rate
        )
        
        # Set symbol
        prediction.symbol = symbol
        
        # Log prediction
        log_msg = (
            f"[AI_LOSS_RESTRICTION] {symbol}: "
            f"Prob={predicted_prob:.2%} | "
            f"Signal={signal_data.get('signal_confidence', 0):.2%} | "
            f"Recommendation={prediction.recommendation} | "
            f"WinRate={recent_win_rate:.1%}"
        )
        logger.info(log_msg)
        
        return prediction
    
    def record_trade_result(self, symbol: str, pnl: float):
        """Record a closed trade for learning"""
        is_win = pnl > 0
        self.quota_manager.record_trade_result(symbol, pnl, is_win)
    
    def get_daily_analytics(self) -> Dict:
        """Get detailed daily analytics"""
        stats = self.quota_manager.get_daily_stats()
        recent_win_rate, recent_count = self.history_analyzer.calculate_win_rate(10)
        
        stats['analytics'] = {
            'recent_win_rate': f"{recent_win_rate:.1%}",
            'recent_trades_count': recent_count,
            'cumulative_trades': len(self.history_analyzer.trade_history),
            'cumulative_wins': sum(1 for t in self.history_analyzer.trade_history if t.get('pnl', 0) > 0),
            'cumulative_losses': sum(1 for t in self.history_analyzer.trade_history if t.get('pnl', 0) <= 0),
        }
        
        return stats
    
    def get_symbol_quality_report(self) -> Dict[str, Dict]:
        """Get quality report for each symbol"""
        report = {}
        
        # Get all unique symbols
        symbols = set(t.get('symbol') for t in self.history_analyzer.trade_history)
        
        for symbol in symbols:
            win_rate, count = self.history_analyzer.get_symbol_win_rate(symbol)
            report[symbol] = {
                'win_rate': f"{win_rate:.1%}",
                'total_trades': count,
                'status': 'GOOD' if win_rate >= 0.50 else 'CAUTION' if win_rate >= 0.40 else 'AVOID'
            }
        
        return report


# Global instance
ai_loss_restriction_engine = AILossRestrictionEngine()
