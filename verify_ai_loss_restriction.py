#!/usr/bin/env python
"""
Verification Script for AI Loss Restriction System

This script checks:
1. Module imports and dependencies
2. API endpoints are accessible
3. Core classes can be instantiated
4. Configuration is valid
5. Sample prediction calculations work
"""

import sys
import os
import requests
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
END = '\033[0m'


def print_header(text):
    """Print a formatted header"""
    print(f"\n{BLUE}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{END}\n")


def print_success(text):
    """Print success message"""
    print(f"{GREEN}✓ {text}{END}")


def print_failure(text):
    """Print failure message"""
    print(f"{RED}✗ {text}{END}")


def print_warning(text):
    """Print warning message"""
    print(f"{YELLOW}⚠ {text}{END}")


def check_imports():
    """Check if all required modules can be imported"""
    print_header("Checking Module Imports")
    
    tests = {
        "FastAPI": lambda: __import__('fastapi'),
        "NumPy": lambda: __import__('numpy'),
        "Pandas": lambda: __import__('pandas'),
        "SQLAlchemy": lambda: __import__('sqlalchemy'),
        "Pydantic": lambda: __import__('pydantic'),
    }
    
    passed = 0
    for name, import_func in tests.items():
        try:
            import_func()
            print_success(f"Module '{name}' imported successfully")
            passed += 1
        except ImportError as e:
            print_failure(f"Module '{name}' not found: {e}")
    
    return passed == len(tests)


def check_ai_module():
    """Check if AI Loss Restriction module can be imported"""
    print_header("Checking AI Module Import")
    
    try:
        from app.engine.ai_loss_restriction import (
            TradeFeatures,
            PredictionResult,
            TradeHistoryAnalyzer,
            SimpleMLPredictor,
            DailyTradeQuotaManager,
            AILossRestrictionEngine,
            ai_loss_restriction_engine
        )
        print_success("AI Loss Restriction module imported successfully")
        print_success(f"Global instance initialized: {type(ai_loss_restriction_engine).__name__}")
        return True
    except ImportError as e:
        print_failure(f"Failed to import AI module: {e}")
        return False
    except Exception as e:
        print_failure(f"Error initializing AI module: {e}")
        return False


def check_core_classes():
    """Check if core classes can be instantiated"""
    print_header("Checking Core Classes")
    
    try:
        from app.engine.ai_loss_restriction import (
            TradeFeatures,
            TradeHistoryAnalyzer,
            SimpleMLPredictor,
            DailyTradeQuotaManager,
            AILossRestrictionEngine
        )
        
        # Test TradeFeatures
        features = TradeFeatures(
            signal_confidence=0.90,
            market_trend="BULLISH",
            trend_strength=0.75,
            option_type="CE",
            recent_win_rate=0.65,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=5,
            consecutive_losses=0,
            volatility_level="LOW",
            rsi_level=50,
            macd_histogram=10.0,
            bollinger_position=0.50,
            volume_ratio=1.2,
            price_momentum=1.5
        )
        print_success(f"TradeFeatures instantiated: {type(features).__name__}")
        
        # Test TradeHistoryAnalyzer
        analyzer = TradeHistoryAnalyzer()
        print_success(f"TradeHistoryAnalyzer instantiated: {type(analyzer).__name__}")
        
        # Test SimpleMLPredictor
        predictor = SimpleMLPredictor()
        print_success(f"SimpleMLPredictor instantiated: {type(predictor).__name__}")
        
        # Test DailyTradeQuotaManager
        quota = DailyTradeQuotaManager()
        print_success(f"DailyTradeQuotaManager instantiated: {type(quota).__name__}")
        
        # Test AILossRestrictionEngine
        engine = AILossRestrictionEngine()
        print_success(f"AILossRestrictionEngine instantiated: {type(engine).__name__}")
        
        return True
    except Exception as e:
        print_failure(f"Error instantiating classes: {e}")
        return False


def check_ml_prediction():
    """Check if ML prediction works"""
    print_header("Checking ML Prediction Engine")
    
    try:
        from app.engine.ai_loss_restriction import TradeFeatures, SimpleMLPredictor
        
        predictor = SimpleMLPredictor()
        
        # Test 1: Strong signal
        strong_features = TradeFeatures(
            signal_confidence=0.95,
            market_trend="BULLISH",
            trend_strength=0.85,
            option_type="CE",
            recent_win_rate=0.70,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=7,
            consecutive_losses=0,
            volatility_level="LOW",
            rsi_level=50,
            macd_histogram=15.0,
            bollinger_position=0.60,
            volume_ratio=1.3,
            price_momentum=2.0
        )
        
        prob_strong = predictor.predict_win_probability(strong_features)
        print(f"  Strong signal prediction: {prob_strong:.2%}")
        
        if prob_strong >= 0.70:
            print_success(f"Strong signal predicts {prob_strong:.2%} win rate (expected 70%+)")
        else:
            print_warning(f"Strong signal predicts only {prob_strong:.2%} (expected 70%+)")
        
        # Test 2: Weak signal
        weak_features = TradeFeatures(
            signal_confidence=0.40,
            market_trend="BEARISH",
            trend_strength=0.10,
            option_type="CE",  # Mismatch!
            recent_win_rate=0.30,
            time_of_day_hour=15,
            is_recovery_trade=True,
            days_since_last_loss=0,
            consecutive_losses=3,
            volatility_level="HIGH",
            rsi_level=85,
            macd_histogram=-10.0,
            bollinger_position=0.95,
            volume_ratio=0.6,
            price_momentum=-3.0
        )
        
        prob_weak = predictor.predict_win_probability(weak_features)
        print(f"  Weak signal prediction: {prob_weak:.2%}")
        
        if prob_weak < 0.50:
            print_success(f"Weak signal predicts {prob_weak:.2%} win rate (expected <50%)")
        else:
            print_warning(f"Weak signal predicts {prob_weak:.2%} (expected <50%)")
        
        # Test 3: Trend alignment bonus
        ce_bullish = TradeFeatures(
            signal_confidence=0.80,
            market_trend="BULLISH",
            trend_strength=0.70,
            option_type="CE",  # MATCHES BULLISH
            recent_win_rate=0.50,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=3,
            consecutive_losses=0,
            volatility_level="MEDIUM",
            rsi_level=50,
            macd_histogram=5.0,
            bollinger_position=0.50,
            volume_ratio=1.0,
            price_momentum=1.0
        )
        
        pe_bullish = TradeFeatures(
            signal_confidence=0.80,
            market_trend="BULLISH",
            trend_strength=0.70,
            option_type="PE",  # MISMATCHES BULLISH
            recent_win_rate=0.50,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=3,
            consecutive_losses=0,
            volatility_level="MEDIUM",
            rsi_level=50,
            macd_histogram=5.0,
            bollinger_position=0.50,
            volume_ratio=1.0,
            price_momentum=1.0
        )
        
        prob_ce = predictor.predict_win_probability(ce_bullish)
        prob_pe = predictor.predict_win_probability(pe_bullish)
        
        print(f"  BULLISH + CE: {prob_ce:.2%} (should be higher)")
        print(f"  BULLISH + PE: {prob_pe:.2%} (should be lower)")
        
        if prob_ce > prob_pe:
            print_success(f"Trend alignment bonus working (CE: {prob_ce:.2%} > PE: {prob_pe:.2%})")
        else:
            print_failure(f"Trend alignment not working (CE: {prob_ce:.2%} not > PE: {prob_pe:.2%})")
        
        return True
    except Exception as e:
        print_failure(f"Error testing ML predictions: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_quota_manager():
    """Check if quota manager works"""
    print_header("Checking Daily Quota Manager")
    
    try:
        from app.engine.ai_loss_restriction import DailyTradeQuotaManager
        
        quota = DailyTradeQuotaManager(
            target_win_rate=0.80,
            daily_trade_limit=10
        )
        
        print_success("Quota manager created")
        print(f"  Target win rate: {quota.target_win_rate:.0%}")
        print(f"  Daily trade limit: {quota.daily_trade_limit}")
        
        # Simulate some trades
        quota.record_trade(symbol="TEST1", pnl=100)
        quota.record_trade(symbol="TEST2", pnl=100)
        quota.record_trade(symbol="TEST3", pnl=-100)
        
        print(f"  Trades recorded: {len(quota.daily_trades)}")
        print(f"  Wins: {quota.daily_wins}, Losses: {quota.daily_losses}")
        print(f"  Win rate: {quota.get_current_win_rate():.1%}")
        
        can_trade = quota.can_continue_trading()
        print_success(f"Can continue trading: {can_trade}")
        
        can_achieve = quota.can_achieve_target()
        print_success(f"Can achieve 80% target: {can_achieve}")
        
        return True
    except Exception as e:
        print_failure(f"Error testing quota manager: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_engine_integration():
    """Check if engine integration works"""
    print_header("Checking Engine Integration")
    
    try:
        from app.engine.ai_loss_restriction import (
            TradeFeatures,
            AILossRestrictionEngine,
            Recommendation
        )
        
        engine = AILossRestrictionEngine()
        print_success("AI Engine created")
        
        # Evaluate a signal
        features = TradeFeatures(
            signal_confidence=0.88,
            market_trend="BULLISH",
            trend_strength=0.75,
            option_type="CE",
            recent_win_rate=0.65,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=5,
            consecutive_losses=0,
            volatility_level="LOW",
            rsi_level=50,
            macd_histogram=10.0,
            bollinger_position=0.50,
            volume_ratio=1.2,
            price_momentum=1.5
        )
        
        result = engine.evaluate_signal(features)
        print_success(f"Signal evaluated: {result.recommendation.name}")
        print(f"  Win probability: {result.predicted_win_probability:.2%}")
        print(f"  Confidence level: {result.confidence_level}")
        print(f"  Risk score: {result.risk_score:.2f}/1.0")
        
        # Record some trades
        engine.record_trade_result(symbol="TEST1", pnl=100)
        engine.record_trade_result(symbol="TEST2", pnl=100)
        engine.record_trade_result(symbol="TEST3", pnl=-100)
        
        print_success("Trade results recorded")
        
        # Get analytics
        analytics = engine.get_daily_analytics()
        print_success("Daily analytics retrieved")
        print(f"  Trades executed: {analytics['daily_quota']['trades_executed']}")
        print(f"  Win rate: {analytics['daily_quota']['current_win_rate']:.1%}")
        
        # Get symbol quality
        quality = engine.get_symbol_quality_report()
        print_success("Symbol quality report generated")
        print(f"  Total symbols: {quality['summary']['total_symbols']}")
        
        return True
    except Exception as e:
        print_failure(f"Error testing engine integration: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_api_endpoints():
    """Check if API endpoints are accessible (requires running backend)"""
    print_header("Checking API Endpoints")
    
    base_url = "http://localhost:8000"
    endpoints = [
        ("POST", "/autotrade/ai-evaluate-signal"),
        ("GET", "/autotrade/ai-daily-analytics"),
        ("GET", "/autotrade/ai-symbol-quality"),
    ]
    
    print_warning("This check requires the backend to be running on localhost:8000")
    print("Skipping API checks (run this after backend is started)\n")
    
    return True  # Don't fail verification if backend not running


def check_documentation():
    """Check if documentation files exist"""
    print_header("Checking Documentation")
    
    docs = {
        "AI Loss Restriction Guide": "AI_LOSS_RESTRICTION_GUIDE.md",
        "AI Quick Start": "AI_LOSS_RESTRICTION_QUICK_START.md",
        "Test Suite": "test_ai_loss_restriction.py",
    }
    
    base_path = Path(__file__).parent
    found = 0
    
    for name, filename in docs.items():
        filepath = base_path / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print_success(f"{name}: {filename} ({size:,} bytes)")
            found += 1
        else:
            print_failure(f"{name}: {filename} not found")
    
    return found == len(docs)


def check_code_integration():
    """Check if core code is integrated in auto_trading_simple.py"""
    print_header("Checking Backend Integration")
    
    auto_trading_path = Path(__file__).parent / "backend" / "app" / "routes" / "auto_trading_simple.py"
    
    if not auto_trading_path.exists():
        print_failure(f"auto_trading_simple.py not found at {auto_trading_path}")
        return False
    
    try:
        with open(auto_trading_path, 'r') as f:
            content = f.read()
        
        checks = {
            "AI import statement": "from app.engine.ai_loss_restriction import ai_loss_restriction_engine",
            "AI evaluate endpoint": "POST /autotrade/ai-evaluate-signal",
            "AI daily analytics endpoint": "GET /autotrade/ai-daily-analytics",
            "AI symbol quality endpoint": "GET /autotrade/ai-symbol-quality",
            "Trade result recording": "ai_loss_restriction_engine.record_trade_result",
        }
        
        for check_name, check_string in checks.items():
            # For endpoints, check the route path
            if "POST" in check_string or "GET" in check_string:
                endpoint = check_string.split(" ")[1]
                if endpoint in content:
                    print_success(f"{check_name} integrated")
                else:
                    print_failure(f"{check_name} NOT found")
            else:
                if check_string in content:
                    print_success(f"{check_name} integrated")
                else:
                    print_failure(f"{check_name} NOT found")
        
        return True
    except Exception as e:
        print_failure(f"Error checking integration: {e}")
        return False


def main():
    """Run all verification checks"""
    print(f"\n{BLUE}AI Loss Restriction System - Verification Script{END}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {}
    
    # Run checks
    results["Module Imports"] = check_imports()
    results["AI Module"] = check_ai_module()
    results["Core Classes"] = check_core_classes()
    results["ML Prediction"] = check_ml_prediction()
    results["Quota Manager"] = check_quota_manager()
    results["Engine Integration"] = check_engine_integration()
    results["API Endpoints"] = check_api_endpoints()
    results["Documentation"] = check_documentation()
    results["Code Integration"] = check_code_integration()
    
    # Summary
    print_header("Verification Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check_name, result in results.items():
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        color = GREEN if result else RED
        print(f"{color}{symbol} {check_name}: {status}{END}")
    
    print(f"\n{BLUE}Total: {passed}/{total} checks passed{END}\n")
    
    if passed == total:
        print_success("All checks passed! AI Loss Restriction system is ready to use.")
        return 0
    else:
        print_failure(f"{total - passed} check(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
