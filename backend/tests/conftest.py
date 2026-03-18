"""Pytest configuration and shared fixtures for all tests."""
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import Base
from app.models.trading import PaperTrade, TradeReport
from app.models.auth import User, BrokerCredential


@pytest.fixture
def test_db_engine():
    """Create isolated in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db_engine):
    """Create a new database session for each test."""
    TestingSessionLocal = sessionmaker(bind=test_db_engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashedpassword123",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_broker_credential(db_session, sample_user):
    """Create sample broker credentials."""
    cred = BrokerCredential(
        user_id=sample_user.id,
        broker_name="zerodha",
        api_key="test_api_key",
        api_secret="test_api_secret",
        access_token="test_token_123",
        refresh_token="test_refresh_123",
        created_at=datetime.utcnow(),
        token_expiry=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add(cred)
    db_session.commit()
    return cred


@pytest.fixture
def sample_paper_trade(db_session):
    """Create a sample paper trade."""
    trade = PaperTrade(
        symbol="NIFTY2631723850PE",
        side="BUY",
        entry_price=287.50,
        stop_loss=275.00,
        target=314.85,
        quantity=65,
        entry_time=datetime.utcnow(),
        status="OPEN",
        signal_data={
            "quality_score": 95.0,
            "confirmation_score": 94.4,
            "ai_edge_score": 25.0,
            "momentum_score": 85.0,
            "breakout_score": 90.0,
            "market_regime": "STRONG_ONE_SIDE",
        },
    )
    db_session.add(trade)
    db_session.commit()
    return trade


@pytest.fixture
def mock_signal():
    """Create a mock trading signal."""
    return {
        "symbol": "NIFTY2631723850PE",
        "action": "BUY",
        "entry_price": 287.50,
        "target": 314.85,
        "stop_loss": 275.00,
        "quantity": 65,
        "confidence": 94.4,
        "quality_score": 95.0,
        "confirmation_score": 94.4,
        "ai_edge_score": 25.0,
        "momentum_score": 85.0,
        "breakout_score": 90.0,
        "breakout_confirmed": True,
        "momentum_confirmed": True,
        "market_regime": "STRONG_ONE_SIDE",
        "signal_type": "index",
        "is_stock": False,
        "rr": 1.25,
        "strategy": "AI_MOMENTUM",
    }


@pytest.fixture
def mock_stock_signal():
    """Create a mock stock trading signal."""
    return {
        "symbol": "SBIN-EQ",
        "action": "BUY",
        "entry_price": 500.00,
        "target": 525.00,
        "stop_loss": 480.00,
        "quantity": 1,
        "confidence": 75.0,
        "quality_score": 70.0,
        "confirmation_score": 72.0,
        "ai_edge_score": 18.0,
        "momentum_score": 75.0,
        "breakout_score": 80.0,
        "breakout_confirmed": True,
        "momentum_confirmed": True,
        "market_regime": "MODERATE_BOTH",
        "signal_type": "stock",
        "is_stock": True,
        "rr": 1.25,
        "strategy": "BREAKOUT",
    }
