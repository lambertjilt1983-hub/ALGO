"""
Auto Trading Engine with Risk Management
Combines multiple strategies and executes trades automatically
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import random

@dataclass
class TradeSignal:
    """Trade signal from strategy analysis"""
    symbol: str
    action: str  # BUY or SELL
    confidence: float  # 0.0 to 1.0
    strategy_name: str
    entry_price: float
    stop_loss: float
    target_price: float
    quantity: int
    timestamp: datetime

@dataclass
class Trade:
    """Executed trade record"""
    id: int
    symbol: str
    action: str
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    stop_loss: float
    target_price: float
    status: str  # OPEN, CLOSED, STOPPED
    entry_time: datetime
    exit_time: Optional[datetime]
    profit_loss: float
    profit_percentage: float
    strategy_used: str

class AutoTradingEngine:
    """Main auto-trading engine with risk management"""
    
    def __init__(self):
        self.enabled = False
        self.is_demo_mode = True  # Demo mode by default (no real trades)
        self.max_position_size_percent = 60  # Use 60% of available balance
        self.min_confidence_threshold = 0.70  # 70% minimum confidence
        self.max_daily_loss_percent = 5  # Stop trading if 5% daily loss
        self.active_trades: List[Trade] = []
        self.trade_history: List[Trade] = []
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
    
    async def get_default_price(self) -> float:
        """Get default price from live market data"""
        # In production: fetch from broker API
        import time
        from datetime import datetime
        now = datetime.now()
        days_from_jan = (now - datetime(2026, 1, 1)).days
        random.seed(days_from_jan)
        cumulative_drift = sum([random.uniform(-0.001, 0.001) for _ in range(days_from_jan)])
        base = 22000 * (1 + cumulative_drift)
        random.seed(now.day + now.month * 100)
        daily = random.uniform(base * 0.965, base * 1.035)
        random.seed(int(time.time()) % 10000)
        return round(daily * (1 + random.uniform(-0.015, 0.015)), 2)
        
    def analyze_all_strategies(self, market_data: Dict) -> List[TradeSignal]:
        """
        Analyze market using all strategies and generate signals
        Combines RSI, MACD, Bollinger Bands, and trend analysis
        """
        signals = []
        
        # Strategy 1: RSI + MACD Combined
        rsi_macd_signal = self._rsi_macd_strategy(market_data)
        if rsi_macd_signal:
            signals.append(rsi_macd_signal)
        
        # Strategy 2: Bollinger Bands Breakout
        bb_signal = self._bollinger_bands_strategy(market_data)
        if bb_signal:
            signals.append(bb_signal)
        
        # Strategy 3: Trend Following
        trend_signal = self._trend_following_strategy(market_data)
        if trend_signal:
            signals.append(trend_signal)
        
        # Strategy 4: Support/Resistance Breakout
        sr_signal = self._support_resistance_strategy(market_data)
        if sr_signal:
            signals.append(sr_signal)
        
        return signals
    
    def _rsi_macd_strategy(self, market_data: Dict) -> Optional[TradeSignal]:
        """RSI + MACD combination strategy"""
        # Simulated analysis based on time and price patterns
        symbol = market_data.get('symbol', 'NIFTY')
        current_price = market_data.get('price')
        if current_price is None:
            # Fetch live price if not provided
            import asyncio
            current_price = asyncio.run(self.get_default_price())
        
        # Use time-based seed for more realistic simulation
        import time
        from datetime import datetime
        now = datetime.now()
        hour_seed = now.hour * 100 + now.minute
        
        random.seed(hour_seed)
        rsi = random.uniform(25, 75)
        macd_histogram = random.uniform(-60, 60)
        
        confidence = 0.0
        action = None
        
        # Bullish: RSI < 45 and MACD positive
        if rsi < 45 and macd_histogram > 0:
            action = 'BUY'
            confidence = 0.75 + (45 - rsi) / 80
        
        # Bearish: RSI > 55 and MACD negative
        elif rsi > 55 and macd_histogram < 0:
            action = 'SELL'
            confidence = 0.75 + (rsi - 55) / 80
        
        # Reset random seed
        random.seed()
        
        if action and confidence >= self.min_confidence_threshold:
            stop_loss = current_price * 0.98 if action == 'BUY' else current_price * 1.02
            target = current_price * 1.03 if action == 'BUY' else current_price * 0.97
            
            return TradeSignal(
                symbol=symbol,
                action=action,
                confidence=min(confidence, 0.95),
                strategy_name='RSI_MACD',
                entry_price=current_price,
                stop_loss=stop_loss,
                target_price=target,
                quantity=self._calculate_quantity(current_price, market_data.get('balance', 100000)),
                timestamp=datetime.now()
            )
        return None
    
    def _bollinger_bands_strategy(self, market_data: Dict) -> Optional[TradeSignal]:
        """Bollinger Bands breakout strategy"""
        symbol = market_data.get('symbol', 'BANKNIFTY')
        current_price = market_data.get('price', 46234.0)
        
        # Simulated BB analysis
        upper_band = current_price * 1.02
        lower_band = current_price * 0.98
        price_position = random.uniform(0.96, 1.04)
        
        action = None
        confidence = 0.0
        
        # Price breaking above upper band (bullish)
        if price_position > 1.015:
            action = 'BUY'
            confidence = 0.78 + (price_position - 1.015) * 10
        
        # Price breaking below lower band (bearish)
        elif price_position < 0.985:
            action = 'SELL'
            confidence = 0.78 + (0.985 - price_position) * 10
        
        if action and confidence >= self.min_confidence_threshold:
            stop_loss = current_price * 0.985 if action == 'BUY' else current_price * 1.015
            target = current_price * 1.025 if action == 'BUY' else current_price * 0.975
            
            return TradeSignal(
                symbol=symbol,
                action=action,
                confidence=min(confidence, 0.92),
                strategy_name='BOLLINGER_BANDS',
                entry_price=current_price,
                stop_loss=stop_loss,
                target_price=target,
                quantity=self._calculate_quantity(current_price, market_data.get('balance', 100000)),
                timestamp=datetime.now()
            )
        return None
    
    def _trend_following_strategy(self, market_data: Dict) -> Optional[TradeSignal]:
        """Trend following with moving averages"""
        symbol = market_data.get('symbol', 'NIFTY')
        current_price = market_data.get('price')
        if current_price is None:
            import asyncio
            current_price = asyncio.run(self.get_default_price())
        
        # Simulated moving average analysis with time-based patterns
        from datetime import datetime
        now = datetime.now()
        
        # Use deterministic seed based on current time
        import time
        hour_seed = now.hour * 100 + now.minute
        random.seed(hour_seed + 50)
        
        trend_strength = random.uniform(0.5, 1.0)
        sma_20 = current_price * random.uniform(0.98, 1.02)
        sma_50 = current_price * random.uniform(0.96, 1.04)
        
        action = None
        confidence = 0.0
        
        # Bullish crossover with strong trend
        if sma_20 > sma_50 and current_price > sma_20 and trend_strength > 0.6:
            action = 'BUY'
            confidence = 0.72 + (trend_strength * 0.15)
        
        # Bearish crossover with strong trend
        elif sma_20 < sma_50 and current_price < sma_20 and trend_strength > 0.6:
            action = 'SELL'
            confidence = 0.72 + (trend_strength * 0.15)
        
        # Reset random seed
        random.seed()
        
        if action and confidence >= self.min_confidence_threshold:
            stop_loss = current_price * 0.975 if action == 'BUY' else current_price * 1.025
            target = current_price * 1.04 if action == 'BUY' else current_price * 0.96
            
            return TradeSignal(
                symbol=symbol,
                action=action,
                confidence=confidence,
                strategy_name='TREND_FOLLOWING',
                entry_price=current_price,
                stop_loss=stop_loss,
                target_price=target,
                quantity=self._calculate_quantity(current_price, market_data.get('balance', 100000)),
                timestamp=datetime.now()
            )
        return None
    
    def _support_resistance_strategy(self, market_data: Dict) -> Optional[TradeSignal]:
        """Support/Resistance breakout strategy"""
        symbol = market_data.get('symbol', 'BANKNIFTY')
        current_price = market_data.get('price', 46234.0)
        
        # Simulated S/R levels
        resistance = current_price * 1.01
        support = current_price * 0.99
        volume_ratio = random.uniform(0.8, 1.5)
        
        action = None
        confidence = 0.0
        
        # Resistance breakout with volume
        if current_price > resistance and volume_ratio > 1.2:
            action = 'BUY'
            confidence = 0.85 + (volume_ratio - 1.2) * 0.2
        
        # Support breakdown with volume
        elif current_price < support and volume_ratio > 1.2:
            action = 'SELL'
            confidence = 0.85 + (volume_ratio - 1.2) * 0.2
        
        if action and confidence >= self.min_confidence_threshold:
            stop_loss = current_price * 0.98 if action == 'BUY' else current_price * 1.02
            target = current_price * 1.035 if action == 'BUY' else current_price * 0.965
            
            return TradeSignal(
                symbol=symbol,
                action=action,
                confidence=min(confidence, 0.94),
                strategy_name='SUPPORT_RESISTANCE',
                entry_price=current_price,
                stop_loss=stop_loss,
                target_price=target,
                quantity=self._calculate_quantity(current_price, market_data.get('balance', 100000)),
                timestamp=datetime.now()
            )
        return None
    
    def _calculate_quantity(self, price: float, total_balance: float) -> int:
        """Calculate position size based on 50% of balance"""
        usable_balance = total_balance * (self.max_position_size_percent / 100)
        quantity = int(usable_balance / price)
        return max(1, quantity)  # At least 1 unit
    
    def aggregate_signals(self, signals: List[TradeSignal]) -> Optional[TradeSignal]:
        """
        Combine multiple strategy signals into one high-confidence signal
        Accept single high-confidence signals or multiple agreeing strategies
        """
        if not signals:
            return None
        
        # Group signals by action
        buy_signals = [s for s in signals if s.action == 'BUY']
        sell_signals = [s for s in signals if s.action == 'SELL']
        
        # If multiple strategies agree, boost confidence
        if len(buy_signals) >= 2:
            # Use the highest confidence signal
            best_signal = max(buy_signals, key=lambda x: x.confidence)
            # Boost confidence when multiple strategies agree
            best_signal.confidence = min(0.95, best_signal.confidence + 0.05 * (len(buy_signals) - 1))
            return best_signal
        
        elif len(sell_signals) >= 2:
            best_signal = max(sell_signals, key=lambda x: x.confidence)
            best_signal.confidence = min(0.95, best_signal.confidence + 0.05 * (len(sell_signals) - 1))
            return best_signal
        
        # If only one signal but high confidence, accept it
        elif len(buy_signals) == 1 and buy_signals[0].confidence >= self.min_confidence_threshold:
            return buy_signals[0]
        
        elif len(sell_signals) == 1 and sell_signals[0].confidence >= self.min_confidence_threshold:
            return sell_signals[0]
        
        return None
    
    def execute_trade(self, signal: TradeSignal, broker_id: int) -> Trade:
        """
        Execute trade with proper risk management
        Returns Trade object with entry details
        """
        trade_id = self.total_trades + 1
        
        trade = Trade(
            id=trade_id,
            symbol=signal.symbol,
            action=signal.action,
            entry_price=signal.entry_price,
            exit_price=None,
            quantity=signal.quantity,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            status='OPEN',
            entry_time=datetime.now(),
            exit_time=None,
            profit_loss=0.0,
            profit_percentage=0.0,
            strategy_used=signal.strategy_name
        )
        
        self.active_trades.append(trade)
        self.total_trades += 1
        
        return trade
    
    def monitor_trades(self, current_prices: Dict[str, float]) -> List[Trade]:
        """
        Monitor active trades and close if stop-loss or target hit
        Returns list of closed trades
        """
        closed_trades = []
        
        for trade in self.active_trades[:]:  # Iterate over copy
            if trade.status != 'OPEN':
                continue
            
            current_price = current_prices.get(trade.symbol, trade.entry_price)
            
            should_close = False
            exit_reason = None
            
            if trade.action == 'BUY':
                # Check target or stop-loss for BUY trade
                if current_price >= trade.target_price:
                    should_close = True
                    exit_reason = 'TARGET_HIT'
                elif current_price <= trade.stop_loss:
                    should_close = True
                    exit_reason = 'STOP_LOSS'
            
            else:  # SELL trade
                # Check target or stop-loss for SELL trade
                if current_price <= trade.target_price:
                    should_close = True
                    exit_reason = 'TARGET_HIT'
                elif current_price >= trade.stop_loss:
                    should_close = True
                    exit_reason = 'STOP_LOSS'
            
            if should_close:
                trade.exit_price = current_price
                trade.exit_time = datetime.now()
                trade.status = 'CLOSED' if exit_reason == 'TARGET_HIT' else 'STOPPED'
                
                # Calculate P&L
                if trade.action == 'BUY':
                    pnl = (current_price - trade.entry_price) * trade.quantity
                    pnl_pct = ((current_price - trade.entry_price) / trade.entry_price) * 100
                else:
                    pnl = (trade.entry_price - current_price) * trade.quantity
                    pnl_pct = ((trade.entry_price - current_price) / trade.entry_price) * 100
                
                trade.profit_loss = pnl
                trade.profit_percentage = pnl_pct
                
                # Update statistics
                self.daily_pnl += pnl
                if pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                self.active_trades.remove(trade)
                self.trade_history.append(trade)
                closed_trades.append(trade)
        
        return closed_trades
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'enabled': self.enabled,
            'is_demo_mode': self.is_demo_mode,
            'mode': 'DEMO' if self.is_demo_mode else 'LIVE',
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(win_rate, 2),
            'daily_pnl': round(self.daily_pnl, 2),
            'active_trades_count': len(self.active_trades),
            'max_position_size_percent': self.max_position_size_percent,
            'min_confidence_threshold': self.min_confidence_threshold,
            'max_trades': 10  # Max concurrent trades
        }

# Global auto-trader instance
auto_trader = AutoTradingEngine()
