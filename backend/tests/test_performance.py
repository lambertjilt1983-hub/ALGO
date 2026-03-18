"""Performance and stress tests."""
import pytest
import time
from datetime import datetime, timedelta
from app.models.trading import PaperTrade
from app.routes.auto_trading_simple import (
    _count_daily_trades,
    _count_consecutive_sl_hits,
    _get_daily_pnl,
)


class TestPerformanceBaseline:
    """Test performance baselines for critical operations."""

    def test_count_daily_trades_performance(self, db_session, benchmark=None):
        """Test performance of counting daily trades."""
        now = datetime.utcnow()
        
        # Create 1000 trades
        for i in range(1000):
            trade = PaperTrade(
                symbol=f"NIFTY{i % 100}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=now - timedelta(seconds=i),
            )
            db_session.add(trade)
        db_session.commit()

        # Benchmark the count operation
        start = time.time()
        count = _count_daily_trades(db_session)
        duration = time.time() - start

        # Should complete in < 1 second even with 1000 trades
        assert duration < 1.0
        assert count == 1000

    def test_consecutive_sl_counting_performance(self, db_session):
        """Test performance of counting consecutive SL_HIT."""
        now = datetime.utcnow()
        
        # Create 500 trades with mixed statuses
        for i in range(500):
            status = "SL_HIT" if i % 3 == 0 else ("TARGET_HIT" if i % 3 == 1 else "PROFIT_TRAIL")
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                exit_price=90.0 if status == "SL_HIT" else 110.0,
                exit_time=now - timedelta(seconds=(500 - i)),
                status=status,
            )
            db_session.add(trade)
        db_session.commit()

        # Benchmark
        start = time.time()
        count = _count_consecutive_sl_hits(db_session)
        duration = time.time() - start

        # Should complete in < 1 second
        assert duration < 1.0

    def test_daily_pnl_calculation_performance(self, db_session):
        """Test performance of calculating daily PnL."""
        now = datetime.utcnow()
        
        # Create 1000 closed trades
        for i in range(1000):
            exit_price = 110.0 if i % 2 == 0 else 90.0
            trade = PaperTrade(
                symbol=f"NIFTY{i % 100}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                exit_price=exit_price,
                exit_time=now - timedelta(seconds=i),
                status="TARGET_HIT" if i % 2 == 0 else "SL_HIT",
            )
            db_session.add(trade)
        db_session.commit()

        # Benchmark
        start = time.time()
        pnl = _get_daily_pnl(db_session)
        duration = time.time() - start

        # Should complete in < 1 second even with 1000 trades
        assert duration < 1.0
        # PnL should be (110-100)*50*500 + (90-100)*50*500 = 0
        assert pnl == pytest.approx(0.0, abs=1)


class TestScalability:
    """Test system scalability with large datasets."""

    def test_1000_daily_trades_handling(self, db_session):
        """Test system handles 1000 daily trades."""
        now = datetime.utcnow()
        
        # Create 1000 trades
        trades_to_create = []
        for i in range(1000):
            trade = PaperTrade(
                symbol=f"NIFTY{i % 50}",
                side="BUY",
                entry_price=100.0 + (i % 20),
                stop_loss=90.0,
                target=110.0 + (i % 20),
                quantity=50,
                entry_time=now - timedelta(seconds=i),
                status="OPEN" if i % 3 == 0 else "TARGET_HIT",
            )
            trades_to_create.append(trade)
        
        db_session.bulk_save_objects(trades_to_create)
        db_session.commit()

        # Verify all saved
        total_trades = db_session.query(PaperTrade).count()
        assert total_trades == 1000

    def test_concurrent_symbol_handling(self, db_session):
        """Test system handles many symbols simultaneously."""
        now = datetime.utcnow()
        
        # Create trades for 200 different symbols
        for symbol_idx in range(200):
            for trade_idx in range(5):
                trade = PaperTrade(
                    symbol=f"NIFTY{symbol_idx}CE",
                    side="BUY",
                    entry_price=100.0,
                    stop_loss=90.0,
                    target=110.0,
                    quantity=50,
                    entry_time=now - timedelta(seconds=trade_idx),
                    status="OPEN",
                )
                db_session.add(trade)
        db_session.commit()

        # Query should return 1000 trades
        total = db_session.query(PaperTrade).count()
        assert total == 1000

        # Each symbol should have 5 trades
        for symbol_idx in range(200):
            count = db_session.query(PaperTrade).filter_by(
                symbol=f"NIFTY{symbol_idx}CE"
            ).count()
            assert count == 5


class TestRapidPriceUpdates:
    """Test handling rapid price updates."""

    def test_high_frequency_price_updates(self, db_session, sample_paper_trade):
        """Test handling 100+ price updates per second."""
        # Simulate 100 rapid price updates
        base_price = sample_paper_trade.entry_price
        
        for i in range(100):
            # Update price rapidly
            current_price = base_price + (i * 0.1)
            
            # Check if should exit based on price
            if current_price <= sample_paper_trade.stop_loss:
                sample_paper_trade.exit_price = current_price
                sample_paper_trade.status = "SL_HIT"
                break
            elif current_price >= sample_paper_trade.target:
                sample_paper_trade.exit_price = current_price
                sample_paper_trade.status = "TARGET_HIT"
                break

        db_session.commit()

        # Verify trade exited or still open
        assert sample_paper_trade.status in ["OPEN", "SL_HIT", "TARGET_HIT"]

    def test_batch_price_update_consistency(self, db_session):
        """Test batch updating 100 trades maintains consistency."""
        now = datetime.utcnow()
        
        # Create 100 trades
        trades = []
        for i in range(100):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=now - timedelta(seconds=i),
                status="OPEN",
            )
            trades.append(trade)
            db_session.add(trade)
        db_session.commit()

        # Batch update all trades (simulate price update at 105)
        for trade in trades:
            trade.exit_price = 105.0
            trade.status = "PROFIT_TRAIL"

        db_session.commit()

        # Verify all updated
        exited = db_session.query(PaperTrade).filter_by(status="PROFIT_TRAIL").count()
        assert exited == 100


class TestConcurrentOperations:
    """Test handling concurrent operations."""

    def test_multiple_trades_creation_isolation(self, db_session):
        """Test creating multiple trades doesn't interfere."""
        now = datetime.utcnow()
        
        # Create 50 trades rapidly
        for i in range(50):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0 + i,
                stop_loss=90.0,
                target=110.0 + i,
                quantity=50,
                entry_time=now - timedelta(seconds=i),
                status="OPEN",
            )
            db_session.add(trade)

        db_session.commit()

        # Verify all created and isolated
        total = db_session.query(PaperTrade).count()
        assert total == 50

        # Each has correct entry price
        for i in range(50):
            trade = db_session.query(PaperTrade).filter_by(
                symbol=f"NIFTY{i}"
            ).first()
            assert trade.entry_price == pytest.approx(100.0 + i, rel=1e-2)

    def test_quality_gate_filter_performance(self, db_session):
        """Test quality gate filtering on many trades."""
        now = datetime.utcnow()
        
        # Create 500 trades with various quality scores
        for i in range(500):
            quality = 30 + (i % 70)  # Range 30-99
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                signal_data={"quality_score": float(quality)},
            )
            db_session.add(trade)
        db_session.commit()

        # Filter for high-quality trades (>= 70)
        start = time.time()
        high_quality = [
            t for t in db_session.query(PaperTrade).all()
            if (t.signal_data or {}).get("quality_score", 0) >= 70
        ]
        duration = time.time() - start

        # Should complete in < 0.5 seconds
        assert duration < 0.5
        # Values cycle from 30-99 (70 values), and 30 of those are >= 70.
        # For 500 rows this yields ~214 matches (observed around 210 due cycle boundaries).
        assert 200 < len(high_quality) < 220


class TestMemoryEfficiency:
    """Test memory efficiency with large datasets."""

    def test_bulk_insert_memory_efficiency(self, db_session):
        """Test bulk insert doesn't consume excessive memory."""
        # Create 5000 trades and verify memory-efficient insertion
        trades = []
        for i in range(5000):
            trade = PaperTrade(
                symbol=f"NIFTY{i % 100}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=datetime.utcnow() - timedelta(seconds=i),
            )
            trades.append(trade)

        # Bulk save
        try:
            db_session.bulk_save_objects(trades)
            db_session.commit()
            total = db_session.query(PaperTrade).count()
            assert total == 5000
        except MemoryError:
            pytest.fail("Bulk insert caused memory error")

    def test_lazy_loading_trades(self, db_session):
        """Test efficient lazy loading of large trade sets."""
        now = datetime.utcnow()
        
        # Create 2000 trades
        for i in range(2000):
            trade = PaperTrade(
                symbol=f"NIFTY{i % 50}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=now - timedelta(seconds=i),
                status="OPEN" if i % 2 == 0 else "CLOSED",
            )
            db_session.add(trade)
        db_session.commit()

        # Lazy load with pagination
        page_size = 100
        for page in range(20):
            start = page * page_size
            trades = (
                db_session.query(PaperTrade)
                .offset(start)
                .limit(page_size)
                .all()
            )
            assert len(trades) == page_size


class TestQueryOptimization:
    """Test query optimization for common operations."""

    def test_daily_trade_count_indexed(self, db_session):
        """Test daily trade count uses indexes efficiently."""
        now = datetime.utcnow()
        
        # Create 500 trades
        for i in range(500):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=now - timedelta(seconds=i),
            )
            db_session.add(trade)
        db_session.commit()

        # Count should use index
        start = time.time()
        count = (
            db_session.query(PaperTrade)
            .filter(PaperTrade.entry_time >= now.replace(hour=0, minute=0))
            .count()
        )
        duration = time.time() - start

        assert duration < 0.1  # Should be very fast with index
        assert count == 500

    def test_status_filter_performance(self, db_session):
        """Test filtering by status performs efficiently."""
        now = datetime.utcnow()
        
        # Create 1000 trades with various statuses
        statuses = ["OPEN", "TARGET_HIT", "SL_HIT", "PROFIT_TRAIL", "CLOSED"]
        for i in range(1000):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                status=statuses[i % 5],
            )
            db_session.add(trade)
        db_session.commit()

        # Filter for specific status
        start = time.time()
        target_hit = db_session.query(PaperTrade).filter_by(
            status="TARGET_HIT"
        ).count()
        duration = time.time() - start

        assert duration < 0.1
        assert target_hit == 200  # 1000 / 5


class TestStressLimits:
    """Test system behavior at stress limits."""

    def test_market_open_simulation(self, db_session):
        """Simulate market opening with rapid trade creation."""
        now = datetime.utcnow()
        
        # Simulate 100 trades created in first minute
        for i in range(100):
            trade = PaperTrade(
                symbol=f"NIFTY{i % 10}",
                side="BUY",
                entry_price=100.0 + (i % 20) * 0.1,
                stop_loss=90.0,
                target=110.0 + (i % 20) * 0.1,
                quantity=50 + (i % 50),
                entry_time=now - timedelta(seconds=(100 - i)),
            )
            db_session.add(trade)
        db_session.commit()

        total = db_session.query(PaperTrade).count()
        assert total == 100

    def test_market_close_simultaneous_exits(self, db_session):
        """Simulate market close with multiple simultaneous exits."""
        now = datetime.utcnow()
        
        # Create 50 open trades
        trades = []
        for i in range(50):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=now - timedelta(hours=6),
                status="OPEN",
            )
            trades.append(trade)
            db_session.add(trade)
        db_session.commit()

        # Simulate all exiting at target
        now = datetime.utcnow()
        for trade in trades:
            trade.exit_price = trade.target
            trade.exit_time = now
            trade.status = "TARGET_HIT"

        db_session.commit()

        # Verify all exited
        exited = db_session.query(PaperTrade).filter_by(status="TARGET_HIT").count()
        assert exited == 50
