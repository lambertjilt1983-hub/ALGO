"""Tests for quality gate helper functions."""
import pytest
from datetime import datetime, timedelta
from app.models.trading import PaperTrade
from app.routes.auto_trading_simple import (
    _count_daily_trades,
    _count_consecutive_sl_hits,
    _get_daily_pnl,
    _should_allow_new_trade,
)


class TestCountDailyTrades:
    """Test _count_daily_trades helper function."""

    def test_no_trades(self, db_session):
        """Test counting when no trades exist."""
        count = _count_daily_trades(db_session)
        assert count == 0

    def test_single_trade_today(self, db_session):
        """Test counting single trade created today."""
        trade = PaperTrade(
            symbol="NIFTY2631723850PE",
            side="BUY",
            entry_price=287.50,
            stop_loss=275.00,
            target=314.85,
            quantity=65,
            entry_time=datetime.utcnow(),
        )
        db_session.add(trade)
        db_session.commit()

        count = _count_daily_trades(db_session)
        assert count == 1

    def test_multiple_trades_today(self, db_session):
        """Test counting multiple trades created today."""
        for i in range(15):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=datetime.utcnow(),
            )
            db_session.add(trade)
        db_session.commit()

        count = _count_daily_trades(db_session)
        assert count == 15

    def test_exclude_old_trades(self, db_session):
        """Test that trades from yesterday are not counted."""
        # Add trade from yesterday
        yesterday = datetime.utcnow() - timedelta(days=1)
        old_trade = PaperTrade(
            symbol="NIFTY_OLD",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            entry_time=yesterday,
        )
        db_session.add(old_trade)

        # Add trade from today
        new_trade = PaperTrade(
            symbol="NIFTY_NEW",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            entry_time=datetime.utcnow(),
        )
        db_session.add(new_trade)
        db_session.commit()

        count = _count_daily_trades(db_session)
        assert count == 1

    def test_count_trades_across_both_tables(self, db_session):
        """Test counting trades from both active and history tables."""
        # Add trades to active table
        for i in range(5):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=datetime.utcnow(),
                status="OPEN",
            )
            db_session.add(trade)

        # Add trades to history (closed trades)
        for i in range(5, 8):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=datetime.utcnow(),
                exit_time=datetime.utcnow() + timedelta(minutes=5),
                status="TARGET_HIT",
            )
            db_session.add(trade)
        db_session.commit()

        count = _count_daily_trades(db_session)
        assert count == 8


class TestCountConsecutiveSLHits:
    """Test _count_consecutive_sl_hits helper function."""

    def test_no_trades(self, db_session):
        """Test when no trades exist."""
        count = _count_consecutive_sl_hits(db_session)
        assert count == 0

    def test_single_sl_hit(self, db_session):
        """Test with single SL_HIT trade."""
        trade = PaperTrade(
            symbol="NIFTY2631723850PE",
            side="BUY",
            entry_price=287.50,
            stop_loss=275.00,
            target=314.85,
            quantity=65,
            exit_price=275.00,
            exit_time=datetime.utcnow(),
            status="SL_HIT",
        )
        db_session.add(trade)
        db_session.commit()

        count = _count_consecutive_sl_hits(db_session)
        assert count == 1

    def test_three_consecutive_sl_hits(self, db_session):
        """Test counting 3 consecutive SL_HIT trades."""
        now = datetime.utcnow()
        for i in range(3):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                exit_price=90.0,
                exit_time=now - timedelta(minutes=(3 - i)),
                status="SL_HIT",
            )
            db_session.add(trade)
        db_session.commit()

        count = _count_consecutive_sl_hits(db_session)
        assert count == 3

    def test_sl_hit_broken_by_win(self, db_session):
        """Test that consecutive SL_HIT count resets on win."""
        now = datetime.utcnow()
        
        # Two SL_HIT trades
        for i in range(2):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                exit_price=90.0,
                exit_time=now - timedelta(minutes=(3 - i)),
                status="SL_HIT",
            )
            db_session.add(trade)

        # One winning trade
        win = PaperTrade(
            symbol="NIFTY_WIN",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=110.0,
            exit_time=now - timedelta(minutes=1),
            status="TARGET_HIT",
        )
        db_session.add(win)
        db_session.commit()

        count = _count_consecutive_sl_hits(db_session)
        assert count == 0

    def test_sl_hit_after_win(self, db_session):
        """Test that new SL_HIT after win restarts count."""
        now = datetime.utcnow()
        
        # Winning trade (most recent)
        win = PaperTrade(
            symbol="NIFTY_WIN",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=110.0,
            exit_time=now,
            status="TARGET_HIT",
        )
        db_session.add(win)

        # One SL_HIT after win
        sl = PaperTrade(
            symbol="NIFTY_SL",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=90.0,
            exit_time=now + timedelta(minutes=1),
            status="SL_HIT",
        )
        db_session.add(sl)
        db_session.commit()

        count = _count_consecutive_sl_hits(db_session)
        assert count == 1


class TestGetDailyPnL:
    """Test _get_daily_pnl helper function."""

    def test_no_trades(self, db_session):
        """Test PnL when no trades exist."""
        pnl = _get_daily_pnl(db_session)
        assert pnl == 0.0

    def test_single_profit_trade(self, db_session):
        """Test PnL from single profitable trade."""
        trade = PaperTrade(
            symbol="NIFTY2631723850PE",
            side="BUY",
            entry_price=287.50,
            stop_loss=275.00,
            target=314.85,
            quantity=65,
            exit_price=314.85,
            exit_time=datetime.utcnow(),
            status="TARGET_HIT",
        )
        db_session.add(trade)
        db_session.commit()

        pnl = _get_daily_pnl(db_session)
        expected = (314.85 - 287.50) * 65
        assert pnl == pytest.approx(expected, rel=1e-2)

    def test_single_loss_trade(self, db_session):
        """Test PnL from single loss trade."""
        trade = PaperTrade(
            symbol="NIFTY2631723850PE",
            side="BUY",
            entry_price=287.50,
            stop_loss=275.00,
            target=314.85,
            quantity=65,
            exit_price=275.00,
            exit_time=datetime.utcnow(),
            status="SL_HIT",
        )
        db_session.add(trade)
        db_session.commit()

        pnl = _get_daily_pnl(db_session)
        expected = (275.00 - 287.50) * 65
        assert pnl == pytest.approx(expected, rel=1e-2)

    def test_multiple_trades_combined_pnl(self, db_session):
        """Test combined PnL from multiple trades."""
        now = datetime.utcnow()
        
        # Profitable trade
        profit_trade = PaperTrade(
            symbol="NIFTY_PROFIT",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=110.0,
            exit_time=now,
            status="TARGET_HIT",
        )
        db_session.add(profit_trade)

        # Loss trade
        loss_trade = PaperTrade(
            symbol="NIFTY_LOSS",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=90.0,
            exit_time=now + timedelta(minutes=5),
            status="SL_HIT",
        )
        db_session.add(loss_trade)
        db_session.commit()

        pnl = _get_daily_pnl(db_session)
        expected = (110.0 - 100.0) * 50 + (90.0 - 100.0) * 50
        assert pnl == pytest.approx(expected, rel=1e-2)

    def test_exclude_old_trades_from_pnl(self, db_session):
        """Test that yesterday's trades are not included in PnL."""
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Yesterday's profitable trade
        old_trade = PaperTrade(
            symbol="NIFTY_OLD",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=110.0,
            exit_time=yesterday,
            status="TARGET_HIT",
        )
        db_session.add(old_trade)

        # Today's loss trade
        new_trade = PaperTrade(
            symbol="NIFTY_NEW",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=90.0,
            exit_time=datetime.utcnow(),
            status="SL_HIT",
        )
        db_session.add(new_trade)
        db_session.commit()

        pnl = _get_daily_pnl(db_session)
        expected = (90.0 - 100.0) * 50  # Only today's loss
        assert pnl == pytest.approx(expected, rel=1e-2)

    def test_open_trades_not_included(self, db_session):
        """Test that open trades are not included in PnL."""
        # Open trade (no exit)
        open_trade = PaperTrade(
            symbol="NIFTY2631723850PE",
            side="BUY",
            entry_price=287.50,
            stop_loss=275.00,
            target=314.85,
            quantity=65,
            entry_time=datetime.utcnow(),
            status="OPEN",
        )
        db_session.add(open_trade)

        # Closed profitable trade
        closed_trade = PaperTrade(
            symbol="NIFTY_CLOSED",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=110.0,
            exit_time=datetime.utcnow(),
            status="TARGET_HIT",
        )
        db_session.add(closed_trade)
        db_session.commit()

        pnl = _get_daily_pnl(db_session)
        expected = (110.0 - 100.0) * 50  # Only closed trade
        assert pnl == pytest.approx(expected, rel=1e-2)


class TestShouldAllowNewTrade:
    """Test _should_allow_new_trade helper function."""

    def test_allow_first_trade_of_day(self, db_session):
        """Test allowing first trade of the day."""
        allowed = _should_allow_new_trade(db_session)
        assert allowed is True

    def test_reject_after_20_daily_trades(self, db_session):
        """Test rejecting trade after 20 daily trades."""
        now = datetime.utcnow()
        for i in range(20):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=now - timedelta(minutes=i),
            )
            db_session.add(trade)
        db_session.commit()

        allowed = _should_allow_new_trade(db_session)
        assert allowed is False

    def test_allow_19_trades(self, db_session):
        """Test allowing 19th trade."""
        now = datetime.utcnow()
        for i in range(19):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                entry_time=now - timedelta(minutes=i),
            )
            db_session.add(trade)
        db_session.commit()

        allowed = _should_allow_new_trade(db_session)
        assert allowed is True

    def test_reject_after_3_consecutive_sl_hits(self, db_session):
        """Test rejecting trade after 3 consecutive SL_HIT."""
        now = datetime.utcnow()
        for i in range(3):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                exit_price=90.0,
                exit_time=now - timedelta(minutes=(3 - i)),
                status="SL_HIT",
            )
            db_session.add(trade)
        db_session.commit()

        allowed = _should_allow_new_trade(db_session)
        assert allowed is False

    def test_reject_after_reaching_profit_target(self, db_session):
        """Test rejecting trade after hitting daily profit target."""
        now = datetime.utcnow()
        for i in range(3):
            trade = PaperTrade(
                symbol=f"NIFTY{i}",
                side="BUY",
                entry_price=1000.0,
                stop_loss=990.0,
                target=1100.0,
                quantity=50,
                exit_price=1100.0,
                exit_time=now - timedelta(minutes=(3 - i)),
                status="TARGET_HIT",
            )
            db_session.add(trade)
        db_session.commit()

        # Total PnL: (1100 - 1000) * 50 * 3 = 15000 > 5000 target
        allowed = _should_allow_new_trade(db_session)
        assert allowed is False

    def test_allow_with_moderate_pnl(self, db_session):
        """Test allowing trade when PnL is below profit target."""
        now = datetime.utcnow()
        # One profitable trade: (110 - 100) * 50 = 500 < 5000 target
        trade = PaperTrade(
            symbol="NIFTY",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=110.0,
            exit_time=now,
            status="TARGET_HIT",
        )
        db_session.add(trade)
        db_session.commit()

        allowed = _should_allow_new_trade(db_session)
        assert allowed is True

    def test_allow_with_mixed_win_loss(self, db_session):
        """Test allowing trade with mixed wins and losses below profit target."""
        now = datetime.utcnow()
        
        # Win trade: (110 - 100) * 50 = 500
        win = PaperTrade(
            symbol="NIFTY_WIN",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=110.0,
            exit_time=now,
            status="TARGET_HIT",
        )
        db_session.add(win)

        # Loss trade: (90 - 100) * 50 = -500
        loss = PaperTrade(
            symbol="NIFTY_LOSS",
            side="BUY",
            entry_price=100.0,
            stop_loss=90.0,
            target=110.0,
            quantity=50,
            exit_price=90.0,
            exit_time=now + timedelta(minutes=5),
            status="SL_HIT",
        )
        db_session.add(loss)
        db_session.commit()

        # Total PnL: 500 - 500 = 0 < 5000
        allowed = _should_allow_new_trade(db_session)
        assert allowed is True
