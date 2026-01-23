from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.core.database import Base

class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    mobile = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_email_verified = Column(Boolean, default=False)
    is_mobile_verified = Column(Boolean, default=False)
    otp_code = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    last_otp_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BrokerCredential(Base):
    """Store encrypted broker credentials per user"""
    __tablename__ = "broker_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    broker_name = Column(String)  # zerodha, upstox, angel_one, groww
    api_key = Column(String)  # encrypted
    api_secret = Column(String)  # encrypted
    access_token = Column(String, nullable=True)  # For OAuth
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RefreshToken(Base):
    """JWT Refresh tokens"""
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
