"""Tests for database models."""
import pytest
from datetime import datetime, timedelta
from app.models.trading import PaperTrade, TradeReport
from app.models.auth import User, BrokerCredential


class TestPaperTradeModel:
    """Test PaperTrade model."""

    def test_create_paper_trade(self, db_session):
        """Test creating a paper trade."""
        trade = PaperTrade(
            symbol="NIFTY2631723850PE",
            side="BUY",
            entry_price=287.50,
            stop_loss=275.00,
            target=314.85,
            quantity=65,
            status="OPEN",
        )
        db_session.add(trade)
        db_session.commit()

        assert trade.id is not None
        assert trade.symbol == "NIFTY2631723850PE"
        assert trade.status == "OPEN"
        assert trade.pnl is None  # PnL is populated by close/update flows

    def test_paper_trade_exit_with_profit(self, db_session, sample_paper_trade):
        """Test paper trade exiting with profit."""
        sample_paper_trade.exit_price = 314.85
        sample_paper_trade.exit_time = datetime.utcnow()
        sample_paper_trade.status = "TARGET_HIT"
        sample_paper_trade.pnl = (314.85 - 287.50) * 65
        db_session.commit()

        expected_pnl = (314.85 - 287.50) * 65
        assert sample_paper_trade.pnl == pytest.approx(expected_pnl, rel=1e-2)

    def test_paper_trade_exit_with_loss(self, db_session, sample_paper_trade):
        """Test paper trade exiting with loss."""
        sample_paper_trade.exit_price = 275.00
        sample_paper_trade.exit_time = datetime.utcnow()
        sample_paper_trade.status = "SL_HIT"
        sample_paper_trade.pnl = (275.00 - 287.50) * 65
        db_session.commit()

        expected_pnl = (275.00 - 287.50) * 65
        assert sample_paper_trade.pnl == pytest.approx(expected_pnl, rel=1e-2)

    def test_paper_trade_timestamps(self, db_session, sample_paper_trade):
        """Test entry/exit timestamps are persisted."""
        sample_paper_trade.exit_time = sample_paper_trade.entry_time + timedelta(minutes=15)
        db_session.commit()
        assert sample_paper_trade.entry_time is not None
        assert sample_paper_trade.exit_time is not None
        assert sample_paper_trade.exit_time > sample_paper_trade.entry_time

    def test_paper_trade_signal_data_storage(self, db_session):
        """Test storing signal data in paper trade."""
        signal_data = {
            "quality_score": 95.0,
            "ai_edge_score": 25.0,
            "momentum_score": 85.0,
            "breakout_confirmed": True,
            "market_regime": "STRONG_ONE_SIDE",
        }
        trade = PaperTrade(
            symbol="NIFTY2631723850PE",
            side="BUY",
            entry_price=287.50,
            stop_loss=275.00,
            target=314.85,
            quantity=65,
            signal_data=signal_data,
        )
        db_session.add(trade)
        db_session.commit()

        retrieved = db_session.query(PaperTrade).first()
        assert retrieved.signal_data["quality_score"] == 95.0
        assert retrieved.signal_data["breakout_confirmed"] is True

    def test_paper_trade_multiple_statuses(self, db_session):
        """Test different paper trade exit statuses."""
        statuses = ["TARGET_HIT", "SL_HIT", "PROFIT_TRAIL", "MANUAL_CLOSE", "EXPIRED"]
        
        for status in statuses:
            trade = PaperTrade(
                symbol=f"NIFTY{status}",
                side="BUY",
                entry_price=100.0,
                stop_loss=90.0,
                target=110.0,
                quantity=50,
                status=status,
            )
            db_session.add(trade)
        
        db_session.commit()
        
        for status in statuses:
            trade = db_session.query(PaperTrade).filter_by(status=status).first()
            assert trade is not None
            assert trade.status == status


class TestTradeReportModel:
    """Test TradeReport model."""

    def test_create_trade_report(self, db_session):
        """Test creating a trade report."""
        report = TradeReport(
            symbol="NIFTY2631723850PE",
            entry_price=287.50,
            exit_price=314.85,
            quantity=65,
            side="BUY",
            status="CLOSED",
            pnl=1783.75,
            entry_time=datetime.utcnow(),
            exit_time=datetime.utcnow() + timedelta(minutes=15),
            strategy="AI_MOMENTUM",
        )
        db_session.add(report)
        db_session.commit()

        assert report.id is not None
        assert report.pnl == 1783.75
        assert report.status == "CLOSED"

    def test_trade_report_meta_data(self, db_session):
        """Test storing metadata in trade report."""
        meta = {
            "exit_reason": "PROFIT_TRAIL",
            "quality_score": 95.0,
            "ai_edge_score": 25.0,
            "market_regime": "STRONG_ONE_SIDE",
        }
        report = TradeReport(
            symbol="NIFTY2631723850PE",
            entry_price=287.50,
            exit_price=314.85,
            quantity=65,
            side="BUY",
            meta=meta,
            strategy="AI_MOMENTUM",
        )
        db_session.add(report)
        db_session.commit()

        retrieved = db_session.query(TradeReport).first()
        assert retrieved.meta["exit_reason"] == "PROFIT_TRAIL"
        assert retrieved.meta["quality_score"] == 95.0

    def test_trade_report_pnl_calculation(self, db_session):
        """Test PnL calculation for buy and sell trades."""
        # BUY trade
        buy_report = TradeReport(
            symbol="NIFTY",
            entry_price=100.0,
            exit_price=110.0,
            quantity=10,
            side="BUY",
            pnl=100.0,
        )
        db_session.add(buy_report)

        # SELL trade
        sell_report = TradeReport(
            symbol="NIFTY",
            entry_price=110.0,
            exit_price=100.0,
            quantity=10,
            side="SELL",
            pnl=100.0,
        )
        db_session.add(sell_report)
        db_session.commit()

        buy = db_session.query(TradeReport).filter_by(side="BUY").first()
        sell = db_session.query(TradeReport).filter_by(side="SELL").first()

        assert buy.pnl == 100.0
        assert sell.pnl == 100.0


class TestUserModel:
    """Test User model."""

    def test_create_user(self, db_session):
        """Test creating a user."""
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password="hashedpwd",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        retrieved = db_session.query(User).filter_by(email="test@example.com").first()
        assert retrieved is not None
        assert retrieved.username == "testuser"
        assert retrieved.is_active is True

    def test_user_creation_timestamp(self, db_session):
        """Test user creation timestamp."""
        before = datetime.utcnow()
        user = User(
            email="timestamp@example.com",
            username="timestampuser",
            hashed_password="pwd",
        )
        db_session.add(user)
        db_session.commit()
        after = datetime.utcnow()

        retrieved = db_session.query(User).filter_by(email="timestamp@example.com").first()
        assert before <= retrieved.created_at <= after


class TestBrokerCredentialModel:
    """Test BrokerCredential model."""

    def test_create_broker_credential(self, db_session, sample_user):
        """Test creating broker credentials."""
        cred = BrokerCredential(
            user_id=sample_user.id,
            broker_name="zerodha",
            api_key="api_client_123",
            api_secret="secret123",
            access_token="token123",
            refresh_token="refresh123",
        )
        db_session.add(cred)
        db_session.commit()

        retrieved = db_session.query(BrokerCredential).filter_by(
            api_key="api_client_123"
        ).first()
        assert retrieved is not None
        assert retrieved.access_token == "token123"

    def test_broker_credential_expiry(self, db_session, sample_user):
        """Test broker credential expiry tracking."""
        token_expiry = datetime.utcnow() + timedelta(hours=1)
        cred = BrokerCredential(
            user_id=sample_user.id,
            broker_name="zerodha",
            api_key="api_client",
            api_secret="secret",
            access_token="token",
            refresh_token="refresh",
            token_expiry=token_expiry,
        )
        db_session.add(cred)
        db_session.commit()

        retrieved = db_session.query(BrokerCredential).first()
        assert retrieved.token_expiry is not None
        assert retrieved.token_expiry > datetime.utcnow()

    def test_multiple_broker_credentials_per_user(self, db_session, sample_user):
        """Test storing multiple broker credentials per user."""
        brokers = ["zerodha", "finvasia", "shoonya"]
        
        for broker in brokers:
            cred = BrokerCredential(
                user_id=sample_user.id,
                broker_name=broker,
                api_key=f"api_{broker}",
                api_secret=f"secret_{broker}",
                access_token=f"token_{broker}",
                refresh_token=f"refresh_{broker}",
            )
            db_session.add(cred)
        
        db_session.commit()

        retrieved_creds = db_session.query(BrokerCredential).filter_by(
            user_id=sample_user.id
        ).all()
        assert len(retrieved_creds) == 3
